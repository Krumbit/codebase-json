"""LLM tool loop with OpenAI or Anthropic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_lut.metrics import RunMetrics
from agent_lut.prompts import AGENT_SYSTEM_PROMPT
from agent_lut.tools import (
    LOOKUP_FILES_ANTHROPIC_TOOL,
    LOOKUP_FILES_OPENAI_TOOL,
    run_lookup_files,
)


def run_agent_openai(
    *,
    api_key: str,
    model: str,
    map_path: Path,
    user_message: str,
    system_prompt: str = AGENT_SYSTEM_PROMPT,
    max_turns: int = 16,
    metrics: RunMetrics | None = None,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    tools = [LOOKUP_FILES_OPENAI_TOOL]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    m = metrics or RunMetrics()
    out_text = ""

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        m.totals.add_openai_usage(response.usage)
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                if tc.function.name != "lookup_files":
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"error": "unknown tool"}),
                        }
                    )
                    continue
                m.tool_lookup_calls += 1
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                kw = str(args.get("keyword", ""))
                result = run_lookup_files(map_path, kw)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            continue

        out_text = (msg.content or "").strip()
        break

    return out_text


def run_agent_anthropic(
    *,
    api_key: str,
    model: str,
    map_path: Path,
    user_message: str,
    system_prompt: str = AGENT_SYSTEM_PROMPT,
    max_turns: int = 16,
    metrics: RunMetrics | None = None,
) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    tools = [LOOKUP_FILES_ANTHROPIC_TOOL]
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    m = metrics or RunMetrics()
    out_text = ""

    for _ in range(max_turns):
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=messages,
            tools=tools,
        )
        m.totals.add_anthropic_usage(response.usage)

        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if response.stop_reason == "tool_use" and tool_blocks:
            messages.append({"role": "assistant", "content": response.content})
            tool_results: list[dict[str, Any]] = []
            for block in tool_blocks:
                if block.name != "lookup_files":
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps({"error": "unknown tool"}),
                            "is_error": True,
                        }
                    )
                    continue
                m.tool_lookup_calls += 1
                inp = getattr(block, "input", {}) or {}
                kw = str(inp.get("keyword", ""))
                result = run_lookup_files(map_path, kw)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
            messages.append({"role": "user", "content": tool_results})
            continue

        out_text = "".join(b.text for b in text_blocks).strip()
        break

    return out_text


def run_agent(
    *,
    provider: str,
    model: str,
    map_path: Path,
    user_message: str,
    max_turns: int = 16,
    metrics: RunMetrics | None = None,
) -> str:
    import os

    provider = provider.lower().strip()
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise SystemExit("OPENAI_API_KEY is not set")
        return run_agent_openai(
            api_key=key,
            model=model,
            map_path=map_path,
            user_message=user_message,
            max_turns=max_turns,
            metrics=metrics,
        )
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise SystemExit("ANTHROPIC_API_KEY is not set")
        return run_agent_anthropic(
            api_key=key,
            model=model,
            map_path=map_path,
            user_message=user_message,
            max_turns=max_turns,
            metrics=metrics,
        )
    raise SystemExit(f"unknown provider: {provider}")
