"""
dashboard/app.py

脆弱性診断システム 管理ダッシュボード
- ログイン認証 (bcrypt + session)
- GitHubリポジトリ管理
- 診断スケジュール設定 (cron形式)
- 診断レポート一覧・詳細確認
- 検出結果のステータス管理
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")

# ─── データベース設定 ─────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{BASE_DIR / 'database' / 'app.db'}"
)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


# ─── モデル定義 ───────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode(), self.password_hash.encode()
        )


class Repository(db.Model):
    __tablename__ = "repositories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    url = db.Column(db.String(512), nullable=False)
    schedule = db.Column(db.String(64), default="0 2 * * *")  # cron形式
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    scans = db.relationship("Scan", backref="repository", lazy=True)


class Scan(db.Model):
    __tablename__ = "scans"
    id = db.Column(db.String(64), primary_key=True)
    repository_id = db.Column(db.Integer, db.ForeignKey("repositories.id"), nullable=False)
    status = db.Column(
        db.String(32), default="pending"
    )  # pending / scanning / ai_analysis / reporting / done / error
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    finding_count = db.Column(db.Integer, default=0)
    pr_url = db.Column(db.String(512), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    findings = db.relationship("Finding", backref="scan", lazy=True)


class Finding(db.Model):
    __tablename__ = "findings"
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.String(64), db.ForeignKey("scans.id"), nullable=False)
    rule_id = db.Column(db.String(256), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    line_number = db.Column(db.Integer, default=0)
    severity = db.Column(db.String(16), default="INFO")
    message = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.String(32), default="open"
    )  # open / fixed / wont_fix / false_positive
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# ─── ログイン必須デコレータ ───────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


# ─── 認証 ─────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("dashboard"))
        flash("ユーザー名またはパスワードが正しくありません", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── ダッシュボード ─────────────────────────────────────────────────────────
@app.route("/")
@login_required
def dashboard():
    recent_scans = (
        Scan.query.order_by(Scan.started_at.desc()).limit(10).all()
    )
    repos = Repository.query.filter_by(enabled=True).all()
    total_findings = Finding.query.filter_by(status="open").count()
    return render_template(
        "dashboard.html",
        recent_scans=recent_scans,
        repos=repos,
        total_findings=total_findings,
    )


# ─── リポジトリ管理 ───────────────────────────────────────────────────────────
@app.route("/repositories")
@login_required
def repositories():
    repos = Repository.query.order_by(Repository.created_at.desc()).all()
    return render_template("repositories.html", repos=repos)


@app.route("/repositories/new", methods=["GET", "POST"])
@login_required
def new_repository():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        url = request.form.get("url", "").strip()
        schedule = request.form.get("schedule", "0 2 * * *").strip()

        if not name or not url:
            flash("リポジトリ名とURLは必須です", "danger")
            return render_template("repository_form.html", repo=None)

        repo = Repository(name=name, url=url, schedule=schedule)
        db.session.add(repo)
        db.session.commit()
        flash(f"リポジトリ「{name}」を追加しました", "success")
        return redirect(url_for("repositories"))

    return render_template("repository_form.html", repo=None)


@app.route("/repositories/<int:repo_id>/edit", methods=["GET", "POST"])
@login_required
def edit_repository(repo_id: int):
    repo = Repository.query.get_or_404(repo_id)
    if request.method == "POST":
        repo.name = request.form.get("name", repo.name).strip()
        repo.url = request.form.get("url", repo.url).strip()
        repo.schedule = request.form.get("schedule", repo.schedule).strip()
        repo.enabled = "enabled" in request.form
        db.session.commit()
        flash("リポジトリを更新しました", "success")
        return redirect(url_for("repositories"))
    return render_template("repository_form.html", repo=repo)


@app.route("/repositories/<int:repo_id>/delete", methods=["POST"])
@login_required
def delete_repository(repo_id: int):
    repo = Repository.query.get_or_404(repo_id)
    db.session.delete(repo)
    db.session.commit()
    flash("リポジトリを削除しました", "success")
    return redirect(url_for("repositories"))


@app.route("/repositories/<int:repo_id>/scan", methods=["POST"])
@login_required
def trigger_scan(repo_id: int):
    repo = Repository.query.get_or_404(repo_id)

    scan_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + f"-{repo_id}"
    scan = Scan(
        id=scan_id,
        repository_id=repo.id,
        status="pending",
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(scan)
    db.session.commit()

    # バックグラウンドでスキャン開始
    _run_scan_async(scan_id, repo.url)

    flash(f"診断を開始しました (Scan ID: {scan_id})", "success")
    return redirect(url_for("scan_detail", scan_id=scan_id))


def _run_scan_async(scan_id: str, repo_url: str) -> None:
    """スキャンをバックグラウンドで非同期実行する。"""
    scanner = BASE_DIR / "scanner" / "scan.sh"
    agent = BASE_DIR / "ai-agent" / "agent.py"
    reporter = BASE_DIR / "reporter" / "generate_report.sh"
    log_path = REPORTS_DIR / scan_id / "run.log"
    (REPORTS_DIR / scan_id).mkdir(parents=True, exist_ok=True)

    # シェルインジェクションを防ぐため、コマンドは引数リストで渡す
    # 3つのステップをシェルスクリプトで連結せず、ラッパースクリプトで順番に実行する
    runner_script = REPORTS_DIR / scan_id / "_runner.sh"
    runner_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -e\n"
        f"bash {scanner} \"$1\" \"$2\" >> \"$3\" 2>&1\n"
        f"python {agent} \"$2\" >> \"$3\" 2>&1\n"
        f"bash {reporter} \"$2\" >> \"$3\" 2>&1\n",
        encoding="utf-8",
    )
    runner_script.chmod(0o700)

    subprocess.Popen(
        [str(runner_script), repo_url, scan_id, str(log_path)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ─── スキャン詳細 ─────────────────────────────────────────────────────────────
@app.route("/scans")
@login_required
def scans():
    all_scans = Scan.query.order_by(Scan.started_at.desc()).all()
    return render_template("scans.html", scans=all_scans)


@app.route("/scans/<scan_id>")
@login_required
def scan_detail(scan_id: str):
    scan = Scan.query.get_or_404(scan_id)

    # レポートファイルを直接読み込む（DBにインポートされていない場合の表示用）
    sast_report = None
    final_report_exists = False
    sast_path = REPORTS_DIR / scan_id / "sast_report.json"
    final_path = REPORTS_DIR / scan_id / "final_report.html"

    if sast_path.exists():
        try:
            sast_report = json.loads(sast_path.read_text())
        except json.JSONDecodeError:
            pass

    final_report_exists = final_path.exists()

    findings = Finding.query.filter_by(scan_id=scan_id).all()

    return render_template(
        "scan_detail.html",
        scan=scan,
        sast_report=sast_report,
        final_report_exists=final_report_exists,
        findings=findings,
    )


@app.route("/scans/<scan_id>/report")
@login_required
def view_report(scan_id: str):
    """生成済みHTMLレポートを表示する。"""
    report_path = REPORTS_DIR / scan_id / "final_report.html"
    if not report_path.exists():
        flash("レポートがまだ生成されていません", "warning")
        return redirect(url_for("scan_detail", scan_id=scan_id))
    return report_path.read_text(), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/scans/<scan_id>/log")
@login_required
def view_log(scan_id: str):
    """診断実行ログを表示する。"""
    log_path = REPORTS_DIR / scan_id / "run.log"
    content = log_path.read_text() if log_path.exists() else "ログがありません"
    return render_template("log_view.html", scan_id=scan_id, log_content=content)


# ─── 検出結果ステータス更新 ───────────────────────────────────────────────────
@app.route("/findings/<int:finding_id>/status", methods=["POST"])
@login_required
def update_finding_status(finding_id: int):
    finding = Finding.query.get_or_404(finding_id)
    new_status = request.json.get("status") if request.is_json else request.form.get("status")

    valid_statuses = {"open", "fixed", "wont_fix", "false_positive"}
    if new_status not in valid_statuses:
        return jsonify({"error": "Invalid status"}), 400

    finding.status = new_status
    finding.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    if request.is_json:
        return jsonify({"ok": True, "status": finding.status})
    flash("ステータスを更新しました", "success")
    return redirect(request.referrer or url_for("scans"))


# ─── 設定画面 ─────────────────────────────────────────────────────────────────
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        for key in ("scan_window_start", "scan_window_end", "notification_email"):
            value = request.form.get(key, "").strip()
            if value:
                setting = Setting.query.get(key)
                if setting:
                    setting.value = value
                    setting.updated_at = datetime.now(timezone.utc)
                else:
                    db.session.add(Setting(key=key, value=value))
        db.session.commit()
        flash("設定を保存しました", "success")
        return redirect(url_for("settings"))

    all_settings = {s.key: s.value for s in Setting.query.all()}
    return render_template("settings.html", settings=all_settings)


# ─── API: スキャン状態確認 ───────────────────────────────────────────────────
@app.route("/api/scans/<scan_id>/status")
@login_required
def api_scan_status(scan_id: str):
    scan = Scan.query.get_or_404(scan_id)
    return jsonify(
        {
            "scan_id": scan.id,
            "status": scan.status,
            "finding_count": scan.finding_count,
            "pr_url": scan.pr_url,
        }
    )


# ─── 初期化 ───────────────────────────────────────────────────────────────────
def init_db():
    """データベースとデフォルトユーザーを初期化する。"""
    with app.app_context():
        db.create_all()

        # デフォルト管理者ユーザー作成 (初回のみ)
        if User.query.count() == 0:
            default_password = os.environ.get("ADMIN_PASSWORD", "change-me")
            hashed = bcrypt.hashpw(
                default_password.encode(), bcrypt.gensalt()
            ).decode()
            admin = User(username="admin", password_hash=hashed)
            db.session.add(admin)
            db.session.commit()
            print(f"[Init] Default admin user created (password: {default_password})")

        # デフォルト設定
        for key, value in {
            "scan_window_start": "02:00",
            "scan_window_end": "05:00",
            "notification_email": "",
        }.items():
            if not Setting.query.get(key):
                db.session.add(Setting(key=key, value=value))
        db.session.commit()


if __name__ == "__main__":
    init_db()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
