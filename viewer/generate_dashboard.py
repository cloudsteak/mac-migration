#!/usr/bin/env python3
"""Generate an interactive HTML dashboard from migration inventory JSON."""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

INVENTORY_DIR = Path.home() / "migration-inventory"
DEFAULT_OUTPUT = INVENTORY_DIR / "dashboard.html"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mac-migration dashboard</title>
<style>
  :root {
    --bg: #f5f5f7;
    --surface: #fff;
    --text: #1d1d1f;
    --muted: #6e6e73;
    --border: #d2d2d7;
    --copy: #248a3d;
    --app: #0066cc;
    --skip: #8e8e93;
    --review: #bf4800;
    --accent: #0071e3;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.45;
  }
  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 1.25rem 1.5rem;
    position: sticky;
    top: 0;
    z-index: 10;
  }
  header h1 { margin: 0 0 .25rem; font-size: 1.35rem; font-weight: 600; }
  header p { margin: 0; color: var(--muted); font-size: .9rem; }
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: .75rem;
    align-items: center;
    margin-top: .85rem;
  }
  .toolbar input[type="search"] {
    flex: 1 1 220px;
    padding: .45rem .65rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: .9rem;
  }
  .toolbar select, .toolbar button {
    padding: .45rem .65rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface);
    font-size: .85rem;
    cursor: pointer;
  }
  .toolbar button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  main { max-width: 1280px; margin: 0 auto; padding: 1.25rem 1.5rem 2rem; }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: .75rem;
    margin-bottom: 1.25rem;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem;
  }
  .card .label { font-size: .78rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
  .card .value { font-size: 1.6rem; font-weight: 600; margin-top: .15rem; }
  .card.copy { border-top: 3px solid var(--copy); }
  .card.app { border-top: 3px solid var(--app); }
  .card.skip { border-top: 3px solid var(--skip); }
  .card.review { border-top: 3px solid var(--review); }
  .bars {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.1rem;
    margin-bottom: 1.25rem;
  }
  .bars h2, .panel h2 { margin: 0 0 .85rem; font-size: 1rem; font-weight: 600; }
  .bar-row { display: flex; align-items: center; gap: .75rem; margin-bottom: .55rem; font-size: .85rem; }
  .bar-label { width: 110px; color: var(--muted); }
  .bar-track { flex: 1; height: 10px; background: #ececee; border-radius: 999px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 999px; }
  .bar-fill.copy { background: var(--copy); }
  .bar-fill.app { background: var(--app); }
  .bar-fill.skip { background: var(--skip); }
  .bar-fill.review { background: var(--review); }
  .bar-size { width: 70px; text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; }
  .tabs { display: flex; flex-wrap: wrap; gap: .45rem; margin-bottom: .85rem; }
  .tabs button {
    padding: .4rem .75rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--surface);
    cursor: pointer;
    font-size: .82rem;
  }
  .tabs button.active { background: var(--text); color: #fff; border-color: var(--text); }
  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.1rem;
    margin-bottom: 1.25rem;
  }
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: .84rem; }
  th, td { padding: .55rem .45rem; border-bottom: 1px solid #ececee; text-align: left; vertical-align: top; }
  th { color: var(--muted); font-weight: 600; cursor: pointer; user-select: none; white-space: nowrap; }
  th:hover { color: var(--text); }
  td.path { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .78rem; word-break: break-all; }
  .badge {
    display: inline-block;
    padding: .12rem .45rem;
    border-radius: 999px;
    font-size: .72rem;
    font-weight: 600;
    color: #fff;
  }
  .badge.user_custom { background: var(--copy); }
  .badge.app_data { background: var(--app); }
  .badge.cache_or_temp { background: var(--skip); }
  .badge.uncertain { background: var(--review); }
  .checklist label {
    display: flex;
    gap: .65rem;
    align-items: flex-start;
    padding: .45rem 0;
    border-bottom: 1px solid #ececee;
    font-size: .86rem;
  }
  .checklist input { margin-top: .2rem; }
  .checklist .done { opacity: .55; text-decoration: line-through; }
  .inventory-links { display: grid; gap: .45rem; }
  .inventory-links a {
    color: var(--accent);
    text-decoration: none;
    font-size: .88rem;
  }
  .inventory-links a:hover { text-decoration: underline; }
  .empty { color: var(--muted); font-size: .88rem; padding: .5rem 0; }
  .hidden { display: none !important; }
  footer { text-align: center; color: var(--muted); font-size: .78rem; padding: 1rem; }
</style>
</head>
<body>
<header>
  <h1>mac-migration dashboard</h1>
  <p id="meta"></p>
  <div class="toolbar">
    <input type="search" id="search" placeholder="Filter by path or reason…">
    <select id="lang">
      <option value="en">Reasons: English</option>
      <option value="hu">Reasons: Hungarian</option>
    </select>
    <button type="button" id="reset-checks">Reset checklist</button>
  </div>
</header>
<main>
  <div class="cards" id="cards"></div>
  <div class="bars">
    <h2>Storage by category</h2>
    <div id="size-bars"></div>
  </div>
  <div class="panel">
    <h2>Folders</h2>
    <div class="tabs" id="folder-tabs"></div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th data-sort="category">Category</th>
            <th data-sort="path">Path</th>
            <th data-sort="size_bytes">Size</th>
            <th data-sort="confidence">Confidence</th>
            <th data-sort="reason">Reason</th>
          </tr>
        </thead>
        <tbody id="folder-rows"></tbody>
      </table>
    </div>
    <p class="empty hidden" id="folder-empty">No folders match the current filter.</p>
  </div>
  <div class="panel">
    <h2>Migration checklist</h2>
    <div class="tabs" id="plan-tabs"></div>
    <div class="checklist" id="checklist"></div>
  </div>
  <div class="panel">
    <h2>Inventory reports (Phase A)</h2>
    <div class="inventory-links" id="inventory-links"></div>
  </div>
</main>
<footer>Generated by mac-migration viewer — checklist progress saved in this browser only.</footer>
<script>
const DATA = __DATA__;
const STORAGE_KEY = "mac-migration-checklist-v1";

const CATEGORY_LABELS = {
  user_custom: "Copy",
  app_data: "App data",
  cache_or_temp: "Skip",
  uncertain: "Review",
};

const PLAN_SECTIONS = [
  { key: "copy", label: "Copy 1:1", category: "user_custom" },
  { key: "skip", label: "Skip", category: "cache_or_temp" },
  { key: "review", label: "Manual review", category: "uncertain" },
  { key: "app_data", label: "App data", category: "app_data" },
];

let folderFilter = "all";
let planFilter = "copy";
let sortKey = "size_bytes";
let sortAsc = false;
let lang = "en";

function fmtBytes(n) {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i ? 1 : 0)} ${units[i]}`;
}

function reason(item) {
  return lang === "hu" ? (item.reason_hu || item.reason_en || "") : (item.reason_en || item.reason_hu || "");
}

function results() {
  return DATA.analysis.results || [];
}

function loadChecks() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); }
  catch { return {}; }
}

function saveChecks(state) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function renderMeta() {
  const a = DATA.analysis;
  const c = DATA.collector || {};
  const parts = [
    c.generated_at ? `Collected: ${c.generated_at}` : null,
    c.folder_count ? `${c.folder_count} folders profiled` : null,
    a.mode ? `Analysis: ${a.mode}` : null,
    a.model ? `Model: ${a.model}` : null,
    a.project ? `Project: ${a.project}` : null,
  ].filter(Boolean);
  document.getElementById("meta").textContent = parts.join(" · ");
}

function renderCards() {
  const counts = DATA.plan.counts || {};
  const cards = [
    { cls: "copy", label: "Copy", value: counts.copy ?? 0 },
    { cls: "app", label: "App data", value: counts.app ?? 0 },
    { cls: "skip", label: "Skip", value: counts.skip ?? 0 },
    { cls: "review", label: "Review", value: counts.review ?? 0 },
  ];
  document.getElementById("cards").innerHTML = cards.map(c => `
    <div class="card ${c.cls}">
      <div class="label">${c.label}</div>
      <div class="value">${c.value}</div>
    </div>
  `).join("");
}

function renderBars() {
  const totals = { user_custom: 0, app_data: 0, cache_or_temp: 0, uncertain: 0 };
  for (const r of results()) {
    const cat = r.category || "uncertain";
    totals[cat] = (totals[cat] || 0) + (r.size_bytes || 0);
  }
  const max = Math.max(...Object.values(totals), 1);
  document.getElementById("size-bars").innerHTML = Object.entries(totals).map(([cat, bytes]) => {
    const cls = cat === "cache_or_temp" ? "skip" : cat === "user_custom" ? "copy" : cat === "app_data" ? "app" : "review";
    const pct = Math.max(2, (bytes / max) * 100);
    return `<div class="bar-row">
      <div class="bar-label">${CATEGORY_LABELS[cat] || cat}</div>
      <div class="bar-track"><div class="bar-fill ${cls}" style="width:${pct}%"></div></div>
      <div class="bar-size">${fmtBytes(bytes)}</div>
    </div>`;
  }).join("");
}

function filteredFolders() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  return results().filter(r => {
    if (folderFilter !== "all" && r.category !== folderFilter) return false;
    if (!q) return true;
    const hay = [r.path, r.category, reason(r), r.size_human].join(" ").toLowerCase();
    return hay.includes(q);
  });
}

function renderFolderTabs() {
  const tabs = [{ id: "all", label: "All" }, ...Object.entries(CATEGORY_LABELS).map(([id, label]) => ({ id, label }))];
  document.getElementById("folder-tabs").innerHTML = tabs.map(t => `
    <button type="button" data-folder-tab="${t.id}" class="${folderFilter === t.id ? "active" : ""}">${t.label}</button>
  `).join("");
}

function renderFolderRows() {
  let rows = filteredFolders().slice();
  rows.sort((a, b) => {
    let av = a[sortKey];
    let bv = b[sortKey];
    if (sortKey === "reason") { av = reason(a); bv = reason(b); }
    if (typeof av === "string") av = av.toLowerCase();
    if (typeof bv === "string") bv = bv.toLowerCase();
    if (av === bv) return 0;
    return (av < bv ? -1 : 1) * (sortAsc ? 1 : -1);
  });

  const tbody = document.getElementById("folder-rows");
  const empty = document.getElementById("folder-empty");
  if (!rows.length) {
    tbody.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td><span class="badge ${r.category}">${CATEGORY_LABELS[r.category] || r.category}</span></td>
      <td class="path">${r.path || ""}</td>
      <td>${r.size_human || fmtBytes(r.size_bytes || 0)}</td>
      <td>${r.confidence ?? ""}</td>
      <td>${reason(r)}</td>
    </tr>
  `).join("");
}

