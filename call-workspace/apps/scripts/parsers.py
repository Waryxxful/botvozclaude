"""Pure-function parser for script templates with {{input}}, [[output]], and ## comment ## syntax."""

import re
from dataclasses import dataclass
from typing import Mapping

INPUT_PATTERN = re.compile(r"\{\{(\w+)\}\}")
OUTPUT_PATTERN = re.compile(r"\[\[(\w+)\]\]")
COMMENT_PATTERN = re.compile(r"##(.+?)##", re.DOTALL)


@dataclass(frozen=True)
class ParsedTemplate:
    input_params: list[str]
    output_params: list[str]


def parse_template(prompt: str, greeting: str = "") -> ParsedTemplate:
    """Extract {{input}} and [[output]] params from greeting + prompt combined.
    Greeting variables appear first in input_params. Outputs only from prompt.
    """
    combined_inputs = _unique_in_order(
        INPUT_PATTERN.findall(greeting) + INPUT_PATTERN.findall(prompt)
    )
    return ParsedTemplate(
        input_params=combined_inputs,
        output_params=_unique_in_order(OUTPUT_PATTERN.findall(prompt)),
    )


def render_template(text: str, values: Mapping[str, str]) -> str:
    """Replace {{params}} with values; leave [[params]] and ## ## comments untouched.

    Raises KeyError if a value is missing.
    """
    parsed = parse_template(text, "")
    missing = [p for p in parsed.input_params if p not in values]
    if missing:
        raise KeyError(f"Missing values for: {', '.join(missing)}")

    def substitute(match: re.Match) -> str:
        return str(values[match.group(1)])

    return INPUT_PATTERN.sub(substitute, text)


def extract_comments(text: str) -> list[str]:
    """Extract all comments (text between ## ##) in order of appearance."""
    comments = []
    for match in COMMENT_PATTERN.finditer(text):
        comment = match.group(1).strip()
        if comment:
            comments.append(comment)
    return comments


def _unique_in_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
