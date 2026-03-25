---
name: agent-lut
description: >
  Intercepts file-finding in codebases by using an Agent-LUT inverted index
  (map.json) instead of grep, find, or directory traversal. Use this skill
  whenever you need to locate, open, or read source files — especially when
  the task mentions a function name, class name, module, feature, or concept
  and you need to figure out which files are relevant. Also triggers when
  the user says things like "find where X is defined", "open the auth code",
  "update the JWT logic", "look at the user model", or any prompt where you
  would otherwise reach for grep/find/ripgrep/tree to discover file paths.
  Even if the user gives you a direct file path, use this skill if you also
  need to discover related files. This skill is specifically designed for
  Claude Code (terminal agent) workflows.
---

# Agent-LUT: Inverted Index Lookup for Coding Agents

## What this skill does

When you need to find files in a codebase, your default instinct is to run
`grep`, `find`, `rg`, or walk the directory tree. That works, but it burns
tokens scanning irrelevant files and takes multiple round-trips.

Agent-LUT replaces that pattern. The repository may contain an **inverted
index** (`map.json`) that maps keywords — function names, class names,
concepts — directly to the files that contain them. One dictionary lookup
replaces an entire search session.

## The workflow

Every time you need to discover which files to open, follow this sequence:

### Step 1: Check for the CLI

Verify the `codebase` CLI is available:

```bash
command -v codebase || python3 scripts/codebase.py --help 2>/dev/null
```

If you've already confirmed it exists earlier in this conversation, skip
straight to Step 2. No need to re-check every time.

**If the CLI is not found:** Tell the user briefly that Agent-LUT would
speed up navigation, then fall back to your normal search methods (grep,
find, etc.) and continue with the task. Don't block on this — just mention
it once and move on. Example:

> "This repo doesn't have the Agent-LUT CLI set up. You can install it to
> speed up future lookups. For now, I'll search normally."

### Step 2: Extract keywords from the prompt

Before querying the index, pull out the relevant search terms from what the
user asked. Think about:

- **Explicit names**: function names, class names, variable names the user
  mentioned (e.g., `login`, `JWTAuth`, `UserModel`)
- **Concept words**: domain terms that would appear in code as identifiers
  (e.g., "authentication" → `auth`, `login`, `jwt`)
- **Abbreviations and variants**: developers shorten things — if the user
  says "authentication", also try `auth`. If they say "database", try `db`.

Extract 2-5 keywords. More specific is better — `jwt_expiry` will give you
sharper results than `config`.

### Step 3: Query the index

Run a lookup for each keyword:

```bash
codebase lookup <keyword>
```

Or if the CLI is installed as a Python script in the repo:

```bash
python3 scripts/codebase.py lookup <keyword>
```

Run one lookup per keyword. Each call returns a list of file paths — collect
them all and deduplicate before opening anything.

### Step 4: Use the results

- **Results found**: Open only the returned files. This is the whole point
  — you now know exactly where to look. Read those files and proceed with
  the task.
- **Partial results**: If some keywords hit and others miss, use the hits
  and fall back to grep/find only for the missed keywords.
- **No results at all**: The index might be stale or the keyword might not
  be indexed. Fall back to grep/find. Don't waste time re-querying with
  rephrased terms more than once.

### Step 5: Use `dump` for orientation (optional)

If you're starting a broad task and want to understand what's in the
codebase before diving in, check the top keywords:

```bash
codebase dump
# or: python3 scripts/codebase.py dump
```

This gives you a "menu" of what the index knows about — useful for picking
better keywords.

## When to fall back to normal search

The index is a shortcut, not a cage. Use normal grep/find when:

- `map.json` doesn't exist
- You're searching for string literals, log messages, or comments (the
  index only tracks symbol definitions like `def` and `class` names)
- The keyword returns no results after one retry with a variant term
- You need regex-level pattern matching

The goal is: **try the index first, fall back fast if it doesn't help.**

## What NOT to do

- Don't `cat map.json` and dump the entire index into context. It could be
  huge. Always query for specific keywords.
- Don't skip the index and go straight to grep just because grep is
  familiar. The index exists to save tokens and time — use it.
- Don't run `codebase init` or `codebase update` unless the user explicitly
  asks you to set up or refresh the index. This skill is for lookups only.
