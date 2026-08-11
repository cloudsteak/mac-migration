#!/usr/bin/env python3
"""
Comprehensive system inventory — captures everything migration-relevant in one pass.

Supplements specialized collectors by scanning login items, browsers, VPN, cron,
launch agents, launcher tools, docker, cloud CLI, fonts, printers, and more.
Also aggregates counts from all other inventory JSON files.
"""

from __future__ import annotations

import configparser
import json
import os
import plistlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()

# Chromium-based: each entry = display name, app name(s), user data root
BROWSER_DEFINITIONS: list[dict] = [
    {
        "name": "Google Chrome",
        "apps": ["Google Chrome.app"],
        "data_root": HOME / "Library/Application Support/Google/Chrome",
        "engine": "chromium",
    },
    {
        "name": "Brave",
        "apps": ["Brave Browser.app"],
        "data_root": HOME / "Library/Application Support/BraveSoftware/Brave-Browser",
        "engine": "chromium",
    },
    {
        "name": "Microsoft Edge",
        "apps": ["Microsoft Edge.app"],
        "data_root": HOME / "Library/Application Support/Microsoft Edge",
        "engine": "chromium",
    },
    {
        "name": "Arc",
        "apps": ["Arc.app"],
        "data_root": HOME / "Library/Application Support/Arc/User Data",
        "engine": "chromium",
    },
    {
        "name": "Vivaldi",
        "apps": ["Vivaldi.app"],
        "data_root": HOME / "Library/Application Support/Vivaldi",
        "engine": "chromium",
    },
    {
        "name": "Opera",
        "apps": ["Opera.app"],
        "data_root": HOME / "Library/Application Support/com.operasoftware.Opera",
        "engine": "chromium",
    },
    {
        "name": "Chromium",
        "apps": ["Chromium.app"],
        "data_root": HOME / "Library/Application Support/Chromium",
        "engine": "chromium",
    },
    {
        "name": "Firefox",
        "apps": ["Firefox.app"],
        "data_root": HOME / "Library/Application Support/Firefox",
        "engine": "firefox",
    },
    {
        "name": "Safari",
        "apps": ["Safari.app"],
        "data_root": HOME / "Library/Safari",
        "engine": "safari",
    },
    {
        "name": "Tor Browser",
        "apps": ["Tor Browser.app"],
        "data_root": HOME / "Library/Application Support/TorBrowser-Data",
        "engine": "firefox",
    },
]

APP_SEARCH_ROOTS = (Path("/Applications"), HOME / "Applications")


