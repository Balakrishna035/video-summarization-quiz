import os
import subprocess
import logging

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = "uploads"

# On Render, Secret Files are mounted at /etc/secrets/<filename>.
# Fall back to a local core/cookies.txt for local development.
_default_local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
COOKIES_PATH = os.environ.get(
    "COOKIES_PATH",
    "/etc/secrets/cookies.txt" if os.path.exists("/etc/secrets/cookies.txt") else _default_local_path
)

def download_video(url: str, job_id: str):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    output_path = os.path.join(UPLOAD_FOLDER, f"raw_{job_id}.%(ext)s")

    cmd = ["yt-dlp"]

    if os.path.exists(COOKIES_PATH):
        cmd += ["--cookies", COOKIES_PATH]
        logger.info("Using cookies file: %s", COOKIES_PATH)
    else:
        logger.warning("No cookies file found at %s — proceeding without cookies", COOKIES_PATH)

    cmd += [
        "-f", "bestaudio/best",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "-o", output_path,
        url,
    ]

    logger.info("Running: %s", " ".join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for file in os.listdir(UPLOAD_FOLDER):
            if file.startswith(f"raw_{job_id}") and file.endswith(".mp3"):
                return os.path.join(UPLOAD_FOLDER, file)
    except subprocess.CalledProcessError as e:
        logger.error("yt-dlp failed: %s", e.stderr)
        raise RuntimeError(f"Download failed: {e.stderr}")

    raise FileNotFoundError("Downloaded file not found.")
