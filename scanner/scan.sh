#!/usr/bin/env bash
# scanner/scan.sh
# SASTスキャンを実行し、JSONレポートを出力します。
# 使用方法: ./scan.sh <github-repo-url> <scan-id>
#
# 依存: git, semgrep
# semgrep インストール: pip install semgrep

set -euo pipefail

# ─── 引数チェック ──────────────────────────────────────────────────────────────
if [ $# -lt 2 ]; then
  echo "Usage: $0 <github-repo-url> <scan-id>" >&2
  exit 1
fi

REPO_URL="$1"
SCAN_ID="$2"

# ─── 入力バリデーション ───────────────────────────────────────────────────────
# SCAN_ID にパストラバーサル・シェルメタキャラクタが含まれていないか確認する
if [[ ! "$SCAN_ID" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Error: SCAN_ID contains invalid characters: $SCAN_ID" >&2
  exit 1
fi

# REPO_URL が http(s):// で始まることを確認する
if [[ ! "$REPO_URL" =~ ^https?:// ]]; then
  echo "Error: REPO_URL must start with http:// or https://" >&2
  exit 1
fi

# ─── ディレクトリ設定 ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
REPORTS_DIR="${ROOT_DIR}/reports/${SCAN_ID}"
CLONE_DIR="${REPORTS_DIR}/source"

mkdir -p "$REPORTS_DIR"
mkdir -p "$CLONE_DIR"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting SAST scan"
echo "  Repo   : $REPO_URL"
echo "  Scan ID: $SCAN_ID"
echo "  Output : $REPORTS_DIR"

# ─── コードクローン ──────────────────────────────────────────────────────────
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Cloning repository..."
if [ -d "${CLONE_DIR}/.git" ]; then
  echo "  Already cloned. Pulling latest changes..."
  git -C "$CLONE_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO_URL" "$CLONE_DIR"
fi

# ─── semgrep スキャン ────────────────────────────────────────────────────────
SAST_REPORT="${REPORTS_DIR}/sast_report.json"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Running Semgrep..."

# semgrep が存在するか確認
if ! command -v semgrep &>/dev/null; then
  echo "Error: semgrep is not installed. Run: pip install semgrep" >&2
  exit 1
fi

semgrep \
  --config=auto \
  --json \
  --output="$SAST_REPORT" \
  "$CLONE_DIR" \
  || true  # 検出があっても終了コード 1 になるため続行

# ─── メタデータ付与 ──────────────────────────────────────────────────────────
REPO_NAME=$(basename "$REPO_URL" .git)
COMMIT_SHA=$(git -C "$CLONE_DIR" rev-parse HEAD 2>/dev/null || echo "unknown")
SCANNED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# jq が利用可能であれば、メタデータをマージする
if command -v jq &>/dev/null && [ -f "$SAST_REPORT" ]; then
  TEMP_FILE=$(mktemp)
  jq \
    --arg scan_id "$SCAN_ID" \
    --arg repo_url "$REPO_URL" \
    --arg repo_name "$REPO_NAME" \
    --arg commit_sha "$COMMIT_SHA" \
    --arg scanned_at "$SCANNED_AT" \
    '. + {
      scan_id: $scan_id,
      repo_url: $repo_url,
      repo_name: $repo_name,
      commit_sha: $commit_sha,
      scanned_at: $scanned_at
    }' \
    "$SAST_REPORT" > "$TEMP_FILE"
  mv "$TEMP_FILE" "$SAST_REPORT"
fi

# ─── サマリー表示 ────────────────────────────────────────────────────────────
if command -v jq &>/dev/null && [ -f "$SAST_REPORT" ]; then
  FINDING_COUNT=$(jq '.results | length' "$SAST_REPORT" 2>/dev/null || echo "unknown")
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Scan complete. Findings: ${FINDING_COUNT}"
else
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Scan complete."
fi

echo "  Report saved to: $SAST_REPORT"
