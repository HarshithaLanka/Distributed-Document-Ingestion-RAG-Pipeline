# This file handles local LLM calls using Ollama.

# Import requests to call Ollama local HTTP API.
import requests

# Import Ollama settings from config.py.
from app.config import OLLAMA_BASE_URL
from app.config import OLLAMA_MODEL


# Generate answer using local Ollama model.
def generate_answer_with_ollama(prompt: str) -> str:
    # Create Ollama generate API URL.
    url = f"{OLLAMA_BASE_URL}/api/generate"

    # Strong system instruction for document Q&A.
    system_prompt = (
        "You are a strict document extraction assistant. "
        "Your job is to read the provided document context and answer the user's question. "
        "Use only the document context. "
        "Do not use outside knowledge. "
        "If the answer is present in the context, extract it directly. "
        "If the answer is not present in the context, say exactly: "
        "'I could not find this information in the document.' "
        "Do not say the context does not provide information if the answer appears in the context."
    )

    # Create request payload for Ollama.
    payload = {
        # Model name from .env.
        "model": OLLAMA_MODEL,

        # System prompt controls model behavior.
        "system": system_prompt,

        # Main prompt contains retrieved chunks + question.
        "prompt": prompt,

        # stream=False means return one full response.
        "stream": False,

        # Low temperature makes answer less creative and more factual.
        "options": {
            "temperature": 0.0
        }
    }

    # Send request to Ollama.
    response = requests.post(
        url,
        json=payload,
        timeout=120
    )

    # Raise error if Ollama request failed.
    response.raise_for_status()

    # Convert response JSON to Python dictionary.
    data = response.json()

    # Extract answer text.
    answer = data.get("response", "")

    # Return cleaned answer.
    return answer.strip()


# Keep this function name so your old qa_service.py import does not break.
def generate_answer_with_grok(prompt: str) -> str:
    # Internally use Ollama instead of Grok.
    return generate_answer_with_ollama(prompt)