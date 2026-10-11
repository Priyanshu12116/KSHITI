"""Language of a question: Devanagari Hindi, Hindi in English letters, or English."""
from __future__ import annotations

import re

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# Common Hindi words typed in English letters at a counter.
HINGLISH = {
    "kitna", "kitni", "kitne", "mera", "meri", "mere", "hai", "hain", "kya", "kaise", "kahan",
    "chahiye", "chhodna", "chhodni", "chodni", "jagah", "sadak", "makaan", "makan", "ghar", "naksha",
    "anumati", "shulk", "fees", "lagegi", "lagega", "milegi", "banana", "banwana", "kab", "tak",
    "aage", "peeche", "piche", "manzil", "manjil", "zameen", "jameen", "bhukhand", "nahi", "nahin",
    "aur", "ke", "ki", "ka", "ko", "se", "mein", "par",
}


def detect_lang(text: str) -> str:
    """Return 'hi' for Devanagari or Hinglish, otherwise 'en'."""
    if not text:
        return "en"
    letters = [c for c in text if c.isalpha()]
    if letters and sum(bool(DEVANAGARI.match(c)) for c in letters) / len(letters) > 0.3:
        return "hi"
    words = re.findall(r"[a-zA-Z]+", text.lower())
    hits = sum(w in HINGLISH for w in words)
    strong = sum(w in HINGLISH and len(w) > 3 for w in words)
    return "hi" if words and strong >= 1 and hits / len(words) >= 0.25 else "en"
