import json
import os
import sqlite3
import time
import logging
import traceback

from flask import Flask, g, jsonify, render_template, request
from werkzeug.utils import secure_filename

from core.download_video  import download_video
from core.transcribe      import speech_to_text
from core.summarize       import generate_summary_and_insights
from core.mcq_generator   import generate_mcq_quiz
from core.cut_audio       import clear_runtime_buffers

# ── App setup ─────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["DB_PATH"]       = "history.db"
app.config["MAX_QUESTIONS"] = 20   # guard against absurd frontend values

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

LANGUAGES = {
    "en": "English", "hi": "Hindi",  "te": "Telugu",
    "ta": "Tamil",   "kn": "Kannada","ml": "Malayalam",
    "es": "Spanish", "fr": "French", "de": "German",
    "ja": "Japanese","ar": "Arabic",
}

# ── Database ──────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    """Return a per-request DB connection (stored on Flask's g object)."""
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
        get_db().execute("""
            CREATE TABLE IF NOT EXISTS history (
                id          INTEGER PRIMARY KEY,
                title       TEXT    NOT NULL,
                summary     TEXT,
                key_points  TEXT,       -- JSON array
                transcript  TEXT,
                quiz        TEXT,       -- JSON array
                metadata    TEXT,       -- JSON object
                favorite    INTEGER NOT NULL DEFAULT 0,
                created_at  INTEGER NOT NULL
            )
        """)
        get_db().commit()

init_db()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_history_node(job_id: str, summary: dict, transcript_data: dict,
                         quiz: list, lang_name: str) -> dict:
    return {
        "id":         int(job_id),
        "title":      summary.get("title", "Analysis"),
        "summary":    summary.get("summary_text", ""),
        "key_points": summary.get("key_insights", []),
        "transcript": transcript_data.get("formatted_transcript",
                                          transcript_data.get("full_text", "")),
        "quiz":       quiz,
        "favorite":   False,
        "metadata": {
            "category":   "Analysis",
            "language":   lang_name,
            "word_count": transcript_data.get("word_count", 0),
            "duration":   transcript_data.get("duration", ""),
        },
    }

def _insert_history(node: dict):
    get_db().execute(
        """INSERT INTO history
           (id, title, summary, key_points, transcript, quiz, metadata, favorite, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        (
            node["id"], node["title"], node["summary"],
            json.dumps(node["key_points"]),
            node["transcript"],
            json.dumps(node["quiz"]),
            json.dumps(node["metadata"]),
            int(time.time()),
        ),
    )
    get_db().commit()

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", languages=LANGUAGES)


@app.route("/api/analyze", methods=["POST"])
def execute_video_analysis_pipeline():
    video_file      = request.files.get("video")
    video_url       = request.form.get("url", "").strip()
    language_code   = request.form.get("lang", "en")
    target_questions = min(
        int(request.form.get("questions", 5)),
        app.config["MAX_QUESTIONS"],
    )

    if language_code not in LANGUAGES:
        return jsonify({"success": False, "error": f"Unsupported language: {language_code}"}), 400

    job_id     = str(int(time.time()))
    media_path = None

    try:
        # ── Acquire media ─────────────────────────────────────────────────────
        if video_file and video_file.filename:
            filename   = secure_filename(video_file.filename)
            media_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            video_file.save(media_path)
        elif video_url:
            media_path = download_video(video_url, job_id)
        else:
            return jsonify({"success": False, "error": "No video file or URL provided."}), 400

        # ── Pipeline ──────────────────────────────────────────────────────────
        lang_name       = LANGUAGES[language_code]
        transcript_data = speech_to_text(media_path, language_code)
        full_text       = transcript_data.get("full_text", "")

        summary = generate_summary_and_insights(full_text, lang_name, video_url)
        quiz    = generate_mcq_quiz(full_text, lang_name, target_questions)

        # ── Persist & respond ─────────────────────────────────────────────────
        node = _build_history_node(job_id, summary, transcript_data, quiz, lang_name)
        _insert_history(node)

        return jsonify({"success": True, "data": node})

    except ValueError as exc:
        # config / input errors (missing API key, bad language, etc.)
        logger.warning("Bad request: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 400

    except Exception as exc:
        logger.error("Pipeline failure:\n%s", traceback.format_exc())
        return jsonify({"success": False, "error": str(exc)}), 500

    finally:
        if media_path and os.path.exists(media_path):
            clear_runtime_buffers(media_path)


@app.route("/api/history", methods=["GET"])
def get_history():
    rows = get_db().execute(
        "SELECT id, title, favorite FROM history ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    return jsonify({
        "success": True,
        "history": [{"id": r["id"], "title": r["title"], "favorite": bool(r["favorite"])}
                    for r in rows],
    })


@app.route("/api/history/<int:entry_id>", methods=["GET"])
def get_history_entry(entry_id: int):
    row = get_db().execute(
        "SELECT * FROM history WHERE id = ?", (entry_id,)
    ).fetchone()

    if not row:
        return jsonify({"success": False, "error": "Entry not found"}), 404

    return jsonify({
        "success": True,
        "data": {
            "id":         row["id"],
            "title":      row["title"],
            "summary":    row["summary"],
            "key_points": json.loads(row["key_points"] or "[]"),
            "transcript": row["transcript"],
            "quiz":       json.loads(row["quiz"]       or "[]"),
            "favorite":   bool(row["favorite"]),
            "metadata":   json.loads(row["metadata"]   or "{}"),
        },
    })


@app.route("/api/history/<int:entry_id>/favorite", methods=["POST"])
def toggle_favorite(entry_id: int):
    row = get_db().execute(
        "SELECT favorite FROM history WHERE id = ?", (entry_id,)
    ).fetchone()

    if not row:
        return jsonify({"success": False, "error": "Entry not found"}), 404

    new_val = 0 if row["favorite"] else 1
    get_db().execute(
        "UPDATE history SET favorite = ? WHERE id = ?", (new_val, entry_id)
    )
    get_db().commit()
    return jsonify({"success": True, "favorite": bool(new_val)})


@app.route("/api/history/<int:entry_id>", methods=["DELETE"])
def delete_history_entry(entry_id: int):
    result = get_db().execute(
        "DELETE FROM history WHERE id = ?", (entry_id,)
    )
    get_db().commit()

    if result.rowcount == 0:
        return jsonify({"success": False, "error": "Entry not found"}), 404
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(debug=True)