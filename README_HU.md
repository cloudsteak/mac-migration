> **Nyelv / Language:** [English](README.md) | Magyar

MAC Migrációs Eszköz

CLI eszköz tudatos macOS gép-migrációhoz (pl. M1 → új M-series Mac).
Akkor használd, ha **nem** akarsz 1:1 klónozást (Migration Assistant), de az egyedi
adatokat (sample library, exportok, szabálytalanul elnevezett mappák) sem akarod elveszíteni.

## Miért nem elég egy fix szabály alapú script?

Egy statikus script csak az előre bedobott mintákat ismeri (`Ableton`, `Samples` stb.).
Az olyan mappák, mint `vegleges-export` vagy `mintak-v2`, kontextuális
értelmezést igényelnek — a B fázis a Google Enterprise Agent Platformot (Gemini Flash Lite)
használja erre, szabály alapú fallbackkel, ha nem akarsz felhő API-t.

## Architektúra

| Fázis | Script | Kimenet |
|-------|--------|---------|
| **A — Collect** | `collector/*` (11 lépés) | `~/migration-inventory/` (Markdown + JSON) |
| **B — Analyze** | `analyzer/analyze.py` | `analysis-report.md` + `analysis-report_HU.md` (+ JSON) |
| **C — Plan** | `planner/generate-plan.py` | `migration-plan.md` + `migration-plan_HU.md` (+ JSON) |
| **D — Guide** | `planner/generate-reinstall-guide.py` | `reinstall-guide.md` + `reinstall-guide_HU.md` |
| **Restore** | `restorer/restore.py` | Új Mac: aliasok, shell, Homebrew, VS Code, Quick Actions, audio |
| **View** | `viewer/generate_dashboard.py` | `dashboard.html` |

Minden felhasználói adat **lokálisan** marad a `~/migration-inventory/` alatt. Csak mappa
metaadat (útvonal, méret, kiterjesztés-statisztika — soha fájltartalom vagy credential)
kerül az Agent Platformra.

## Előfeltételek

- macOS (forrás gép)
- **Homebrew** (ajánlott, collectorhez nem kötelező)
- **Python 3.11+**
- GCP projekt billinggel (AI analyze-hoz; `--fallback`-kel opcionális)
- **Application Default Credentials (ADC)** — nincs API kulcs, nincs JSON kulcsfájl

### Hitelesítés (csak ADC)

**Nem támogatott:** API kulcs, service account JSON kulcs, `GOOGLE_APPLICATION_CREDENTIALS`.

```bash
gcloud auth application-default login
```

Az első `analyze` futtatáskor a mac-migration automatikusan a háttérben:

1. Ellenőrzi az ADC-t (`google.auth.default()`)
2. Engedélyezi a **Vertex AI API**-t (`aiplatform.googleapis.com`) a `--project` projektben

`--skip-gcp-setup`, ha az API már engedélyezve van.

## Gyors indulás

```bash
git clone <repo-url> mac-migration
cd mac-migration
chmod +x mac-migration

pip install -r analyzer/requirements.txt

./mac-migration all --project YOUR_PROJECT_ID -i
./mac-migration all --fallback
```

### Lépésről lépésre

```bash
# A fázis — teljes leltár (11 lépés, nagy home-nál 10–30 perc)
./mac-migration collect

# B fázis — interaktív AI felülvizsgálat (ajánlott)
./mac-migration analyze --project YOUR_PROJECT_ID --interactive

# C fázis — checklist
./mac-migration plan

# D fázis — önálló újratelepítési útmutató
./mac-migration guide

# HTML dashboard
./mac-migration view

# Új Mac-en — automatikus visszaállítás
bash ~/migration-inventory/restore.sh
# vagy: ./mac-migration restore all
```

### A fázis — mit gyűjt?

A collect **11 lépésben** a teljes gépet feltérképezi:

