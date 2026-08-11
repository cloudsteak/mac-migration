"""Discover every migration-relevant component on the machine."""

from __future__ import annotations

import json
import re
from pathlib import Path

SKIP_ENTRY_NAMES = frozenset(
    {
        ".",
        "..",
        ".Trash",
        ".Trashes",
        ".DS_Store",
        ".CFUserTextEncoding",
        ".localized",
    }
)

SENSITIVE_NAMES = frozenset(
    {
        ".ssh",
        ".gnupg",
        ".aws",
        ".azure",
        ".kube",
        ".docker",
        ".terraform.d",
        "Keychains",
    }
)

LIBRARY_AREAS = (
    "Application Support",
    "Caches",
    "Containers",
    "Preferences",
    "Logs",
    "LaunchAgents",
    "LaunchDaemons",
    "Saved Application State",
    "Group Containers",
    "WebKit",
    "Mail",
    "Cookies",
    "Safari",
    "Application Scripts",
    "Fonts",
    "Fonts (Removed)",
    "Input Methods",
    "KeyboardServices",
    "Services",
    "Spelling",
    "Sync",
    "Assistants",
    "Audio",
    "Calendars",
    "ColorPickers",
    "Colors",
    "Compositions",
    "Dictionaries",
    "Favorites",
    "Finance",
    "FontCollections",
    "Frameworks",
    "Google",
    "HomeKit",
    "HTTPStorages",
    "Internet Plug-Ins",
    "Keyboard Layouts",
    "Keychains",
    "Messages",
    "Metadata",
    "Passes",
    "Photos",
    "Printers",
    "PrivateCloudCompute",
    "Reminders",
    "ResponseKit",
    "SafariSafeBrowsing",
    "Sharing",
    "Sounds",
    "Speech",
    "Staging",
    "StatusKit",
    "Suggestions",
    "Translation",
    "UnifiedAssetFramework",
)

SYSTEM_SCAN_ROOTS = (
    "/Applications",
    "/Library",
    "/opt/homebrew",
    "/usr/local",
)


def _home(home: Path | None = None) -> Path:
    return home or Path.home()


