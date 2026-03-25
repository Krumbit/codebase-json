# Agent-LUT

Inverted keyword-to-file index (`map.json`) for coding agents. CLI: `codebase init|update|lookup|dump|agent`.

## Quick start

**From another clone or another project** (install published package from GitHub; replace the repo path if yours differs):

```bash
pip install "agent-lut @ git+https://github.com/Krumbit/codebase-md.git@main"
```

**Developing this repo:**

```bash
pip install -e ".[dev]"
codebase init --repo-root .
codebase lookup some_function
codebase dump
```

For `codebase agent`, set API keys either in the environment or in a **`.env`** file at the project root (or any parent of your current working directory). Values in the real environment take precedence over `.env`.

Example `.env` (do not commit; `.env` is gitignored):

```bash
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
```

## GitHub Actions

[`.github/workflows/sync.yml`](.github/workflows/sync.yml) runs `codebase update` on changed Python files and commits `map.json` when it changes. Use a PAT or relax branch protection if commits from `GITHUB_TOKEN` are blocked.
