"""
Simple deterministic reranking service for Week 14.

This version does not download another ML model.
It reranks candidate chunks using:
- existing hybrid score
- important query-token overlap
- exact phrase overlap
- entity overlap
- section-title overlap
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app.services.entity_extraction_service import extract_query_entities


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
    "for", "from", "how", "in", "is", "it", "of", "on", "or", "the", "this",
    "to", "was", "were", "what", "when", "where", "which", "who", "why", "with",
}


def _clamp(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def tokenize_meaningful_words(text: str) -> List[str]:
    """Return unique meaningful lowercase tokens in original order."""

    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.:+#-]*", text or "")
    output: List[str] = []
    seen: set[str] = set()

    for word in words:
        token = word.lower().strip("._:-")
        if len(token) < 2 or token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        output.append(token)

    return output


def calculate_query_overlap(question: str, text: str) -> float:
    query_tokens = tokenize_meaningful_words(question)
    if not query_tokens:
        return 0.0

    lower_text = (text or "").lower()
    matched = sum(1 for token in query_tokens if token in lower_text)
    return matched / len(query_tokens)


def calculate_exact_phrase_score(question: str, text: str) -> float:
    """
    Reward exact multi-word phrases and structured references.

    Example:
    "week 14", "section 2.1", "privacy aware embeddings"
    """

    lower_question = " ".join((question or "").lower().split())
    lower_text = " ".join((text or "").lower().split())

    if not lower_question or not lower_text:
        return 0.0

    phrases = re.findall(
        r"\b(?:week|day|chapter|section|clause|module|unit|part)\s+\d+(?:\.\d+)*\b",
        lower_question,
    )

    words = tokenize_meaningful_words(lower_question)
    for size in (4, 3, 2):
        for index in range(len(words) - size + 1):
            phrases.append(" ".join(words[index:index + size]))

    unique_phrases = list(dict.fromkeys(phrases))
    if not unique_phrases:
        return 0.0

    matches = sum(1 for phrase in unique_phrases if phrase in lower_text)
    return matches / len(unique_phrases)


def calculate_entity_overlap(question: str, candidate: Dict[str, Any]) -> float:
    entities = extract_query_entities(question)
    query_names = {
        entity["normalized_text"]
        for entity in entities
        if entity.get("normalized_text")
    }

    if not query_names:
        return 0.0

    candidate_text = " ".join(
        [
            str(candidate.get("text") or ""),
            str(candidate.get("section_title") or ""),
            " ".join(candidate.get("matched_entities") or []),
        ]
    ).lower()

    matched = sum(1 for name in query_names if name in candidate_text)
    return matched / len(query_names)


def calculate_section_title_score(question: str, section_title: str) -> float:
    if not section_title:
        return 0.0

    query_tokens = set(tokenize_meaningful_words(question))
    section_tokens = set(tokenize_meaningful_words(section_title))

    if not query_tokens or not section_tokens:
        return 0.0

    return len(query_tokens & section_tokens) / len(query_tokens)


def rerank_candidates(
    question: str,
    candidates: List[Dict[str, Any]],
    final_top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Rerank candidate chunks and return the strongest final context."""

    if not question or not question.strip():
        raise ValueError("question cannot be empty")

    if final_top_k <= 0 or not candidates:
        return []

    reranked: List[Dict[str, Any]] = []

    for original_rank, candidate in enumerate(candidates, start=1):
        item = dict(candidate)
        text = str(item.get("text") or item.get("source_text") or "")

        hybrid_score = _clamp(item.get("hybrid_score", item.get("score", 0.0)))
        query_overlap = _clamp(calculate_query_overlap(question, text))
        exact_phrase = _clamp(calculate_exact_phrase_score(question, text))
        entity_overlap = _clamp(calculate_entity_overlap(question, item))
        section_score = _clamp(
            calculate_section_title_score(
                question,
                str(item.get("section_title") or ""),
            )
        )

        rerank_score = (
            0.45 * hybrid_score
            + 0.20 * query_overlap
            + 0.15 * exact_phrase
            + 0.15 * entity_overlap
            + 0.05 * section_score
        )

        item.update(
            {
                "original_rank": original_rank,
                "hybrid_score": hybrid_score,
                "query_overlap_score": query_overlap,
                "exact_phrase_score": exact_phrase,
                "entity_overlap_score": entity_overlap,
                "section_title_score": section_score,
                "rerank_score": _clamp(rerank_score),
            }
        )
        reranked.append(item)

    reranked.sort(
        key=lambda item: (
            item["rerank_score"],
            item.get("hybrid_score", 0.0),
            len(item.get("retrieval_sources", [])),
        ),
        reverse=True,
    )

    final_results = reranked[: min(final_top_k, 20)]

    for final_rank, item in enumerate(final_results, start=1):
        item["final_rank"] = final_rank

    return final_results