def run(cmd: list[str], timeout: int = 60) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (r.stdout or r.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def which(name: str) -> str:
    return run(["/usr/bin/which", name])


def read_plist(path: Path) -> dict | list | None:
    try:
        with path.open("rb") as fh:
            return plistlib.load(fh)
    except (OSError, plistlib.InvalidFileException):
        return None


def redact_value(key: str, value: str) -> str:
    sensitive = ("token", "password", "secret", "key", "credential", "auth")
    if any(s in key.lower() for s in sensitive):
        return "[REDACTED]"
    if "@" in value and "." in value:
        return "[REDACTED_EMAIL]"
    return value


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------


def scan_login_items() -> list[dict]:
    items: list[dict] = []
    # osascript — classic login items
    raw = run(["osascript", "-e", 'tell application "System Events" to get the name of every login item'])
    if raw and raw != "missing value":
        for name in raw.split(", "):
            name = name.strip()
            if name:
                items.append({"name": name, "source": "login_items"})
    # Background items / sfltool (macOS 13+)
    btm = run(["/usr/bin/sfltool", "dumpbtm"], timeout=90)
    if btm:
        for line in btm.splitlines():
            if "Name:" in line or "name:" in line.lower():
                match = re.search(r"[Nn]ame:\s*(.+)$", line)
                if match:
                    items.append({"name": match.group(1).strip(), "source": "background_items"})
    return items


def scan_launch_agents() -> list[dict]:
    items: list[dict] = []
    roots = [
        HOME / "Library/LaunchAgents",
        Path("/Library/LaunchAgents"),
        Path("/Library/LaunchDaemons"),
        HOME / "Library/LaunchDaemons",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for plist in sorted(root.glob("*.plist")):
            data = read_plist(plist) or {}
            label = data.get("Label", plist.stem) if isinstance(data, dict) else plist.stem
            program = ""
            if isinstance(data, dict):
                program = data.get("Program", "") or (
                    data.get("ProgramArguments", [""])[0] if data.get("ProgramArguments") else ""
                )
            items.append(
                {
                    "label": str(label),
                    "path": str(plist),
                    "program": str(program)[:200],
                    "root": str(root),
                }
            )
    return items


def find_app(app_names: list[str]) -> str | None:
    for root in APP_SEARCH_ROOTS:
        if not root.is_dir():
            continue
        for app_name in app_names:
            candidate = root / app_name
            if candidate.is_dir():
                return str(candidate)
    return None


def count_chromium_extensions(data_root: Path) -> tuple[int, list[str]]:
    if not data_root.is_dir():
        return 0, []
    total = 0
    profiles: list[str] = []
    for profile in data_root.iterdir():
        if not profile.is_dir() or profile.name in ("System Profile", "Guest Profile"):
            continue
        ext_dir = profile / "Extensions"
        if ext_dir.is_dir():
            profiles.append(profile.name)
            total += sum(1 for e in ext_dir.iterdir() if e.is_dir())
    return total, profiles


def count_firefox_extensions(firefox_root: Path) -> tuple[int, list[str]]:
    profiles_dir = firefox_root / "Profiles"
    if not profiles_dir.is_dir():
        return 0, []
    total = 0
    profiles: list[str] = []
    for profile in profiles_dir.iterdir():
        if not profile.is_dir():
            continue
        ext_dir = profile / "extensions"
        if ext_dir.is_dir():
            profiles.append(profile.name)
            total += sum(1 for e in ext_dir.iterdir() if e.exists())
    return total, profiles


def scan_installed_browsers() -> list[dict]:
    items: list[dict] = []
    for spec in BROWSER_DEFINITIONS:
        data_root = spec["data_root"]
        app_path = find_app(spec["apps"])
        has_data = data_root.is_dir()
        if not app_path and not has_data:
            continue

        ext_count = 0
        profiles: list[str] = []
        engine = spec["engine"]
        if engine == "chromium":
            ext_count, profiles = count_chromium_extensions(data_root)
        elif engine == "firefox":
            ext_count, profiles = count_firefox_extensions(data_root)
        elif engine == "safari":
            ext_dir = data_root / "Extensions"
            if ext_dir.is_dir():
                ext_count = len(list(ext_dir.glob("*.safariextz")))
            profiles = ["Default"] if has_data else []

        items.append(
            {
                "name": spec["name"],
                "installed": bool(app_path or has_data),
                "app_path": app_path,
                "data_root": str(data_root) if has_data else None,
                "engine": engine,
                "extension_count": ext_count,
                "profiles": profiles,
            }
        )
    return items


def scan_browser_extensions() -> list[dict]:
    items: list[dict] = []
    for spec in BROWSER_DEFINITIONS:
        if spec["engine"] != "chromium":
            continue
        data_root = spec["data_root"]
        if not data_root.is_dir():
            continue
        browser = spec["name"]
        for profile in data_root.iterdir():
            ext_dir = profile / "Extensions"
            if not ext_dir.is_dir() or not profile.is_dir():
                continue
            for ext in ext_dir.iterdir():
                if not ext.is_dir():
                    continue
                manifest = ext / "manifest.json"
                name = ext.name
                version = ""
                if manifest.is_file():
                    try:
                        meta = json.loads(manifest.read_text(encoding="utf-8"))
                        name = meta.get("name", name)
                        version = meta.get("version", "")
                    except (json.JSONDecodeError, OSError):
                        pass
                items.append(
                    {
                        "browser": browser,
                        "profile": profile.name,
                        "name": name,
                        "id": ext.name,
                        "version": version,
                        "path": str(ext),
                    }
                )

    firefox_root = HOME / "Library/Application Support/Firefox/Profiles"
    if firefox_root.is_dir():
        for profile in firefox_root.iterdir():
            ext_dir = profile / "extensions"
            if not ext_dir.is_dir():
                continue
            for ext in ext_dir.iterdir():
                items.append(
                    {
                        "browser": "Firefox",
                        "profile": profile.name,
                        "name": ext.name,
                        "path": str(ext),
                    }
                )

    safari_ext = HOME / "Library/Safari/Extensions"
    if safari_ext.is_dir():
        for ext in safari_ext.glob("*.safariextz"):
            items.append({"browser": "Safari", "name": ext.stem, "path": str(ext)})

    return items


def scan_git_config() -> dict:
    cfg_path = HOME / ".gitconfig"
    result: dict = {"path": str(cfg_path), "exists": cfg_path.is_file(), "sections": {}}
    if not cfg_path.is_file():
        return result
    parser = configparser.ConfigParser()
    try:
        parser.read(cfg_path, encoding="utf-8")
    except configparser.Error:
        return result
    for section in parser.sections():
        result["sections"][section] = {
            k: redact_value(k, v) for k, v in parser.items(section)
        }
    includes = run(["git", "config", "--global", "--get-all", "include.path"]).splitlines()
    result["includes"] = [p.strip() for p in includes if p.strip()]
    return result


def scan_vpn_profiles() -> list[dict]:
    items: list[dict] = []
    candidates = [
        HOME / ".wireguard",
        HOME / ".tailscale",
        Path("/Library/Application Support/Tailscale"),
        HOME / "Library/Application Support/VPN",
        HOME / "Library/Preferences/com.wireguard.macos.plist",
    ]
    for path in candidates:
        if path.exists():
            items.append({"type": path.name, "path": str(path), "exists": True})
    # NetworkExtension preferences
    ne_dir = HOME / "Library/Preferences/ByHost"
    if ne_dir.is_dir():
        for plist in ne_dir.glob("*com.apple.networkextension*"):
            items.append({"type": "network_extension", "path": str(plist)})
    return items


def scan_cron_jobs() -> list[dict]:
    items: list[dict] = []
    crontab = run(["crontab", "-l"])
    if crontab and "no crontab" not in crontab.lower():
        for i, line in enumerate(crontab.splitlines(), 1):
            line = line.strip()
            if line and not line.startswith("#"):
                items.append({"source": "crontab", "line": line, "line_no": i})
    cron_dir = Path("/usr/lib/cron/tabs")
    if cron_dir.is_dir():
        try:
            for tab in cron_dir.iterdir():
                items.append({"source": "system_cron", "user": tab.name, "path": str(tab)})
        except OSError:
            pass
    return items


def scan_keyboard_shortcuts() -> dict:
    raw = run(["defaults", "read", "com.apple.symbolichotkeys", "AppleSymbolicHotKeys"])
    return {"raw_available": bool(raw), "path": "com.apple.symbolichotkeys/AppleSymbolicHotKeys", "note": "Full plist exported for restore reference"}


def scan_launcher_tools() -> list[dict]:
    items: list[dict] = []
    paths = [
        ("Alfred", HOME / "Library/Application Support/Alfred"),
        ("Alfred prefs", HOME / "Library/Preferences/com.runningwithcrayons.Alfred.plist"),
        ("Raycast", HOME / ".config/raycast"),
        ("Karabiner", HOME / ".config/karabiner"),
        ("Karabiner assets", HOME / ".local/share/karabiner"),
    ]
    for label, path in paths:
        if path.exists():
            entry: dict = {"tool": label.split()[0], "path": str(path), "type": "dir" if path.is_dir() else "file"}
            if path.is_dir():
                try:
                    entry["children"] = sorted(c.name for c in path.iterdir())[:30]
                except OSError:
                    pass
            items.append(entry)
    return items


def scan_terminal_profiles() -> list[dict]:
    items: list[dict] = []
    iterm = HOME / "Library/Application Support/iTerm2"
    if iterm.is_dir():
        items.append({"app": "iTerm2", "path": str(iterm), "files": sorted(p.name for p in iterm.iterdir())[:20]})
    iterm_plist = HOME / "Library/Preferences/com.googlecode.iterm2.plist"
    if iterm_plist.is_file():
        items.append({"app": "iTerm2", "path": str(iterm_plist), "type": "preferences"})
    warp = HOME / ".warp"
    if warp.is_dir():
        items.append({"app": "Warp", "path": str(warp)})
    return items


def scan_docker() -> dict:
    info: dict = {"installed": bool(which("docker"))}
    if not info["installed"]:
        return info
    info["version"] = run(["docker", "version", "--format", "{{.Server.Version}}"])
    info["context"] = run(["docker", "context", "show"])
    info["contexts"] = run(["docker", "context", "ls"]).splitlines()
    info["compose_files"] = []
    for base in (HOME / "dev", HOME / "projects", HOME / "Documents", HOME):
        if not base.is_dir():
            continue
        try:
            for compose in base.rglob("docker-compose.y*ml"):
                if compose.is_file() and len(info["compose_files"]) < 50:
                    info["compose_files"].append(str(compose))
        except OSError:
            pass
    config = HOME / ".docker/config.json"
    if config.is_file():
        info["config_path"] = str(config)
        info["config_exists"] = True
    return info


def scan_cloud_cli() -> dict:
    return {
        "aws_profiles": run(["aws", "configure", "list-profiles"]).splitlines() if which("aws") else [],
        "aws_config_exists": (HOME / ".aws/config").is_file(),
        "gcloud_configurations": run(["gcloud", "config", "configurations", "list"]).splitlines()
        if which("gcloud")
        else [],
        "kubectl_contexts": run(["kubectl", "config", "get-contexts", "-o", "name"]).splitlines()
        if which("kubectl")
        else [],
        "az_accounts": run(["az", "account", "list", "--query", "[].name", "-o", "tsv"]).splitlines()
        if which("az")
        else [],
    }


def scan_system_extensions() -> list[dict]:
    raw = run(["systemextensionsctl", "list"])
    items: list[dict] = []
    if raw:
        for line in raw.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 3:
                items.append({"raw": line.strip()})
    return items


def scan_fonts() -> list[dict]:
    items: list[dict] = []
    for root in (HOME / "Library/Fonts", Path("/Library/Fonts")):
        if not root.is_dir():
            continue
        for font in sorted(root.iterdir()):
            if font.suffix.lower() in (".ttf", ".otf", ".ttc", ".dfont"):
                items.append({"name": font.name, "path": str(font)})
    return items


def scan_printers() -> list[dict]:
    raw = run(["lpstat", "-p"])
    items: list[dict] = []
    for line in raw.splitlines():
        match = re.match(r"printer (\S+)", line)
        if match:
            items.append({"name": match.group(1), "raw": line.strip()})
    return items


def scan_hosts_file() -> dict:
    hosts = Path("/etc/hosts")
    if not hosts.is_file():
        return {"exists": False}
    try:
        lines = [ln for ln in hosts.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip() and not ln.strip().startswith("#")]
    except OSError:
        return {"exists": True, "readable": False}
    return {"exists": True, "custom_lines": lines, "line_count": len(lines)}


def scan_mac_app_store() -> list[dict]:
    items: list[dict] = []
    mas = which("mas")
    if mas:
        for line in run([mas, "list"]).splitlines():
            match = re.match(r"(\d+)\s+(.+?)\s+([\d.]+)", line)
            if match:
                items.append({"id": match.group(1), "name": match.group(2), "version": match.group(3), "source": "mas"})
    sp = run(["system_profiler", "SPApplicationsDataType", "-json"], timeout=120)
    if sp:
        try:
            data = json.loads(sp)
            for group in data.get("SPApplicationsDataType", []):
                for app in group.get("_items", []):
                    source = app.get("obtained_from", "")
                    if "app_store" in str(source).lower() or "mac_app_store" in str(source).lower():
                        items.append(
                            {
                                "name": app.get("_name", ""),
                                "path": app.get("path", ""),
                                "version": app.get("version", ""),
                                "source": "system_profiler",
                            }
                        )
        except json.JSONDecodeError:
            pass
    return items


def scan_dot_directories() -> list[dict]:
    items: list[dict] = []
    try:
        for entry in sorted(HOME.iterdir()):
            if entry.name.startswith(".") and entry.name not in (".", "..", ".Trash"):
                items.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "type": "dir" if entry.is_dir() else "file",
                    }
                )
    except OSError:
        pass
    return items


