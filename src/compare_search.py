"""
Phase 6 — Compare pure vector search vs. hybrid (SQL-filtered) search
side by side, on the same question.

This exists to make the improvement visible and easy to screenshot
for a portfolio writeup, using the exact failure case found during
Phase 5 testing: a question naming one drug pulling in an unrelated
drug's chunk because it happened to mention the right word in passing.

Usage:
    python compare_search.py "what is the max daily dose of ibuprofen?"
"""

import sys

from fastembed import TextEmbedding
import pg8000

from config import DB_CONFIG, EMBEDDING_MODEL_NAME
from embed_and_load import vector_to_pg_literal
from retrieval import hybrid_search, detect_drug_filter


def get_connection():
    return pg8000.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def pure_vector_search(conn, query_vector_literal: str, top_k: int = 5):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.drug_name, s.section_title, c.chunk_text,
                   c.embedding <=> %s::vector AS distance
            FROM chunks c
            JOIN sections s ON c.section_id = s.section_id
            JOIN drugs d ON c.drug_id = d.drug_id
            ORDER BY distance
            LIMIT %s;
            """,
            (query_vector_literal, top_k),
        )
        return cur.fetchall()


def print_results(title, rows_or_results, is_hybrid=False):
    print(f"\n--- {title} ---")
    if not rows_or_results:
        print("  (no results)")
        return
    for i, r in enumerate(rows_or_results, 1):
        if is_hybrid:
            drug_name, section_title, chunk_text, distance = (
                r.drug_name, r.section_title, r.chunk_text, r.distance
            )
        else:
            drug_name, section_title, chunk_text, distance = r
        preview = chunk_text[:120].replace("\n", " ")
        print(f"  {i}. [{drug_name} — {section_title}]  (distance: {distance:.4f})")
        print(f"     {preview}...")


def compare(question: str, top_k: int = 5):
    print(f"Loading {EMBEDDING_MODEL_NAME}...")
    model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    query_vector = list(model.embed([question]))[0]
    query_literal = vector_to_pg_literal(query_vector)

    conn = get_connection()
    try:
        print(f"\nQuestion: {question}")

        drug_ids = detect_drug_filter(conn, question)
        if drug_ids:
            print(f"Detected drug filter: drug_id(s) {drug_ids}")
        else:
            print("Detected drug filter: none (searching all drugs)")

        pure_results = pure_vector_search(conn, query_literal, top_k)
        print_results("Pure vector search (Phase 5)", pure_results, is_hybrid=False)

        hybrid_results = hybrid_search(conn, query_literal, question, top_k)
        print_results("Hybrid search (Phase 6)", hybrid_results, is_hybrid=True)

    finally:
        conn.close()


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "what is the max daily dose of ibuprofen?"
    compare(question)
