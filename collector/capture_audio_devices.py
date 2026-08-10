#!/usr/bin/env python3
"""Capture macOS audio devices, virtual drivers (BlackHole), and HAL plugins."""

from __future__ import annotations

import json
import plistlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
HAL_DIR = Path("/Library/Audio/Plug-Ins/HAL")
BLACKHOLE_CASKS = ("blackhole-2ch", "blackhole-16ch", "blackhole-64ch")


def run(cmd: list[str], timeout: int = 90) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def which(name: str) -> str:
    return run(["/usr/bin/which", name])


def system_profiler_audio() -> list[dict]:
    raw = run(["system_profiler", "SPAudioDataType", "-json"])
    if not raw:
        return parse_audio_text(run(["system_profiler", "SPAudioDataType"]))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return parse_audio_text(raw)

    devices: list[dict] = []
    for item in data.get("SPAudioDataType", []):
        for dev in item.get("_items", []):
            name = dev.get("_name", "")
            if not name:
                continue
            devices.append(
                {
                    "name": name,
                    "manufacturer": dev.get("coreaudio_device_manufacturer", ""),
                    "transport": dev.get("coreaudio_device_transport", ""),
                    "input_channels": dev.get("coreaudio_input_channel_count", ""),
                    "output_channels": dev.get("coreaudio_output_channel_count", ""),
                    "sample_rate": dev.get("coreaudio_device_srate", ""),
                    "default_input": dev.get("coreaudio_default_input_device") == "spaudio_yes",
                    "default_output": dev.get("coreaudio_default_output_device") == "spaudio_yes",
                    "source": "system_profiler",
                }
            )
    return devices


def parse_audio_text(raw: str) -> list[dict]:
    devices: list[dict] = []
    current: dict | None = None
    skip_names = {"audio", "devices"}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Device header: indented line ending with ':' and no value after colon
        if stripped.endswith(":") and ":" not in stripped[:-1]:
            name = stripped[:-1].strip()
            if name.lower() in skip_names:
                continue
            if current and current.get("name"):
                devices.append(current)
            current = {"name": name, "source": "system_profiler"}
            continue
        if current is None:
            continue
        match = re.match(r"^\s+([^:]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.group(1).strip(), match.group(2).strip()
        key_map = {
            "Manufacturer": "manufacturer",
            "Transport": "transport",
            "Input Channels": "input_channels",
            "Output Channels": "output_channels",
            "Current SampleRate": "sample_rate",
            "Default Input Device": "default_input",
            "Default Output Device": "default_output",
            "Default System Output Device": "default_system_output",
        }
        mapped = key_map.get(key)
        if mapped:
            if mapped.startswith("default"):
                current[mapped] = value.lower() in ("yes", "true")
            else:
                current[mapped] = value
    if current and current.get("name"):
        devices.append(current)
    return devices


def hal_plugins() -> list[dict]:
    if not HAL_DIR.is_dir():
        return []
    items: list[dict] = []
    for entry in sorted(HAL_DIR.iterdir()):
        if not entry.name.endswith(".driver"):
            continue
        info: dict = {
            "name": entry.stem,
            "path": str(entry),
            "bundle": entry.name,
            "type": "hal_plugin",
        }
        plist_path = entry / "Contents" / "Info.plist"
        if plist_path.is_file():
            try:
                with plist_path.open("rb") as fh:
                    plist = plistlib.load(fh)
                info["display_name"] = plist.get("CFBundleName") or plist.get("CFBundleDisplayName", "")
                info["manufacturer"] = plist.get("CFBundleIdentifier", "")
            except (OSError, plistlib.InvalidFileException):
                pass
        info["is_blackhole"] = "blackhole" in entry.name.lower()
        items.append(info)
    return items


def homebrew_audio_casks() -> list[str]:
    brew = which("brew")
    if not brew:
        return []
    casks = run([brew, "list", "--cask"]).splitlines()
    audio_keywords = ("blackhole", "loopback", "soundflower", "vb-cable", "audio")
    return [c for c in casks if any(k in c.lower() for k in audio_keywords)]


def build_restore_hints(devices: list[dict], hal: list[dict], casks: list[str]) -> list[dict]:
    hints: list[dict] = []
    blackhole_hal = [h for h in hal if h.get("is_blackhole")]
    blackhole_devices = [d for d in devices if "blackhole" in d.get("name", "").lower()]

    if blackhole_hal or blackhole_devices or any("blackhole" in c for c in casks):
        cask = next((c for c in casks if "blackhole" in c), "blackhole-16ch")
        hints.append(
            {
                "product": "BlackHole",
                "detected_via": "hal_plugin" if blackhole_hal else "system_device",
                "install_command": f"brew install --cask {cask}",
                "note": "Restart CoreAudio after install: sudo killall coreaudiod",
            }
        )

    for plugin in hal:
        name = plugin.get("name", "")
        if plugin.get("is_blackhole"):
            continue
        if any(k in name.lower() for k in ("xdj", "ddj", "djm", "pioneer")):
            hints.append(
                {
                    "product": plugin.get("display_name") or name,
                    "detected_via": "hal_plugin",
                    "path": plugin.get("path"),
                    "install_command": "# Install vendor driver (Rekordbox / Pioneer DJ app)",
                    "note": "Comes with DJ software — reinstall Rekordbox/Pioneer app on new Mac",
                }
            )
    return hints


def build_snapshot(inventory_dir: Path) -> dict:
    devices = system_profiler_audio()
    hal = hal_plugins()
    casks = homebrew_audio_casks()
    virtual = [d for d in devices if d.get("transport", "").lower() == "virtual"]
    hints = build_restore_hints(devices, hal, casks)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device_count": len(devices),
        "virtual_device_count": len(virtual),
        "hal_plugin_count": len(hal),
        "devices": devices,
        "virtual_devices": virtual,
        "hal_plugins": hal,
        "homebrew_audio_casks": casks,
        "restore_hints": hints,
        "restore_command": "./mac-migration restore audio",
    }


