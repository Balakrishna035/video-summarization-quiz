import os
import json
import logging
from groq import Groq, APIStatusError, RateLimitError

logger = logging.getLogger(__name__)

MODEL = "llama-3.3-70b-versatile"
MAX_INPUT_CHARS = 4000

# Updated prompt: "options" is now an array to match frontend needs
SYSTEM_PROMPT = """\
You are an expert multilingual quiz generator.
Generate {num_questions} multiple-choice questions from the transcript below.
Every word must be in {target_language}.

RULES:
- Each question must have exactly 4 options.
- Only one option is correct.
- Respond ONLY with a valid JSON array.
- No markdown, no code fences.

Format:
[
  {{
    "question": "The question text here",
    "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
    "answer": "A",
    "explanation": "Brief explanation"
  }}
]
"""

def generate_mcq_quiz(
    text_corpus: str,
    target_language: str,
    num_questions: int = 5,
) -> list:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    client = Groq(api_key=api_key)
    prompt = SYSTEM_PROMPT.format(
        num_questions=num_questions,
        target_language=target_language,
    )

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Transcript:\n{text_corpus[:MAX_INPUT_CHARS]}"},
            ],
        )
    except (RateLimitError, APIStatusError) as exc:
        logger.error(f"Groq API error: {exc}")
        return []

    raw = completion.choices[0].message.content.strip()
    
    # Clean up potential markdown artifacts
    if "```" in raw:
        raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        questions = json.loads(raw)
        if not isinstance(questions, list):
            raise ValueError("Output is not a JSON list")
        return questions
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse MCQ JSON: %s\nRaw output:\n%s", exc, raw)
        return []