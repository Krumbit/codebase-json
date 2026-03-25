"""lookup_files tool schema and execution."""

from __future__ import annotations

import json
from pathlib import Path

from agent_lut.store import load_map

LOOKUP_FILES_OPENAI_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup_files",
        "description": (
            "Look up file paths in the codebase keyword index for a symbol, class name, "
            "or topic keyword. Call this before guessing which files to read."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Keyword to look up (case-insensitive).",
                },
            },
            "required": ["keyword"],
        },
    },
}

LOOKUP_FILES_ANTHROPIC_TOOL = {
    "name": "lookup_files",
    "description": LOOKUP_FILES_OPENAI_TOOL["function"]["description"],
    "input_schema": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "Keyword to look up (case-insensitive).",
            },
        },
        "required": ["keyword"],
    },
}


def run_lookup_files(map_path: Path, keyword: str) -> str:
    if not map_path.is_file():
        return json.dumps({"paths": [], "error": f"map not found: {map_path}"})
    keywords, _meta = load_map(map_path)
    k = keyword.strip().lower()
    paths = keywords.get(k, [])
    return json.dumps({"keyword": k, "paths": paths})