def render_markdown(data: dict) -> str:
    lines = [
        f"# Audio devices — {data.get('generated_at', '')}",
        "",
        f"**{data.get('device_count', 0)}** device(s), "
        f"**{data.get('virtual_device_count', 0)}** virtual, "
        f"**{data.get('hal_plugin_count', 0)}** HAL plugin(s).",
        "",
        "JSON: `audio-devices-inventory.json`",
        "",
    ]

    blackhole = [d for d in data.get("devices", []) if "blackhole" in d.get("name", "").lower()]
    if blackhole:
        lines.extend(["## BlackHole", ""])
        for d in blackhole:
            lines.append(
                f"- **{d.get('name')}** — {d.get('input_channels', '?')} in / "
                f"{d.get('output_channels', '?')} out @ {d.get('sample_rate', '?')} Hz"
            )
        lines.append("")

    if data.get("virtual_devices"):
        lines.extend(["## Virtual audio devices", ""])
        for d in data["virtual_devices"]:
            if "blackhole" in d.get("name", "").lower():
                continue
            lines.append(f"- **{d.get('name')}** ({d.get('manufacturer', '')})")
        lines.append("")

    if data.get("hal_plugins"):
        lines.extend(["## HAL plugins (/Library/Audio/Plug-Ins/HAL)", ""])
        for p in data["hal_plugins"]:
            label = p.get("display_name") or p.get("name", "?")
            lines.append(f"- `{p.get('bundle', '')}` — {label}")
        lines.append("")

    if data.get("restore_hints"):
        lines.extend(["## Restore on new Mac", ""])
        for hint in data["restore_hints"]:
            lines.append(f"### {hint.get('product', '?')}")
            lines.append(f"```bash")
            lines.append(hint.get("install_command", ""))
            lines.append("```")
            if hint.get("note"):
                lines.append(f"_{hint['note']}_")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HOME / "migration-inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = build_snapshot(out_dir)
    json_path = out_dir / "audio-devices-inventory.json"
    md_path = out_dir / "15-audio-devices.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")

    bh = [d for d in data.get("devices", []) if "blackhole" in d.get("name", "").lower()]
    print(f"==> Audio devices: {json_path} ({data['device_count']} devices, {len(bh)} BlackHole)")
    print(f"==> Report: {md_path}")


if __name__ == "__main__":
    main()
