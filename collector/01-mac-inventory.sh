#!/usr/bin/env bash
#
# 01-mac-inventory.sh — system inventory for macOS migration (English + Hungarian reports)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${HOME}/migration-inventory"
mkdir -p "$OUT"
TS=$(date "+%Y-%m-%d %H:%M:%S")

echo "==> Inventory started: ${TS}"
echo "==> Output directory: ${OUT}"

# ---------------------------------------------------------------
# 1. APPLICATIONS
# ---------------------------------------------------------------
{
  echo "# Applications — ${TS}"
  echo
  echo "## /Applications"
  ls -la /Applications 2>/dev/null
  echo
  echo "## ~/Applications (user-scope)"
  ls -la "${HOME}/Applications" 2>/dev/null
  echo
  echo "## App Store purchases (requires mas-cli: brew install mas)"
  if command -v mas >/dev/null 2>&1; then
    mas list
  else
    echo "mas not installed — run: brew install mas, then re-run this section"
  fi
  echo
  echo "## pkgutil receipts (non-App Store / non-brew installers)"
  pkgutil --pkgs | sort
} > "${OUT}/01-applications.md"

# ---------------------------------------------------------------
# 2. PACKAGE MANAGERS
# ---------------------------------------------------------------
{
  echo "# Package managers — ${TS}"
  echo
  echo "## Homebrew (formula + cask + tap — reusable via Brewfile)"
  if command -v brew >/dev/null 2>&1; then
    brew bundle dump --file="${OUT}/Brewfile" --force
    echo "Brewfile written: ${OUT}/Brewfile"
    echo
    echo "### brew list --formula"
    brew list --formula
    echo
    echo "### brew list --cask"
    brew list --cask
  else
    echo "Homebrew not installed."
  fi
  echo
  echo "## npm global packages"
  command -v npm >/dev/null 2>&1 && npm list -g --depth=0
  echo
  echo "## pipx"
  command -v pipx >/dev/null 2>&1 && pipx list
  echo
  echo "## pip (global/user — informational; pyenv versions differ)"
  command -v pip3 >/dev/null 2>&1 && pip3 list --format=freeze 2>/dev/null
  echo
  echo "## gem (Ruby)"
  command -v gem >/dev/null 2>&1 && gem list
  echo
  echo "## cargo (Rust)"
  command -v cargo >/dev/null 2>&1 && ls "${HOME}/.cargo/bin" 2>/dev/null
  echo
  echo "## binaries installed via go install"
  [ -d "${HOME}/go/bin" ] && ls -la "${HOME}/go/bin"
} > "${OUT}/02-package-managers.md"

# ---------------------------------------------------------------
# 3. VERSION-MANAGED RUNTIMES
# ---------------------------------------------------------------
{
  echo "# Version-managed runtimes — ${TS}"
  echo
  for tool in pyenv tenv tfenv tgenv nvm rbenv sdkman asdf; do
    echo "## ${tool}"
    case "$tool" in
      pyenv) command -v pyenv >/dev/null 2>&1 && { pyenv versions; echo "global: $(pyenv global 2>/dev/null)"; echo "plugins:"; ls "${HOME}/.pyenv/plugins" 2>/dev/null; } ;;
      tenv)  command -v tenv >/dev/null 2>&1 && { echo "Terraform:"; tenv tf list 2>/dev/null; echo "OpenTofu:"; tenv tofu list 2>/dev/null; echo "Terragrunt:"; tenv tg list 2>/dev/null; } ;;
      tfenv) command -v tfenv >/dev/null 2>&1 && tfenv list ;;
      tgenv) command -v tgenv >/dev/null 2>&1 && tgenv list ;;
      nvm)   [ -d "${HOME}/.nvm" ] && ls "${HOME}/.nvm/versions/node" 2>/dev/null ;;
      rbenv) command -v rbenv >/dev/null 2>&1 && rbenv versions ;;
      sdkman) [ -d "${HOME}/.sdkman/candidates" ] && ls "${HOME}/.sdkman/candidates" 2>/dev/null ;;
      asdf)  command -v asdf >/dev/null 2>&1 && asdf list ;;
    esac
    echo
  done
} > "${OUT}/03-version-managers.md"

# ---------------------------------------------------------------
# 4. BACKGROUND SERVICES
# ---------------------------------------------------------------
{
  echo "# Background services (LaunchAgents/Daemons) — ${TS}"
  echo
  echo "## ~/Library/LaunchAgents (user-level)"
  ls -la "${HOME}/Library/LaunchAgents" 2>/dev/null
  echo
  echo "## /Library/LaunchAgents (system, all users)"
  ls -la /Library/LaunchAgents 2>/dev/null
  echo
  echo "## /Library/LaunchDaemons"
  ls -la /Library/LaunchDaemons 2>/dev/null
} > "${OUT}/04-background-services.md"

# ---------------------------------------------------------------
# 5. CONFIGS / DOTFILES
# ---------------------------------------------------------------
{
  echo "# Configs and dotfiles — ${TS}"
  echo
  echo "## Hidden files in home (dotfiles)"
  find "${HOME}" -maxdepth 1 -name '.*' ! -name '.' ! -name '..' -exec basename {} \; 2>/dev/null | sort
  echo
  echo "## ~/.config subfolders"
  find "${HOME}/.config" -maxdepth 1 -mindepth 1 2>/dev/null
  echo
  echo "## ~/Library/Application Support — by size (TOP 50)"
  du -sh "${HOME}/Library/Application Support/"*/ 2>/dev/null | sort -rh | head -50
  echo
  echo "## ~/Library/Preferences (.plist list — apps storing settings)"
  find "${HOME}/Library/Preferences" -maxdepth 1 -name '*.plist' -exec basename {} \; 2>/dev/null | sort
} > "${OUT}/05-configs-dotfiles.md"