function checklistId(section, item) {
  return `${section}:${item.path || item.name || item}`;
}

function renderPlanTabs() {
  document.getElementById("plan-tabs").innerHTML = PLAN_SECTIONS.map(s => `
    <button type="button" data-plan-tab="${s.key}" class="${planFilter === s.key ? "active" : ""}">${s.label}</button>
  `).join("");
}

function renderChecklist() {
  const checks = loadChecks();
  const section = PLAN_SECTIONS.find(s => s.key === planFilter);
  const items = (DATA.plan.sections && DATA.plan.sections[section.key]) || [];
  const container = document.getElementById("checklist");

  if (!items.length) {
    container.innerHTML = '<p class="empty">No items in this section.</p>';
    return;
  }

  container.innerHTML = items.map(item => {
    const id = checklistId(section.key, item);
    const checked = !!checks[id];
    const label = item.path
      ? `${item.path} (${item.size_human || fmtBytes(item.size_bytes || 0)}) — ${reason(item)}`
      : String(item);
    return `<label class="${checked ? "done" : ""}">
      <input type="checkbox" data-check-id="${id}" ${checked ? "checked" : ""}>
      <span>${label}</span>
    </label>`;
  }).join("");

  container.querySelectorAll("input[type=checkbox]").forEach(el => {
    el.addEventListener("change", () => {
      const state = loadChecks();
      state[el.dataset.checkId] = el.checked;
      saveChecks(state);
      el.closest("label").classList.toggle("done", el.checked);
    });
  });
}

