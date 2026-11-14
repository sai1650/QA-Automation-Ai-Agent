import hashlib
import re
from typing import Any


_REDACTIONS = (
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    (
        re.compile(
            r'(?i)("(?:password|passwd|secret|api[_-]?key|access[_-]?token|'
            r'token|authorization|cookie|set-cookie|username|form[_-]?value|'
            r'input[_-]?value|field[_-]?value)"\s*:\s*")[^"]*(")'
        ),
        r"\1[REDACTED]\2",
    ),
    (
        re.compile(
            r"(?i)(password|passwd|secret|api[_-]?key|access[_-]?token|token|"
            r"authorization|cookie|set-cookie|username|form[_-]?value|"
            r"input[_-]?value|field[_-]?value)\s*([=:]\s*|\"\s*:\s*\")"
            r"([^,\s\";]+)"
        ),
        r"\1\2[REDACTED]",
    ),
    (
        re.compile(r"(?i)(https?://[^/\s:@]+):[^@/\s]+@"),
        r"\1:[REDACTED]@",
    ),
    (
        re.compile(
            r"(?i)([?&](?:token|key|password|secret|auth|session)=)[^&\s#]+"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        "[REDACTED_EMAIL]",
    ),
)


def sanitize_knowledge_text(text: str) -> str:
    normalized = text.replace("\x00", " ")
    for pattern, replacement in _REDACTIONS:
        normalized = pattern.sub(replacement, normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def chunk_text(
    text: str,
    *,
    document_id: str,
    chunk_size: int,
    chunk_overlap: int,
    max_chunks: int,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    if not text.strip():
        raise ValueError("Knowledge content must not be empty.")
    if chunk_overlap >= chunk_size:
        raise ValueError("Chunk overlap must be smaller than chunk size.")

    chunks: list[dict[str, Any]] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(" ", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary
        content = text[start:end].strip()
        if content:
            index = len(chunks)
            digest = hashlib.sha256(
                f"{document_id}:{index}:{content}".encode("utf-8")
            ).hexdigest()[:20]
            chunks.append(
                {
                    "chunk_id": f"{document_id}:{digest}",
                    "document_id": document_id,
                    "content": content,
                    "metadata": {**metadata, "chunk_index": index},
                }
            )
            if len(chunks) > max_chunks:
                raise ValueError("Document exceeds the configured maximum chunk count.")
        if end == len(text):
            break
        start = max(start + 1, end - chunk_overlap)
    return chunks
