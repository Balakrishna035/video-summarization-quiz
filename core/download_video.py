import os
import subprocess
import logging

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = "uploads"
COOKIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

def download_video(url: str, job_id: str) -> str:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    output_path = os.path.join(UPLOAD_FOLDER, f"raw_{job_id}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--cookies", COOKIES_PATH,
        "--extractor-args", "youtube:player_client=web",  # ← supports cookies + audio
        "-f", "bestaudio/best",                          # ← fallback if bestaudio fails
        "-o", output_path,
        "--no-playlist",
        "--no-check-certificates",
        url,
    ]

    logger.info("Downloading video: %s", url)
    result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed:\n{result.stderr.decode(errors='replace')}")

    for fname in os.listdir(UPLOAD_FOLDER):
        if fname.startswith(f"raw_{job_id}"):
            full_path = os.path.join(UPLOAD_FOLDER, fname)
            logger.info("Downloaded to: %s", full_path)
            return full_path

    raise FileNotFoundError(f"yt-dlp finished but no output file found for job {job_id}")