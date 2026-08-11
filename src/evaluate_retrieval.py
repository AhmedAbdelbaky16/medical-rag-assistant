"""
Phase 11 — Run the eval set against real hybrid retrieval and report
recall@k / MRR.

    python evaluate_retrieval.py

Saves detailed results to eval_results_retrieval.json (kept out of
data/, since this is evaluation output, not pipeline data) — useful
both for spotting patterns in failures and as evidence for a portfolio
writeup.
"""

import json
import logging

from fastembed import TextEmbedding
import pg8000

from config import DB_CONFIG, EMBEDDING_MODEL_NAME, PROJECT_ROOT
from embed_and_load import vector_to_pg_literal
from retrieval import hybrid_search
from eval_set import EVAL_QUESTIONS
from eval_metrics import compute_question_metrics, aggregate_metrics

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

TOP_K = 5
RESULTS_PATH = PROJECT_ROOT / "eval_results_retrieval.json"


def get_connection():
    return pg8000.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def run_evaluation():
    print(f"Loading {EMBEDDING_MODEL_NAME}...")
    model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)

    conn = get_connection()
    per_question_results = []

    try:
        for eval_q in EVAL_QUESTIONS:
            query_vector = list(model.embed([eval_q.question]))[0]
            query_literal = vector_to_pg_literal(query_vector)

            results = hybrid_search(conn, query_literal, eval_q.question, TOP_K)
            metrics = compute_question_metrics(results, eval_q)

            metrics["top_result"] = (
                f"{results[0].drug_name} — {results[0].section_title}" if results else None
            )
            per_question_results.append(metrics)

            status = "✓" if metrics["rank"] and metrics["rank"] <= 3 else ("~" if metrics["rank"] else "✗")
            print(f"{status} rank={metrics['rank']}  {eval_q.question}")
            if metrics["rank"] is None or metrics["rank"] > 1:
                print(f"    top result was: {metrics['top_result']}")

    finally:
        conn.close()

    aggregate = aggregate_metrics(per_question_results)

    print(f"\n{'=' * 50}")
    print("AGGREGATE RESULTS")
    print(f"{'=' * 50}")
    for k, v in aggregate.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")
        else:
            print(f"  {k}: {v}")

    output = {"aggregate": aggregate, "per_question": per_question_results}
    RESULTS_PATH.write_text(json.dumps(output, indent=2))
    print(f"\nDetailed results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    run_evaluation()
