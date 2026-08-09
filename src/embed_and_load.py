"""
Phase 5 — Generate embeddings for every chunk and store them in Postgres.

Uses `fastembed` to run bge-small-en-v1.5 via ONNX Runtime (CPU-only,
no PyTorch needed — much lighter install). Same model, same output
vectors, as if we'd used sentence-transformers.

First run downloads the ONNX model files (~130MB, one-time, cached
afterward) — needs normal internet access.

Only embeds chunks that don't already have an embedding, so this is
safe to re-run after adding new drugs later without redoing existing
work.
"""

import logging

from fastembed import TextEmbedding
import pg8000

from config import DB_CONFIG, EMBEDDING_MODEL_NAME

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

BATCH_SIZE = 32


def get_connection():
    return pg8000.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def vector_to_pg_literal(vector) -> str:
    """
    pg8000 doesn't know about pgvector's `vector` type natively, so we
    send it as text in pgvector's own literal format: '[0.1,0.2,...]',
    cast to `vector` on the SQL side.
    """
    return "[" + ",".join(str(float(x)) for x in vector) + "]"


def fetch_chunks_needing_embeddings(conn) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT chunk_id, chunk_text FROM chunks WHERE embedding IS NULL;"
        )
        return cur.fetchall()


def update_embedding(conn, chunk_id: int, vector) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE chunks SET embedding = %s::vector WHERE chunk_id = %s;",
            (vector_to_pg_literal(vector), chunk_id),
        )


def create_similarity_index(conn) -> None:
    """
    Build the ivfflat similarity-search index now that real embeddings
    exist. Safe to call every run — IF NOT EXISTS skips it if already
    built. If you add a lot more data later, dropping and recreating
    this index would improve search quality, since its clusters are
    based on a snapshot of the data at creation time.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                ON chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """
        )
    conn.commit()
    log.info("Similarity index ready.")


def embed_all_chunks():
    log.info(f"Loading embedding model {EMBEDDING_MODEL_NAME} (downloads on first run)...")
    model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    log.info("Model loaded.")

    conn = get_connection()
    try:
        rows = fetch_chunks_needing_embeddings(conn)
        log.info(f"Found {len(rows)} chunks needing embeddings.")

        if not rows:
            log.info("Nothing to do.")
            return

        chunk_ids = [r[0] for r in rows]
        texts = [r[1] for r in rows]

        embedded = 0
        for batch_start in range(0, len(texts), BATCH_SIZE):
            batch_ids = chunk_ids[batch_start:batch_start + BATCH_SIZE]
            batch_texts = texts[batch_start:batch_start + BATCH_SIZE]

            # model.embed() returns a generator of numpy arrays, one per input text
            vectors = list(model.embed(batch_texts))

            for chunk_id, vector in zip(batch_ids, vectors):
                update_embedding(conn, chunk_id, vector)

            conn.commit()
            embedded += len(batch_ids)
            log.info(f"Embedded {embedded}/{len(texts)} chunks...")

        create_similarity_index(conn)
        log.info(f"Done. Embedded {embedded} chunks.")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    embed_all_chunks()
