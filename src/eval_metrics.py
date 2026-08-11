"""
Phase 11 — Evaluation metrics.

Kept separate from the retrieval/generation calls (evaluate_retrieval.py,
evaluate_generation.py) so the scoring logic itself can be tested with
synthetic, controlled inputs — no real DB, embeddings, or LLM needed to
verify recall@k and MRR are computed correctly.
"""

from dataclasses import dataclass


@dataclass
class EvalQuestion:
    question: str
    expected_drug: str
    # A result "matches" if its section_title contains ANY of these
    # keywords (case-insensitive). Keyword-based rather than exact
    # title match, since real FDA labels phrase the same kind of
    # section differently across drugs (e.g. "Directions" vs.
    # "2.2 Recommended Dosage for...") — matching on keywords like
    # "dosage"/"direction" catches the right section regardless of
    # the exact wording a given label uses.
    expected_section_keywords: list[str]


def result_matches(result, expected_drug: str, expected_section_keywords: list[str]) -> bool:
    """Does this single search result count as the "correct" answer?"""
    if expected_drug.lower() not in result.drug_name.lower():
        return False
    section_lower = result.section_title.lower()
    return any(kw.lower() in section_lower for kw in expected_section_keywords)


def find_rank(results: list, expected_drug: str, expected_section_keywords: list[str]) -> int | None:
    """
    1-indexed rank of the first matching result, or None if no result
    in the list matches.
    """
    for i, r in enumerate(results, 1):
        if result_matches(r, expected_drug, expected_section_keywords):
            return i
    return None


def hit_at_k(rank: int | None, k: int) -> bool:
    """Did a matching result appear within the top k?"""
    return rank is not None and rank <= k


def compute_question_metrics(results: list, eval_q: EvalQuestion, k_values: list[int] = [1, 3, 5]) -> dict:
    rank = find_rank(results, eval_q.expected_drug, eval_q.expected_section_keywords)
    return {
        "question": eval_q.question,
        "rank": rank,
        "reciprocal_rank": (1.0 / rank) if rank else 0.0,
        **{f"hit@{k}": hit_at_k(rank, k) for k in k_values},
    }


def aggregate_metrics(per_question_results: list[dict], k_values: list[int] = [1, 3, 5]) -> dict:
    """
    Combines per-question results into overall recall@k (fraction of
    questions with a hit within top k) and MRR (mean reciprocal rank
    — rewards ranking the right answer higher, not just "somewhere in
    top k").
    """
    n = len(per_question_results)
    if n == 0:
        return {}

    aggregate = {"num_questions": n}
    for k in k_values:
        hits = sum(1 for r in per_question_results if r[f"hit@{k}"])
        aggregate[f"recall@{k}"] = hits / n

    aggregate["mrr"] = sum(r["reciprocal_rank"] for r in per_question_results) / n
    return aggregate
