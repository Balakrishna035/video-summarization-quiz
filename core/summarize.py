import os
import logging

from groq import Groq, APIStatusError, RateLimitError

logger = logging.getLogger(__name__)

MODEL           = "llama-3.3-70b-versatile"
MAX_INPUT_CHARS = 4000
SUMMARY_LOG     = "summary.txt"

SYSTEM_PROMPT = """\
You are an expert multilingual study-note generator.

The transcript below was auto-detected by Whisper and may be in any language.
Convert it into concise, high-value study notes written ENTIRELY in {target_language}.
Every single word — title, summary, and all insights — must be in {target_language}.

RULES:
- Write directly about the topic. No introductory sentences.
- Never mention the video, instructor, transcript, tutorial, or speaker.
- Write as professional revision notes focused on concepts, tools, and workflows.
- Generate a short specific title (3-8 words).

Respond EXACTLY in this format — no markdown, no extra lines:
TITLE: <title in {target_language}>
SUMMARY_TEXT: <study notes in {target_language}>
INSIGHT_1: <key concept in {target_language}>
INSIGHT_2: <key concept in {target_language}>
INSIGHT_3: <key concept in {target_language}>\
"""


def _parse_response(raw: str) -> dict:
    result = {"title": "", "summary_text": "", "key_insights": []}
    for line in raw.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not value:
            continue
        if key == "TITLE":
            result["title"] = value
        elif key == "SUMMARY_TEXT":
            result["summary_text"] = value
        elif key.startswith("INSIGHT_"):
            result["key_insights"].append(value)
    return result


def _apply_fallbacks(parsed: dict, text_corpus: str) -> dict:
    if not parsed["title"]:
        parsed["title"] = "Analysis Result"
    if not parsed["summary_text"]:
        parsed["summary_text"] = text_corpus[:500].strip()
    if not parsed["key_insights"]:
        parsed["key_insights"] = ["Key concept extracted from content."]
    return parsed


def generate_summary_and_insights(
    text_corpus: str,
    target_language: str,
    video_reference: str = "",
    summary_log: str = SUMMARY_LOG,
) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    client = Groq(api_key=api_key)
    prompt = SYSTEM_PROMPT.format(target_language=target_language)

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user",   "content": f"Transcript:\n{text_corpus[:MAX_INPUT_CHARS]}"},
            ],
        )
    except RateLimitError:
        raise
    except APIStatusError as exc:
        raise RuntimeError(f"Groq API error {exc.status_code}: {exc.message}") from exc

    raw = completion.choices[0].message.content.strip()
    logger.debug("Raw summary output:\n%s", raw)

    try:
        with open(summary_log, "w", encoding="utf-8") as f:
            f.write(raw)
    except OSError as exc:
        logger.warning("Could not write summary log: %s", exc)

    parsed = _parse_response(raw)
    return _apply_fallbacks(parsed, text_corpus)