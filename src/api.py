"""
Phase 8 — FastAPI backend wrapping the RAG pipeline as a real HTTP service.

Run with:
    uvicorn api:app --reload

Then:
    POST http://localhost:8000/ask   with body {"question": "..."}
    GET  http://localhost:8000/health
    GET  http://localhost:8000/docs   — interactive API docs, generated
         automatically from the Pydantic models below.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastembed import TextEmbedding
import pg8000
import requests as http_requests

from config import DB_CONFIG, EMBEDDING_MODEL_NAME
from embed_and_load import vector_to_pg_literal
from retrieval import hybrid_search, detect_drug_filter
from generate import generate_answer, check_faithfulness, build_context

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Loaded once at startup (see lifespan below), reused across every
# request — reloading the embedding model per-request would be slow
# and pointless, since the model itself never changes between
# questions. Kept in a plain dict rather than a global variable so
# tests can swap it out cleanly.
_model_holder: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Loading embedding model {EMBEDDING_MODEL_NAME}...")
    _model_holder["model"] = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    log.info("Model loaded. API ready.")
    yield
    _model_holder.clear()


app = FastAPI(
    title="Medical RAG Assistant API",
    description=(
        "Answers questions about FDA drug labels, grounded in retrieved "
        "label text with citations. Educational project only — not "
        "medical advice."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


def get_connection():
    # A new connection per request, matching every other script in this
    # project. Fine at this project's scale — a production API handling
    # real concurrent traffic would use a connection pool instead.
    return pg8000.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


# --- Request / response models ------------------------------------------
# Pydantic models double as both request validation and the source for
# FastAPI's auto-generated /docs page — one definition, two jobs.

class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)
    check_faithfulness: bool = Field(
        default=True,
        description="Run the second faithfulness-check model call (slower but safer).",
    )


class SourceOut(BaseModel):
    index: int
    drug_name: str
    section_title: str
    chunk_text: str
    distance: float
    cited: bool


class FaithfulnessOut(BaseModel):
    supported: bool | None
    explanation: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sufficient_context: bool | None
    drug_filter_applied: bool
    sources: list[SourceOut]
    faithfulness: FaithfulnessOut | None


# --- Endpoints -------------------------------------------------------------

@app.get("/health")
def health():
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL;")
            embedded_count = cur.fetchone()[0]
        conn.close()
        return {"status": "ok", "embedded_chunks": embedded_count}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    model = _model_holder.get("model")
    if model is None:
        raise HTTPException(status_code=503, detail="Embedding model not loaded yet.")

    query_vector = list(model.embed([request.question]))[0]
    query_literal = vector_to_pg_literal(query_vector)

    conn = get_connection()
    try:
        drug_ids = detect_drug_filter(conn, request.question)
        results = hybrid_search(conn, query_literal, request.question, request.top_k)

        if not results:
            return AskResponse(
                question=request.question,
                answer="No relevant information was found for this question.",
                sufficient_context=False,
                drug_filter_applied=bool(drug_ids),
                sources=[],
                faithfulness=None,
            )

        try:
            response = generate_answer(request.question, results)
        except http_requests.RequestException as e:
            raise HTTPException(
                status_code=503,
                detail=f"Could not reach the generation service. ({e})",
            )

        faithfulness_out = None
        if request.check_faithfulness and not response["parse_error"]:
            context, _ = build_context(response["sources"])
            check = check_faithfulness(response["answer"], context)
            faithfulness_out = FaithfulnessOut(
                supported=check["supported"], explanation=check["explanation"]
            )

        sources_out = [
            SourceOut(
                index=i,
                drug_name=r.drug_name,
                section_title=r.section_title,
                chunk_text=r.chunk_text,
                distance=r.distance,
                cited=i in response["cited_sources"],
            )
            for i, r in enumerate(response["sources"], 1)
        ]

        return AskResponse(
            question=request.question,
            answer=response["answer"],
            sufficient_context=response["sufficient_context"],
            drug_filter_applied=bool(drug_ids),
            sources=sources_out,
            faithfulness=faithfulness_out,
        )

    finally:
        conn.close()
