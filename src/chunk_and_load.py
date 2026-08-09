"""
Phase 4 — Chunk every section in the database and store the results.

Reads all rows from `sections`, splits each one into chunks using the
real bge-small tokenizer (so token counts match what Phase 5's
embedding model will actually see), and writes the results into
`chunks`.

First run downloads the tokenizer files from Hugging Face (~1-2 MB,
one-time, cached locally afterward) — needs normal internet access,
which your machine has (this doesn't happen inside any sandbox).
"""

import logging

from tokenizers import Tokenizer

import pg8000

from config import (
    DB_CONFIG,
    EMBEDDING_MODEL_NAME,
    CHUNK_TARGET_TOKENS,
    CHUNK_MAX_TOKENS,
    CHUNK_OVERLAP_TOKENS,
)
from chunking import chunk_section_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def get_connection():
    return pg8000.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def load_tokenizer() -> Tokenizer:
    log.info(f"Loading tokenizer for {EMBEDDING_MODEL_NAME} (downloads on first run)...")
    tokenizer = Tokenizer.from_pretrained(EMBEDDING_MODEL_NAME)
    log.info("Tokenizer loaded.")
    return tokenizer


def make_token_counter(tokenizer: Tokenizer):
    """
    Wraps the tokenizer in a plain function so chunking.py never has
    to know anything about the tokenizers library specifically — it
    just calls count_tokens(text) -> int.
    """
    def count_tokens(text: str) -> int:
        return len(tokenizer.encode(text).ids)
    return count_tokens


def fetch_all_sections(conn) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute("SELECT section_id, drug_id, section_text FROM sections;")
        return cur.fetchall()


def delete_existing_chunks(conn, section_id: int):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM chunks WHERE section_id = %s;", (section_id,))


def insert_chunk(conn, section_id: int, drug_id: int, chunk_index: int, text: str, token_count: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chunks (section_id, drug_id, chunk_index, chunk_text, token_count)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (section_id, drug_id, chunk_index, text, token_count),
        )


def chunk_all_sections():
    tokenizer = load_tokenizer()
    count_tokens = make_token_counter(tokenizer)

    conn = get_connection()
    try:
        sections = fetch_all_sections(conn)
        log.info(f"Found {len(sections)} sections to chunk.")

        total_chunks = 0
        sections_split = 0

        for section_id, drug_id, section_text in sections:
            chunks = chunk_section_text(
                section_text,
                count_tokens,
                target_tokens=CHUNK_TARGET_TOKENS,
                max_tokens=CHUNK_MAX_TOKENS,
                overlap_tokens=CHUNK_OVERLAP_TOKENS,
            )

            delete_existing_chunks(conn, section_id)
            for chunk in chunks:
                insert_chunk(
                    conn, section_id, drug_id, chunk.chunk_index, chunk.text, chunk.token_count
                )

            total_chunks += len(chunks)
            if len(chunks) > 1:
                sections_split += 1

            conn.commit()

        log.info(
            f"Done. {len(sections)} sections -> {total_chunks} chunks "
            f"({sections_split} sections were split into multiple chunks)."
        )

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    chunk_all_sections()
