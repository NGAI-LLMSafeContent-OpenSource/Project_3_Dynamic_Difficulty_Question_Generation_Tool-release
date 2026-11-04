from __future__ import annotations

def ensure_sentence(text: str) -> str:
    stripped = text.strip()
    if stripped.endswith(("。", "！", "？", ".", "!", "?")):
        return stripped
    return f"{stripped}。"


def join_sentences(texts: list[str]) -> str:
    return "".join(ensure_sentence(text) for text in texts)
