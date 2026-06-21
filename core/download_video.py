import os
import subprocess
import logging

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = "uploads"
COOKIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

def download_video(url: str, job_id: str):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Template path for yt-dlp
    output_path = os.path.join(UPLOAD_FOLDER, f"raw_{job_id}.%(ext)s")

    # Using -x for --extract-audio and --audio-format inside the command
    # Removed --no-check-certificates (it's rarely needed and insecure)
    cmd = [
        "yt-dlp",
        "--cookies", COOKIES_PATH,
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
        # Use subprocess.run with check=True to handle errors automatically
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Look for the generated file
        for file in os.listdir(UPLOAD_FOLDER):
            if file.startswith(f"raw_{job_id}") and file.endswith(".mp3"):
                return os.path.join(UPLOAD_FOLDER, file)
                
    except subprocess.CalledProcessError as e:
        logger.error("yt-dlp failed: %s", e.stderr)
        raise RuntimeError(f"Download failed: {e.stderr}")

    raise FileNotFoundError("Downloaded file not found.")