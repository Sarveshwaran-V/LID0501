"""SQLite database initialization and connection management for LID0501."""

import sqlite3
from pathlib import Path
from typing import Generator
from contextlib import contextmanager

from lid.config import DEFAULT_DB_PATH


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    website_url TEXT NOT NULL,
    linkedin_company_url TEXT,
    headquarters TEXT DEFAULT 'Unavailable',
    business_category TEXT DEFAULT 'B2B Software',
    target_segment TEXT DEFAULT 'Unavailable',
    employee_count INTEGER,
    employee_count_type TEXT DEFAULT 'unavailable',
    funding_stage TEXT DEFAULT 'Unavailable',
    latest_funding_announcement TEXT,
    public_contact_method TEXT,
    status TEXT DEFAULT 'candidate',
    review_status TEXT DEFAULT 'pending',
    rejection_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    full_name TEXT DEFAULT 'Unavailable',
    current_role TEXT DEFAULT 'Unavailable',
    public_linkedin_url TEXT,
    public_business_email TEXT,
    contact_page_url TEXT,
    role_evidence_source TEXT,
    verification_status TEXT DEFAULT 'incomplete',
    last_verified_at TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS buying_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    signal_type TEXT NOT NULL,
    description TEXT NOT NULL,
    publication_date TEXT NOT NULL,
    original_source_url TEXT NOT NULL,
    source_publisher TEXT NOT NULL,
    retrieval_timestamp TEXT NOT NULL,
    verification_status TEXT DEFAULT 'verified',
    confidence_level TEXT DEFAULT 'high',
    uncertainty_notes TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    raw_snippet TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS qualification_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER UNIQUE NOT NULL,
    total_score REAL NOT NULL,
    icp_fit_score REAL NOT NULL,
    buying_signal_score REAL NOT NULL,
    commercial_opportunity_score REAL NOT NULL,
    decision_maker_score REAL NOT NULL,
    commercial_plausibility_score REAL NOT NULL,
    personalization_evidence_score REAL NOT NULL,
    classification TEXT NOT NULL,
    explanation TEXT NOT NULL,
    scored_at TEXT NOT NULL,
    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS outreach_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER UNIQUE NOT NULL,
    why_fit TEXT NOT NULL,
    relevant_buying_signal TEXT NOT NULL,
    signal_website_relevance TEXT NOT NULL,
    outreach_angle TEXT NOT NULL,
    opening_sentence TEXT NOT NULL,
    missing_verification_questions TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS manual_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    note_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS suppression_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE NOT NULL,
    company_name TEXT,
    reason TEXT DEFAULT 'User opt-out',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS export_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    export_format TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    exported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    query TEXT,
    status TEXT NOT NULL,
    candidates_found INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_companies_review ON companies(review_status);
CREATE INDEX IF NOT EXISTS idx_signals_company ON buying_signals(company_id);
"""


def init_db(db_path: Path | str | None = None) -> None:
    """Initialize database tables and schema."""
    target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(target_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


@contextmanager
def get_db_connection(db_path: Path | str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections with row factory."""
    target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    if not target_path.exists():
        init_db(target_path)
        
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
