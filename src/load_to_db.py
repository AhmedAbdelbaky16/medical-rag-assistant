"""
Phase 3 — Load parsed drug label JSON into PostgreSQL.

Two things happen here:
  1. apply_schema()  -> runs sql/schema.sql to create the tables
                        (safe to re-run; CREATE TABLE IF NOT EXISTS)
  2. load_all_drugs() -> reads every JSON file in data/processed/,
                        inserts one row into `drugs`, then inserts
                        one row per section into `sections`, linked
                        by the drug's generated drug_id (the FK).

Run this after Phase 1 (parse_labels.py) and Phase 2 (docker compose up).
"""

import json
import logging
from pathlib import Path

import pg8000

from config import DB_CONFIG, PROCESSED_DIR, PROJECT_ROOT

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"


def get_connection():
    # pg8000 uses "database" not "dbname" as the keyword — everything
    # else matches what we already have in DB_CONFIG.
    return pg8000.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def apply_schema(conn):
    """
    Run schema.sql to create tables (idempotent).

    pg8000's cursor.execute() only runs one statement at a time (unlike
    psycopg2, which can run a whole multi-statement SQL file in one
    call) — so we split the file on ';' and execute each statement
    separately.

    Before splitting, we strip full-line SQL comments (lines starting
    with '--'). Without this, a semicolon inside a comment's prose
    (e.g. "...every time; with it...") gets mistaken for a real
    statement terminator and breaks the split.
    """
    raw_sql = SCHEMA_PATH.read_text()
    code_lines = [
        line for line in raw_sql.splitlines()
        if not line.strip().startswith("--")
    ]
    sql = "\n".join(code_lines)

    statements = [s.strip() for s in sql.split(";") if s.strip()]

    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    conn.commit()
    log.info(f"Schema applied ({len(statements)} statements).")


def load_drug(conn, drug_json: dict) -> int:
    """
    Insert one drug row, return its generated drug_id.

    ON CONFLICT (setid) DO UPDATE lets us safely re-run this script:
    if a drug with this setid already exists, update it instead of
    erroring out or creating a duplicate.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO drugs (drug_name, setid, source_file)
            VALUES (%s, %s, %s)
            ON CONFLICT (setid) DO UPDATE
                SET drug_name = EXCLUDED.drug_name
            RETURNING drug_id;
            """,
            (drug_json["drug_name"], drug_json["setid"], drug_json["source_file"]),
        )
        drug_id = cur.fetchone()[0]
    return drug_id


def load_sections(conn, drug_id: int, sections: list[dict]):
    """
    Insert all sections for a drug.

    We delete existing sections for this drug first — simpler than
    trying to diff/update individual sections, and safe since sections
    are fully re-derived from the JSON each time (no user edits to
    preserve).
    """
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sections WHERE drug_id = %s;", (drug_id,))

        for section in sections:
            cur.execute(
                """
                INSERT INTO sections (drug_id, section_title, section_text)
                VALUES (%s, %s, %s);
                """,
                (drug_id, section["section_title"], section["text"]),
            )


def load_all_drugs():
    json_files = sorted(PROCESSED_DIR.glob("*.json"))
    if not json_files:
        log.warning(f"No JSON files found in {PROCESSED_DIR}. Run parse_labels.py first.")
        return

    conn = get_connection()
    try:
        apply_schema(conn)

        loaded = 0
        for json_path in json_files:
            drug_json = json.loads(json_path.read_text())

            drug_id = load_drug(conn, drug_json)
            load_sections(conn, drug_id, drug_json["sections"])
            conn.commit()

            log.info(
                f"Loaded {drug_json['drug_name']} "
                f"(drug_id={drug_id}, {len(drug_json['sections'])} sections)"
            )
            loaded += 1

        log.info(f"Done. Loaded {loaded}/{len(json_files)} drugs.")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    load_all_drugs()
