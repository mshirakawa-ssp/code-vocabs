#!/usr/bin/env bash
# reporter/generate_report.sh
# SASTレポートと検証結果JSONからHTMLレポートを生成します。
# 使用方法: ./generate_report.sh <scan-id>
#
# 依存: jq

set -euo pipefail

# ─── 引数チェック ──────────────────────────────────────────────────────────────
if [ $# -lt 1 ]; then
  echo "Usage: $0 <scan-id>" >&2
  exit 1
fi

SCAN_ID="$1"

# ─── 入力バリデーション ───────────────────────────────────────────────────────
# SCAN_ID にパストラバーサル・シェルメタキャラクタが含まれていないか確認する
if [[ ! "$SCAN_ID" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Error: SCAN_ID contains invalid characters: $SCAN_ID" >&2
  exit 1
fi

# ─── ディレクトリ設定 ─────────────────────────────────────────────────────────
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SCAN_DIR="${ROOT_DIR}/reports/${SCAN_ID}"
SAST_REPORT="${SCAN_DIR}/sast_report.json"
VERIFICATION="${SCAN_DIR}/verification.json"
FIX_SUGGESTIONS="${SCAN_DIR}/fix_suggestions.json"
TEMPLATE="${SCRIPT_DIR}/templates/report_template.html"
OUTPUT="${SCAN_DIR}/final_report.html"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Generating final report for scan: $SCAN_ID"

# ─── 入力ファイル確認 ────────────────────────────────────────────────────────
if [ ! -f "$SAST_REPORT" ]; then
  echo "Error: sast_report.json not found: $SAST_REPORT" >&2
  exit 1
fi

# ─── データ抽出 (jq) ─────────────────────────────────────────────────────────
if ! command -v jq &>/dev/null; then
  echo "Error: jq is not installed." >&2
  exit 1
fi

REPO_URL=$(jq -r '.repo_url // "unknown"' "$SAST_REPORT")
REPO_NAME=$(jq -r '.repo_name // "unknown"' "$SAST_REPORT")
COMMIT_SHA=$(jq -r '.commit_sha // "unknown"' "$SAST_REPORT")
SCANNED_AT=$(jq -r '.scanned_at // "unknown"' "$SAST_REPORT")
FINDING_COUNT=$(jq '.results | length' "$SAST_REPORT")
GENERATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

HIGH_COUNT=$(jq '[.results[] | select(.extra.severity == "ERROR" or .extra.severity == "HIGH")] | length' "$SAST_REPORT")
MEDIUM_COUNT=$(jq '[.results[] | select(.extra.severity == "WARNING" or .extra.severity == "MEDIUM")] | length' "$SAST_REPORT")
LOW_COUNT=$(jq '[.results[] | select(.extra.severity == "INFO" or .extra.severity == "LOW")] | length' "$SAST_REPORT")

VERIFIED_COUNT=0
FIX_COUNT=0
PR_URL="N/A"

if [ -f "$VERIFICATION" ]; then
  VERIFIED_COUNT=$(jq '.browser_results | length' "$VERIFICATION")
fi
if [ -f "$FIX_SUGGESTIONS" ]; then
  FIX_COUNT=$(jq '. | length' "$FIX_SUGGESTIONS")
fi
if [ -f "${SCAN_DIR}/pr_info.json" ]; then
  PR_URL=$(jq -r '.pr_url // "N/A"' "${SCAN_DIR}/pr_info.json")
fi

# ─── SAST検出結果の行テーブル生成 ────────────────────────────────────────────
FINDINGS_ROWS=$(jq -r '
  .results[] |
  "<tr>" +
  "<td><code>" + (.check_id // "N/A") + "</code></td>" +
  "<td>" + (.path // "N/A") + ":" + ((.start.line // 0) | tostring) + "</td>" +
  "<td><span class=\"badge bg-" +
    (if (.extra.severity == "ERROR" or .extra.severity == "HIGH") then "danger"
     elif (.extra.severity == "WARNING" or .extra.severity == "MEDIUM") then "warning text-dark"
     else "secondary"
     end) + "\">" + (.extra.severity // "INFO") + "</span></td>" +
  "<td>" + ((.extra.message // "") | gsub("<"; "&lt;") | gsub(">"; "&gt;")) + "</td>" +
  "</tr>"
' "$SAST_REPORT" || echo "<tr><td colspan=\"4\">検出なし</td></tr>")

# ─── 修整案の行テーブル生成 ──────────────────────────────────────────────────
FIX_ROWS="<tr><td colspan=\"3\">修整案なし</td></tr>"
if [ -f "$FIX_SUGGESTIONS" ]; then
  FIX_ROWS=$(jq -r '
    .[] |
    "<tr>" +
    "<td><span class=\"badge bg-" +
      (if .severity == "HIGH" then "danger"
       elif .severity == "MEDIUM" then "warning text-dark"
       else "secondary"
       end) + "\">" + .severity + "</span></td>" +
    "<td><strong>" + (.title // "N/A") + "</strong><br><small><code>" + (.file_path // "") + "</code></small></td>" +
    "<td>" + ((.description // "") | gsub("<"; "&lt;") | gsub(">"; "&gt;")) + "</td>" +
    "</tr>"
  ' "$FIX_SUGGESTIONS" || echo "<tr><td colspan=\"3\">修整案なし</td></tr>")
fi

# ─── HTMLレポート生成 ────────────────────────────────────────────────────────
cat > "$OUTPUT" << HTMLEOF
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>脆弱性診断レポート - ${SCAN_ID}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #f8f9fa; }
    .stat-card { border-radius: 12px; }
    .severity-high { border-left: 4px solid #dc3545; }
    .severity-medium { border-left: 4px solid #ffc107; }
    .severity-low { border-left: 4px solid #6c757d; }
    pre { background: #212529; color: #f8f9fa; padding: 1rem; border-radius: 8px; font-size: 0.85em; }
  </style>
</head>
<body>
<div class="container py-4">

  <div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3">🔒 脆弱性診断レポート</h1>
    <span class="badge bg-secondary fs-6">${SCAN_ID}</span>
  </div>

  <!-- サマリー情報 -->
  <div class="card mb-4">
    <div class="card-header">診断サマリー</div>
    <div class="card-body">
      <table class="table table-sm mb-0">
        <tr><th>リポジトリ</th><td><a href="${REPO_URL}">${REPO_NAME}</a></td></tr>
        <tr><th>コミット</th><td><code>${COMMIT_SHA}</code></td></tr>
        <tr><th>スキャン日時</th><td>${SCANNED_AT}</td></tr>
        <tr><th>レポート生成日時</th><td>${GENERATED_AT}</td></tr>
        <tr><th>GitHubPR</th><td><a href="${PR_URL}">${PR_URL}</a></td></tr>
      </table>
    </div>
  </div>

  <!-- 統計カード -->
  <div class="row g-3 mb-4">
    <div class="col-md-3">
      <div class="card stat-card text-center p-3 severity-high">
        <div class="fs-1 fw-bold text-danger">${HIGH_COUNT}</div>
        <div class="text-muted">HIGH / ERROR</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="card stat-card text-center p-3 severity-medium">
        <div class="fs-1 fw-bold text-warning">${MEDIUM_COUNT}</div>
        <div class="text-muted">MEDIUM / WARNING</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="card stat-card text-center p-3 severity-low">
        <div class="fs-1 fw-bold text-secondary">${LOW_COUNT}</div>
        <div class="text-muted">LOW / INFO</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="card stat-card text-center p-3">
        <div class="fs-1 fw-bold text-success">${FIX_COUNT}</div>
        <div class="text-muted">修整案</div>
      </div>
    </div>
  </div>

  <!-- SAST検出結果 -->
  <div class="card mb-4">
    <div class="card-header d-flex justify-content-between">
      <span>SAST検出結果</span>
      <span class="badge bg-primary">${FINDING_COUNT} 件</span>
    </div>
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-hover table-sm mb-0">
          <thead class="table-dark">
            <tr>
              <th>ルールID</th>
              <th>ファイル:行</th>
              <th>重要度</th>
              <th>説明</th>
            </tr>
          </thead>
          <tbody>
${FINDINGS_ROWS}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- 修整案 -->
  <div class="card mb-4">
    <div class="card-header d-flex justify-content-between">
      <span>修整案</span>
      <span class="badge bg-success">${FIX_COUNT} 件</span>
    </div>
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-hover table-sm mb-0">
          <thead class="table-dark">
            <tr>
              <th>重要度</th>
              <th>タイトル・ファイル</th>
              <th>説明</th>
            </tr>
          </thead>
          <tbody>
${FIX_ROWS}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <p class="text-center text-muted small mt-4">
    このレポートはAI脆弱性診断システムによって自動生成されました。
  </p>
</div>
</body>
</html>
HTMLEOF

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Report generated: ${OUTPUT}"
