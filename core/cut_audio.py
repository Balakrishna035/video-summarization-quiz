import os
import logging

logger = logging.getLogger(__name__)


def clear_runtime_buffers(media_path: str) -> None:
    """Delete a temp media file after the pipeline finishes."""
    try:
        if media_path and os.path.exists(media_path):
            os.remove(media_path)
            logger.info("[HYGIENE] Deleted temp file: %s", media_path)
    except OSError as exc:
        logger.warning("Could not delete temp file %s: %s", media_path, exc)