def _human_size(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def _folder_id(path: str) -> str:
    return f"folder:{path}"


def _is_sensitive_path(path: str) -> bool:
    parts = Path(path).parts
    if any(part in SENSITIVE_NAMES for part in parts):
        return True
    return "/.config/gcloud" in path


def _component(
    *,
    comp_id: str,
    comp_type: str,
    name: str,
    source: str,
    paths: list[str],
    sensitive: bool = False,
    profile: dict | None = None,
    tags: list[str] | None = None,
) -> dict:
    return {
        "id": comp_id,
        "type": comp_type,
        "name": name,
        "source": source,
        "paths": paths,
        "sensitive": sensitive or any(_is_sensitive_path(p) for p in paths),
        "profile": profile or {},
        "tags": tags or [],
    }


def load_collector_folders(inventory_dir: Path) -> list[dict]:
    collector_json = inventory_dir / "collector-output.json"
    if not collector_json.exists():
        return []
    data = json.loads(collector_json.read_text(encoding="utf-8"))
    return data.get("folders", [])


def components_from_tools(inventory_dir: Path) -> list[dict]:
    tools_json = inventory_dir / "tools-inventory.json"
    if not tools_json.exists():
        return []
    data = json.loads(tools_json.read_text(encoding="utf-8"))
    items: list[dict] = []
    for tool in data.get("tools", []):
        items.append(
            _component(
                comp_id=tool.get("id", f"tool:{tool.get('name', '?')}"),
                comp_type=f"tool_{tool.get('category', 'other')}",
                name=tool.get("name", "?"),
                source="tools-inventory",
                paths=tool.get("paths") or [],
                tags=["tool", tool.get("category", "other")],
                profile={
                    "cli": tool.get("cli"),
                    "applications": tool.get("applications"),
                    "app_support_paths": tool.get("app_support_paths"),
                    "support_sizes": tool.get("support_sizes"),
                },
            )
        )
    return items


def components_from_vscode(inventory_dir: Path) -> list[dict]:
    path = inventory_dir / "vscode-extensions.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict] = []
    for ed in data.get("editors", []):
        ext_paths = [e.get("path") for e in ed.get("extensions", []) if e.get("path")]
        user_paths = [p for p in (ed.get("paths") or {}).values() if p]
        items.append(
            _component(
                comp_id=f"editor:{ed.get('editor', '?')}",
                comp_type="vscode_editor",
                name=ed.get("name", "?"),
                source="vscode-extensions",
                paths=user_paths,
                tags=["editor", "vscode", ed.get("editor", "")],
                profile={
                    "extension_count": ed.get("extension_count", 0),
                    "extensions": ed.get("extensions", []),
                    "reinstall_script_lines": ed.get("reinstall_script_lines", []),
                },
            )
        )
        for ext in ed.get("extensions", []):
            ext_id = ext.get("id", "")
            if not ext_id:
                continue
            items.append(
                _component(
                    comp_id=f"vscode_ext:{ext_id}",
                    comp_type="vscode_extension",
                    name=ext.get("display_name") or ext_id,
                    source=ed.get("name", "vscode"),
                    paths=[ext["path"]] if ext.get("path") else [],
                    tags=["vscode_extension", ed.get("editor", "")],
                    profile={"id": ext_id, "version": ext.get("version", "")},
                )
            )
    return items


def components_from_quick_actions(inventory_dir: Path) -> list[dict]:
    path = inventory_dir / "quick-actions-inventory.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict] = []
    for wf in data.get("automator_workflows") or []:
        items.append(
            _component(
                comp_id=f"quick_action:{wf.get('bundle_name', wf.get('name', '?'))}",
                comp_type="quick_action_workflow",
                name=wf.get("name", "?"),
                source="quick-actions",
                paths=[wf.get("path", ""), wf.get("inventory_copy", "")],
                tags=["quick_action", "automator"],
                profile={
                    "bundle_name": wf.get("bundle_name"),
                    "file_types": wf.get("file_types", []),
                    "actions": wf.get("actions", []),
                    "restore_method": wf.get("restore_method"),
                },
            )
        )
    for sc in data.get("shortcuts_app") or []:
        name = sc.get("name", "?")
        items.append(
            _component(
                comp_id=f"shortcut:{name}",
                comp_type="shortcuts_app",
                name=name,
                source="shortcuts.app",
                paths=[],
                tags=["quick_action", "shortcuts"],
                profile={"restore_note": sc.get("restore_note", "")},
            )
        )
    return items


def components_from_homebrew(inventory_dir: Path) -> list[dict]:
    path = inventory_dir / "homebrew-inventory.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("installed"):
        return []
    items: list[dict] = []
    for pkg in data.get("formulae", []):
        name = pkg.get("name", "")
        if not name:
            continue
        items.append(
            _component(
                comp_id=f"brew:formula:{name}",
                comp_type="homebrew_formula",
                name=name,
                source="homebrew-inventory",
                paths=[],
                tags=["homebrew", "formula"],
                profile={"version": pkg.get("version", "")},
            )
        )
    for pkg in data.get("casks", []):
        name = pkg.get("name", "")
        if not name:
            continue
        items.append(
            _component(
                comp_id=f"brew:cask:{name}",
                comp_type="homebrew_cask",
                name=name,
                source="homebrew-inventory",
                paths=[],
                tags=["homebrew", "cask"],
                profile={"version": pkg.get("version", "")},
            )
        )
    return items


def components_from_environment(inventory_dir: Path) -> list[dict]:
    path = inventory_dir / "environment-snapshot.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict] = []
    for alias in (data.get("aliases") or {}).get("items") or []:
        items.append(
            _component(
                comp_id=f"alias:{alias.get('name', '?')}",
                comp_type="shell_alias",
                name=f"alias {alias.get('name', '?')}",
                source=alias.get("source_file", ".zshrc"),
                paths=[alias.get("source_path", "")],
                tags=["shell", "alias"],
                profile={"definition": alias.get("definition", ""), "raw": alias.get("raw", "")},
            )
        )
    pyenv = (data.get("python") or {}).get("pyenv") or {}
    if pyenv.get("installed"):
        items.append(
            _component(
                comp_id="runtime:pyenv",
                comp_type="version_manager",
                name="pyenv",
                source="environment-snapshot",
                paths=[pyenv.get("root", "")],
                tags=["runtime", "python"],
                profile={"versions": pyenv.get("versions", []), "global": pyenv.get("global", "")},
            )
        )
    nvm = (data.get("node") or {}).get("nvm") or {}
    if nvm.get("installed") or nvm.get("versions"):
        items.append(
            _component(
                comp_id="runtime:nvm",
                comp_type="version_manager",
                name="nvm",
                source="environment-snapshot",
                paths=[nvm.get("nvm_dir", "")],
                tags=["runtime", "node"],
                profile={"versions": nvm.get("versions", [])},
            )
        )
    return items


def components_from_audio(inventory_dir: Path) -> list[dict]:
    path = inventory_dir / "audio-devices-inventory.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict] = []
    for dev in data.get("devices") or []:
        items.append(
            _component(
                comp_id=f"audio:{dev.get('name', '?')}",
                comp_type="audio_device",
                name=dev.get("name", "?"),
                source="audio-devices",
                paths=[],
                tags=["audio"],
                profile=dev,
            )
        )
    for plugin in data.get("hal_plugins") or []:
        items.append(
            _component(
                comp_id=f"hal:{plugin.get('name', '?')}",
                comp_type="hal_plugin",
                name=plugin.get("display_name") or plugin.get("name", "?"),
                source="audio-devices",
                paths=[plugin.get("path", "")],
                tags=["audio", "hal"],
                profile=plugin,
            )
        )
    return items


def components_from_system_inventory(inventory_dir: Path) -> list[dict]:
    path = inventory_dir / "system-inventory.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict] = []

    for item in data.get("login_items") or []:
        items.append(
            _component(
                comp_id=f"login:{item.get('name', '?')}",
                comp_type="login_item",
                name=item.get("name", "?"),
                source=item.get("source", "login"),
                paths=[],
                tags=["login", "startup"],
            )
        )
    for la in data.get("launch_agents") or []:
        items.append(
            _component(
                comp_id=f"launch:{la.get('label', '?')}",
                comp_type="launch_agent",
                name=la.get("label", "?"),
                source="system-inventory",
                paths=[la.get("path", "")],
                tags=["launchd", "background"],
                profile={"program": la.get("program", "")},
            )
        )
    for ext in data.get("browser_extensions") or []:
        items.append(
            _component(
                comp_id=f"browser_ext:{ext.get('browser', '?')}:{ext.get('id', ext.get('name', '?'))}",
                comp_type="browser_extension",
                name=f"{ext.get('browser', '?')}: {ext.get('name', '?')}",
                source="system-inventory",
                paths=[ext.get("path", "")],
                tags=["browser", "extension"],
                profile=ext,
            )
        )
    for browser in data.get("browsers") or []:
        items.append(
            _component(
                comp_id=f"browser:{browser.get('name', '?')}",
                comp_type="browser",
                name=browser.get("name", "?"),
                source="system-inventory",
                paths=[p for p in (browser.get("app_path"), browser.get("data_root")) if p],
                tags=["browser"],
                profile=browser,
            )
        )
    for tool in data.get("launcher_tools") or []:
        items.append(
            _component(
                comp_id=f"launcher:{tool.get('tool', '?')}",
                comp_type="launcher_tool",
                name=tool.get("tool", "?"),
                source="system-inventory",
                paths=[tool.get("path", "")],
                tags=["launcher", "productivity"],
                profile=tool,
            )
        )
    for vpn in data.get("vpn_profiles") or []:
        items.append(
            _component(
                comp_id=f"vpn:{vpn.get('type', '?')}",
                comp_type="vpn_profile",
                name=vpn.get("type", "?"),
                source="system-inventory",
                paths=[vpn.get("path", "")],
                tags=["vpn", "network"],
            )
        )
    for dot in data.get("dot_directories") or []:
        items.append(
            _component(
                comp_id=f"dotdir:{dot.get('name', '?')}",
                comp_type="dotdir",
                name=dot.get("name", "?"),
                source="system-inventory",
                paths=[dot.get("path", "")],
                tags=["home", "dotdir"],
            )
        )
    if data.get("git_config", {}).get("exists"):
        items.append(
            _component(
                comp_id="config:git",
                comp_type="git_config",
                name="Git global config",
                source="system-inventory",
                paths=[data["git_config"].get("path", "")],
                tags=["git", "config"],
                profile={"sections": list((data["git_config"].get("sections") or {}).keys())},
            )
        )
    docker = data.get("docker") or {}
    if docker.get("installed"):
        items.append(
            _component(
                comp_id="tool:docker",
                comp_type="docker",
                name="Docker",
                source="system-inventory",
                paths=[docker.get("config_path", "")] if docker.get("config_path") else [],
                tags=["docker", "containers"],
                profile=docker,
            )
        )
    return items


def components_from_custom_paths(inventory_dir: Path) -> list[dict]:
    path = inventory_dir / "custom-paths.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict] = []
    for entry in data.get("paths", []):
        p = entry.get("path", "")
        if not p:
            continue
        items.append(
            _component(
                comp_id=f"custom:{p}",
                comp_type=f"custom_{entry.get('kind', 'path')}",
                name=entry.get("name", Path(p).name),
                source=entry.get("source", "custom-paths"),
                paths=[p],
                tags=["custom", entry.get("kind", "path")],
                profile={
                    "size_human": entry.get("size_human", ""),
                    "size_bytes": entry.get("size_bytes", 0),
                },
            )
        )
    return items


def components_from_collector_folders(folders: list[dict]) -> list[dict]:
    """Every profiled folder from the collector is its own reviewable component."""
    items: list[dict] = []
    for folder in folders:
        path = folder.get("path", "")
        if not path:
            continue
        p = Path(path)
        items.append(
            _component(
                comp_id=_folder_id(path),
                comp_type="profiled_folder",
                name=p.name or path,
                source="collector",
                paths=[path],
                sensitive=bool(folder.get("sensitive")) or _is_sensitive_path(path),
                profile=dict(folder),
                tags=["profiled"],
            )
        )
    return items


def scan_directory_children(
    root: Path,
    *,
    comp_type: str,
    source: str,
    prefix: str,
    dirs_only: bool = True,
    include_non_hidden: bool = True,
) -> list[dict]:
    if not root.is_dir():
        return []
    items: list[dict] = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []

    for entry in entries:
        if entry.name in SKIP_ENTRY_NAMES:
            continue
        if not include_non_hidden and not entry.name.startswith("."):
            continue
        if dirs_only and not entry.is_dir():
            continue
        if not dirs_only and entry.is_dir():
            continue
        path = str(entry)
        items.append(
            _component(
                comp_id=f"{prefix}:{entry.name}",
                comp_type=comp_type,
                name=entry.name,
                source=source,
                paths=[path],
                sensitive=_is_sensitive_path(path),
                tags=[source],
            )
        )
    return items


def scan_home_all_entries(home: Path | None = None) -> list[dict]:
    root = _home(home)
    items: list[dict] = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return items

    for entry in entries:
        if entry.name in SKIP_ENTRY_NAMES:
            continue
        path = str(entry)
        if entry.is_dir():
            comp_type = "dotdir" if entry.name.startswith(".") else "home_dir"
        else:
            comp_type = "dotfile" if entry.name.startswith(".") else "home_file"
        items.append(
            _component(
                comp_id=f"home:{entry.name}",
                comp_type=comp_type,
                name=entry.name,
                source="home",
                paths=[path],
                sensitive=_is_sensitive_path(path),
                tags=["home"],
            )
        )
    return items


def scan_library_areas(home: Path | None = None) -> list[dict]:
    library_root = _home(home) / "Library"
    items: list[dict] = []
    if not library_root.is_dir():
        return items

    for area in LIBRARY_AREAS:
        area_path = library_root / area
        if not area_path.is_dir():
            continue
        items.extend(
            scan_directory_children(
                area_path,
                comp_type="library_item",
                source=f"~/Library/{area}",
                prefix=f"library:{area}",
            )
        )
        items.append(
            _component(
                comp_id=f"library_root:{area}",
                comp_type="library_area",
                name=area,
                source=f"~/Library/{area}",
                paths=[str(area_path)],
                sensitive=area == "Keychains",
                tags=["library", "area_root"],
            )
        )
    return items


def scan_applications_live(home: Path | None = None) -> list[dict]:
    items: list[dict] = []
    roots = [
        (Path("/Applications"), "system"),
        (_home(home) / "Applications", "user"),
    ]
    for root, source in roots:
        if not root.is_dir():
            continue
        try:
            for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
                if entry.suffix == ".app" and entry.is_dir():
                    items.append(
                        _component(
                            comp_id=f"app:{entry.name}",
                            comp_type="application",
                            name=entry.name,
                            source=source,
                            paths=[str(entry)],
                            tags=["application"],
                        )
                    )
        except OSError:
            continue
    return items


def scan_system_roots() -> list[dict]:
    items: list[dict] = []
    for root_str in SYSTEM_SCAN_ROOTS:
        root = Path(root_str)
        if not root.is_dir():
            continue
        items.append(
            _component(
                comp_id=f"system_root:{root_str}",
                comp_type="system_root",
                name=root_str,
                source="system",
                paths=[root_str],
                tags=["system"],
            )
        )
        if root_str in ("/opt/homebrew", "/usr/local"):
            items.extend(
                scan_directory_children(
                    root,
                    comp_type="system_path",
                    source=root_str,
                    prefix=f"system:{root_str}",
                    dirs_only=False,
                    include_non_hidden=True,
                )
            )
    return items


def parse_applications_md(path: Path, home: Path | None = None) -> list[dict]:
    if not path.exists():
        return []
    apps: list[dict] = []
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## /Applications"):
            section = "system"
        elif line.startswith("## ~/Applications"):
            section = "user"
        elif section:
            match = re.search(r"(\S+\.app)\s*$", line)
            if match:
                name = match.group(1)
                base = "/Applications" if section == "system" else str(_home(home) / "Applications")
                apps.append(
                    _component(
                        comp_id=f"app:{name}",
                        comp_type="application",
                        name=name,
                        source=section,
                        paths=[f"{base}/{name}"],
                        tags=["application", "inventory"],
                    )
                )
    return apps


def parse_brewfile(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith('brew "'):
            name = line[6:-1]
            items.append(
                _component(
                    comp_id=f"brew:formula:{name}",
                    comp_type="homebrew_formula",
                    name=name,
                    source="homebrew",
                    paths=[],
                    tags=["homebrew", "formula"],
                )
            )
        elif line.startswith('cask "'):
            name = line[6:-1]
            items.append(
                _component(
                    comp_id=f"brew:cask:{name}",
                    comp_type="homebrew_cask",
                    name=name,
                    source="homebrew",
                    paths=[],
                    tags=["homebrew", "cask"],
                )
            )
    return items


def parse_inventory_list_items(path: Path, section_prefix: str, comp_type: str) -> list[dict]:
    if not path.exists():
        return []
    items: list[dict] = []
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("|"):
            continue
        if line.startswith("- [ ]"):
            line = line[5:].strip()
        # package lines like `├── foo` or plain names
        token = line.split()[-1] if line.split() else line
        if len(token) < 2:
            continue
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", token)[:80]
        items.append(
            _component(
                comp_id=f"inventory:{section_prefix}:{safe}",
                comp_type=comp_type,
                name=token,
                source=f"{path.name}:{section}",
                paths=[],
                tags=["inventory", section_prefix],
            )
        )
    return items


def parse_launch_agents(path: Path, home: Path | None = None) -> list[dict]:
    if not path.exists():
        return []
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.search(r"(\S+\.plist)\s*$", line)
        if match:
            name = match.group(1)
            items.append(
                _component(
                    comp_id=f"launch_agent:{name}",
                    comp_type="launch_agent",
                    name=name,
                    source="launch_agent",
                    paths=[],
                    tags=["background_service"],
                )
            )
    return items


def parse_config_paths(path: Path, home: Path | None = None) -> list[dict]:
    if not path.exists():
        return []
    items: list[dict] = []
    home_str = str(_home(home))
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("/") or line.startswith(home_str):
            items.append(
                _component(
                    comp_id=f"inventory_path:{line}",
                    comp_type="inventory_path",
                    name=Path(line).name or line,
                    source=path.name,
                    paths=[line],
                    sensitive=_is_sensitive_path(line),
                    tags=["inventory", "path"],
                )
            )
    return items


def parse_inventory_all(inventory_dir: Path, home: Path | None = None) -> list[dict]:
    inventory_dir = Path(inventory_dir)
    items: list[dict] = []
    items.extend(parse_applications_md(inventory_dir / "01-applications.md", home))
    items.extend(parse_brewfile(inventory_dir / "Brewfile"))
    items.extend(parse_config_paths(inventory_dir / "05-configs-dotfiles.md", home))
    items.extend(parse_launch_agents(inventory_dir / "04-background-services.md", home))
    for md_name, prefix, comp_type in (
        ("02-package-managers.md", "pkg", "package_manager"),
        ("03-version-managers.md", "runtime", "version_manager"),
        ("06-system-customizations.md", "custom", "system_customization"),
        ("07-auth-cli-configs.md", "auth", "auth_config"),
        ("08-editors-ides.md", "editor", "editor_ide"),
    ):
        items.extend(
            parse_inventory_list_items(inventory_dir / md_name, prefix, comp_type)
        )
    return items


def _folder_index(folders: list[dict]) -> dict[str, dict]:
    return {f.get("path", ""): f for f in folders if f.get("path")}


def _finalize_component(comp: dict, by_path: dict[str, dict], home: Path | None = None) -> None:
    home_str = str(_home(home))
    related: set[str] = set(comp.get("paths") or [])

    for path in list(related):
        if path in by_path:
            continue
        prefix = path if path.endswith("/") else path + "/"
        for folder_path in by_path:
            if folder_path == path.rstrip("/") or folder_path.startswith(prefix):
                related.add(folder_path)

    comp_type = comp.get("type", "")
    name = comp.get("name", "")

    if comp_type == "application":
        stem = name.removesuffix(".app")
        stem_lower = stem.lower().replace(" ", "")
        for folder_path in by_path:
            if stem_lower in folder_path.lower().replace(" ", "").replace("-", ""):
                related.add(folder_path)

    if comp_type in ("homebrew_formula", "homebrew_cask"):
        token = name.lower().replace("-", "")
        for folder_path in by_path:
            if token and token in folder_path.lower().replace("-", ""):
                related.add(folder_path)

    if comp_type == "profiled_folder":
        path = (comp.get("paths") or [""])[0]
        if path in by_path:
            comp["profile"] = by_path[path]

    comp["related_paths"] = sorted(related)
    comp["related_folders"] = [by_path[p] for p in comp["related_paths"] if p in by_path]
    if comp.get("profile") and comp["profile"].get("path") in related:
        profile_bytes = comp["profile"].get("size_bytes", 0)
    else:
        profile_bytes = 0
    total_bytes = sum(f.get("size_bytes", 0) for f in comp["related_folders"])
    if profile_bytes and not comp["related_folders"]:
        total_bytes = profile_bytes
    comp["total_size_bytes"] = total_bytes
    comp["total_size_human"] = _human_size(total_bytes)


def merge_components(items: list[dict]) -> list[dict]:
    """Merge duplicate IDs; prefer collector profile data."""
    by_id: dict[str, dict] = {}
    for item in items:
        comp_id = item["id"]
        if comp_id not in by_id:
            by_id[comp_id] = item
            continue
        existing = by_id[comp_id]
        for key in ("paths", "tags"):
            merged = sorted(set(existing.get(key, []) + item.get(key, [])))
            existing[key] = merged
        if item.get("profile") and not existing.get("profile"):
            existing["profile"] = item["profile"]
        existing["sensitive"] = existing.get("sensitive") or item.get("sensitive")
    return list(by_id.values())


INTERACTIVE_SKIP_TYPES = frozenset(
    {
        "browser_extension",
        "shell_alias",
        "login_item",
        "launch_agent",
        "library_item",
        "library_area",
        "dotdir",
        "dotfile",
        "home_dir",
        "home_file",
        "inventory_path",
        "system_path",
        "system_root",
        "hal_plugin",
        "package_manager",
        "editor_ide",
        "auth_config",
        "system_customization",
    }
)

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

# Helper bundles / nested names that appear as top-level duplicates in inventory scans.
APPLICATION_HELPER_NAMES = frozenset(
    {
        "App.app",
        "Audio.app",
        "Code.app",
        "Studio.app",
        "Suite.app",
        "Editor.app",
        "Access.app",
        "Active.app",
        "Hub.app",
        "Portal.app",
        "Depot.app",
        "Deck.app",
        "OEM.app",
        "Screen.app",
        "Wallet.app",
        "Docs.app",
        "Sheets.app",
        "Slides.app",
        "2.app",
        "9.app",
    }
)

MAIN_EXTENSION_KEYWORDS = (
    "python",
    "pylance",
    "pyright",
    "csharp",
    "dotnet",
    "docker",
    "terraform",
    "aws",
    "azure",
    "kubernetes",
    "kubectl",
    "helm",
    "github",
    "copilot",
    "claude",
    "cursor",
    "prettier",
    "eslint",
    "remote-ssh",
    "remote-containers",
    "openapi",
    "swagger",
    "sql",
    "postgres",
    "redis",
    "golang",
    "rust",
    "java",
    "yaml",
    "shell",
    "powershell",
    "biome",
    "makefile",
    "boto3",
    "codex",
)

EXTENSION_NOISE_KEYWORDS = (
    "theme",
    "icon-theme",
    "color-theme",
    "language-pack",
    "snippets",
    "colorizer",
    "material-icon",
    "symbols",
)

IMPORTANT_APP_MARKERS = (
    "microsoft",
    "adobe",
    "google",
    "jetbrains",
    "ableton",
    "docker",
    "cursor",
    "claude",
    "xcode",
    "logic pro",
    "final cut",
    "davinci",
    "spitfire",
    "native instruments",
    "pioneer",
    "rekordbox",
    "serato",
    "traktor",
    "steam",
    "slack",
    "discord",
    "zoom",
    "teams",
    "1password",
    "bitwarden",
    "parallels",
    "vmware",
    "virtualbox",
    "chrome",
    "firefox",
    "brave",
    "arc",
    "visual studio",
    "insomnia",
    "postman",
    "figma",
    "miro",
    "notion",
    "obsidian",
    "raycast",
    "alfred",
    "iterm",
    "warp",
    "codex",
    "ollama",
    "onedrive",
    "dropbox",
)

MAIN_BREW_FORMULAE = frozenset(
    {
        "git",
        "node",
        "python",
        "go",
        "rust",
        "ruby",
        "kubectl",
        "helm",
        "terraform",
        "awscli",
        "azure-cli",
        "gh",
        "docker",
        "docker-compose",
        "postgresql",
        "redis",
        "sqlite",
        "jq",
        "yq",
        "ripgrep",
        "fd",
        "bat",
        "fzf",
        "tmux",
        "neovim",
        "vim",
        "shellcheck",
        "pre-commit",
        "pyenv",
        "nvm",
        "rbenv",
        "gcloud-cli",
    }
)

INTERACTIVE_SKIP_PROFILED_PARTS = (
    "/.vscode/extensions/",
    "/.cursor/extensions/",
    "/node_modules/",
    "/Library/Caches/",
    "/Library/Logs/",
    "/Library/Application Support/CrashReporter/",
)


def _interactive_group_component(
    *,
    comp_id: str,
    comp_type: str,
    name: str,
    members: list[dict],
    source: str = "grouped",
    tags: list[str] | None = None,
    profile_extra: dict | None = None,
) -> dict:
    paths = sorted({p for member in members for p in (member.get("paths") or []) if p})
    profile: dict = {
        "member_count": len(members),
        "member_ids": [member["id"] for member in members],
        "members_preview": [
            {
                "id": member["id"],
                "name": member.get("name"),
                "type": member.get("type"),
            }
            for member in members[:40]
        ],
    }
    if len(members) > 40:
        profile["members_truncated"] = len(members) - 40
    if profile_extra:
        profile.update(profile_extra)
    return _component(
        comp_id=comp_id,
        comp_type=comp_type,
        name=name,
        source=source,
        paths=paths,
        sensitive=any(member.get("sensitive") for member in members),
        profile=profile,
        tags=tags or [],
    )


def _profiled_folder_size(comp: dict) -> int:
    return int(
        comp.get("total_size_bytes")
        or (comp.get("profile") or {}).get("size_bytes")
        or 0
    )


def _skip_profiled_folder_path(path: str) -> bool:
    return any(part in path for part in INTERACTIVE_SKIP_PROFILED_PARTS)


def _priority_context(components: list[dict]) -> dict:
    tool_app_paths: set[str] = set()
    tool_app_names: set[str] = set()
    tool_clis: set[str] = set()
    cask_names: set[str] = set()
    for comp in components:
        comp_type = comp.get("type", "")
        if comp_type == "homebrew_cask":
            cask_names.add(comp.get("name", "").lower())
        if not comp_type.startswith("tool_"):
            continue
        profile = comp.get("profile") or {}
        for app_path in profile.get("applications") or []:
            tool_app_paths.add(app_path)
            tool_app_names.add(Path(app_path).name)
        cli = profile.get("cli")
        if cli:
            tool_clis.add(str(cli).lower())
    return {
        "tool_app_paths": tool_app_paths,
        "tool_app_names": tool_app_names,
        "tool_clis": tool_clis,
        "cask_names": cask_names,
    }


def _is_helper_application(name: str, all_names: set[str]) -> bool:
    if name.startswith("com.microsoft.package."):
        return True
    if name in {"Google Docs.app", "Google Sheets.app", "Google Slides.app"}:
        return True
    if name in APPLICATION_HELPER_NAMES:
        return True
    base = name.removesuffix(".app")
    if base.isdigit() or len(base) <= 2:
        return True
    for other in all_names:
        if other == name:
            continue
        other_base = other.removesuffix(".app")
        if base in other_base and len(other_base) > len(base):
            return True
    return False


def _is_main_application(comp: dict, *, all_names: set[str], priority: dict) -> bool:
    name = comp.get("name", "")
    path = (comp.get("paths") or [""])[0]
    base = name.removesuffix(".app")
    base_lower = base.lower()
    if name in APPLE_SYSTEM_APPS:
        return False
    if _is_helper_application(name, all_names):
        return False
    if path in priority["tool_app_paths"] or name in priority["tool_app_names"]:
        return True
    if comp.get("source") == "user":
        return True
    for cask in priority["cask_names"]:
        if cask and (cask in base_lower or base_lower in cask):
            return True
    if any(marker in base_lower for marker in IMPORTANT_APP_MARKERS):
        return True
    return False


def _is_main_homebrew(comp: dict, priority: dict) -> bool:
    if comp.get("type") == "homebrew_cask":
        return True
    name = comp.get("name", "").lower()
    if name in MAIN_BREW_FORMULAE:
        return True
    for cli in priority["tool_clis"]:
        if cli and (cli in name or name in cli):
            return True
    return False


def _extension_id(comp: dict) -> str:
    profile = comp.get("profile") or {}
    ext_id = profile.get("id") or comp.get("id", "").removeprefix("vscode_ext:")
    return str(ext_id).lower()


def _extension_priority(comp: dict) -> int:
    ext_id = _extension_id(comp)
    name = (comp.get("name") or "").lower()
    if not name or "%" in name:
        return -100
    haystack = f"{ext_id} {name}"
    if any(noise in haystack for noise in EXTENSION_NOISE_KEYWORDS):
        return -100
    score = 0
    for keyword in MAIN_EXTENSION_KEYWORDS:
        if keyword in haystack:
            score += 10
    if comp.get("source") in ("Visual Studio Code", "Cursor"):
        score += 1
    return score


def _is_main_extension(comp: dict) -> bool:
    return _extension_priority(comp) > 0


def _select_main_extensions(extensions: list[dict], *, limit: int = 30) -> tuple[list[dict], list[dict]]:
    ranked = sorted(extensions, key=lambda comp: (-_extension_priority(comp), comp.get("name", "").lower()))
    main = [comp for comp in ranked if _is_main_extension(comp)][:limit]
    main_ids = {comp["id"] for comp in main}
    other = [comp for comp in extensions if comp["id"] not in main_ids]
    return main, other


def consolidate_for_interactive(
    components: list[dict],
    *,
    min_size_bytes: int = 100 * 1024 * 1024,
    max_profiled_folders: int = 150,
) -> list[dict]:
    """
    Reduce full discovery to a human-scale review queue focused on main apps,
    packages, and extensions. Secondary items are grouped, not dropped.
    """
    priority = _priority_context(components)
    result: list[dict] = []
    profiled_candidates: list[dict] = []
    applications: list[dict] = []
    homebrew_main: list[dict] = []
    homebrew_other: list[dict] = []
    vscode_extensions: list[dict] = []
    shell_aliases: list[dict] = []
    login_items: list[dict] = []
    launch_agents: list[dict] = []
    browser_ext_by_browser: dict[str, list[dict]] = {}

    for comp in components:
        comp_type = comp.get("type", "")

        if comp_type == "application":
            applications.append(comp)
            continue

        if comp_type == "vscode_extension":
            vscode_extensions.append(comp)
            continue

        if comp_type in ("homebrew_formula", "homebrew_cask"):
            if _is_main_homebrew(comp, priority):
                homebrew_main.append(comp)
            else:
                homebrew_other.append(comp)
            continue

        if comp_type in INTERACTIVE_SKIP_TYPES:
            if comp_type == "shell_alias":
                shell_aliases.append(comp)
            elif comp_type == "login_item":
                login_items.append(comp)
            elif comp_type == "launch_agent":
                launch_agents.append(comp)
            elif comp_type == "browser_extension":
                browser = (comp.get("profile") or {}).get("browser") or comp.get("name", "?").split(":", 1)[0]
                browser_ext_by_browser.setdefault(browser.strip(), []).append(comp)
            continue

        if comp_type.startswith("custom_"):
            continue

        if comp_type == "profiled_folder":
            path = (comp.get("paths") or [""])[0]
            if _skip_profiled_folder_path(path):
                continue
            if comp.get("sensitive") or _profiled_folder_size(comp) >= min_size_bytes:
                profiled_candidates.append(comp)
            continue

        if comp_type == "version_manager" and comp.get("source") != "environment-snapshot":
            continue

        result.append(comp)

    app_names = {comp.get("name", "") for comp in applications}
    main_apps: list[dict] = []
    other_apps: list[dict] = []
    for comp in applications:
        if _is_main_application(comp, all_names=app_names, priority=priority):
            main_apps.append(comp)
        else:
            other_apps.append(comp)
    result.extend(main_apps)

    result.extend(homebrew_main)

    main_ext, other_ext = _select_main_extensions(vscode_extensions)
    result.extend(main_ext)

    if profiled_candidates:
        profiled_candidates.sort(key=lambda comp: -_profiled_folder_size(comp))
        result.extend(profiled_candidates[:max_profiled_folders])
        overflow = profiled_candidates[max_profiled_folders:]
        if overflow:
            total_bytes = sum(_profiled_folder_size(comp) for comp in overflow)
            result.append(
                _interactive_group_component(
                    comp_id="group:profiled_folders_overflow",
                    comp_type="profiled_folders_group",
                    name=(
                        f"Other large folders ({len(overflow)} folders ≥ "
                        f"{min_size_bytes // (1024 * 1024)} MB, {_human_size(total_bytes)})"
                    ),
                    members=overflow,
                    source="collector",
                    tags=["profiled"],
                    profile_extra={
                        "min_size_bytes": min_size_bytes,
                        "total_size_bytes": total_bytes,
                        "total_size_human": _human_size(total_bytes),
                    },
                )
            )

    if other_apps:
        result.append(
            _interactive_group_component(
                comp_id="group:applications_other",
                comp_type="applications_group",
                name=f"Other applications ({len(other_apps)})",
                members=other_apps,
                source="applications",
                tags=["application"],
            )
        )

    if homebrew_other:
        result.append(
            _interactive_group_component(
                comp_id="group:homebrew_other",
                comp_type="homebrew_group",
                name=f"Other Homebrew formulae ({len(homebrew_other)})",
                members=homebrew_other,
                source="homebrew-inventory",
                tags=["homebrew", "formula"],
                profile_extra={
                    "restore_note": "Reinstall via Brewfile / restore.sh homebrew step.",
                },
            )
        )

    if other_ext:
        by_editor: dict[str, list[dict]] = {}
        for comp in other_ext:
            editor = comp.get("source", "editor")
            by_editor.setdefault(editor, []).append(comp)
        for editor, extensions in sorted(by_editor.items()):
            result.append(
                _interactive_group_component(
                    comp_id=f"group:vscode_ext_other:{editor.lower().replace(' ', '_')}",
                    comp_type="vscode_extensions_group",
                    name=f"Other {editor} extensions ({len(extensions)})",
                    members=extensions,
                    source=editor,
                    tags=["vscode_extension"],
                    profile_extra={
                        "editor": editor,
                        "extension_names": [member.get("name") for member in extensions[:30]],
                    },
                )
            )

    if shell_aliases:
        result.append(
            _interactive_group_component(
                comp_id="group:shell_aliases",
                comp_type="shell_aliases_group",
                name=f"Shell aliases ({len(shell_aliases)})",
                members=shell_aliases,
                source="environment-snapshot",
                tags=["shell", "alias"],
                profile_extra={
                    "aliases": [
                        {
                            "name": (member.get("profile") or {}).get("definition")
                            or member.get("name"),
                            "source": member.get("source"),
                        }
                        for member in shell_aliases[:30]
                    ],
                },
            )
        )

    if login_items:
        result.append(
            _interactive_group_component(
                comp_id="group:login_items",
                comp_type="login_items_group",
                name=f"Login items ({len(login_items)})",
                members=login_items,
                source="system-inventory",
                tags=["login", "startup"],
            )
        )

    if launch_agents:
        result.append(
            _interactive_group_component(
                comp_id="group:launch_agents",
                comp_type="launch_agents_group",
                name=f"LaunchAgents ({len(launch_agents)})",
                members=launch_agents,
                source="system-inventory",
                tags=["launchd", "background"],
            )
        )

    for browser, extensions in sorted(browser_ext_by_browser.items()):
        result.append(
            _interactive_group_component(
                comp_id=f"group:browser_ext:{browser.lower().replace(' ', '_')}",
                comp_type="browser_extensions_group",
                name=f"{browser} extensions ({len(extensions)})",
                members=extensions,
                source="system-inventory",
                tags=["browser", "extension"],
                profile_extra={
                    "browser": browser,
                    "extension_names": [member.get("name") for member in extensions[:30]],
                },
            )
        )

    result.sort(
        key=lambda c: (
            -(c.get("total_size_bytes") or 0),
            c.get("type", ""),
            c.get("name", "").lower(),
        )
    )
    return result


def discover_components(
    inventory_dir: Path,
    collector_folders: list[dict] | None = None,
    home: Path | None = None,
) -> list[dict]:
    """
    Discover everything: all collector folders + live filesystem + full inventory.
    """
    inventory_dir = Path(inventory_dir)
    folders = collector_folders if collector_folders is not None else load_collector_folders(
        inventory_dir
    )

    items: list[dict] = []
    items.extend(components_from_collector_folders(folders))
    items.extend(scan_home_all_entries(home))
    items.extend(scan_library_areas(home))
    items.extend(scan_applications_live(home))
    items.extend(scan_system_roots())
    items.extend(parse_inventory_all(inventory_dir, home))
    items.extend(components_from_tools(inventory_dir))
    items.extend(components_from_vscode(inventory_dir))
    items.extend(components_from_quick_actions(inventory_dir))
    items.extend(components_from_environment(inventory_dir))
    items.extend(components_from_audio(inventory_dir))
    items.extend(components_from_system_inventory(inventory_dir))
    items.extend(components_from_homebrew(inventory_dir))
    items.extend(components_from_custom_paths(inventory_dir))

    components = merge_components(items)
    by_path = _folder_index(folders)
    for comp in components:
        _finalize_component(comp, by_path, home)

    components.sort(
        key=lambda c: (
            -(c.get("total_size_bytes") or 0),
            c.get("type", ""),
            c.get("name", "").lower(),
        )
    )
    return components


def group_components(components: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group for interactive navigation — profiled folders by top-level area."""
    buckets: dict[str, list[dict]] = {
        "VS Code / Cursor extensions": [],
        "Quick Actions (Automator + Shortcuts)": [],
        "Audio devices & HAL plugins": [],
        "Login items & startup": [],
        "Browser extensions": [],
        "Installed browsers": [],
        "Launcher tools (Alfred/Raycast/Karibiner)": [],
        "VPN & network profiles": [],
        "Shell aliases & runtimes": [],
        "Homebrew packages (all)": [],
        "Custom paths (non-stock macOS)": [],
        "AI assistants & coding tools": [],
        "DevOps & infrastructure": [],
        "Creative & DJ / DAW apps": [],
        "Applications": [],
        "Homebrew & package managers": [],
        "Home directory (top level)": [],
        "Library & app data": [],
        "Profiled folders — home": [],
        "Profiled folders — system": [],
        "Background services & agents": [],
        "Editors, auth & config (inventory)": [],
        "Other": [],
    }

    home_str = str(_home())

    for comp in components:
        comp_type = comp.get("type", "")
        paths = comp.get("paths") or []
        first_path = paths[0] if paths else ""
        tags = comp.get("tags") or []

        if comp_type in ("vscode_extension", "vscode_editor"):
            buckets["VS Code / Cursor extensions"].append(comp)
            continue
        if comp_type == "vscode_extensions_group":
            buckets["VS Code / Cursor extensions"].append(comp)
            continue
        if comp_type == "applications_group":
            buckets["Applications"].append(comp)
            continue
        if comp_type == "homebrew_group":
            buckets["Homebrew packages (all)"].append(comp)
            continue
        if comp_type == "browser_extensions_group":
            buckets["Browser extensions"].append(comp)
            continue
        if comp_type == "shell_aliases_group":
            buckets["Shell aliases & runtimes"].append(comp)
            continue
        if comp_type == "login_items_group":
            buckets["Login items & startup"].append(comp)
            continue
        if comp_type == "launch_agents_group":
            buckets["Background services & agents"].append(comp)
            continue
        if comp_type == "profiled_folders_group":
            buckets["Profiled folders — home"].append(comp)
            continue
        if comp_type in ("quick_action_workflow", "shortcuts_app"):
            buckets["Quick Actions (Automator + Shortcuts)"].append(comp)
            continue
        if comp_type in ("audio_device", "hal_plugin"):
            buckets["Audio devices & HAL plugins"].append(comp)
            continue
        if comp_type in ("login_item",):
            buckets["Login items & startup"].append(comp)
            continue
        if comp_type == "browser_extension":
            buckets["Browser extensions"].append(comp)
            continue
        if comp_type == "browser":
            buckets["Installed browsers"].append(comp)
            continue
        if comp_type == "launcher_tool":
            buckets["Launcher tools (Alfred/Raycast/Karibiner)"].append(comp)
            continue
        if comp_type == "vpn_profile":
            buckets["VPN & network profiles"].append(comp)
            continue
        if comp_type in ("shell_alias",) or (comp_type == "version_manager" and comp.get("source") == "environment-snapshot"):
            buckets["Shell aliases & runtimes"].append(comp)
            continue
        if comp_type == "launch_agent" and comp.get("source") == "system-inventory":
            buckets["Login items & startup"].append(comp)
            continue
        if comp_type == "docker":
            buckets["DevOps & infrastructure"].append(comp)
            continue
        if comp_type in ("homebrew_formula", "homebrew_cask") and comp.get("source") == "homebrew-inventory":
            buckets["Homebrew packages (all)"].append(comp)
            continue
        if comp_type.startswith("custom_") or "custom" in tags:
            buckets["Custom paths (non-stock macOS)"].append(comp)
            continue

        if comp_type.startswith("tool_") or "tool" in tags:
            cat = comp_type.replace("tool_", "")
            if cat in ("ai_assistant", "ai_coding", "ai_local", "ai_config"):
                buckets["AI assistants & coding tools"].append(comp)
            elif cat in ("devops", "runtime"):
                buckets["DevOps & infrastructure"].append(comp)
            elif cat == "creative":
                buckets["Creative & DJ / DAW apps"].append(comp)
            else:
                buckets["Other"].append(comp)
            continue

        if comp_type == "application":
            buckets["Applications"].append(comp)
        elif comp_type.startswith("homebrew") or comp_type == "package_manager":
            buckets["Homebrew & package managers"].append(comp)
        elif comp_type in ("home_dir", "home_file", "dotdir", "dotfile"):
            buckets["Home directory (top level)"].append(comp)
        elif comp_type in ("library_item", "library_area") or "/Library/" in first_path:
            if comp_type != "profiled_folder":
                buckets["Library & app data"].append(comp)
                continue
        if comp_type in ("launch_agent",) or "background_service" in comp.get("tags", []):
            buckets["Background services & agents"].append(comp)
        elif comp_type in (
            "version_manager",
            "system_customization",
            "auth_config",
            "editor_ide",
            "inventory_path",
        ):
            buckets["Editors, auth & config (inventory)"].append(comp)

        if comp_type == "profiled_folder":
            if first_path.startswith(home_str):
                buckets["Profiled folders — home"].append(comp)
            elif first_path.startswith("/"):
                buckets["Profiled folders — system"].append(comp)
            else:
                buckets["Other"].append(comp)
        elif comp_type in ("system_root", "system_path"):
            buckets["Profiled folders — system"].append(comp)
        elif comp_type not in (
            "application",
            "homebrew_formula",
            "homebrew_cask",
            "home_dir",
            "home_file",
            "dotdir",
            "dotfile",
            "library_item",
            "library_area",
            "launch_agent",
            "package_manager",
            "version_manager",
            "system_customization",
            "auth_config",
            "editor_ide",
            "inventory_path",
        ):
            buckets["Other"].append(comp)

    grouped: list[tuple[str, list[dict]]] = []
    for title, items in buckets.items():
        if items:
            grouped.append((title, items))
    return grouped


def discovery_summary(components: list[dict]) -> dict:
    profiled = sum(1 for c in components if c.get("type") == "profiled_folder")
    sensitive = sum(1 for c in components if c.get("sensitive"))
    total_bytes = sum(c.get("total_size_bytes", 0) for c in components)
    return {
        "total_components": len(components),
        "profiled_folders": profiled,
        "sensitive_components": sensitive,
        "total_size_human": _human_size(total_bytes),
    }