# ---------------------------------------------------------------
# 6. SYSTEM CUSTOMIZATIONS
# ---------------------------------------------------------------
{
  echo "# System customizations — ${TS}"
  echo
  echo "## Quick Actions / Automator (~/Library/Services)"
  ls -la "${HOME}/Library/Services" 2>/dev/null
  echo
  echo "## Shortcuts.app stored shortcuts"
  command -v shortcuts >/dev/null 2>&1 && shortcuts list
  echo
  echo "## Dock layout (raw plist for analysis)"
  defaults read com.apple.dock persistent-apps 2>/dev/null | grep "file-label"
  echo
  echo "## Custom keyboard shortcuts / global settings export"
  echo "(defaults read com.apple.symbolichotkeys AppleSymbolicHotKeys — large; review manually)"
} > "${OUT}/06-system-customizations.md"

# ---------------------------------------------------------------
# 7. AUTH / CLI CONFIGS
# ---------------------------------------------------------------
{
  echo "# Authentication / keys / CLI configs — ${TS}"
  echo
  echo "## SSH"
  ls -la "${HOME}/.ssh" 2>/dev/null
  echo
  echo "## known_hosts line count (count only — no content)"
  [ -f "${HOME}/.ssh/known_hosts" ] && wc -l < "${HOME}/.ssh/known_hosts"
  echo
  echo "## GPG"
  command -v gpg >/dev/null 2>&1 && gpg --list-keys
  echo
  echo "## Git global config (key names only — values/secrets redacted)"
  if [ -f "${HOME}/.gitconfig" ]; then
    grep -E '^\s*\[|^\s*[a-zA-Z]' "${HOME}/.gitconfig" 2>/dev/null \
      | sed 's/=.*$/= [REDACTED]/' || echo "(unreadable)"
  fi
  echo
  echo "## Cloud CLI configs (existence + file count only — no secrets)"
  for d in "${HOME}/.aws" "${HOME}/.azure" "${HOME}/.config/gcloud" "${HOME}/.kube" "${HOME}/.terraform.d" "${HOME}/.docker"; do
    if [ -d "$d" ]; then
      echo "${d} -> exists, $(find "$d" -type f | wc -l | tr -d ' ') files"
    fi
  done
} > "${OUT}/07-auth-cli-configs.md"

# ---------------------------------------------------------------
# 8. EDITORS / IDEs
# ---------------------------------------------------------------
{
  echo "# Editors / IDEs — ${TS}"
  echo
  echo "## VSCode extension list"
  command -v code >/dev/null 2>&1 && code --list-extensions
  echo
  echo "## VSCode user settings path/size"
  ls -la "${HOME}/Library/Application Support/Code/User/" 2>/dev/null
  echo
  echo "## iTerm2 profile plist"
  ls -la "${HOME}/Library/Preferences/com.googlecode.iterm2.plist" 2>/dev/null
  echo
  echo "## JetBrains / other IDE traces"
  ls -la "${HOME}/Library/Application Support/JetBrains" 2>/dev/null
} > "${OUT}/08-editors-ides.md"

# ---------------------------------------------------------------
# SUMMARY INDEX (English base — localize-inventory.py adds HU + lang links)
# ---------------------------------------------------------------
{
  echo "# Migration Inventory — Summary index"
  echo "Generated: ${TS}"
  echo
  echo "| # | Category | File |"
  echo "|---|-----------|------|"
  echo "| 1 | Applications | 01-applications.md |"
  echo "| 2 | Package managers | 02-package-managers.md |"
  echo "| 3 | Version-managed runtimes | 03-version-managers.md |"
  echo "| 4 | Background services | 04-background-services.md |"
  echo "| 5 | Configs / dotfiles | 05-configs-dotfiles.md |"
  echo "| 6 | System customizations | 06-system-customizations.md |"
  echo "| 7 | Auth / CLI configs | 07-auth-cli-configs.md |"
  echo "| 8 | Editors / IDEs | 08-editors-ides.md |"
  echo "| 9 | Shell & runtime (pyenv, Homebrew) | 09-shell-environment.md |"
  echo "| 10 | AI, dev & creative tools | 10-ai-dev-creative-tools.md |"
  echo "| 11 | VS Code / Cursor extensions | 11-vscode-extensions.md |"
  echo "| 12 | Homebrew (full package list) | 12-homebrew-full.md |"
  echo "| 13 | Custom paths (non-stock macOS) | 13-custom-paths.md |"
  echo "| 14 | Quick Actions (Automator + Shortcuts) | 14-quick-actions.md |"
  echo "| 15 | Audio devices (BlackHole, HAL) | 15-audio-devices.md |"
  echo "| 16 | Full system inventory (everything) | 16-full-system-inventory.md |"
  echo
  echo "Machine-readable JSON: \`environment-snapshot.json\`, \`system-inventory.json\`, \`restore-manifest.json\`,"
  echo "\`vscode-extensions.json\`, \`homebrew-inventory.json\`, \`custom-paths.json\`, \`quick-actions-inventory.json\`,"
  echo "\`audio-devices-inventory.json\`."
  echo
  echo "Next step: run collector/02-folder-profiler.sh, then analyzer/analyze.py -i for interactive review."
} > "${OUT}/00-INDEX.md"

python3 "${SCRIPT_DIR}/localize-inventory.py" "${OUT}"

echo "==> Done. Review: ${OUT}/00-INDEX.md (English) or ${OUT}/00-INDEX_HU.md (Hungarian)"
