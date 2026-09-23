import os
import json
import time
import uuid
import logging
import traceback
import sqlite3
from flask import (
    Flask, g, jsonify, render_template, request,
    redirect, url_for, flash, session
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_dance.contrib.google import make_google_blueprint, google

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from core.download_video import download_video
from core.transcribe import speech_to_text
from core.summarize import generate_summary_and_insights
from core.mcq_generator import generate_mcq_quiz
from core.cut_audio import clear_runtime_buffers

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Secret key must be set via environment variable — no hardcoded fallback
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is not set.")

app.config.update(
    UPLOAD_FOLDER="uploads",
    DB_PATH="history.db",
    MAX_QUESTIONS=20,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ── Google OAuth ──────────────────────────────────────────────────────────────
# Credentials must be set via environment variables — no hardcoded fallback
_gcid     = os.environ.get("GOOGLE_CLIENT_ID")
_gcsecret = os.environ.get("GOOGLE_CLIENT_SECRET")

if not _gcid or not _gcsecret:
    logger.warning(
        "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set — "
        "Google login button will be disabled."
    )

google_bp = make_google_blueprint(
    client_id=_gcid,
    client_secret=_gcsecret,
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
    redirect_url="/google/callback",
)
app.register_blueprint(google_bp, url_prefix="/login")

LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
    "kn": "Kannada",
}

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name          TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id          INTEGER PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                title       TEXT NOT NULL,
                summary     TEXT,
                key_points  TEXT,
                transcript  TEXT,
                quiz        TEXT,
                metadata    TEXT,
                favorite    INTEGER NOT NULL DEFAULT 0,
                created_at  INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        db.commit()

init_db()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("register.html")
        try:
            get_db().execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, generate_password_hash(password)),
            )
            get_db().commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_db().execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"]    = user["id"]
            session["user_email"] = user["email"]
            session["user_name"]  = user["name"] or ""
            session.modified = True

            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)

        flash("Invalid email or password.", "error")

    return render_template("login.html", google_configured=bool(_gcid and _gcsecret))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    flash("Password recovery feature coming soon!", "info")
    return redirect(url_for("login"))


@app.route("/auth/google")
def google_login():
    if not _gcid or not _gcsecret:
        return redirect(url_for("login"))
    if not google.authorized:
        return redirect(url_for("google.login"))
    return redirect(url_for("google_auth_callback"))


@app.route("/google/callback")
def google_auth_callback():
    if not google.authorized:
        flash("Google login failed. Please try again.", "error")
        return redirect(url_for("login"))

    try:
        resp = google.get("/oauth2/v2/userinfo")
        if not resp.ok:
            flash("Could not fetch your Google account info.", "error")
            return redirect(url_for("login"))

        info  = resp.json()
        email = info.get("email", "").strip().lower()
        name  = info.get("name", "") or email

        if not email:
            flash("Google did not provide an email address.", "error")
            return redirect(url_for("login"))

        db   = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user:
            db.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                (email, generate_password_hash(os.urandom(32).hex()), name),
            )
            db.commit()
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        session.clear()
        session["user_id"]    = user["id"]
        session["user_email"] = email
        session["user_name"]  = name
        session.modified = True

        logger.info("Google login success: %s", email)
        return redirect(url_for("index"))

    except Exception:
        logger.error("Google login error:\n%s", traceback.format_exc())
        flash("Something went wrong with Google login.", "error")
        return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template(
        "index.html",
        languages=LANGUAGES,
        user_email=session.get("user_email", ""),
        user_name=session.get("user_name", ""),
        google_configured=bool(_gcid and _gcsecret),
    )


@app.route("/api/analyze", methods=["POST"])
@login_required
def execute_video_analysis_pipeline():
    video_file      = request.files.get("video")
    video_url       = request.form.get("url", "").strip()
    language_code   = request.form.get("lang", "en")
    media_path      = None

    if language_code not in LANGUAGES:
        language_code = "en"

    try:
        target_questions = min(
            int(request.form.get("questions", 5)),
            app.config["MAX_QUESTIONS"],
        )
    except (ValueError, TypeError):
        target_questions = 5

    if not (video_file and video_file.filename) and not video_url:
        return jsonify({"success": False, "error": "No video source provided."}), 400

    job_id = str(uuid.uuid4().int)[:12]

    try:
        if video_file and video_file.filename:
            filename   = secure_filename(video_file.filename)
            media_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            video_file.save(media_path)
        else:
            media_path = download_video(video_url, job_id)

        transcript_data = speech_to_text(media_path, language_code)
        full_text       = transcript_data.get("full_text", "")

        summary = generate_summary_and_insights(
            full_text, LANGUAGES[language_code], video_url
        )
        quiz = generate_mcq_quiz(
            full_text, LANGUAGES[language_code], target_questions
        )

        if not quiz:
            raise RuntimeError("Quiz generation returned no questions.")

        node = {
            "id":         int(job_id),
            "user_id":    session["user_id"],
            "title":      summary.get("title", "Analysis"),
            "summary":    summary.get("summary_text", ""),
            "key_points": json.dumps(summary.get("key_insights", [])),
            "transcript": transcript_data.get("formatted_transcript", full_text),
            "quiz":       json.dumps(quiz),
            "metadata":   json.dumps({"lang": LANGUAGES[language_code]}),
            "created_at": int(time.time()),
        }

        get_db().execute(
            """INSERT INTO history
               (id, user_id, title, summary, key_points, transcript, quiz, metadata, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                node["id"], node["user_id"], node["title"], node["summary"],
                node["key_points"], node["transcript"], node["quiz"],
                node["metadata"], node["created_at"],
            ),
        )
        get_db().commit()
        return jsonify({"success": True, "data": node})

    except Exception as exc:
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(exc)}), 500

    finally:
        if media_path and os.path.exists(media_path):
            clear_runtime_buffers(media_path)


@app.route("/api/history", methods=["GET"])
@login_required
def get_history():
    rows = get_db().execute(
        """SELECT id, title
           FROM history
           WHERE user_id = ?
           GROUP BY title
           ORDER BY MAX(created_at) DESC
           LIMIT 5""",
        (session["user_id"],),
    ).fetchall()
    return jsonify({
        "success": True,
        "history": [{"id": r["id"], "title": r["title"]} for r in rows],
    })


@app.route("/api/history/<int:session_id>", methods=["GET"])
@login_required
def get_session(session_id):
    row = get_db().execute(
        "SELECT * FROM history WHERE id = ? AND user_id = ?",
        (session_id, session["user_id"]),
    ).fetchone()

    if not row:
        return jsonify({"success": False, "error": "Session not found."}), 404

    return jsonify({"success": True, "data": dict(row)})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
