> **Nyelv / Language:** [English](README.md) | Magyar

MAC Migrációs Eszköz

Háromfázisú CLI eszköz tudatos macOS gép-migrációhoz (pl. M1 → új M-series Mac).
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
| **A — Collect** | `collector/*.sh` | `~/migration-inventory/` (Markdown + JSON, en + hu) |
| **B — Analyze** | `analyzer/analyze.py` | `analysis-report.md` + `analysis-report_HU.md` (+ JSON) |
| **C — Plan** | `planner/generate-plan.py` | `migration-plan.md` + `migration-plan_HU.md` (+ JSON) |

Minden felhasználói adat **lokálisan** marad a `~/migration-inventory/` alatt. Csak mappa
metaadat (útvonal, méret, kiterjesztés-statisztika — soha fájltartalom vagy credential)
kerül az Agent Platformra.

## Előfeltételek

- macOS (forrás gép)
- **Homebrew** (ajánlott, collectorhez nem kötelező)
- **Python 3.11+**
- **gcloud CLI** (csak B fázishoz, Agent Platform)
- GCP projekt Enterprise Agent Platform API-val

### ADC beállítás (Agent Platform)

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Nincs API kulcs — csak Application Default Credentials (ADC).

## Gyors indulás

```bash
git clone <repo-url> mac-migration
cd mac-migration
chmod +x mac-migration

# Python függőségek (egyszer)
pip install -r analyzer/requirements.txt

# Teljes folyamat (kétnyelvű riportok; angol konzol)
./mac-migration all --project YOUR_PROJECT_ID

# Magyar konzolüzenetek
./mac-migration all --project YOUR_PROJECT_ID --lang hu

# Agent Platform nélkül (fallback)
./mac-migration all --fallback
```

### Lépésről lépésre

```bash
# A fázis — leltár + mappa-profiler (nagy home-nál percek)
./mac-migration collect

# B fázis — LLM kategorizálás
./mac-migration analyze --project YOUR_PROJECT_ID

# C fázis — checklist
./mac-migration plan
```

## Konfiguráció

Minden **CLI flag**-gel állítható (nincs hardcoded project ID):

| Flag | Alapértelmezés | Leírás |
|------|----------------|--------|
| `--project` | _(kötelező)_ | GCP project ID |
| `--model` | `gemini-3.5-flash-lite` | Globális Gemini modell |
| `--location` | `global` | Agent Platform location |
| `--lang` | `en` | Konzol nyelve (`en`/`hu`); riportok mindig kétnyelvűek |
| `--batch-size` | `30` | Mappák API hívásonként |
| `--min-size-mb` | `100` | Ennél kisebb mappák kihagyása |
| `--fallback` | ki | Szabály alapú elemzés, felhő nélkül |

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

- Érzékeny mappák (`.ssh`, `.gnupg`, `.aws`, `.kube`, `.config/gcloud` stb.)
  **ki vannak zárva** a profilozásból JSON export előtt.
- Auth szekció: csak létezés/darabszám — secret tartalom nem kerül ki.
- Git config értékek redaktálva a leltárban.

## GYIK

### Nincs Agent Platform hozzáférésem

Használd a `--fallback` kapcsolót. Kevesebb pontosság szokatlan mappaneveknél,
de a gyűjtés után teljesen offline:

```bash
./mac-migration analyze --fallback
./mac-migration plan
```

### Mennyi ideig tart az A fázis?

A home méretétől függ. Nagy `~/Library` esetén több perc; 100 mappánként progress.

### Hova kerül a kimenet?

Minden a `~/migration-inventory/` alá — nem kerül gitbe.

### Melyik modell és régió?

Alapértelmezés: `gemini-3.5-flash-lite` @ `global`.

## Fejlesztés

```bash
pytest analyzer/tests/ -v
shellcheck collector/*.sh mac-migration
```

## Licenc

[CloudMentor Use License](LICENSE) — díjmentes használat (kereskedelmi is),
**változatlan** másolat továbbadása engedélyezett. **Módosítás csak CloudMentor írásos engedélyével**
([info@cloudmentor.hu](mailto:info@cloudmentor.hu)). Magyar összefoglaló: [LICENSE_HU.md](LICENSE_HU.md).
