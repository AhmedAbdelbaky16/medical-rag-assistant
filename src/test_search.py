"""
Quick manual test of semantic search — not part of the pipeline,
just a way to see pgvector similarity search actually working before
we build the real retrieval logic in Phase 6.

Usage:
    python test_search.py "what is the max dose of ibuprofen?"
"""

import sys

from fastembed import TextEmbedding
import pg8000

from config import DB_CONFIG, EMBEDDING_MODEL_NAME
from embed_and_load import vector_to_pg_literal


def get_connection():
    return pg8000.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def search(question: str, top_k: int = 5):
    print(f"Loading {EMBEDDING_MODEL_NAME}...")
    model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)

    query_vector = list(model.embed([question]))[0]
    query_literal = vector_to_pg_literal(query_vector)

    conn = get_connection()
    try:
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
                (query_literal, top_k),
            )
            rows = cur.fetchall()

        print(f"\nQuestion: {question}\n")
        print(f"Top {top_k} matches:\n")
        for i, (drug_name, section_title, chunk_text, distance) in enumerate(rows, 1):
            preview = chunk_text[:200].replace("\n", " ")
            print(f"{i}. [{drug_name} — {section_title}]  (distance: {distance:.4f})")
            print(f"   {preview}...\n")
    finally:
        conn.close()


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "what is the max daily dose of ibuprofen?"
    search(question)
