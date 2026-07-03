from __future__ import annotations

import hashlib
import re


def normalize_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).lower().encode()).hexdigest()
