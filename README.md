> **Language / Nyelv:** English | [Magyar](README_HU.md)

MAC Migration Tool

CLI tool for conscious macOS machine migration (e.g. M1 → new M-series Mac).
Use this when you do **not** want a 1:1 clone (Migration Assistant), but also do not
want to lose custom data (sample libraries, exports, oddly named project folders).

## Why not a fixed rules script?

A static script only catches patterns you thought of in advance (`Ableton`, `Samples`, etc.).
Folders like `final-export` or `samples-v2` need contextual interpretation —
Phase B uses Google Enterprise Agent Platform (Gemini Flash Lite) for that, with a rule-based
fallback if you skip the cloud API.

## Architecture

| Phase | Script | Output |
|-------|--------|--------|
| **A — Collect** | `collector/*` (11 steps) | `~/migration-inventory/` (Markdown + JSON) |
| **B — Analyze** | `analyzer/analyze.py` | `analysis-report.md` + `analysis-report_HU.md` (+ JSON) |
| **C — Plan** | `planner/generate-plan.py` | `migration-plan.md` + `migration-plan_HU.md` (+ JSON) |
| **D — Guide** | `planner/generate-reinstall-guide.py` | `reinstall-guide.md` + `reinstall-guide_HU.md` |
| **Restore** | `restorer/restore.py` | On new Mac: aliases, shell, Homebrew, VS Code, Quick Actions, audio |
| **View** | `viewer/generate_dashboard.py` | `dashboard.html` |

All user data stays **local** under `~/migration-inventory/`. Only folder metadata
(path, size, extension stats — never file contents or credentials) is sent to Agent Platform.

## Prerequisites

- macOS (source machine)
- **Homebrew** (recommended, not required for collector)
- **Python 3.11+**
- GCP project with billing enabled (for AI analyze; optional with `--fallback`)
- **Application Default Credentials (ADC)** — no API keys, no JSON key files

### Authentication (ADC only)

**Not supported:** API keys, service account JSON keys, `GOOGLE_APPLICATION_CREDENTIALS`.

One-time setup **outside** this tool (then every `analyze` run is automatic):

```bash
gcloud auth application-default login
```

On the first `analyze` run, mac-migration automatically in the background:

1. Verifies ADC is available (via `google.auth.default()`)
2. Enables **Vertex AI API** (`aiplatform.googleapis.com`) on your `--project`

Use `--skip-gcp-setup` if the API is already enabled.

## Quick start

```bash
git clone <repo-url> mac-migration
cd mac-migration
chmod +x mac-migration

pip install -r analyzer/requirements.txt

# Full pipeline (after ADC is configured)
./mac-migration all --project YOUR_PROJECT_ID -i

# Without Agent Platform (rule-based fallback)
./mac-migration all --fallback
```

### Step by step

```bash
# Phase A — full inventory (11 steps, ~10–30 min on large homes)
./mac-migration collect

# Phase B — interactive AI review (recommended)
./mac-migration analyze --project YOUR_PROJECT_ID --interactive

# Phase C — checklist
./mac-migration plan

# Phase D — self-contained reinstall guide
./mac-migration guide

# HTML dashboard
./mac-migration view

# On new Mac — automatic restore
bash ~/migration-inventory/restore.sh
# or: ./mac-migration restore all
```

### Phase A — what gets collected?

The collect runs **11 steps** and inventories the whole machine:

| # | Output | Coverage |
|---|--------|----------|
| 1 | `01`–`08` *.md | Apps, package managers, runtimes, dotfiles, auth, editors |
| 2 | `09-shell-environment.md` | Shell, **aliases**, pyenv, nvm, PATH |
| 3 | `12-homebrew-full.md` | Every Homebrew formula, cask, tap, service |
| 4 | `11-vscode-extensions.md` | VS Code, Cursor, Insiders, VSCodium extensions |
| 5 | `14-quick-actions.md` | Quick Actions (Automator) + Shortcuts.app |
| 6 | `15-audio-devices.md` | BlackHole, HAL plugins, DJ/audio devices |
| 7 | `10-ai-dev-creative-tools.md` | AI, dev, creative apps (Cursor, Terraform, Ableton, …) |
| 8 | `collector-output.json` | 7000+ folder profiles (includes `~/.*` dot dirs) |
| 9 | `13-custom-paths.md` | Non-stock macOS paths |
| 10 | `16-full-system-inventory.md` | Login items, browser extensions, LaunchAgents, VPN, cron, git, Docker, Alfred/Karabiner, iTerm, fonts, printers, Wi‑Fi, Bluetooth, App Store |
| 11 | `restore-manifest.json` + `restore.sh` | Dynamic restore plan for the new Mac |

**Key JSON files:** `system-inventory.json`, `environment-snapshot.json`, `homebrew-inventory.json`, `vscode-extensions.json`, `quick-actions-inventory.json`, `audio-devices-inventory.json`, `tools-inventory.json`, `custom-paths.json`, `restore-manifest.json`

**Automatic restore on new Mac:** `bash ~/migration-inventory/restore.sh` applies aliases, shell init, Homebrew, VS Code extensions, Quick Actions, and audio drivers dynamically.

**Restore components:** `./mac-migration restore [aliases|shell|homebrew|vscode|quick-actions|audio|all]`

## Configuration

| Flag | Default | Description |
|------|---------|-------------|
| `--project` | _(required)_ | GCP project ID |
| `--model` | `gemini-3.5-flash-lite` | Gemini 3.5 Flash Lite (global model ID) |
| `--location` | `global` | Agent Platform location (global endpoint) |
| `--batch-size` | `30` | Folders per API call (batch mode) |
| `--min-size-mb` | `100` | Skip smaller folders (batch mode) |
| `--fallback` | off | Rule-based analysis, no cloud |
| `-i`, `--interactive` | off | AI review per component (recommended) |

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

- Sensitive directories (`.ssh`, `.gnupg`, `.aws`, `.kube`, `.config/gcloud`, etc.) are **profiled with a `sensitive` flag** — metadata only, never file contents.
- Auth section: existence/count only — no secret contents exported.
- Git config values are redacted in inventory output.
- Passwords, SSH keys, and Keychain contents are **never** auto-copied.

## FAQ

### I don't have Agent Platform access

```bash
./mac-migration analyze --fallback --interactive
./mac-migration plan
```

### How long does Phase A take?

Depends on home directory size. Large `~/Library` trees can take 10–30 minutes.
Progress is printed every 100 folders.

### Where is output stored?

Everything under `~/migration-inventory/` — not committed to git.

## Development

```bash
pytest collector/tests/ analyzer/tests/ planner/tests/ restorer/tests/ -q
shellcheck collector/*.sh mac-migration
```

## License

[CloudMentor Use License](LICENSE) — free use (including commercial) and
redistribution of **unmodified** copies. **Modifications require written
permission** from CloudMentor ([info@cloudmentor.hu](mailto:info@cloudmentor.hu)).
Hungarian summary: [LICENSE_HU.md](LICENSE_HU.md).
