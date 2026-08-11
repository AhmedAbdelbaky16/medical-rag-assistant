"""
Phase 11 — Run the eval set through the full generation pipeline
(retrieval + LLM answer + faithfulness check) and report the
faithfulness pass rate.

    python evaluate_generation.py

Much slower than evaluate_retrieval.py — every question makes two
Ollama calls (generation + faithfulness check) on a 7B model. Runs the
full eval set by default; pass a number to test on a subset first,
e.g. `python evaluate_generation.py 5`.
"""

import json
import sys
import logging

from fastembed import TextEmbedding
import pg8000

from config import DB_CONFIG, EMBEDDING_MODEL_NAME, PROJECT_ROOT
from embed_and_load import vector_to_pg_literal
from retrieval import hybrid_search
from generate import generate_answer, check_faithfulness, build_context
from eval_set import EVAL_QUESTIONS

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

TOP_K = 5
RESULTS_PATH = PROJECT_ROOT / "eval_results_generation.json"


def get_connection():
    return pg8000.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def run_evaluation(limit: int | None = None):
    questions = EVAL_QUESTIONS[:limit] if limit else EVAL_QUESTIONS

    print(f"Loading {EMBEDDING_MODEL_NAME}...")
    model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)

    conn = get_connection()
    per_question_results = []

    try:
        for i, eval_q in enumerate(questions, 1):
            print(f"\n[{i}/{len(questions)}] {eval_q.question}")

            query_vector = list(model.embed([eval_q.question]))[0]
            query_literal = vector_to_pg_literal(query_vector)
            results = hybrid_search(conn, query_literal, eval_q.question, TOP_K)

            if not results:
                per_question_results.append({
                    "question": eval_q.question, "answer": None,
                    "sufficient_context": False, "faithfulness_supported": None,
                    "parse_error": False, "no_results": True,
                })
                print("  no results found")
                continue

            response = generate_answer(eval_q.question, results)
            context, _ = build_context(response["sources"])
            faithfulness = check_faithfulness(response["answer"], context)

            per_question_results.append({
                "question": eval_q.question,
                "answer": response["answer"],
                "sufficient_context": response["sufficient_context"],
                "faithfulness_supported": faithfulness["supported"],
                "faithfulness_explanation": faithfulness["explanation"],
                "parse_error": response["parse_error"],
                "no_results": False,
            })

            marker = {True: "✓", False: "⚠️", None: "?"}[faithfulness["supported"]]
            print(f"  {marker} faithfulness: {faithfulness['supported']}")

    finally:
        conn.close()

    scored = [r for r in per_question_results if r["faithfulness_supported"] is not None]
    supported_count = sum(1 for r in scored if r["faithfulness_supported"] is True)
    parse_errors = sum(1 for r in per_question_results if r["parse_error"])
    no_results = sum(1 for r in per_question_results if r["no_results"])

    aggregate = {
        "num_questions": len(per_question_results),
        "faithfulness_pass_rate": (supported_count / len(scored)) if scored else None,
        "faithfulness_scored_count": len(scored),
        "parse_errors": parse_errors,
        "no_results": no_results,
    }

    print(f"\n{'=' * 50}")
    print("AGGREGATE RESULTS")
    print(f"{'=' * 50}")
    for k, v in aggregate.items():
        print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")

    output = {"aggregate": aggregate, "per_question": per_question_results}
    RESULTS_PATH.write_text(json.dumps(output, indent=2))
    print(f"\nDetailed results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_evaluation(limit)