function renderInventoryLinks() {
  const files = DATA.inventory_files || [];
  document.getElementById("inventory-links").innerHTML = files.length
    ? files.map(f => `<a href="${f}" target="_blank" rel="noopener">${f}</a>`).join("")
    : '<p class="empty">No inventory markdown files found.</p>';
}

function bindEvents() {
  document.getElementById("search").addEventListener("input", renderFolderRows);
  document.getElementById("lang").addEventListener("change", e => {
    lang = e.target.value;
    renderFolderRows();
    renderChecklist();
  });
  document.getElementById("reset-checks").addEventListener("click", () => {
    if (confirm("Clear all checklist progress in this browser?")) {
      localStorage.removeItem(STORAGE_KEY);
      renderChecklist();
    }
  });
  document.getElementById("folder-tabs").addEventListener("click", e => {
    const btn = e.target.closest("[data-folder-tab]");
    if (!btn) return;
    folderFilter = btn.dataset.folderTab;
    renderFolderTabs();
    renderFolderRows();
  });
  document.getElementById("plan-tabs").addEventListener("click", e => {
    const btn = e.target.closest("[data-plan-tab]");
    if (!btn) return;
    planFilter = btn.dataset.planTab;
    renderPlanTabs();
    renderChecklist();
  });
  document.querySelectorAll("th[data-sort]").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (sortKey === key) sortAsc = !sortAsc;
      else { sortKey = key; sortAsc = key === "path" || key === "reason"; }
      renderFolderRows();
    });
  });
}

