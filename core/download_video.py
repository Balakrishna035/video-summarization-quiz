import os
import subprocess
import logging

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = "uploads"


def download_video(url: str, job_id: str) -> str:
    """
    Download audio from a YouTube URL using yt-dlp.
    Returns the path to the downloaded .webm / .mp4 file.
    """
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    output_path = os.path.join(UPLOAD_FOLDER, f"raw_{job_id}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--cookies", "cookies.txt",
        "-f", "bestaudio",
        "-o", output_path,
        "--no-playlist",
        url,
    ]

    logger.info("Downloading video: %s", url)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed:\n{result.stderr.decode(errors='replace')}"
        )

    # Find the file yt-dlp actually wrote (extension varies)
    for fname in os.listdir(UPLOAD_FOLDER):
        if fname.startswith(f"raw_{job_id}"):
            full_path = os.path.join(UPLOAD_FOLDER, fname)
            logger.info("Downloaded to: %s", full_path)
            return full_path

    raise FileNotFoundError(f"yt-dlp finished but no output file found for job {job_id}")