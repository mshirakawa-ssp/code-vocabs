#!/usr/bin/env python3
"""
ai-agent/agent.py

SASTレポートを読み込み、以下を行います:
  1. AIによる脆弱性分析・手動検証計画の策定
  2. Playwrightによるヘッドレスブラウザ検証
  3. 検証結果をJSONで出力
  4. AIによる修整案生成
  5. GitHub APIでPR作成

使用方法:
  python agent.py <scan-id>

必要な環境変数 (.env ファイルに設定):
  OPENAI_API_BASE   - OpenAI互換APIのエンドポイント (例: Qwen 3.5)
  OPENAI_API_KEY    - APIキー
  OPENAI_MODEL      - 使用するモデル名 (例: qwen3.5)
  GITHUB_TOKEN      - GitHub Personal Access Token (PR作成に必要)
  TARGET_BASE_URL   - 検証対象のベースURL (例: https://example.com)
  TARGET_USERNAME   - 検証用ログインID
  TARGET_PASSWORD   - 検証用パスワード
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from playwright.sync_api import sync_playwright

load_dotenv(Path(__file__).parent.parent / ".env")

# ─── 設定 ──────────────────────────────────────────────────────────────────────
REPORTS_DIR = Path(__file__).parent.parent / "reports"

OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TARGET_BASE_URL = os.environ.get("TARGET_BASE_URL", "")
TARGET_USERNAME = os.environ.get("TARGET_USERNAME", "")
TARGET_PASSWORD = os.environ.get("TARGET_PASSWORD", "")


# ─── AI クライアント初期化 ───────────────────────────────────────────────────
def create_ai_client() -> OpenAI:
    return OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE,
    )


# ─── 1. 検証計画の策定 ────────────────────────────────────────────────────────
def plan_verification(client: OpenAI, sast_report: dict) -> list[dict]:
    """SASTレポートを読み込み、手動検証が必要な項目の計画を立てる。"""

    findings = sast_report.get("results", [])
    if not findings:
        print("[AI] No findings to analyze.")
        return []

    findings_summary = json.dumps(findings[:50], ensure_ascii=False, indent=2)

    prompt = (
        "あなたはセキュリティエンジニアです。\n"
        "以下のSASTスキャン結果を分析し、ヘッドレスブラウザを使って手動検証が必要な項目を特定してください。\n"
        "各検証項目について以下のJSONフォーマットで返してください:\n"
        "[\n"
        "  {\n"
        '    "finding_id": "<semgrep finding のcheck_id>",\n'
        '    "severity": "HIGH|MEDIUM|LOW",\n'
        '    "description": "<脆弱性の説明>",\n'
        '    "verification_type": "browser|manual|skip",\n'
        '    "browser_steps": [\n'
        '      {"action": "navigate", "url": "<URL>"},\n'
        '      {"action": "fill", "selector": "<CSS selector>", "value": "<値>"},\n'
        '      {"action": "click", "selector": "<CSS selector>"},\n'
        '      {"action": "assert", "selector": "<CSS selector>", "expected": "<期待値>"}\n'
        "    ],\n"
        '    "reason": "<なぜこの検証が必要か>"\n'
        "  }\n"
        "]\n\n"
        "JSONのみを返してください（説明文は不要）。\n\n"
        f"SASTスキャン結果:\n{findings_summary}"
    )

    print("[AI] Planning verification steps...")
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    content = response.choices[0].message.content or "[]"
    parsed = json.loads(content)

    # レスポンスがリストまたはオブジェクト（"items" キーなど）の場合に対応
    if isinstance(parsed, list):
        return parsed
    for key in ("items", "findings", "verifications", "results"):
        if key in parsed and isinstance(parsed[key], list):
            return parsed[key]
    return []


# ─── 2. ヘッドレスブラウザ検証 ────────────────────────────────────────────────
def run_browser_verification(plan: list[dict]) -> list[dict]:
    """Playwrightでヘッドレスブラウザ検証を実施する。"""

    results = []

    browser_items = [p for p in plan if p.get("verification_type") == "browser"]
    if not browser_items:
        print("[Browser] No browser verification steps to run.")
        return results

    print(f"[Browser] Running {len(browser_items)} browser verification(s)...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            ignore_https_errors=True,
        )

        # ログイン（対象URLが設定されている場合）
        if TARGET_BASE_URL and TARGET_USERNAME and TARGET_PASSWORD:
            page = context.new_page()
            try:
                _login(page)
            except Exception as e:
                print(f"[Browser] Login failed: {e}")
                browser.close()
                return results
        else:
            page = context.new_page()

        for item in browser_items:
            finding_id = item.get("finding_id", "unknown")
            steps = item.get("browser_steps", [])
            result = {
                "finding_id": finding_id,
                "severity": item.get("severity", "UNKNOWN"),
                "description": item.get("description", ""),
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "status": "not_verified",
                "evidence": [],
                "error": None,
            }

            try:
                for step in steps:
                    action = step.get("action")
                    if action == "navigate":
                        url = step.get("url", "").replace("{{BASE_URL}}", TARGET_BASE_URL)
                        page.goto(url, timeout=15000)
                    elif action == "fill":
                        page.fill(step["selector"], step.get("value", ""))
                    elif action == "click":
                        page.click(step["selector"])
                    elif action == "assert":
                        element = page.query_selector(step["selector"])
                        text = element.inner_text() if element else ""
                        expected = step.get("expected", "")
                        if expected in text:
                            result["evidence"].append(
                                {"step": step, "actual": text, "passed": True}
                            )
                        else:
                            result["evidence"].append(
                                {"step": step, "actual": text, "passed": False}
                            )

                result["status"] = "verified"
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
                print(f"[Browser]   [{finding_id}] Error: {e}")

            results.append(result)
            print(f"[Browser]   [{finding_id}] Status: {result['status']}")

        browser.close()

    return results


def _login(page) -> None:
    """対象サービスにログインする。"""
    login_url = TARGET_BASE_URL.rstrip("/") + "/login"
    page.goto(login_url, timeout=15000)
    page.fill('input[name="username"], input[type="email"]', TARGET_USERNAME)
    page.fill('input[name="password"], input[type="password"]', TARGET_PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=10000)


# ─── 3. 検証結果を保存 ────────────────────────────────────────────────────────
def save_verification_report(
    scan_id: str, plan: list[dict], browser_results: list[dict]
) -> Path:
    """検証結果をJSONに保存する。"""
    report = {
        "scan_id": scan_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
        "browser_results": browser_results,
    }

    output_path = REPORTS_DIR / scan_id / "verification.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[Report] Verification report saved: {output_path}")
    return output_path


# ─── 4. 修整案の生成 ──────────────────────────────────────────────────────────
def generate_fix_suggestions(
    client: OpenAI, sast_report: dict, verification: dict
) -> list[dict]:
    """SASTと検証結果から修整案を生成する。"""

    findings = sast_report.get("results", [])
    browser_results = verification.get("browser_results", [])

    if not findings:
        return []

    summary = json.dumps(
        {"findings": findings[:20], "browser_results": browser_results},
        ensure_ascii=False,
        indent=2,
    )

    prompt = (
        "あなたはセキュリティエンジニアです。\n"
        "以下の脆弱性診断結果を基に、修整案を作成してください。\n"
        "各修整案を以下のJSONフォーマットで返してください:\n"
        "[\n"
        "  {\n"
        '    "finding_id": "<check_id>",\n'
        '    "file_path": "<修正対象ファイルパス>",\n'
        '    "severity": "HIGH|MEDIUM|LOW",\n'
        '    "title": "<修整案タイトル>",\n'
        '    "description": "<詳細な説明>",\n'
        '    "original_code": "<修正前コード>",\n'
        '    "fixed_code": "<修正後コード>",\n'
        '    "explanation": "<修正理由>"\n'
        "  }\n"
        "]\n\n"
        "JSONのみを返してください。\n\n"
        f"診断結果:\n{summary}"
    )

    print("[AI] Generating fix suggestions...")
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    content = response.choices[0].message.content or "[]"
    parsed = json.loads(content)

    if isinstance(parsed, list):
        return parsed
    for key in ("items", "fixes", "suggestions", "results"):
        if key in parsed and isinstance(parsed[key], list):
            return parsed[key]
    return []


# ─── 5. GitHub PR作成 ─────────────────────────────────────────────────────────
def create_github_pr(
    sast_report: dict, fix_suggestions: list[dict]
) -> str | None:
    """修整案を含むGitHub PRを作成する。"""

    if not GITHUB_TOKEN:
        print("[GitHub] GITHUB_TOKEN not set. Skipping PR creation.")
        return None

    if not fix_suggestions:
        print("[GitHub] No fix suggestions. Skipping PR creation.")
        return None

    repo_url = sast_report.get("repo_url", "")
    if not repo_url:
        print("[GitHub] repo_url not found in SAST report. Skipping PR creation.")
        return None

    # GitHubリポジトリのオーナーとリポジトリ名を抽出
    # 例: https://github.com/owner/repo → owner/repo
    import re
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", repo_url)
    if not match:
        print(f"[GitHub] Could not parse repo from URL: {repo_url}")
        return None

    repo_full_name = match.group(1)
    scan_id = sast_report.get("scan_id", "unknown")
    branch_name = f"fix/security-{scan_id}"

    # PR本文を生成
    pr_body = _build_pr_body(sast_report, fix_suggestions)

    import urllib.request

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # デフォルトブランチ取得
    repo_api_url = f"https://api.github.com/repos/{repo_full_name}"
    req = urllib.request.Request(repo_api_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        repo_info = json.loads(resp.read())
    default_branch = repo_info.get("default_branch", "main")

    # PR作成
    pr_data = json.dumps({
        "title": f"[Security] 脆弱性修整案 (Scan ID: {scan_id})",
        "body": pr_body,
        "head": branch_name,
        "base": default_branch,
    }).encode()

    pr_url = f"https://api.github.com/repos/{repo_full_name}/pulls"
    req = urllib.request.Request(pr_url, data=pr_data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req) as resp:
            pr_info = json.loads(resp.read())
        pr_html_url = pr_info.get("html_url", "")
        print(f"[GitHub] PR created: {pr_html_url}")
        return pr_html_url
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[GitHub] Failed to create PR: {e.code} {body}")
        return None


def _build_pr_body(sast_report: dict, fix_suggestions: list[dict]) -> str:
    """PR本文をMarkdown形式で生成する。"""
    scan_id = sast_report.get("scan_id", "unknown")
    scanned_at = sast_report.get("scanned_at", "unknown")
    finding_count = len(sast_report.get("results", []))

    lines = [
        "## 🔒 脆弱性診断レポート",
        "",
        f"- **スキャンID**: `{scan_id}`",
        f"- **スキャン日時**: {scanned_at}",
        f"- **検出件数**: {finding_count}",
        "",
        "---",
        "",
        "## 修整案",
        "",
    ]

    for suggestion in fix_suggestions:
        severity = suggestion.get("severity", "UNKNOWN")
        severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚪")
        lines += [
            f"### {severity_emoji} {suggestion.get('title', 'No Title')}",
            "",
            f"**ファイル**: `{suggestion.get('file_path', 'unknown')}`",
            f"**重要度**: {severity}",
            "",
            suggestion.get("description", ""),
            "",
        ]

        original = suggestion.get("original_code", "")
        fixed = suggestion.get("fixed_code", "")
        if original or fixed:
            lines += [
                "**修正前:**",
                "```",
                original,
                "```",
                "",
                "**修正後:**",
                "```",
                fixed,
                "```",
                "",
            ]

        explanation = suggestion.get("explanation", "")
        if explanation:
            lines += [f"**説明**: {explanation}", ""]

        lines.append("---")
        lines.append("")

    lines += [
        "> このPRはAI脆弱性診断システムによって自動生成されました。",
        "> 適用前に必ず内容を確認してください。",
    ]

    return "\n".join(lines)


# ─── メイン処理 ───────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python agent.py <scan-id>", file=sys.stderr)
        sys.exit(1)

    scan_id = sys.argv[1]
    scan_dir = REPORTS_DIR / scan_id
    sast_report_path = scan_dir / "sast_report.json"

    if not sast_report_path.exists():
        print(f"Error: SAST report not found: {sast_report_path}", file=sys.stderr)
        sys.exit(1)

    sast_report = json.loads(sast_report_path.read_text())
    print(f"[Agent] Loaded SAST report. Findings: {len(sast_report.get('results', []))}")

    client = create_ai_client()

    # 1. 検証計画策定
    plan = plan_verification(client, sast_report)
    print(f"[Agent] Verification plan: {len(plan)} item(s)")

    # 2. ヘッドレスブラウザ検証
    browser_results = run_browser_verification(plan)

    # 3. 検証結果を保存
    verification_path = save_verification_report(scan_id, plan, browser_results)
    verification = json.loads(verification_path.read_text())

    # 4. 修整案生成
    fix_suggestions = generate_fix_suggestions(client, sast_report, verification)
    print(f"[Agent] Fix suggestions: {len(fix_suggestions)} item(s)")

    # 修整案をJSONに保存
    fix_path = scan_dir / "fix_suggestions.json"
    fix_path.write_text(json.dumps(fix_suggestions, ensure_ascii=False, indent=2))
    print(f"[Agent] Fix suggestions saved: {fix_path}")

    # 5. GitHub PR作成
    pr_url = create_github_pr(sast_report, fix_suggestions)
    if pr_url:
        pr_info = {"pr_url": pr_url, "scan_id": scan_id}
        pr_path = scan_dir / "pr_info.json"
        pr_path.write_text(json.dumps(pr_info, ensure_ascii=False, indent=2))

    print("[Agent] Done.")


if __name__ == "__main__":
    main()
