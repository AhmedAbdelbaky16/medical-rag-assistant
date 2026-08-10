"""
Phase 7 — Generation.

Takes retrieved chunks (from Phase 6's hybrid_search) and turns them
into an actual answer, grounded in that context, with citations back
to specific sources — instead of just handing the person a list of
raw chunks to read themselves.

Two model calls happen per question:
  1. Generation — answer the question using only the provided context,
     citing which source(s) support each part of the answer.
  2. Faithfulness check — a second pass asking "is this answer
     actually supported by the context?" This catches hallucination
     before the person ever sees it. Originally planned to use a
     smaller/faster model for this second call, but testing showed
     that model wasn't reliable enough at the judgment task itself
     (see FAITHFULNESS_MODEL below) — so it uses the same capable
     model as generation.
"""

import json
import logging

import requests

from config import OLLAMA_BASE_URL, GENERATION_MODEL
from retrieval import SearchResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Approximate context budget, in words. This is a rough proxy for
# tokens (not an exact count from qwen's own tokenizer) — good enough
# to avoid building an absurdly long prompt, without adding the
# complexity of loading yet another model-specific tokenizer just for
# budgeting. A production system would measure this exactly.
MAX_CONTEXT_WORDS = 1500

# NOTE: originally used a small/fast model (qwen2:0.5b) here to save
# time, on the assumption that judging support is simpler than
# generating an answer. Real testing disproved that: the 0.5b model
# misread its own source text ("4 to 6 hours" became a garbled "two-
# fourths hours" in its explanation) and incorrectly flagged a
# genuinely correct, well-cited answer as unsupported. Faithfulness
# checking is its own reasoning task, not a rubber stamp — an
# underpowered model can fail it even when the actual answer is fine.
# Using the same capable model as generation instead, accepting the
# extra latency for a verdict that's actually trustworthy.
FAITHFULNESS_MODEL = GENERATION_MODEL


def build_context(results: list[SearchResult]) -> tuple[str, list[SearchResult]]:
    """
    Format retrieved chunks into a numbered source list for the
    prompt, dropping the lowest-ranked (highest-distance) results if
    the total would exceed MAX_CONTEXT_WORDS.

    Returns (formatted_context, results_actually_included) — the
    second value lets the caller know which sources actually made it
    in, since some may get dropped for budget reasons.
    """
    included: list[SearchResult] = []
    total_words = 0

    for r in results:  # results are already ordered by relevance (closest first)
        chunk_words = len(r.chunk_text.split())
        if total_words + chunk_words > MAX_CONTEXT_WORDS and included:
            break
        included.append(r)
        total_words += chunk_words

    lines = []
    for i, r in enumerate(included, 1):
        lines.append(f"[Source {i}: {r.drug_name} — {r.section_title}]")
        lines.append(r.chunk_text)
        lines.append("")

    return "\n".join(lines), included


SYSTEM_PROMPT = """You are a medical information assistant. Answer the user's \
question using ONLY the information in the provided sources below. \
Do not use any outside knowledge.

Rules:
- If the sources don't contain enough information to answer, say so \
clearly in your answer — do not guess or use outside knowledge.
- Every claim in your answer must be traceable to a specific source.
- Respond with ONLY a JSON object in this exact shape, no other text:
{"answer": "your answer here", "cited_sources": [1, 2], "sufficient_context": true}

- "cited_sources" is a list of the Source numbers your answer actually draws from.
- "sufficient_context" is false if the sources don't adequately answer the question.
"""


def build_user_prompt(question: str, context: str) -> str:
    return f"Sources:\n{context}\nQuestion: {question}"


def call_ollama(model: str, system_prompt: str, user_prompt: str) -> str:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def parse_generation_response(raw_content: str) -> dict:
    """
    Parse the model's JSON response defensively — models occasionally
    produce malformed JSON, extra text, or miss a field even when
    format="json" is requested. Falls back to a clearly-flagged error
    result rather than crashing, since this is a place where real
    models genuinely do misbehave sometimes.
    """
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError:
        log.warning(f"Model returned invalid JSON: {raw_content[:200]}")
        return {
            "answer": "The model returned an invalid response. Please try again.",
            "cited_sources": [],
            "sufficient_context": False,
            "parse_error": True,
        }

    return {
        "answer": data.get("answer", ""),
        "cited_sources": data.get("cited_sources", []),
        "sufficient_context": data.get("sufficient_context", None),
        "parse_error": False,
    }


def generate_answer(question: str, results: list[SearchResult]) -> dict:
    context, included_results = build_context(results)

    if not included_results:
        return {
            "answer": "No relevant information was found for this question.",
            "cited_sources": [],
            "sufficient_context": False,
            "parse_error": False,
            "sources": [],
        }

    user_prompt = build_user_prompt(question, context)
    raw_response = call_ollama(GENERATION_MODEL, SYSTEM_PROMPT, user_prompt)
    parsed = parse_generation_response(raw_response)
    parsed["sources"] = included_results
    return parsed


FAITHFULNESS_SYSTEM_PROMPT = """You are checking whether an answer is fully \
supported by the given sources. Respond with ONLY a JSON object:
{"supported": true, "explanation": "brief reason"}

"supported" is false if the answer contains any claim not backed by the sources."""


def check_faithfulness(answer: str, context: str) -> dict:
    """
    Second model call: does this answer actually say only what the
    sources support? Uses FAITHFULNESS_MODEL (currently the same
    capable model as generation — see the comment above for why the
    smaller model wasn't reliable enough for this).
    """
    user_prompt = f"Sources:\n{context}\nAnswer to check: {answer}"

    try:
        raw_response = call_ollama(FAITHFULNESS_MODEL, FAITHFULNESS_SYSTEM_PROMPT, user_prompt)
        log.info(f"Raw faithfulness response: {raw_response!r}")
        data = json.loads(raw_response)
        return {
            "supported": data.get("supported", None),
            "explanation": data.get("explanation", ""),
        }
    except (requests.RequestException, json.JSONDecodeError) as e:
        log.warning(f"Faithfulness check failed: {e}")
        return {"supported": None, "explanation": "Faithfulness check unavailable."}
