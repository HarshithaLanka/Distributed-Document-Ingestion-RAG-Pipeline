# This file contains the full RAG Q&A logic.

# Import vector search function.
from app.services.pinecone_service import search_similar_chunks

# Import LLM answer generation function.
from app.services.llm_service import generate_answer_with_grok


# Standard not-found answer.
NOT_FOUND_ANSWER = "I could not find this information in the document."


# Create a short preview of citation text.
def create_source_preview(text: str, max_chars: int = 350) -> str:
    # Remove extra spaces and line breaks.
    cleaned_text = " ".join(text.split())

    # If text is short, return full text.
    if len(cleaned_text) <= max_chars:
        return cleaned_text

    # Otherwise return only preview.
    return cleaned_text[:max_chars] + "..."


# Check if answer means not found.
def is_not_found_answer(answer: str) -> bool:
    # Normalize answer for comparison.
    normalized_answer = answer.lower().strip()

    # Detect not-found wording.
    return (
        "could not find this information" in normalized_answer
        or "not present in the context" in normalized_answer
        or "not found in the document" in normalized_answer
        or "not mentioned in the document" in normalized_answer
        or "does not provide information" in normalized_answer
    )


# Filter chunks using Pinecone similarity score.
def filter_chunks_by_score(
    retrieved_chunks: list[dict],
    min_score: float
) -> list[dict]:
    # Create empty list for relevant chunks.
    relevant_chunks = []

    # Loop through retrieved chunks.
    for chunk in retrieved_chunks:
        # Get score safely.
        score = chunk.get("score", 0)

        # Keep only chunks above threshold.
        if score >= min_score:
            relevant_chunks.append(chunk)

    # Return relevant chunks.
    return relevant_chunks


# Build RAG prompt using retrieved chunks.
def build_rag_prompt(question: str, retrieved_chunks: list[dict]) -> str:
    # Create empty list for context sections.
    context_sections = []

    # Loop through retrieved chunks.
    for chunk in retrieved_chunks:
        # Format each chunk clearly.
        context_block = (
            f"Source: Page {chunk['page_number']}, Chunk {chunk['chunk_id']}\n"
            f"Text:\n{chunk['text']}"
        )

        # Add formatted chunk to context list.
        context_sections.append(context_block)

    # Join all chunks into one context.
    context_text = "\n\n---\n\n".join(context_sections)

    # Build strict extraction prompt.
    prompt = f"""
You are answering a question using only the document context below.

Important rules:
1. Read the context carefully.
2. If the answer is explicitly present, extract the answer directly.
3. If the question asks for an opinion, evaluation, or judgment, answer only using evidence from the context.
4. Do not give personal opinion. Say "Based on the document..." and support the answer with document evidence.
5. If the answer is not present, say exactly:
   "{NOT_FOUND_ANSWER}"
6. Do not invent facts.
7. Do not mention that the context is incomplete if the answer is present.

Document Context:
{context_text}

Question:
{question}

Final Answer:
"""

    # Return prompt.
    return prompt


# Main RAG function.
def answer_question_from_document(
    document_id: str,
    question: str,
    top_k: int = 3,
    min_score: float = 0.35
) -> dict:
    # Search Pinecone for relevant chunks.
    retrieved_chunks = search_similar_chunks(
        document_id=document_id,
        query=question,
        top_k=top_k
    )

    # Filter weak chunks.
    relevant_chunks = filter_chunks_by_score(
        retrieved_chunks=retrieved_chunks,
        min_score=min_score
    )

    # If no chunks pass threshold, return no answer and no citations.
    if not relevant_chunks:
        return {
            "answer": NOT_FOUND_ANSWER,
            "citations": []
        }

    # Build RAG prompt.
    prompt = build_rag_prompt(
        question=question,
        retrieved_chunks=relevant_chunks
    )

    # Generate answer using Ollama.
    answer = generate_answer_with_grok(prompt)

    # If LLM says not found, return citations as empty.
    if is_not_found_answer(answer):
        return {
            "answer": NOT_FOUND_ANSWER,
            "citations": []
        }

    # Create citations only when answer is found.
    citations = [
        {
            "chunk_id": chunk["chunk_id"],
            "page_number": chunk["page_number"],
            "score": chunk["score"],
            "source_preview": create_source_preview(chunk["text"])
        }
        for chunk in relevant_chunks
    ]

    # Return answer and citations.
    return {
        "answer": answer,
        "citations": citations
    }