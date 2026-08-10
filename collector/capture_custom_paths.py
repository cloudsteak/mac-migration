#!/usr/bin/env python3
"""Discover custom user paths — directories/files not part of stock macOS layout."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()

# Default top-level entries on a fresh macOS user home (approximate)
MACOS_HOME_DEFAULTS = frozenset(
    {
        "Desktop",
        "Documents",
        "Downloads",
        "Library",
        "Movies",
        "Music",
        "Pictures",
        "Public",
        "Applications",
        ".Trash",
        ".Trashes",
        ".DS_Store",
        ".CFUserTextEncoding",
        ".localized",
    }
)

# Apple-shipped ~/Library subfolders (common on stock macOS)
MACOS_LIBRARY_DEFAULTS = frozenset(
    {
        "Accessibility",
        "Accounts",
        "AppleMediaServices",
        "Application Scripts",
        "Application Support",
        "Assistant",
        "Audio",
        "Autosave Information",
        "Biome",
        "Caches",
        "Calendars",
        "CallServices",
        "CloudStorage",
        "ColorPickers",
        "Colors",
        "Compositions",
        "Contacts",
        "ContainerManager",
        "Containers",
        "Cookies",
        "CoreFollowUp",
        "Daemon Containers",
        "DataDeliveryServices",
        "DoNotDisturb",
        "DuetExpertCenter",
        "Favorites",
        "Finance",
        "FontCollections",
        "Fonts",
        "FrontBoard",
        "GameKit",
        "Group Containers",
        "HomeKit",
        "HTTPStorages",
        "IdentityServices",
        "Input Methods",
        "IntelligencePlatform",
        "Internet Plug-Ins",
        "Keyboard",
        "Keyboard Layouts",
        "KeyboardServices",
        "Keychains",
        "LanguageModeling",
        "LaunchAgents",
        "LockdownMode",
        "Logs",
        "Mail",
        "Maps",
        "Messages",
        "Metadata",
        "Mobile Documents",
        "News",
        "Passes",
        "PersonalizationPortrait",
        "Photos",
        "PreferencePanes",
        "Preferences",
        "Printers",
        "PrivateCloudCompute",
        "Reminders",
        "Safari",
        "SafariSafeBrowsing",
        "SafariSandboxBroker",
        "Saved Application State",
        "Sharing",
        "Shortcuts",
        "Sounds",
        "Speech",
        "Spelling",
        "Spotlight",
        "StatusKit",
        "Suggestions",
        "SyncedPreferences",
        "Translation",
        "Trial",
        "UnifiedAssetFramework",
        "Weather",
        "WebKit",
        "com.apple.appleaccountd",
        "com.apple.bluetooth.services.cloud",
        "com.apple.iTunesCloud",
        "homeenergyd",
        "MediaAnalysis",
        "Staging",
        "Stickers",
        "Stickers/tmp",
    }
)

# Known Apple apps in /Applications (partial — user apps are "custom")
APPLE_SYSTEM_APPS = frozenset(
    {
        "App Store.app",
        "Automator.app",
        "Books.app",
        "Calculator.app",
        "Calendar.app",
        "Chess.app",
        "Clock.app",
        "Contacts.app",
        "Dictionary.app",
        "FaceTime.app",
        "FindMy.app",
        "Font Book.app",
        "Freeform.app",
        "Home.app",
        "Image Capture.app",
        "Launchpad.app",
        "Mail.app",
        "Maps.app",
        "Messages.app",
        "Mission Control.app",
        "Music.app",
        "News.app",
        "Notes.app",
        "Passwords.app",
        "Photo Booth.app",
        "Photos.app",
        "Podcasts.app",
        "Preview.app",
        "QuickTime Player.app",
        "Reminders.app",
        "Safari.app",
        "Shortcuts.app",
        "Siri.app",
        "Stickies.app",
        "Stocks.app",
        "System Settings.app",
        "TextEdit.app",
        "Time Machine.app",
        "Tips.app",
        "TV.app",
        "Utilities",
        "VoiceMemos.app",
        "Weather.app",
        "iPhone Mirroring.app",
    }
)

CUSTOM_SCAN_ROOTS = (
    HOME,
    HOME / "Library",
    HOME / "Applications",
    Path("/Applications"),
    Path("/opt/homebrew"),
    Path("/usr/local"),
    Path("/Users/Shared"),
)


def run_du(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        r = subprocess.run(
            ["/usr/bin/du", "-sh", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return r.stdout.split()[0] if r.stdout else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def classify_home_entry(entry: Path) -> str | None:
    name = entry.name
    if name in MACOS_HOME_DEFAULTS:
        return None
    if name.startswith(".") and name in {".Trash", ".Trashes", ".DS_Store"}:
        return None
    kind = "home_dotdir" if name.startswith(".") else "home_dir"
    if name.startswith(".") and kind == "home_dotdir":
        kind = "home_dotdir"
    elif entry.is_file() and name.startswith("."):
        kind = "home_dotfile"
    return kind


def classify_library_entry(entry: Path) -> str | None:
    if entry.name in MACOS_LIBRARY_DEFAULTS:
        return None
    return "library_custom"


def classify_applications_entry(entry: Path, root: Path) -> str | None:
    if root != Path("/Applications"):
        return "user_application"
    if entry.name in APPLE_SYSTEM_APPS:
        return None
    if entry.name == "Utilities":
        return None
    return "system_non_apple_app"


def scan_custom_paths() -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()

    def add(path: Path, kind: str, source: str) -> None:
        p = str(path.resolve()) if path.exists() else str(path)
        if p in seen:
            return
        seen.add(p)
        items.append(
            {
                "path": p,
                "name": path.name,
                "kind": kind,
                "source": source,
                "is_dir": path.is_dir(),
                "size_human": run_du(path) if path.is_dir() else "",
            }
        )

    # Home top-level
    try:
        for entry in sorted(HOME.iterdir(), key=lambda p: p.name.lower()):
            kind = classify_home_entry(entry)
            if kind:
                add(entry, kind, "~/")
    except OSError:
        pass

    # ~/Library custom
    lib = HOME / "Library"
    if lib.is_dir():
        try:
            for entry in sorted(lib.iterdir(), key=lambda p: p.name.lower()):
                kind = classify_library_entry(entry)
                if kind:
                    add(entry, kind, "~/Library/")
        except OSError:
            pass

    # Applications
    for root in (Path("/Applications"), HOME / "Applications"):
        if not root.is_dir():
            continue
        try:
            for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
                if entry.suffix == ".app" or entry.name.endswith(".app"):
                    kind = classify_applications_entry(entry, root)
                    if kind:
                        add(entry, kind, str(root))
        except OSError:
            pass

    # /opt/homebrew and /usr/local — entirely custom (non-stock macOS)
    for root in (Path("/opt/homebrew"), Path("/usr/local")):
        if not root.is_dir():
            continue
        add(root, "system_custom_root", str(root))
        try:
            for entry in sorted(root.iterdir(), key=lambda p: p.name.lower())[:100]:
                add(entry, "system_custom_child", str(root))
        except OSError:
            pass

    return items


def load_collector_custom(inventory_dir: Path, existing_paths: set[str]) -> list[dict]:
    """Add profiled folders that look user/custom (not pure Apple cache)."""
    extra: list[dict] = []
    collector = inventory_dir / "collector-output.json"
    if not collector.is_file():
        return extra
    data = json.loads(collector.read_text(encoding="utf-8"))
    home_str = str(HOME)
    skip_fragments = (
        "/Library/Caches/",
        "/.Trash",
        "/Library/Logs/DiagnosticMessages",
    )
    for folder in data.get("folders", []):
        path = folder.get("path", "")
        if not path or path in existing_paths:
            continue
        if not path.startswith(home_str) and not path.startswith("/opt/") and not path.startswith("/usr/local"):
            continue
        if any(frag in path for frag in skip_fragments):
            continue
        rel = path[len(home_str) :].lstrip("/") if path.startswith(home_str) else path
        top = rel.split("/")[0] if rel else ""
        if path.startswith(home_str) and top in MACOS_HOME_DEFAULTS and "/" not in rel:
            continue
        extra.append(
            {
                "path": path,
                "name": Path(path).name,
                "kind": "profiled_folder",
                "source": "collector",
                "is_dir": True,
                "size_human": folder.get("size_human", ""),
                "size_bytes": folder.get("size_bytes", 0),
            }
        )
    return extra


def build_snapshot(inventory_dir: Path) -> dict:
    items = scan_custom_paths()
    seen = {i["path"] for i in items}
    items.extend(load_collector_custom(inventory_dir, seen))

    by_kind: dict[str, list] = {}
    for item in items:
        by_kind.setdefault(item["kind"], []).append(item)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "path_count": len(items),
        "note": "Paths not part of stock macOS default layout (user/custom/third-party).",
        "paths": sorted(items, key=lambda x: (-(x.get("size_bytes") or 0), x.get("path", ""))),
        "by_kind": {k: len(v) for k, v in by_kind.items()},
    }


def render_markdown(data: dict) -> str:
    lines = [
        f"# Custom paths (non-stock macOS) — {data.get('generated_at', '')}",
        "",
        data.get("note", ""),
        "",
        f"**{data.get('path_count', 0)}** custom paths. JSON: `custom-paths.json`.",
        "",
        "## Summary by kind",
        "",
    ]
    for kind, count in sorted((data.get("by_kind") or {}).items()):
        lines.append(f"- `{kind}`: {count}")
    lines.extend(["", "## All custom paths", "", "| Path | Kind | Size |", "|---|---|---|"])
    for item in data.get("paths", [])[:500]:
        size = item.get("size_human", "") or ""
        lines.append(f"| `{item.get('path', '')}` | {item.get('kind', '')} | {size} |")
    if data.get("path_count", 0) > 500:
        lines.append(f"| ... | {data['path_count'] - 500} more in JSON | |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HOME / "migration-inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = build_snapshot(out_dir)
    json_path = out_dir / "custom-paths.json"
    md_path = out_dir / "13-custom-paths.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")
    print(f"==> Custom paths: {json_path} ({data['path_count']} paths)")
    print(f"==> Report: {md_path}")


if __name__ == "__main__":
    main()