def scan_hammerspoon_btt() -> list[dict]:
    items: list[dict] = []
    for label, path in (
        ("Hammerspoon", HOME / ".hammerspoon"),
        ("BetterTouchTool", HOME / "Library/Application Support/BetterTouchTool"),
        ("Rectangle", HOME / "Library/Preferences/com.knollsoft.Rectangle.plist"),
    ):
        if path.exists():
            items.append({"tool": label, "path": str(path)})
    return items


def scan_default_apps() -> dict:
    return {
        "default_browser": run(["python3", "-c", "import webbrowser; print(webbrowser.get().name)"]),
        "note": "Check System Settings → Desktop & Dock → Default web browser on new Mac",
    }


def scan_input_sources() -> list[dict]:
    raw = run(["defaults", "read", "com.apple.HIToolbox", "AppleEnabledInputSources"])
    items: list[dict] = []
    if raw:
        items.append({"source": "AppleEnabledInputSources", "raw_length": len(raw)})
    layouts = HOME / "Library/Keyboard Layouts"
    if layouts.is_dir():
        for lay in layouts.iterdir():
            items.append({"name": lay.name, "path": str(lay), "type": "custom_layout"})
    return items


def scan_bluetooth() -> list[dict]:
    raw = run(["system_profiler", "SPBluetoothDataType", "-json"], timeout=60)
    items: list[dict] = []
    if not raw:
        return items
    try:
        data = json.loads(raw)
        for group in data.get("SPBluetoothDataType", []):
            for dev in group.get("device_connected", []) or []:
                if isinstance(dev, dict):
                    items.append({"name": dev.get("device_name", ""), "state": "connected"})
            for dev in group.get("device_not_connected", []) or []:
                if isinstance(dev, dict):
                    items.append({"name": dev.get("device_name", ""), "state": "paired"})
    except (json.JSONDecodeError, TypeError):
        pass
    return items


