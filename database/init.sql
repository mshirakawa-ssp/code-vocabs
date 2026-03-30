-- database/init.sql
-- PostgreSQL 用の初期スキーマ
-- (SQLAlchemy の db.create_all() でも同等のテーブルが自動作成されます)

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    url VARCHAR(512) NOT NULL,
    schedule VARCHAR(64) DEFAULT '0 2 * * *',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scans (
    id VARCHAR(64) PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
    status VARCHAR(32) DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    finding_count INTEGER DEFAULT 0,
    pr_url VARCHAR(512),
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS findings (
    id SERIAL PRIMARY KEY,
    scan_id VARCHAR(64) REFERENCES scans(id) ON DELETE CASCADE,
    rule_id VARCHAR(256) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    line_number INTEGER DEFAULT 0,
    severity VARCHAR(16) DEFAULT 'INFO',
    message TEXT NOT NULL,
    status VARCHAR(32) DEFAULT 'open',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(64) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status);
CREATE INDEX IF NOT EXISTS idx_findings_scan_id ON findings(scan_id);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
