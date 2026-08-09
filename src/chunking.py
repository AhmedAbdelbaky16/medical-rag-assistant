"""
Phase 4 — Chunking logic.

Kept separate from the database/tokenizer-loading code (chunk_and_load.py)
so this core algorithm can be tested with any token-counting function —
including a fake one, without needing internet access or a real model.

Strategy:
  1. If a section's whole text fits within max_tokens, keep it as one
     chunk untouched — no point splitting an already-short section.
  2. Otherwise, split into sentences and greedily pack them into chunks
     up to max_tokens, carrying the last ~overlap_tokens worth of
     sentences into the start of the next chunk for continuity.
  3. If a single "sentence" is itself longer than max_tokens (this
     happens with the flattened data tables we saw in Phase 1 — long
     runs of numbers with no real sentence breaks), fall back to
     splitting it by words instead, since sentence splitting has
     nothing to work with there.
"""

import re
from dataclasses import dataclass
from typing import Callable

TokenCounter = Callable[[str], int]

# Naive sentence splitter: break after . ! or ? when followed by
# whitespace and then an uppercase letter or an opening parenthesis.
# This isn't linguistically perfect (it can be fooled by abbreviations
# like "Dr." or "e.g."), but it's good enough for chunking purposes —
# we don't need perfect grammar, just reasonable break points. It also
# correctly avoids splitting on decimal numbers like "0.33" since a
# digit doesn't match the [A-Z(] lookahead.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


@dataclass
class Chunk:
    text: str
    token_count: int
    chunk_index: int


def split_sentences(text: str) -> list[str]:
    sentences = _SENTENCE_SPLIT_RE.split(text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _split_long_text_by_words(
    text: str, count_tokens: TokenCounter, max_tokens: int, overlap_tokens: int
) -> list[str]:
    """
    Fallback for a single "sentence" that's already too long on its
    own (e.g. flattened table data with no real sentence breaks).
    Greedily packs whole words up to max_tokens, with word-level
    overlap between consecutive pieces.
    """
    words = text.split()
    if not words:
        return []

    pieces = []
    start = 0
    while start < len(words):
        end = start
        # Grow the window word-by-word until adding the next word
        # would exceed max_tokens.
        while end < len(words):
            trial = " ".join(words[start:end + 1])
            if count_tokens(trial) > max_tokens:
                break
            end += 1
        if end == start:
            # Even a single word exceeds max_tokens (very rare) —
            # take it anyway rather than looping forever.
            end = start + 1

        pieces.append(" ".join(words[start:end]))

        # Walk backward from `end` to find the overlap start point for
        # the next piece.
        back = end
        while back > start:
            trial = " ".join(words[back - 1:end])
            if count_tokens(trial) > overlap_tokens:
                break
            back -= 1

        next_start = back if back > start else end
        start = next_start

    return pieces


def chunk_section_text(
    text: str,
    count_tokens: TokenCounter,
    target_tokens: int = 300,
    max_tokens: int = 400,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """
    Split a section's text into Chunk objects. `count_tokens` is
    injected so this function doesn't care whether it's a real
    tokenizer or a stand-in used for testing.
    """
    text = text.strip()
    if not text:
        return []

    total_tokens = count_tokens(text)
    if total_tokens <= max_tokens:
        return [Chunk(text=text, token_count=total_tokens, chunk_index=0)]

    sentences = split_sentences(text)

    raw_chunks: list[str] = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sent_tokens = count_tokens(sentence)

        # A single sentence too big to ever fit on its own — split it
        # by words up front, treat each piece like its own "sentence".
        if sent_tokens > max_tokens:
            # Flush whatever we've built up so far first.
            if current_sentences:
                raw_chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_tokens = 0
            raw_chunks.extend(
                _split_long_text_by_words(sentence, count_tokens, max_tokens, overlap_tokens)
            )
            continue

        if current_tokens + sent_tokens > max_tokens and current_sentences:
            raw_chunks.append(" ".join(current_sentences))

            # Carry forward the tail of the current chunk as overlap.
            overlap_sentences: list[str] = []
            overlap_count = 0
            for s in reversed(current_sentences):
                s_tokens = count_tokens(s)
                if overlap_count + s_tokens > overlap_tokens:
                    break
                overlap_sentences.insert(0, s)
                overlap_count += s_tokens

            current_sentences = overlap_sentences
            current_tokens = overlap_count

        current_sentences.append(sentence)
        current_tokens += sent_tokens

    if current_sentences:
        raw_chunks.append(" ".join(current_sentences))

    return [
        Chunk(text=c, token_count=count_tokens(c), chunk_index=i)
        for i, c in enumerate(raw_chunks)
    ]