def scan_wifi_networks() -> list[dict]:
    raw = run(["networksetup", "-listpreferredwirelessnetworks", "en0"])
    items: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if line and not line.startswith("Preferred networks"):
            items.append({"ssid": line.strip()})
    return items


def aggregate_existing(inventory_dir: Path) -> dict:
    """Pull counts from specialized collectors already run."""
    agg: dict = {}
    mapping = {
        "homebrew": "homebrew-inventory.json",
        "vscode": "vscode-extensions.json",
        "aliases": "environment-snapshot.json",
        "quick_actions": "quick-actions-inventory.json",
        "audio": "audio-devices-inventory.json",
        "ai_dev_tools": "tools-inventory.json",
        "custom_paths": "custom-paths.json",
        "folder_profiles": "collector-output.json",
    }
    for key, filename in mapping.items():
        path = inventory_dir / filename
        if not path.is_file():
            agg[key] = {"present": False, "count": 0}
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            agg[key] = {"present": True, "count": 0}
            continue
        if key == "homebrew":
            count = data.get("formula_count", 0) + data.get("cask_count", 0)
        elif key == "vscode":
            count = sum(len(e.get("extensions", [])) for e in data.get("editors", []))
        elif key == "aliases":
            count = (data.get("aliases") or {}).get("count", 0)
        elif key == "quick_actions":
            count = data.get("workflow_count", 0) + data.get("shortcuts_count", 0)
        elif key == "audio":
            count = data.get("device_count", 0)
        elif key == "ai_dev_tools":
            count = len(data.get("tools", []))
        elif key == "custom_paths":
            count = data.get("path_count", 0)
        elif key == "folder_profiles":
            count = len(data.get("folders", []))
        else:
            count = 0
        agg[key] = {"present": True, "count": count, "file": filename}
    return agg


