"""
Phase 7 — End-to-end: ask a real question, get a grounded, cited answer.

    python ask.py "what is the max daily dose of ibuprofen?"

Pipeline: embed question -> hybrid retrieval (Phase 6) -> generate
answer with citations -> faithfulness check -> print everything,
including the sources, so you can verify the answer yourself.

Requires Ollama running locally (`ollama serve`, or the desktop app)
with GENERATION_MODEL (config.py) already pulled.
"""

import sys

from fastembed import TextEmbedding
import pg8000

from config import DB_CONFIG, EMBEDDING_MODEL_NAME
from embed_and_load import vector_to_pg_literal
from retrieval import hybrid_search, detect_drug_filter
from generate import generate_answer, check_faithfulness, build_context


def get_connection():
    return pg8000.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def ask(question: str, top_k: int = 5, run_faithfulness_check: bool = True):
    print(f"Loading {EMBEDDING_MODEL_NAME}...")
    model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    query_vector = list(model.embed([question]))[0]
    query_literal = vector_to_pg_literal(query_vector)

    conn = get_connection()
    try:
        drug_ids = detect_drug_filter(conn, question)
        print(f"Drug filter: {'drug_id ' + str(drug_ids) if drug_ids else 'none (all drugs)'}")

        results = hybrid_search(conn, query_literal, question, top_k)
        if not results:
            print("\nNo relevant chunks found.")
            return

        print("Generating answer...")
        response = generate_answer(question, results)

        print(f"\n{'=' * 60}")
        print(f"Question: {question}")
        print(f"{'=' * 60}\n")

        if response["parse_error"]:
            print("⚠️  The model's response couldn't be parsed. Raw answer shown below:\n")

        print(f"Answer: {response['answer']}\n")

        if response["sufficient_context"] is False:
            print("⚠️  Model flagged: sources may not fully answer this question.\n")

        print("Sources used:")
        for i, r in enumerate(response["sources"], 1):
            cited_marker = "✓" if i in response["cited_sources"] else " "
            print(f"  [{cited_marker}] Source {i}: {r.drug_name} — {r.section_title} (distance {r.distance:.4f})")

        if run_faithfulness_check and not response["parse_error"]:
            print("\nRunning faithfulness check...")
            context, _ = build_context(response["sources"])
            check = check_faithfulness(response["answer"], context)
            if check["supported"] is True:
                print(f"✓ Faithfulness check passed: {check['explanation']}")
            elif check["supported"] is False:
                print(f"⚠️  Faithfulness check FAILED: {check['explanation']}")
            else:
                print(f"(Faithfulness check inconclusive: {check['explanation']})")

    finally:
        conn.close()


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "what is the max daily dose of ibuprofen?"
    ask(question)
