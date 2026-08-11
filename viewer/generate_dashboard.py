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
  .badge.migrate { background: var(--copy); }
  .badge.reinstall { background: var(--app); }
  .badge.skip { background: var(--skip); }
  .badge.later { background: var(--review); }
  .steps-list { margin: .35rem 0 0 1rem; padding: 0; font-size: .82rem; color: var(--muted); }
  .steps-list li { margin-bottom: .25rem; }
  .paths-list { margin: .25rem 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .76rem; color: var(--muted); }
  .panel.collapsed .table-wrap, .panel.collapsed .tabs { display: none; }
  .panel-toggle { float: right; font-size: .78rem; color: var(--accent); cursor: pointer; border: none; background: none; }
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
  .group-card {
    border: 1px solid #e4e4e8;
    border-radius: 10px;
    margin-bottom: .75rem;
    overflow: hidden;
    background: #fff;
  }
  .group-head {
    display: flex;
    align-items: center;
    gap: .65rem;
    padding: .75rem 1rem;
    cursor: pointer;
    user-select: none;
    background: #fafafa;
  }
  .group-head:hover { background: #f3f3f6; }
  .group-head h3 { margin: 0; font-size: 1rem; flex: 1; }
  .group-meta { font-size: .78rem; color: var(--muted); }
  .group-body { padding: 0 1rem .85rem 1rem; display: none; }
  .group-card.open .group-body { display: block; }
  .group-parent {
    font-size: .86rem;
    margin: .65rem 0 .45rem;
    color: var(--text);
  }
  .group-children { margin: 0; padding-left: 1.1rem; font-size: .84rem; }
  .group-children li { margin-bottom: .35rem; }
  .group-step { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .76rem; color: var(--muted); }
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
    <h2 id="bars-title">Storage by category</h2>
    <div id="size-bars"></div>
  </div>
  <div class="panel" id="groups-panel">
    <h2>Install groups <span id="groups-count" style="font-weight:400;color:var(--muted);font-size:.85rem"></span></h2>
    <p class="empty" id="groups-intro" style="margin-top:0">Grouped view — Homebrew packages, DAW plugins, editor extensions.</p>
    <div id="install-groups"></div>
    <p class="empty hidden" id="groups-empty">No install groups match the current filter.</p>
  </div>
  <div class="panel" id="components-panel">
    <h2>Components <span id="components-count" style="font-weight:400;color:var(--muted);font-size:.85rem"></span></h2>
    <div class="tabs" id="component-tabs"></div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th data-sort-comp="decision">Decision</th>
            <th data-sort-comp="component_name">Component</th>
            <th data-sort-comp="type">Type</th>
            <th>Related paths</th>
            <th>Install / migration steps</th>
          </tr>
        </thead>
        <tbody id="component-rows"></tbody>
      </table>
    </div>
    <p class="empty hidden" id="component-empty">No components match the current filter.</p>
  </div>
  <div class="panel collapsed" id="folders-panel">
    <h2>Folders <button type="button" class="panel-toggle" id="folders-toggle">Show details</button></h2>
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

const INTERACTIVE_SECTIONS = [
  { key: "migrate", label: "Migrate" },
  { key: "reinstall", label: "Reinstall" },
  { key: "skip", label: "Skip" },
  { key: "later", label: "Later" },
];

const DECISION_LABELS = {
  migrate: "Migrate",
  reinstall: "Reinstall",
  skip: "Skip",
  later: "Later",
};

let folderFilter = "all";
let componentFilter = "all";
let planFilter = "migrate";
let sortKey = "size_bytes";
let sortCompKey = "component_name";
let sortAsc = false;
let sortCompAsc = true;
let lang = "en";

function isInteractiveMode() {
  return DATA.analysis.mode === "interactive_report"
    || DATA.plan.mode === "interactive_components"
    || !!(DATA.analysis.components_en && DATA.analysis.components_en.length);
}

function isNoisePath(path) {
  if (!path) return true;
  return path.includes(".app/Contents/") || path.includes("/node_modules/");
}

function installGroups() {
  const key = lang === "hu" ? "install_groups_hu" : "install_groups_en";
  return DATA.analysis[key] || DATA.analysis.install_groups_en || DATA.plan.install_groups || [];
}

function filteredInstallGroups() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  return installGroups().filter(g => {
    if (!q) return true;
    const parent = g.parent ? [g.parent.name, g.parent.decision, g.parent.install_step].join(" ") : "";
    const children = (g.children || []).map(c => [c.name, c.decision, c.install_step, c.path].join(" ")).join(" ");
    const hay = [g.group_name, g.group_type, parent, children, (g.group_steps || []).join(" ")].join(" ").toLowerCase();
    return hay.includes(q);
  });
}