renderMeta();
renderCards();
renderBars();
renderFolderTabs();
renderFolderRows();
renderPlanTabs();
renderChecklist();
renderInventoryLinks();
bindEvents();
</script>
</body>
</html>
"""


def load_payload(inventory_dir: Path) -> dict:
    analysis_path = inventory_dir / "analysis-report.json"
    plan_path = inventory_dir / "migration-plan.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"analysis JSON not found: {analysis_path}")
    if not plan_path.exists():
        raise FileNotFoundError(f"plan JSON not found: {plan_path}")

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    collector_meta: dict = {}
    collector_path = inventory_dir / "collector-output.json"
    if collector_path.exists():
        collector = json.loads(collector_path.read_text(encoding="utf-8"))
        collector_meta = {
            "generated_at": collector.get("generated_at"),
            "folder_count": collector.get("folder_count"),
            "max_depth": collector.get("max_depth"),
        }

    inventory_files = sorted(
        p.name
        for p in inventory_dir.iterdir()
        if p.is_file() and p.suffix == ".md" and not p.name.endswith("_HU.md")
    )

    return {
        "analysis": analysis,
        "plan": plan,
        "collector": collector_meta,
        "inventory_files": inventory_files,
    }


def generate_dashboard(inventory_dir: Path, output: Path) -> Path:
    payload = load_payload(inventory_dir)
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


def open_in_browser(path: Path) -> None:
    webbrowser.open(path.resolve().as_uri())


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate interactive HTML migration dashboard")
    parser.add_argument(
        "--inventory-dir",
        type=Path,
        default=INVENTORY_DIR,
        help="Directory with collector/analysis/plan output",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output HTML path",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the browser",
    )
    args = parser.parse_args()

    try:
        out = generate_dashboard(args.inventory_dir, args.output)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Run analyze and plan phases first.", file=sys.stderr)
        sys.exit(1)

    print(f"Done: {out}")
    if not args.no_open:
        open_in_browser(out)
        print("Opened in browser.")


if __name__ == "__main__":
    main()
