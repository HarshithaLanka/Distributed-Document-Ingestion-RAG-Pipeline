# This file checks whether extracted PDF text is readable enough for RAG.


# This function calculates how many characters are suspicious.
def calculate_noise_ratio(text: str) -> float:
    # If text is empty, return maximum noise.
    if not text.strip():
        return 1.0

    # Count total characters in the text.
    total_chars = len(text)

    # These characters often appear when PDF extraction is corrupted.
    suspicious_chars = ["*", "{", "}", "|", "\\", "^", "~"]

    # Count suspicious characters.
    suspicious_count = sum(text.count(char) for char in suspicious_chars)

    # Count weird broken quote patterns.
    suspicious_count += text.count("''")
    suspicious_count += text.count('""')

    # Return suspicious characters divided by total characters.
    return suspicious_count / total_chars


# This function checks if the text has enough normal alphabet characters.
def calculate_alpha_ratio(text: str) -> float:
    # If text is empty, return zero readable text.
    if not text.strip():
        return 0.0

    # Count alphabet letters.
    alpha_count = sum(1 for char in text if char.isalpha())

    # Count total characters.
    total_chars = len(text)

    # Return alphabet letters divided by total characters.
    return alpha_count / total_chars


# This function decides whether extracted text is good enough for RAG.
def is_text_quality_good(text: str) -> bool:
    # Calculate how noisy the text is.
    noise_ratio = calculate_noise_ratio(text)

    # Calculate how much normal alphabet text exists.
    alpha_ratio = calculate_alpha_ratio(text)

    # If too many suspicious characters exist, text quality is bad.
    if noise_ratio > 0.03:
        return False

    # If alphabet ratio is too low, text quality is bad.
    if alpha_ratio < 0.55:
        return False

    # Otherwise, text quality is acceptable.
    return True