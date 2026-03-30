# 脆弱性診断システム アーキテクチャ設計

## システム概要

本システムは、GitHubリポジトリの脆弱性を自動で診断し、修整案をPRで提案する自動化システムです。

```
┌─────────────────────────────────────────────────────────────────┐
│                         管理ダッシュボード                         │
│  (スケジュール設定 / リポジトリ管理 / レポート確認 / ステータス更新)  │
└────────────────────────────┬────────────────────────────────────┘
                             │ スケジュール起動 / 手動起動
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        タスクキュー (PostgreSQL)                   │
└────────┬────────────────────────────────────────────────────────┘
         │
   ┌─────▼──────┐     ┌──────────────┐     ┌─────────────────┐
   │  1. Scanner │────▶│  2. AI Agent │────▶│  3. Reporter    │
   │  (Shell)   │     │  (Python)    │     │  (Shell)        │
   └────────────┘     └──────────────┘     └─────────────────┘
        │                    │                      │
        ▼                    ▼                      ▼
   sast_report.json   verification.json      final_report.html
                             │
                             ▼
                      GitHub PR (修整案)
```

## コンポーネント詳細

### 1. Scanner（SAST自動スキャン）

**役割**: コードをクローンし、OSSのSASTツールでスキャンしてJSON形式でレポートを出力

**技術スタック**:
- Semgrep（無料・OSS・多言語対応）
- Bashスクリプト

**処理フロー**:
```
git clone → semgrep scan → sast_report.json
```

**ファイル**: `scanner/scan.sh`

---

### 2. AI Agent（AI分析 + ヘッドレスブラウザ検証）

**役割**: SASTレポートを読み込み、手動検証計画を策定し、ヘッドレスブラウザで実際に検証を実施

**技術スタック**:
- Python 3.11
- Qwen 3.5（または OpenAI 互換 API）
- Playwright（ヘッドレスブラウザ）
- GitHub API（PR作成）

**処理フロー**:
```
sast_report.json 
  → AI: 手動検証計画の策定
  → Playwright: ログイン・検証実施
  → verification.json 出力
  → AI: 修整案の生成
  → GitHub PR作成
```

**ファイル**: `ai-agent/agent.py`

---

### 3. Reporter（最終レポート生成）

**役割**: 検証結果JSONから人が読めるHTMLレポートを生成

**技術スタック**:
- Bashスクリプト
- jq（JSON処理）
- HTMLテンプレート

**ファイル**: `reporter/generate_report.sh`

---

### 4. Dashboard（管理画面）

**役割**: スケジュール設定、レポート確認、ステータス更新

**技術スタック**:
- Python / Flask
- PostgreSQL
- Bootstrap 5

**機能**:
- ログイン認証
- 診断スケジュール設定（cron形式）
- GitHubリポジトリ管理（URLとトークン）
- 診断レポート一覧・詳細確認
- 検出結果のステータス管理（未対応 / 対応済み / 対応不要 / 誤検知）
- PR連携表示

**ファイル**: `dashboard/app.py`, `dashboard/templates/`

---

## インフラ構成（スケール・コスト最適化）

```
インターネット
     │
     ▼
┌─────────────┐
│  Load       │   ← 必要なら追加
│  Balancer   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│  Public Subnet                  │
│  ┌──────────┐  ┌─────────────┐  │
│  │ Dashboard│  │  NAT GW     │  │ ← 固定IP出口
│  │ (常時起動)│  │ (Elastic IP)│  │
│  └──────────┘  └──────┬──────┘  │
└────────────────────────┼────────┘
                         │
┌────────────────────────┼────────┐
│  Private Subnet        │        │
│  ┌─────────┐  ┌────────▼─────┐  │
│  │PostgreSQL│  │ Scanner /    │  │ ← コンテナを必要時のみ起動
│  │(常時起動)│  │ AI Agent /   │  │   (ECS Fargate / Cloud Run)
│  └─────────┘  │ Reporter     │  │
│               └──────────────┘  │
└─────────────────────────────────┘
```

### コスト最適化戦略

| コンポーネント | 起動方式 | 理由 |
|---|---|---|
| Dashboard | 常時起動（小インスタンス） | ユーザーアクセスのため |
| PostgreSQL | 常時起動（小インスタンス） | 設定・履歴保持のため |
| Scanner | 診断時のみ起動 | 重い処理・高コスト |
| AI Agent | 診断時のみ起動 | API課金のため必要時のみ |
| Reporter | 診断時のみ起動 | 軽量だが診断後のみ必要 |

**推奨クラウドサービス**:
- AWS: ECS Fargate（Scanner/AI Agent/Reporter をオンデマンド起動）+ RDS PostgreSQL（t3.micro）
- GCP: Cloud Run（自動スケール + 起動時のみ課金）
- セルフホスト: Docker Compose + GitHub Actions Webhook

### 固定IP（アウトバウンド）

診断対象のサーバーにIPホワイトリスト登録が必要な場合：
- AWS: NAT Gateway + Elastic IP
- GCP: Cloud NAT + 静的外部IP

---

## セキュリティ考慮事項

1. **認証情報管理**: `.env` ファイルまたはクラウドのシークレットマネージャー（AWS Secrets Manager / GCP Secret Manager）
2. **ダッシュボード認証**: JWT + bcryptハッシュ
3. **ネットワーク分離**: ScannerとAI AgentはPrivate Subnetに配置
4. **監査ログ**: 全操作をDBに記録
5. **APIキー管理**: Qwen/OpenAI APIキーはシークレット管理

---

## データフロー

```
診断開始
  │
  ├─ [scanner/scan.sh]
  │    ├── git clone <対象リポジトリ>
  │    ├── semgrep --config=auto --json
  │    └── → reports/<scan_id>/sast_report.json
  │
  ├─ [ai-agent/agent.py]
  │    ├── sast_report.json を読み込み
  │    ├── AI: 脆弱性分析・手動検証計画の策定
  │    ├── Playwright: ヘッドレスブラウザで検証
  │    ├── AI: 修整案生成
  │    ├── GitHub API: PR作成
  │    └── → reports/<scan_id>/verification.json
  │
  └─ [reporter/generate_report.sh]
       ├── sast_report.json + verification.json を結合
       └── → reports/<scan_id>/final_report.html
```

---

## 環境変数

`.env.example` を参照してください。

---

## 起動手順

```bash
# 1. 設定
cp .env.example .env
# .env を編集してAPIキー等を設定

# 2. 起動（開発環境）
docker-compose up -d

# 3. ブラウザで管理画面にアクセス
open http://localhost:5000

# 4. 手動で診断を実行（CLIから）
./scanner/scan.sh <github-repo-url> <scan-id>
python ai-agent/agent.py <scan-id>
./reporter/generate_report.sh <scan-id>
```
