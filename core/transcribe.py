import os
import time
import subprocess
import logging
from groq import Groq, InternalServerError, RateLimitError, APIStatusError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _compress_audio(input_path: str, output_path: str) -> None:
    """Compress to 16kHz mono MP3 for maximum compatibility."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vn", "-ar", "16000", "-ac", "1", 
        "-c:a", "libmp3lame", "-b:a", "32k",
        output_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr.decode()}")

def speech_to_text(
    media_file_path: str,
    language_code: str = "te",  # Defaulting to Telugu (ISO 639-1)
    max_retries: int = 3,
    transcript_log: str = "transcript.txt",
) -> dict:
    
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    optimized_path = media_file_path + "_processed.mp3"
    client = Groq(api_key=api_key, max_retries=0)

    try:
        _compress_audio(media_file_path, optimized_path)
        
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info("Transcribing Telugu (attempt %d)...", attempt)
                with open(optimized_path, "rb") as audio_file:
                    # Using json format for stability
                    response = client.audio.transcriptions.create(
                        file=audio_file,
                        model="whisper-large-v3-turbo",
                        language=language_code,
                        response_format="json" 
                    )
                break 
            except InternalServerError as exc:
                if attempt == max_retries: raise
                time.sleep(2 ** attempt) # Exponential backoff

        full_text = response.text if hasattr(response, 'text') else str(response)
        
        with open(transcript_log, "w", encoding="utf-8") as f:
            f.write(full_text)

        return {"full_text": full_text, "word_count": len(full_text.split())}

    finally:
        if os.path.exists(optimized_path):
            os.remove(optimized_path)