function renderInstallGroups() {
  const panel = document.getElementById("groups-panel");
  if (!isInteractiveMode()) {
    panel.style.display = "none";
    return;
  }
  panel.style.display = "";
  const groups = filteredInstallGroups();
  document.getElementById("groups-count").textContent = `(${installGroups().length} groups)`;
  const root = document.getElementById("install-groups");
  const empty = document.getElementById("groups-empty");
  if (!groups.length) {
    root.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  root.innerHTML = groups.map((g, idx) => {
    const summary = Object.entries(g.decision_summary || {})
      .filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`).join(" · ");
    const steps = (g.group_steps || []).map(s => `<div class="group-step">${s}</div>`).join("");
    const parent = g.parent
      ? `<div class="group-parent"><strong>Main:</strong> ${g.parent.name} <span class="badge ${g.parent.decision}">${DECISION_LABELS[g.parent.decision] || g.parent.decision}</span></div>`
      : "";
    const children = (g.children || []).map(c => {
      const step = c.install_step || c.path || "";
      const stepHtml = step ? `<span class="group-step"> — ${step}</span>` : "";
      return `<li><strong>${c.name}</strong> <span class="badge ${c.decision}">${DECISION_LABELS[c.decision] || c.decision}</span>${stepHtml}</li>`;
    }).join("");
    return `<div class="group-card ${idx === 0 ? "open" : ""}" data-group-idx="${idx}">
      <div class="group-head" data-group-toggle="${idx}">
        <h3>${g.group_name || "?"}</h3>
        <span class="group-meta">${summary || g.group_type || ""}</span>
      </div>
      <div class="group-body">
        ${steps}
        ${parent}
        <ul class="group-children">${children}</ul>
      </div>
    </div>`;
  }).join("");
  root.querySelectorAll("[data-group-toggle]").forEach(el => {
    el.addEventListener("click", () => {
      el.closest(".group-card")?.classList.toggle("open");
    });
  });
}

function components() {
  const key = lang === "hu" ? "components_hu" : "components_en";
  return DATA.analysis[key] || DATA.analysis.components_en || [];
}

function planSections() {
  return isInteractiveMode() ? INTERACTIVE_SECTIONS : PLAN_SECTIONS;
}

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
  const all = DATA.analysis.results || [];
  if (isInteractiveMode()) {
    return all.filter(r => !isNoisePath(r.path));
  }
  return all;
}

function componentSteps(comp) {
  const key = lang === "hu" ? "install_steps" : "install_steps";
  return comp[key] || comp.install_steps || [];
}

function componentSummary(comp) {
  if (lang === "hu") return comp.summary || "";
  return comp.summary || "";
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
  let cards;
  if (isInteractiveMode()) {
    const counts = DATA.plan.counts || DATA.analysis.summary || {};
    cards = [
      { cls: "copy", label: "Migrate", value: counts.migrate ?? counts.copy ?? 0 },
      { cls: "app", label: "Reinstall", value: counts.reinstall ?? counts.app ?? 0 },
      { cls: "skip", label: "Skip", value: counts.skip ?? 0 },
      { cls: "review", label: "Later", value: counts.later ?? counts.review ?? 0 },
    ];
  } else {
    const counts = DATA.plan.counts || {};
    cards = [
      { cls: "copy", label: "Copy", value: counts.copy ?? 0 },
      { cls: "app", label: "App data", value: counts.app ?? 0 },
      { cls: "skip", label: "Skip", value: counts.skip ?? 0 },
      { cls: "review", label: "Review", value: counts.review ?? 0 },
    ];
  }
  document.getElementById("cards").innerHTML = cards.map(c => `
    <div class="card ${c.cls}">
      <div class="label">${c.label}</div>
      <div class="value">${c.value}</div>
    </div>
  `).join("");
}

function renderBars() {
  if (isInteractiveMode()) {
    const summary = DATA.analysis.summary || DATA.plan.counts || {};
    const rows = [
      { cls: "copy", label: "Migrate", bytes: summary.migrate ?? summary.copy ?? 0, count: true },
      { cls: "app", label: "Reinstall", bytes: summary.reinstall ?? summary.app ?? 0, count: true },
      { cls: "skip", label: "Skip", bytes: summary.skip ?? 0, count: true },
      { cls: "review", label: "Later", bytes: summary.later ?? summary.review ?? 0, count: true },
    ];
    const max = Math.max(...rows.map(r => r.bytes), 1);
    const barsTitle = document.getElementById("bars-title");
    if (barsTitle) barsTitle.textContent = "Components by decision";
    document.getElementById("size-bars").innerHTML = rows.map(r => {
      const pct = Math.max(2, (r.bytes / max) * 100);
      const val = r.count ? `${r.bytes} items` : fmtBytes(r.bytes);
      return `<div class="bar-row">
        <div class="bar-label">${r.label}</div>
        <div class="bar-track"><div class="bar-fill ${r.cls}" style="width:${pct}%"></div></div>
        <div class="bar-size">${val}</div>
      </div>`;
    }).join("");
    return;
  }
  const totals = { user_custom: 0, app_data: 0, cache_or_temp: 0, uncertain: 0 };
  for (const r of results()) {
    const cat = r.category || "uncertain";
    totals[cat] = (totals[cat] || 0) + (r.size_bytes || 0);
  }
  const max = Math.max(...Object.values(totals), 1);
  const barsTitle = document.getElementById("bars-title");
  if (barsTitle) {
    barsTitle.textContent = isInteractiveMode()
      ? "Storage by folder category (filtered — no .app/Contents noise)"
      : "Storage by category";
  }
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

function filteredComponents() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  return components().filter(c => {
    if (componentFilter !== "all" && c.decision !== componentFilter) return false;
    if (!q) return true;
    const paths = (c.related_paths || []).map(p => p.path).join(" ");
    const steps = componentSteps(c).join(" ");
    const hay = [c.component_name, c.type, c.decision, paths, steps, componentSummary(c)].join(" ").toLowerCase();
    return hay.includes(q);
  });
}

function renderComponentTabs() {
  const panel = document.getElementById("components-panel");
  if (!isInteractiveMode()) {
    panel.style.display = "none";
    return;
  }
  panel.style.display = "";
  const tabs = [{ id: "all", label: "All" }, ...INTERACTIVE_SECTIONS.map(s => ({ id: s.key, label: s.label }))];
  document.getElementById("component-tabs").innerHTML = tabs.map(t => `
    <button type="button" data-component-tab="${t.id}" class="${componentFilter === t.id ? "active" : ""}">${t.label}</button>
  `).join("");
  document.getElementById("components-count").textContent = `(${components().length} items)`;
}

function renderComponentRows() {
  if (!isInteractiveMode()) return;
  let rows = filteredComponents().slice();
  rows.sort((a, b) => {
    let av = a[sortCompKey];
    let bv = b[sortCompKey];
    if (typeof av === "string") av = av.toLowerCase();
    if (typeof bv === "string") bv = bv.toLowerCase();
    if (av === bv) return 0;
    return (av < bv ? -1 : 1) * (sortCompAsc ? 1 : -1);
  });

  const tbody = document.getElementById("component-rows");
  const empty = document.getElementById("component-empty");
  if (!rows.length) {
    tbody.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  tbody.innerHTML = rows.map(c => {
    const paths = (c.related_paths || []).slice(0, 6).map(p =>
      `<div class="paths-list">${p.path || ""} <span>(${p.size_human || "?"})</span></div>`
    ).join("");
    const morePaths = (c.related_paths || []).length > 6
      ? `<div class="paths-list">… +${c.related_paths.length - 6} more</div>` : "";
    const steps = componentSteps(c).slice(0, 5).map(s => `<li>${s}</li>`).join("");
    const moreSteps = componentSteps(c).length > 5
      ? `<li>… +${componentSteps(c).length - 5} more</li>` : "";
    return `<tr>
      <td><span class="badge ${c.decision}">${DECISION_LABELS[c.decision] || c.decision}</span></td>
      <td><strong>${c.component_name || ""}</strong></td>
      <td>${c.type || ""}</td>
      <td>${paths}${morePaths}</td>
      <td><ol class="steps-list">${steps}${moreSteps}</ol></td>
    </tr>`;
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
  if (item.component_id) return `${section}:${item.component_id}`;
  return `${section}:${item.path || item.component_name || item.name || item}`;
}

function renderPlanTabs() {
  document.getElementById("plan-tabs").innerHTML = planSections().map(s => `
    <button type="button" data-plan-tab="${s.key}" class="${planFilter === s.key ? "active" : ""}">${s.label}</button>
  `).join("");
}

function renderChecklist() {
  const checks = loadChecks();
  const section = planSections().find(s => s.key === planFilter);
  if (!section) {
    document.getElementById("checklist").innerHTML = '<p class="empty">No items in this section.</p>';
    return;
  }
  const items = (DATA.plan.sections && DATA.plan.sections[section.key]) || [];
  const container = document.getElementById("checklist");

  if (!items.length) {
    container.innerHTML = '<p class="empty">No items in this section.</p>';
    return;
  }

  container.innerHTML = items.map(item => {
    const id = checklistId(section.key, item);
    const checked = !!checks[id];
    let label;
    if (item.component_name) {
      const steps = (item.install_steps || []).slice(0, 2).join(" · ");
      const paths = (item.related_paths || []).slice(0, 2).map(p => p.path).join(", ");
      label = `<strong>${item.component_name}</strong> (${item.type || "?"})`;
      if (paths) label += `<br><span class="paths-list">${paths}</span>`;
      if (steps) label += `<br><span class="paths-list">${steps}</span>`;
    } else if (item.path) {
      label = `${item.path} (${item.size_human || fmtBytes(item.size_bytes || 0)}) — ${reason(item)}`;
    } else {
      label = String(item);
    }
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
  document.getElementById("search").addEventListener("input", () => {
    renderInstallGroups();
    renderFolderRows();
    renderComponentRows();
  });
  document.getElementById("lang").addEventListener("change", e => {
    lang = e.target.value;
    renderInstallGroups();
    renderFolderRows();
    renderComponentRows();
    renderChecklist();
  });
  document.getElementById("reset-checks").addEventListener("click", () => {
    if (confirm("Clear all checklist progress in this browser?")) {
      localStorage.removeItem(STORAGE_KEY);
      renderChecklist();
    }
  });
  document.getElementById("folders-toggle").addEventListener("click", () => {
    const panel = document.getElementById("folders-panel");
    const btn = document.getElementById("folders-toggle");
    panel.classList.toggle("collapsed");
    btn.textContent = panel.classList.contains("collapsed") ? "Show details" : "Hide details";
  });
  document.getElementById("component-tabs").addEventListener("click", e => {
    const btn = e.target.closest("[data-component-tab]");
    if (!btn) return;
    componentFilter = btn.dataset.componentTab;
    renderComponentTabs();
    renderComponentRows();
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
  document.querySelectorAll("th[data-sort-comp]").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.sortComp;
      if (sortCompKey === key) sortCompAsc = !sortCompAsc;
      else { sortCompKey = key; sortCompAsc = key === "component_name"; }
      renderComponentRows();
    });
  });
}

if (isInteractiveMode()) {
  planFilter = "migrate";
}

renderMeta();
renderCards();
renderBars();
renderInstallGroups();
renderComponentTabs();
renderComponentRows();
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


def slim_component(comp: dict) -> dict:
    name = comp.get("component_name") or ""
    if comp.get("type") in ("homebrew_formula", "homebrew_cask"):
        brew_names = {
            "awscli": "AWS CLI",
            "gcloud-cli": "Google Cloud CLI",
            "azure-cli": "Azure CLI",
        }
        name = brew_names.get(name, name)
    return {
        "component_id": comp.get("component_id"),
        "component_name": name,
        "type": comp.get("type"),
        "decision": comp.get("decision"),
        "related_paths": comp.get("related_paths") or [],
        "install_steps": comp.get("install_steps") or [],
        "summary": comp.get("summary") or "",
    }


def slim_install_group(group: dict) -> dict:
    def slim_child(c: dict) -> dict:
        return {
            k: c[k]
            for k in ("component_id", "name", "type", "decision", "install_step", "path", "source")
            if k in c
        }

    out = {
        k: group[k]
        for k in ("group_id", "group_name", "group_type", "decision_summary", "group_steps")
        if k in group
    }
    if group.get("parent"):
        out["parent"] = slim_child(group["parent"])
    out["children"] = [slim_child(c) for c in (group.get("children") or [])]
    return out


def slim_payload_for_dashboard(payload: dict) -> dict:
    """Keep dashboard HTML small — interactive mode uses components, not 2000+ folder rows."""
    analysis = dict(payload.get("analysis") or {})
    plan = dict(payload.get("plan") or {})
    if analysis.get("mode") == "interactive_report" or plan.get("mode") == "interactive_components":
        slim_analysis = {
            k: analysis[k]
            for k in (
                "mode",
                "model",
                "project",
                "summary",
                "component_count",
                "result_count",
                "generated_by",
                "decisions_file",
            )
            if k in analysis
        }
        slim_analysis["components_en"] = [
            slim_component(c) for c in (analysis.get("components_en") or [])
        ]
        slim_analysis["components_hu"] = [
            slim_component(c) for c in (analysis.get("components_hu") or [])
        ]
        slim_analysis["install_groups_en"] = [
            slim_install_group(g) for g in (analysis.get("install_groups_en") or [])
        ]
        slim_analysis["install_groups_hu"] = [
            slim_install_group(g) for g in (analysis.get("install_groups_hu") or [])
        ]
        slim_plan = {
            "mode": plan.get("mode"),
            "counts": plan.get("counts") or {},
            "sections": {
                key: [slim_component(c) for c in (items or [])]
                for key, items in (plan.get("sections") or {}).items()
            },
            "install_groups": [
                slim_install_group(g) for g in (plan.get("install_groups") or [])
            ],
        }
        return {
            **payload,
            "analysis": slim_analysis,
            "plan": slim_plan,
        }
    return payload


def generate_dashboard(inventory_dir: Path, output: Path) -> Path:
    payload = slim_payload_for_dashboard(load_payload(inventory_dir))
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
