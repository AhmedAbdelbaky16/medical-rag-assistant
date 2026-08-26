"""
Phase 9 — Streamlit frontend.

Run with:
    streamlit run frontend.py

Talks to the FastAPI backend (Phase 8) over plain HTTP — same as any
other client would — rather than importing the pipeline directly. This
keeps the frontend and backend genuinely decoupled: the UI has no idea
how answers get generated, it just calls an API.

Requires both running:
    - Postgres (docker compose up -d)
    - The API (python -m uvicorn api:app --reload, from src/)
    - Ollama (ollama serve)
"""

import requests
import streamlit as st

from config import API_BASE_URL

# Generation can take a while on CPU (two model calls: generation +
# faithfulness check) — a short timeout would fail real, in-progress
# requests, not just genuinely stuck ones.
REQUEST_TIMEOUT = 180


def call_ask_api(question: str, top_k: int = 5, check_faithfulness: bool = True) -> dict:
    """
    Calls the backend's /ask endpoint. Kept separate from the Streamlit
    UI code below so this function can be tested with a mocked
    `requests.post`, independent of Streamlit's runtime.

    Raises requests.RequestException on connection failure — the
    caller (render_chat, below) is responsible for catching it and
    showing a friendly message instead of a raw traceback.
    """
    response = requests.post(
        f"{API_BASE_URL}/ask",
        json={"question": question, "top_k": top_k, "check_faithfulness": check_faithfulness},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def render_answer(result: dict):
    st.markdown(result["answer"])

    if result.get("sufficient_context") is False:
        st.warning("The sources may not fully answer this question.")

    faithfulness = result.get("faithfulness")
    if faithfulness is not None:
        if faithfulness["supported"] is True:
            st.success(f"✓ Faithfulness check passed: {faithfulness['explanation']}")
        elif faithfulness["supported"] is False:
            st.error(f"⚠️ Faithfulness check failed: {faithfulness['explanation']}")
        else:
            st.info(f"Faithfulness check inconclusive: {faithfulness['explanation']}")

    sources = result.get("sources", [])
    if sources:
        with st.expander(f"Sources ({len(sources)})"):
            for s in sources:
                marker = "✓ cited" if s["cited"] else "not cited"
                st.markdown(
                    f"**{s['index']}. {s['drug_name']} — {s['section_title']}** "
                    f"({marker}, distance {s['distance']:.4f})"
                )
                st.caption(s["chunk_text"])


def main():
    st.set_page_config(page_title="Medical RAG Assistant", page_icon="💊")
    st.title("💊 Medical RAG Assistant")
    st.caption(
        "Answers questions about FDA drug labels, grounded in retrieved label "
        "text with citations. **Educational project only — not medical advice.**"
    )

    if "history" not in st.session_state:
        st.session_state.history = []  # list of (question, result) tuples

    for question, result in st.session_state.history:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            render_answer(result)

    question = st.chat_input("Ask about a drug's dosage, warnings, side effects...")

    if question:
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Retrieving and generating..."):
                try:
                    result = call_ask_api(question)
                except requests.exceptions.ConnectionError:
                    st.error(
                        "Can't reach the backend API. Is it running? "
                        "(`python -m uvicorn api:app --reload` from `src/`)"
                    )
                    return
                except requests.exceptions.HTTPError as e:
                    if e.response is not None and e.response.status_code == 503:
                        st.error(
                            "Backend can't reach Ollama. Is it running? (`ollama serve`)"
                        )
                    else:
                        st.error(f"Request failed: {e}")
                    return
                except requests.exceptions.Timeout:
                    st.error("The request took too long and timed out. Try again.")
                    return

            render_answer(result)

        st.session_state.history.append((question, result))


if __name__ == "__main__":
    main()
