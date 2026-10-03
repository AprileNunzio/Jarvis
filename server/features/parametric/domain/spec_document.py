import json
import re
from typing import Any, Dict

import yaml

MAX_DOCUMENT_CHARS = 200_000
_FENCE = re.compile(r"```(?:json|yaml|yml)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_spec_document(raw: str) -> Dict[str, Any]:
    if not isinstance(raw, str) or len(raw) > MAX_DOCUMENT_CHARS:
        raise ValueError("document missing or too large")
    for candidate in _candidates(raw):
        parsed = _load(candidate)
        if isinstance(parsed, dict) and parsed:
            return parsed
    raise ValueError("no JSON or YAML object found")


def _candidates(raw: str):
    for block in _FENCE.findall(raw):
        yield block
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        yield raw[start : end + 1]
    yield raw


def _load(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        pass
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None
