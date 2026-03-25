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

### Step 1: Check for the index

Look for `map.json` in the repository root. Common locations to check, in
order:

```
./map.json
./.agent-lut/map.json
./codebase/map.json
```

Run a quick check:

```bash
# Fast existence check — don't cat the whole file yet
find . -maxdepth 2 -name "map.json" -path "*agent*" -o -name "map.json" 2>/dev/null | head -5
```

If you've already confirmed the index exists earlier in this conversation,
skip straight to Step 2. No need to re-check every time.

**If no index is found:** Tell the user briefly that an Agent-LUT index
would speed up navigation, then fall back to your normal search methods
(grep, find, etc.) and continue with the task. Don't block on this — just
mention it once and move on. Example:

> "I didn't find an Agent-LUT index in this repo. You can set one up with
> `codebase init` to speed up future lookups. For now, I'll search normally."

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

Use the CLI if available:

```bash
codebase lookup <keyword>
```

If the `codebase` CLI is not installed but `map.json` exists, query it
directly with a lightweight command:

```bash
# Single keyword lookup
python3 -c "
import json, sys
m = json.load(open('map.json'))
kw = sys.argv[1].lower()
hits = m.get('keywords', {}).get(kw, [])
print('\n'.join(hits) if hits else f'No results for: {kw}')
" "<keyword>"
```

For multiple keywords in one shot:

```bash
python3 -c "
import json, sys
m = json.load(open('map.json'))
kws = sys.argv[1:]
seen = set()
for kw in kws:
    for f in m.get('keywords', {}).get(kw.lower(), []):
        if f not in seen:
            seen.add(f)
            print(f)
" keyword1 keyword2 keyword3
```

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
```

Or manually:

```bash
python3 -c "
import json
m = json.load(open('map.json'))
kws = m.get('keywords', {})
top = sorted(kws.items(), key=lambda x: len(x[1]), reverse=True)[:20]
for k, v in top:
    print(f'{k}: {len(v)} files')
"
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