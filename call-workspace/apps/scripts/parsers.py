"""Pure-function parser for script templates with {{input}} and [[output]] syntax."""

import re
from dataclasses import dataclass
from typing import Mapping

INPUT_PATTERN = re.compile(r"\{\{(\w+)\}\}")
OUTPUT_PATTERN = re.compile(r"\[\[(\w+)\]\]")


@dataclass(frozen=True)
class ParsedTemplate:
    input_params: list[str]
    output_params: list[str]


def parse_template(text: str) -> ParsedTemplate:
    """Extract {{input}} and [[output]] parameter names, deduplicated, in order of first appearance."""
    return ParsedTemplate(
        input_params=_unique_in_order(INPUT_PATTERN.findall(text)),
        output_params=_unique_in_order(OUTPUT_PATTERN.findall(text)),
    )


def render_template(text: str, values: Mapping[str, str]) -> str:
    """Replace {{params}} with values; leave [[params]] untouched. Raises KeyError if a value is missing."""
    parsed = parse_template(text)
    missing = [p for p in parsed.input_params if p not in values]
    if missing:
        raise KeyError(f"Missing values for: {', '.join(missing)}")

    def substitute(match: re.Match) -> str:
        return str(values[match.group(1)])

    return INPUT_PATTERN.sub(substitute, text)


def _unique_in_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
