# mac-migration

Three-phase CLI tool for conscious macOS machine migration (e.g. M1 → new M-series Mac).
Use this when you do **not** want a 1:1 clone (Migration Assistant), but also do not
want to lose custom data (sample libraries, exports, oddly named project folders).

## Why not a fixed rules script?

A static script only catches patterns you thought of in advance (`Ableton`, `Samples`, etc.).
Folders like `2023-08-19 wedding export` or `sample stash v2` need contextual interpretation —
Phase B uses Vertex AI (Gemini Flash Lite) for that, with a rule-based fallback if you
skip the cloud API.

## Architecture

| Phase | Script | Output |
|-------|--------|--------|
| **A — Collect** | `collector/*.sh` | `~/migration-inventory/` (Markdown + JSON) |
| **B — Analyze** | `analyzer/analyze.py` | `analysis-report.md` + `analysis-report.json` |
| **C — Plan** | `planner/generate-plan.py` | `migration-plan.md` + `migration-plan.json` |

All user data stays **local** under `~/migration-inventory/`. Only folder metadata
(path, size, extension stats — never file contents or credentials) is sent to Vertex AI.

## Prerequisites

- macOS (source machine)
- **Homebrew** (recommended, not required for collector)
- **Python 3.11+**
- **gcloud CLI** (only for Phase B with Vertex AI)
- GCP project with Vertex AI API enabled

### ADC setup (Vertex AI)

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

No API keys are used — only Application Default Credentials (ADC).

## Quick start

```bash
git clone <repo-url> mac-migration
cd mac-migration
chmod +x mac-migration

# Install Python deps (once)
pip install -r analyzer/requirements.txt

# Full pipeline (English output)
./mac-migration all --project YOUR_PROJECT_ID

# Hungarian output
./mac-migration all --project YOUR_PROJECT_ID --lang hu

# Without Vertex AI (rule-based fallback)
./mac-migration all --fallback --lang hu
```

### Step by step

```bash
# Phase A — inventory + folder profiling (~minutes on large homes)
./mac-migration collect

# Phase B — LLM categorization
./mac-migration analyze --project YOUR_PROJECT_ID --lang hu

# Phase C — checklist
./mac-migration plan --lang hu
```

## Configuration

All configuration is via **CLI flags** (no hardcoded project ID):

| Flag | Default | Description |
|------|---------|-------------|
| `--project` | _(required)_ | GCP project ID |
| `--model` | `gemini-3.5-flash-lite` | Global Gemini model |
| `--location` | `global` | Vertex AI location |
| `--lang` | `en` | Output language (`en` or `hu`) |
| `--batch-size` | `30` | Folders per API call |
| `--min-size-mb` | `100` | Skip smaller folders |
| `--fallback` | off | Rule-based analysis, no cloud |

## Folder categories (Phase B)

- **user_custom** — must copy (samples, exports, projects)
- **app_data** — usually restored on reinstall
- **cache_or_temp** — safe to skip
- **uncertain** — manual review

## Migration plan actions (Phase C)

- **Copy 1:1** — `user_custom` folders → external SSD
- **Reinstall** — apps from inventory / Brewfile
- **Rebuild consciously** — dotfiles, runtimes, Homebrew bundle
- **Skip** — cache/temp
- **Re-authenticate** — SSH, GPG, cloud CLIs on new Mac

## Security

- Sensitive directories (`.ssh`, `.gnupg`, `.aws`, `.kube`, `.config/gcloud`, etc.)
  are **excluded from folder profiling** before JSON export.
- Collector auth section reports existence/count only — no secret contents.
- Git config values are redacted in inventory output.

## FAQ

### I don't have Vertex AI access

Use `--fallback` for rule-based categorization. Less accurate for oddly named folders,
but fully offline after collection:

```bash
./mac-migration analyze --fallback --lang hu
./mac-migration plan --lang hu
```

### How long does Phase A take?

Depends on home directory size. Large `~/Library` trees can take several minutes.
Progress is printed every 100 folders.

### Where is output stored?

Everything under `~/migration-inventory/` — not committed to git.

### Which model and region?

Default: `gemini-3.5-flash-lite` at `global` location (Google's global endpoint).

## Development

```bash
# Tests
pytest analyzer/tests/ -v

# Shellcheck
shellcheck collector/*.sh mac-migration
```

## License

MIT — see [LICENSE](LICENSE).
