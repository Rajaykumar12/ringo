"""
eval.py — LLM-as-judge scoring for RAG responses.
Scores faithfulness, answer relevance, and context relevance using Groq.
All functions return None on failure — never raise.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor


def _score(prompt: str) -> float | None:
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0,
        )
        text = resp.choices[0].message.content.strip()
        # Only accept values in [0.0, 1.0] — reject "8 out of 10" style outputs
        match = re.search(r'\b(1(?:\.0+)?|0(?:\.\d+)?)\b', text)
        if match:
            return float(match.group())
    except Exception as e:
        print(f"Eval scoring failed: {e}")
    return None


def evaluate_rag(query: str, context: str, answer: str) -> dict:
    """Score a RAG response on three dimensions. Returns floats 0–1 or None on failure."""
    ctx = context[:3000]
    ans = answer[:1000]

    prompts = {
        "faithfulness": (
            f"Given this context:\n{ctx}\n\nAnd this answer:\n{ans}\n\n"
            "Score 0.0 to 1.0: how much does the answer rely only on the context "
            "(1.0 = entirely grounded in context, 0.0 = ignores context or hallucinates).\n"
            "Respond with only a number between 0.0 and 1.0."
        ),
        "answer_relevance": (
            f"Question: {query}\nAnswer: {ans}\n\n"
            "Score 0.0 to 1.0: how well does the answer address the question.\n"
            "Respond with only a number between 0.0 and 1.0."
        ),
        "context_relevance": (
            f"Question: {query}\nContext:\n{ctx}\n\n"
            "Score 0.0 to 1.0: how relevant is this context to answering the question.\n"
            "Respond with only a number between 0.0 and 1.0."
        ),
    }

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {key: executor.submit(_score, prompt) for key, prompt in prompts.items()}
        return {key: f.result() for key, f in futures.items()}