| # | Kimenet | Mit |
|---|---------|-----|
| 1 | `01`–`08` *.md | Appok, csomagkezelők, runtime-ok, dotfile-ok, auth, szerkesztők |
| 2 | `09-shell-environment.md` | Shell, aliasok, pyenv, nvm, PATH |
| 3 | `12-homebrew-full.md` | Minden Homebrew csomag |
| 4 | `11-vscode-extensions.md` | VS Code / Cursor bővítmények |
| 5 | `14-quick-actions.md` | Quick Actions + Shortcuts |
| 6 | `15-audio-devices.md` | BlackHole, HAL driverek, DJ eszközök |
| 7 | `10-ai-dev-creative-tools.md` | AI, dev, kreatív appok |
| 8 | `collector-output.json` | 7000+ mappa-profil (`~/.*` dot mappák is) |
| 9 | `13-custom-paths.md` | Nem-alap macOS útvonalak |
| 10 | `16-full-system-inventory.md` | Login items, böngésző bővítmények, LaunchAgents, VPN, cron, git, Docker, Alfred/Karabiner, iTerm, fontok, nyomtatók, Wi‑Fi, Bluetooth, App Store |
| 11 | `restore-manifest.json` + `restore.sh` | Automatikus visszaállítási terv |

**Fő JSON fájlok:** `system-inventory.json`, `environment-snapshot.json`, `homebrew-inventory.json`, `vscode-extensions.json`, `quick-actions-inventory.json`, `audio-devices-inventory.json`, `tools-inventory.json`, `custom-paths.json`, `restore-manifest.json`

**Automatikus visszaállítás az új Mac-en:** `bash ~/migration-inventory/restore.sh` — aliasok, shell init, Homebrew, VS Code, Quick Actions, audio.

**Restore komponensek:** `./mac-migration restore [aliases|shell|homebrew|vscode|quick-actions|audio|all]`

## Konfiguráció

| Flag | Alapértelmezés | Leírás |
|------|----------------|--------|
| `--project` | _(kötelező)_ | GCP project ID |
| `--model` | `gemini-3.5-flash-lite` | Gemini 3.5 Flash Lite (globális modell ID) |
| `--location` | `global` | Agent Platform location (global endpoint) |
| `--batch-size` | `30` | Mappák API hívásonként (batch mód) |
| `--min-size-mb` | `100` | Ennél kisebb mappák kihagyása (batch mód) |
| `--fallback` | ki | Szabály alapú elemzés, felhő nélkül |
| `-i`, `--interactive` | ki | AI felülvizsgálat komponensenként (ajánlott) |

## Mappa kategóriák (B fázis)

- **user_custom** — másolandó (sample, export, projekt)
- **app_data** — újratelepítéssel jellemzően visszajön
- **cache_or_temp** — biztonsággal kihagyható
- **uncertain** — kézi ellenőrzés

## Migrációs terv akciók (C fázis)

- **Áthozni 1:1** — `user_custom` mappák → külső SSD
- **Újratelepíteni** — appok a leltárból / Brewfile-ból
- **Újraépíteni tudatosan** — dotfile, runtime, Homebrew bundle
- **Kihagyni** — cache/temp
- **Újra-authentikálni** — SSH, GPG, felhő CLI-k az új Mac-en

## Biztonság

- Érzékeny mappák (`.ssh`, `.gnupg`, `.aws`, `.kube`, `.config/gcloud` stb.) **`sensitive` jelzéssel profilozva** — csak metaadat, soha fájltartalom.
- Auth szekció: csak létezés/darabszám — secret tartalom nem kerül ki.
- Git config értékek redaktálva a leltárban.
- Jelszavak, SSH kulcsok, Keychain tartalom **soha** nem másolódik automatikusan.

## GYIK

### Nincs Agent Platform hozzáférésem

```bash
./mac-migration analyze --fallback --interactive
./mac-migration plan
```

### Mennyi ideig tart az A fázis?

A home méretétől függ. Nagy `~/Library` esetén 10–30 perc; 100 mappánként progress.

### Hova kerül a kimenet?

Minden a `~/migration-inventory/` alá — nem kerül gitbe.

## Fejlesztés

```bash
pytest collector/tests/ analyzer/tests/ planner/tests/ restorer/tests/ -q
shellcheck collector/*.sh mac-migration
```

## Licenc

[CloudMentor Use License](LICENSE) — díjmentes használat (kereskedelmi is),
**változatlan** másolat továbbadása engedélyezett. **Módosítás csak CloudMentor írásos engedélyével**
([info@cloudmentor.hu](mailto:info@cloudmentor.hu)). Magyar összefoglaló: [LICENSE_HU.md](LICENSE_HU.md).
