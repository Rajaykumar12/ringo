"""
vision.py — Multimodal (image + text) chat via a Groq vision-capable model.
Kept separate from rag.py/vectorstore.py since the RAG chain and its prompt
templates are plain-text only; image queries bypass document retrieval and
talk to the vision model directly.
"""
import base64
import logging
import os
import re

from groq import Groq

logger = logging.getLogger("ringo.vision")

# qwen/qwen3.6-27b (and other reasoning models) emit a <think>...</think>
# block ahead of the actual answer — strip it so raw chain-of-thought never
# reaches the user.
_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

VISION_MODEL = os.environ.get("VISION_MODEL", "qwen/qwen3.6-27b")
MAX_IMAGE_SIZE_MB = int(os.environ.get("MAX_IMAGE_SIZE_MB", 8))

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client


def describe_image(image_bytes: bytes, mime_type: str, question: str) -> str:
    """Send an image + accompanying question to the vision model, return the answer text."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    prompt = question.strip() or "Describe this image in detail."

    try:
        completion = _get_client().chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        content = completion.choices[0].message.content
        return _THINK_TAG_RE.sub("", content).strip()
    except Exception as e:
        logger.error("Vision model error: %s", e)
        return "Sorry, I couldn't process that image."
