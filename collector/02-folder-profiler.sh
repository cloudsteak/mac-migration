#!/usr/bin/env bash
#
# 02-folder-profiler.sh
#
# Profiles directory trees (size, file count, dominant extensions, last modified).
# Profiles everything except Trash — sensitive paths are flagged, not skipped.
#
# Run: bash collector/02-folder-profiler.sh
# Output: ~/migration-inventory/collector-output.json

set -uo pipefail

OUT="${HOME}/migration-inventory"
mkdir -p "$OUT"
JSON_OUT="${OUT}/collector-output.json"
TS=$(date "+%Y-%m-%dT%H:%M:%S")

MAX_DEPTH="${MAX_DEPTH:-3}"
SCAN_SYSTEM="${SCAN_SYSTEM:-1}"

# Sensitive directory names — profile metadata but flag in output (no content reads)
readonly -a SENSITIVE_DIR_NAMES=(
  ".ssh"
  ".gnupg"
  ".aws"
  ".azure"
  ".kube"
  ".docker"
  ".terraform.d"
  "Keychains"
)

should_skip_dir() {
  local dir="$1"
  case "$dir" in
    *"/.Trash"|*"/.Trash/"*|*"/.Trashes"|*"/.Trashes/"*)
      return 0
      ;;
  esac
  return 1
}

is_sensitive_dir() {
  local dir="$1"
  local base name

  base=$(basename "$dir")
  for name in "${SENSITIVE_DIR_NAMES[@]}"; do
    if [[ "$base" == "$name" ]]; then
      return 0
    fi
  done
  if [[ "$dir" == *"/.config/gcloud"* ]] || [[ "$dir" == "${HOME}/.config/gcloud" ]]; then
    return 0
  fi
  return 1
}

echo "==> Folder profiler started: ${TS}"
echo "==> Max depth: ${MAX_DEPTH} levels"
echo "==> Scanning home, applications, and local system paths..."
echo "==> This may take a while on a large disk..."

TMP_JSONL=$(mktemp)
trap 'rm -f "${TMP_JSONL}"' EXIT

profile_dir() {
  local dir="$1"
  [[ -d "$dir" ]] || return 0
  [[ -r "$dir" ]] || return 0

  if should_skip_dir "$dir"; then
    return 0
  fi

  local sensitive_flag=0
  if is_sensitive_dir "$dir"; then
    sensitive_flag=1
  fi

  local size_bytes size_human file_count last_mod dominant_ext

  size_bytes=$(du -sk "$dir" 2>/dev/null | awk '{print $1 * 1024}')
  [[ -n "$size_bytes" ]] || size_bytes=0
  size_human=$(du -sh "$dir" 2>/dev/null | cut -f1)
  [[ -n "$size_human" ]] || size_human="0B"

  file_count=$(find "$dir" -maxdepth 2 -type f 2>/dev/null | wc -l | tr -d ' ')
  [[ -n "$file_count" ]] || file_count=0

  last_mod=$(stat -f "%Sm" -t "%Y-%m-%d" "$dir" 2>/dev/null || echo "")

  dominant_ext=$(
    find "$dir" -maxdepth 2 -type f 2>/dev/null \
      | sed -n 's/.*\.\([a-zA-Z0-9]*\)$/\1/p' \
      | tr '[:upper:]' '[:lower:]' \
      | sort | uniq -c | sort -rn | head -3 \
      | awk '{printf "%s:%s,", $2, $1}' | sed 's/,$//'
  )

  python3 - "$dir" "$size_bytes" "$size_human" "$file_count" "$last_mod" "$dominant_ext" "$sensitive_flag" <<'PYEOF' >>"$TMP_JSONL"
import json, sys

path, size_bytes, size_human, file_count, last_mod, dominant_ext, sensitive = sys.argv[1:8]
record = {
    "path": path,
    "size_bytes": int(size_bytes) if str(size_bytes).isdigit() else 0,
    "size_human": size_human,
    "file_count_shallow": int(file_count) if str(file_count).isdigit() else 0,
    "last_modified": last_mod,
    "dominant_extensions": dominant_ext,
    "sensitive": sensitive == "1",
}
print(json.dumps(record, ensure_ascii=False))
PYEOF
}

export -f profile_dir should_skip_dir is_sensitive_dir
export TMP_JSONL HOME

ROOTS=("$HOME" "/Applications" "${HOME}/Applications" "/opt/homebrew" "/usr/local")
if [[ "$SCAN_SYSTEM" == "1" ]]; then
  ROOTS+=("/Library")
fi

count=0
echo "==> Discovering and profiling folders..."

for root in "${ROOTS[@]}"; do
  [[ -d "$root" ]] || continue

  profile_dir "$root"
  count=$((count + 1))

  while IFS= read -r -d '' d; do
    if should_skip_dir "$d"; then
      continue
    fi
    profile_dir "$d"
    count=$((count + 1))
    if (( count % 100 == 0 )); then
      echo "    ... ${count} folders profiled"
    fi
  done < <(find "$root" -mindepth 1 -maxdepth "$MAX_DEPTH" -type d -print0 2>/dev/null)
done

python3 - "$TMP_JSONL" "$JSON_OUT" "$TS" "$MAX_DEPTH" <<'PYEOF'
import json, sys

jsonl_path, out_path, ts, max_depth = sys.argv[1:5]

records = []
with open(jsonl_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

output = {
    "generated_at": ts,
    "max_depth": int(max_depth),
    "folder_count": len(records),
    "folders": records,
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"==> {len(records)} folders profiled.")
PYEOF

echo "==> Done: ${JSON_OUT}"
echo "==> This file is the input for analyzer/analyze.py (Phase B)."