def build_snapshot(inventory_dir: Path) -> dict:
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "login_items": scan_login_items(),
        "launch_agents": scan_launch_agents(),
        "browsers": scan_installed_browsers(),
        "browser_extensions": scan_browser_extensions(),
        "git_config": scan_git_config(),
        "vpn_profiles": scan_vpn_profiles(),
        "cron_jobs": scan_cron_jobs(),
        "keyboard_shortcuts": scan_keyboard_shortcuts(),
        "launcher_tools": scan_launcher_tools(),
        "terminal_profiles": scan_terminal_profiles(),
        "docker": scan_docker(),
        "cloud_cli": scan_cloud_cli(),
        "system_extensions": scan_system_extensions(),
        "fonts": scan_fonts(),
        "printers": scan_printers(),
        "hosts_file": scan_hosts_file(),
        "mac_app_store": scan_mac_app_store(),
        "dot_directories": scan_dot_directories(),
        "hammerspoon_btt": scan_hammerspoon_btt(),
        "default_apps": scan_default_apps(),
        "input_sources": scan_input_sources(),
        "bluetooth": scan_bluetooth(),
        "wifi_networks": scan_wifi_networks(),
        "aggregated": aggregate_existing(inventory_dir),
    }
    snapshot["category_counts"] = {
        k: len(v) if isinstance(v, list) else (1 if v else 0)
        for k, v in snapshot.items()
        if k not in ("generated_at", "aggregated", "category_counts", "git_config", "docker", "cloud_cli", "keyboard_shortcuts", "hosts_file", "default_apps")
    }
    snapshot["category_counts"]["git_config"] = 1 if snapshot["git_config"].get("exists") else 0
    snapshot["category_counts"]["docker"] = 1 if snapshot["docker"].get("installed") else 0
    return snapshot


