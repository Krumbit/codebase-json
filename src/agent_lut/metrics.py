"""Token usage tracking and optional baseline comparison (demo-oriented)."""

from __future__ import annotations

from dataclasses import dataclass, field

import tiktoken


@dataclass
class UsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def add_openai_usage(self, usage: object | None) -> None:
        if usage is None:
            return
        self.input_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
        self.output_tokens += int(getattr(usage, "completion_tokens", 0) or 0)
        t = getattr(usage, "total_tokens", None)
        if t is not None:
            self.total_tokens += int(t)
        else:
            self.total_tokens += self.input_tokens + self.output_tokens

    def add_anthropic_usage(self, usage: object | None) -> None:
        if usage is None:
            return
        self.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
        self.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
        self.total_tokens += self.input_tokens + self.output_tokens


@dataclass
class RunMetrics:
    totals: UsageTotals = field(default_factory=UsageTotals)
    tool_lookup_calls: int = 0
    baseline_tokens_if_n_files: int | None = None

    def record_baseline_n_file_reads(self, n_files: int, chars_per_file: int = 4000) -> None:
        """Rough demo baseline: assume each file read is ~chars_per_file characters."""
        enc = tiktoken.get_encoding("cl100k_base")
        chunk = "x" * chars_per_file
        per = len(enc.encode(chunk))
        self.baseline_tokens_if_n_files = n_files * per


def format_metrics_report(m: RunMetrics) -> str:
    lines = [
        f"API input tokens:  {m.totals.input_tokens}",
        f"API output tokens: {m.totals.output_tokens}",
        f"API total (reported): {m.totals.total_tokens}",
        f"lookup_files calls: {m.tool_lookup_calls}",
    ]
    if m.baseline_tokens_if_n_files is not None:
        lines.append(
            f"Rough baseline if reading N files without index: ~{m.baseline_tokens_if_n_files} tokens (estimate; not comparable 1:1 to API usage)",
        )
    return "\n".join(lines)
