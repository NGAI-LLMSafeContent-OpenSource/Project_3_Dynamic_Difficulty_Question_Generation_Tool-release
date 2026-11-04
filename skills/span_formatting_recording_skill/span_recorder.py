from __future__ import annotations

from typing import Any


class SpanRecorder:
    skill_name = "span_recorder"

    def run(self, *, edited_input: str, harmful_texts: list[str], harmless_texts: list[str]) -> dict[str, list[dict[str, Any]]]:
        return {
            "harmful_spans": locate_spans(edited_input, harmful_texts),
            "harmless_spans": locate_spans(edited_input, harmless_texts),
        }


def locate_spans(text: str, fragments: list[str]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    cursor = 0
    for fragment in fragments:
        start = text.find(fragment, cursor)
        if start < 0:
            start = text.find(fragment)
        if start < 0:
            raise ValueError(f"fragment not found in edited_input: {fragment}")
        end = start + len(fragment)
        spans.append({"text": fragment, "start": start, "end": end})
        cursor = end
    return spans