def render_markdown(data: dict) -> str:
    counts = data.get("category_counts", {})
    lines = [
        f"# Full system inventory — {data.get('generated_at', '')}",
        "",
        "JSON: `system-inventory.json`",
        "",
        "## Category summary",
        "",
    ]
    for key, count in sorted(counts.items(), key=lambda x: -x[1] if isinstance(x[1], int) else 0):
        lines.append(f"- **{key}**: {count}")
    lines.append("")

    if data.get("login_items"):
        lines.extend(["## Login / background items", ""])
        for item in data["login_items"]:
            lines.append(f"- {item.get('name', '?')} ({item.get('source', '')})")
        lines.append("")

    if data.get("browsers"):
        lines.extend(["## Installed browsers", ""])
        for b in data["browsers"]:
            app = b.get("app_path") or "_(no .app found — profile data only)_"
            profiles = ", ".join(b.get("profiles") or []) or "—"
            lines.append(
                f"- **{b.get('name', '?')}** — {b.get('extension_count', 0)} extension(s), "
                f"profiles: {profiles}"
            )
            lines.append(f"  - App: `{app}`")
            if b.get("data_root"):
                lines.append(f"  - Data: `{b['data_root']}`")
        lines.append("")

    if data.get("browser_extensions"):
        lines.extend([f"## Browser extensions ({len(data['browser_extensions'])})", ""])
        by_browser: dict[str, int] = {}
        for ext in data["browser_extensions"]:
            by_browser[ext.get("browser", "?")] = by_browser.get(ext.get("browser", "?"), 0) + 1
        for browser, count in sorted(by_browser.items()):
            lines.append(f"- **{browser}**: {count}")
        lines.append("")

    if data.get("launch_agents"):
        lines.extend([f"## LaunchAgents ({len(data['launch_agents'])})", ""])
        for la in data["launch_agents"][:30]:
            lines.append(f"- `{la.get('label', '?')}` — {la.get('path', '')}")
        if len(data["launch_agents"]) > 30:
            lines.append(f"- ... and {len(data['launch_agents']) - 30} more")
        lines.append("")

    agg = data.get("aggregated", {})
    if agg:
        lines.extend(["## Aggregated from other collectors", ""])
        for key, info in agg.items():
            if info.get("present"):
                lines.append(f"- **{key}**: {info.get('count', 0)} items")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HOME / "migration-inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = build_snapshot(out_dir)
    json_path = out_dir / "system-inventory.json"
    md_path = out_dir / "16-full-system-inventory.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")

    total = sum(data.get("category_counts", {}).values())
    print(f"==> Full system inventory: {json_path}")
    print(f"==> Report: {md_path}")
    print(f"==> Categories scanned: {len(data.get('category_counts', {}))}, total items: {total}")


if __name__ == "__main__":
    main()
