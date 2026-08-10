"""
Phase 6 — Hybrid retrieval: SQL filtering + vector similarity search.

The problem this solves (found for real in Phase 5 testing): pure
vector search across all drugs can return a chunk that's only
thematically close and happens to mention the right word in passing
(e.g. Metformin's drug-interaction table mentioning "ibuprofen" in a
dosage comparison) ahead of the actual drug's own real answer.

The fix: if the question names a specific drug, filter to that drug's
chunks with SQL *before* ranking by vector distance. Vector search
then only has to compete within the right drug's own content.
"""

from dataclasses import dataclass

from config import DRUG_LIST


@dataclass
class SearchResult:
    drug_name: str
    section_title: str
    chunk_text: str
    distance: float


def detect_drug_filter(conn, question: str) -> list[int]:
    """
    Check whether any known drug name appears in the question.
    Returns a list of matching drug_ids (usually 0 or 1 entries).

    Longest names are checked first so "insulin glargine" matches
    before the shorter "insulin" would — otherwise the shorter name
    could match first and we'd filter to the wrong drug.
    """
    question_lower = question.lower()
    candidates = sorted(DRUG_LIST, key=len, reverse=True)

    for name in candidates:
        if name.lower() in question_lower:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT drug_id FROM drugs WHERE drug_name ILIKE %s;",
                    (f"%{name}%",),
                )
                rows = cur.fetchall()
            if rows:
                return [r[0] for r in rows]

    return []


def hybrid_search(conn, query_vector_literal: str, question: str, top_k: int = 5) -> list[SearchResult]:
    """
    Embed the question (caller passes the already-computed vector, as
    a pgvector literal string), detect an optional drug filter from
    the question text, and return the top_k closest chunks — filtered
    to that drug if one was mentioned, unfiltered otherwise.
    """
    drug_ids = detect_drug_filter(conn, question)

    with conn.cursor() as cur:
        if drug_ids:
            cur.execute(
                """
                SELECT d.drug_name, s.section_title, c.chunk_text,
                       c.embedding <=> %s::vector AS distance
                FROM chunks c
                JOIN sections s ON c.section_id = s.section_id
                JOIN drugs d ON c.drug_id = d.drug_id
                WHERE c.drug_id = ANY(%s)
                ORDER BY distance
                LIMIT %s;
                """,
                (query_vector_literal, drug_ids, top_k),
            )
        else:
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
        rows = cur.fetchall()

    return [
        SearchResult(drug_name=r[0], section_title=r[1], chunk_text=r[2], distance=r[3])
        for r in rows
    ]
