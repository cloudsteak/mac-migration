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
        return entries

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

        if comp_type == "vscode_extension":
            buckets["VS Code / Cursor extensions"].append(comp)
            continue
        if comp_type == "vscode_editor":
            buckets["VS Code / Cursor extensions"].append(comp)
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
