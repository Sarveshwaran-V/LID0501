"""Database repository for CRUD, deduplication, and relationship queries."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from lid.db.database import get_db_connection
from lid.db.models import (
    Company,
    Contact,
    BuyingSignal,
    EvidenceSource,
    QualificationScore,
    OutreachNote,
    ManualNote,
)
from lid.security import normalize_domain


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LeadRepository:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = db_path

    def is_suppressed(self, domain: str) -> bool:
        norm_dom = normalize_domain(domain)
        with get_db_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT id FROM suppression_records WHERE domain = ?", (norm_dom,)
            ).fetchone()
            return row is not None

    def add_suppression(self, domain: str, company_name: Optional[str] = None, reason: str = "User opt-out") -> None:
        norm_dom = normalize_domain(domain)
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO suppression_records (domain, company_name, reason, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET reason = excluded.reason;
                """,
                (norm_dom, company_name, reason, now_iso()),
            )

    def upsert_company(self, company: Company) -> tuple[int, bool]:
        """Upsert company record with domain normalization and deduplication.
        
        Returns:
            (company_id, is_new)
        """
        norm_dom = normalize_domain(company.domain or company.website_url)
        if not norm_dom:
            raise ValueError(f"Cannot upsert company without valid domain or website: {company.name}")

        now = now_iso()
        with get_db_connection(self.db_path) as conn:
            existing = conn.execute(
                "SELECT * FROM companies WHERE domain = ?", (norm_dom,)
            ).fetchone()

            if existing:
                comp_id = existing["id"]
                # Non-destructive merge: only update fields if existing was 'Unavailable' or empty
                updates = []
                params = []

                if (existing["headquarters"] in ("Unavailable", "", None)) and company.headquarters not in ("Unavailable", "", None):
                    updates.append("headquarters = ?")
                    params.append(company.headquarters)

                if (existing["target_segment"] in ("Unavailable", "", None)) and company.target_segment not in ("Unavailable", "", None):
                    updates.append("target_segment = ?")
                    params.append(company.target_segment)

                # Only update employee count if existing is null or unavailable and incoming is valid
                if (existing["employee_count"] is None or existing["employee_count_type"] == "unavailable") and company.employee_count is not None and company.employee_count_type != "unavailable":
                    updates.append("employee_count = ?")
                    params.append(company.employee_count)
                    updates.append("employee_count_type = ?")
                    params.append(company.employee_count_type)

                if (existing["funding_stage"] in ("Unavailable", "", None)) and company.funding_stage not in ("Unavailable", "", None):
                    updates.append("funding_stage = ?")
                    params.append(company.funding_stage)

                if (existing["latest_funding_announcement"] is None) and company.latest_funding_announcement:
                    updates.append("latest_funding_announcement = ?")
                    params.append(company.latest_funding_announcement)

                if (existing["linkedin_company_url"] is None) and company.linkedin_company_url:
                    updates.append("linkedin_company_url = ?")
                    params.append(company.linkedin_company_url)

                if (existing["public_contact_method"] is None) and company.public_contact_method:
                    updates.append("public_contact_method = ?")
                    params.append(company.public_contact_method)

                updates.append("updated_at = ?")
                params.append(now)

                if updates:
                    params.append(comp_id)
                    conn.execute(
                        f"UPDATE companies SET {', '.join(updates)} WHERE id = ?",
                        tuple(params),
                    )

                return comp_id, False
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO companies (
                        domain, name, website_url, linkedin_company_url,
                        headquarters, business_category, target_segment,
                        employee_count, employee_count_type, funding_stage,
                        latest_funding_announcement, public_contact_method,
                        status, review_status, rejection_reason, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        norm_dom,
                        company.name or norm_dom,
                        company.website_url or f"https://{norm_dom}",
                        company.linkedin_company_url,
                        company.headquarters or "Unavailable",
                        company.business_category or "B2B Software",
                        company.target_segment or "Unavailable",
                        company.employee_count,
                        company.employee_count_type or "unavailable",
                        company.funding_stage or "Unavailable",
                        company.latest_funding_announcement,
                        company.public_contact_method,
                        company.status or "candidate",
                        company.review_status or "pending",
                        company.rejection_reason,
                        now,
                        now,
                    ),
                )
                return cursor.lastrowid, True

    def add_contact(self, contact: Contact) -> int:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO contacts (
                    company_id, full_name, current_role, public_linkedin_url,
                    public_business_email, contact_page_url, role_evidence_source,
                    verification_status, last_verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contact.company_id,
                    contact.full_name or "Unavailable",
                    contact.current_role or "Unavailable",
                    contact.public_linkedin_url,
                    contact.public_business_email,
                    contact.contact_page_url,
                    contact.role_evidence_source,
                    contact.verification_status or "incomplete",
                    contact.last_verified_at or now_iso(),
                ),
            )
            return cursor.lastrowid

    def add_buying_signal(self, signal: BuyingSignal) -> int:
        now = now_iso()
        with get_db_connection(self.db_path) as conn:
            existing = conn.execute(
                """
                SELECT id FROM buying_signals
                WHERE company_id = ? AND (original_source_url = ? OR description = ?)
                """,
                (signal.company_id, signal.original_source_url, signal.description),
            ).fetchone()
            if existing:
                return existing["id"]

            cursor = conn.execute(
                """
                INSERT INTO buying_signals (
                    company_id, signal_type, description, publication_date,
                    original_source_url, source_publisher, retrieval_timestamp,
                    verification_status, confidence_level, uncertainty_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.company_id,
                    signal.signal_type,
                    signal.description,
                    signal.publication_date or now,
                    signal.original_source_url,
                    signal.source_publisher,
                    signal.retrieval_timestamp or now,
                    signal.verification_status or "verified",
                    signal.confidence_level or "high",
                    signal.uncertainty_notes,
                ),
            )
            return cursor.lastrowid

    def add_evidence_source(self, evidence: EvidenceSource) -> int:
        now = now_iso()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO evidence_sources (
                    company_id, source_name, source_url, retrieved_at, raw_snippet
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    evidence.company_id,
                    evidence.source_name,
                    evidence.source_url,
                    evidence.retrieved_at or now,
                    evidence.raw_snippet,
                ),
            )
            return cursor.lastrowid

    def save_qualification_score(self, score: QualificationScore) -> int:
        now = now_iso()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO qualification_scores (
                    company_id, total_score, icp_fit_score, buying_signal_score,
                    commercial_opportunity_score, decision_maker_score,
                    commercial_plausibility_score, personalization_evidence_score,
                    classification, explanation, scored_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id) DO UPDATE SET
                    total_score = excluded.total_score,
                    icp_fit_score = excluded.icp_fit_score,
                    buying_signal_score = excluded.buying_signal_score,
                    commercial_opportunity_score = excluded.commercial_opportunity_score,
                    decision_maker_score = excluded.decision_maker_score,
                    commercial_plausibility_score = excluded.commercial_plausibility_score,
                    personalization_evidence_score = excluded.personalization_evidence_score,
                    classification = excluded.classification,
                    explanation = excluded.explanation,
                    scored_at = excluded.scored_at;
                """,
                (
                    score.company_id,
                    score.total_score,
                    score.icp_fit_score,
                    score.buying_signal_score,
                    score.commercial_opportunity_score,
                    score.decision_maker_score,
                    score.commercial_plausibility_score,
                    score.personalization_evidence_score,
                    score.classification,
                    score.explanation,
                    score.scored_at or now,
                ),
            )
            new_status = "qualified" if score.total_score >= 8.0 else ("review_required" if score.total_score >= 7.0 else "candidate")
            conn.execute(
                "UPDATE companies SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, score.company_id),
            )
            return cursor.lastrowid or score.company_id

    def save_outreach_note(self, note: OutreachNote) -> int:
        now = now_iso()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO outreach_notes (
                    company_id, why_fit, relevant_buying_signal,
                    signal_website_relevance, outreach_angle, opening_sentence,
                    missing_verification_questions, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id) DO UPDATE SET
                    why_fit = excluded.why_fit,
                    relevant_buying_signal = excluded.relevant_buying_signal,
                    signal_website_relevance = excluded.signal_website_relevance,
                    outreach_angle = excluded.outreach_angle,
                    opening_sentence = excluded.opening_sentence,
                    missing_verification_questions = excluded.missing_verification_questions,
                    generated_at = excluded.generated_at;
                """,
                (
                    note.company_id,
                    note.why_fit,
                    note.relevant_buying_signal,
                    note.signal_website_relevance,
                    note.outreach_angle,
                    note.opening_sentence,
                    note.missing_verification_questions,
                    note.generated_at or now,
                ),
            )
            return cursor.lastrowid or note.company_id

    def add_manual_note(self, company_id: int, note_text: str) -> int:
        now = now_iso()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO manual_notes (company_id, note_text, created_at) VALUES (?, ?, ?)",
                (company_id, note_text, now),
            )
            return cursor.lastrowid

    def update_company_review(
        self, company_id: int, review_status: str, rejection_reason: Optional[str] = None
    ) -> None:
        now = now_iso()
        with get_db_connection(self.db_path) as conn:
            new_status = "rejected" if review_status == "rejected" else ("qualified" if review_status == "approved" else "review_required")
            conn.execute(
                """
                UPDATE companies
                SET review_status = ?, status = ?, rejection_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (review_status, new_status, rejection_reason, now, company_id),
            )

    def delete_company(self, company_id: int) -> None:
        with get_db_connection(self.db_path) as conn:
            conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))

    def get_company_by_id(self, company_id: int) -> Optional[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
            return dict(row) if row else None

    def get_company_by_domain_or_name(self, query: str) -> Optional[dict[str, Any]]:
        norm = normalize_domain(query)
        with get_db_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE domain = ? OR LOWER(name) = ? OR domain LIKE ?",
                (norm, query.strip().lower(), f"%{query.strip().lower()}%"),
            ).fetchone()
            return dict(row) if row else None

    def get_full_lead_dossier(self, company_id: int) -> Optional[dict[str, Any]]:
        company = self.get_company_by_id(company_id)
        if not company:
            return None

        with get_db_connection(self.db_path) as conn:
            contacts = [dict(r) for r in conn.execute("SELECT * FROM contacts WHERE company_id = ?", (company_id,)).fetchall()]
            signals = [dict(r) for r in conn.execute("SELECT * FROM buying_signals WHERE company_id = ? ORDER BY publication_date DESC", (company_id,)).fetchall()]
            score = conn.execute("SELECT * FROM qualification_scores WHERE company_id = ?", (company_id,)).fetchone()
            outreach = conn.execute("SELECT * FROM outreach_notes WHERE company_id = ?", (company_id,)).fetchone()
            evidence = [dict(r) for r in conn.execute("SELECT * FROM evidence_sources WHERE company_id = ?", (company_id,)).fetchall()]
            notes = [dict(r) for r in conn.execute("SELECT * FROM manual_notes WHERE company_id = ?", (company_id,)).fetchall()]

        return {
            "company": company,
            "contacts": contacts,
            "signals": signals,
            "score": dict(score) if score else None,
            "outreach": dict(outreach) if outreach else None,
            "evidence": evidence,
            "notes": notes,
        }

    def get_all_companies(
        self,
        status: Optional[str] = None,
        min_score: Optional[float] = None,
        segment: Optional[str] = None,
        review_status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT c.*, s.total_score, s.classification,
                   (SELECT full_name FROM contacts WHERE company_id = c.id LIMIT 1) as contact_name,
                   (SELECT current_role FROM contacts WHERE company_id = c.id LIMIT 1) as contact_role,
                   (SELECT description FROM buying_signals WHERE company_id = c.id ORDER BY publication_date DESC LIMIT 1) as latest_signal
            FROM companies c
            LEFT JOIN qualification_scores s ON c.id = s.company_id
            WHERE 1=1
        """
        params: list[Any] = []

        if status:
            if status == "qualified":
                query += " AND (c.status = 'qualified' OR s.total_score >= 8.0)"
            elif status == "review_required":
                query += " AND c.status = 'review_required'"
            elif status == "rejected":
                query += " AND c.status = 'rejected'"
            else:
                query += " AND c.status = ?"
                params.append(status)

        if min_score is not None:
            query += " AND s.total_score >= ?"
            params.append(min_score)

        if segment:
            query += " AND c.target_segment LIKE ?"
            params.append(f"%{segment}%")

        if review_status:
            query += " AND c.review_status = ?"
            params.append(review_status)

        query += " ORDER BY COALESCE(s.total_score, 0) DESC, c.id DESC LIMIT ?"
        params.append(limit)

        with get_db_connection(self.db_path) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def record_export(self, export_format: str, row_count: int, file_path: str) -> int:
        now = now_iso()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO export_history (export_format, row_count, file_path, exported_at) VALUES (?, ?, ?, ?)",
                (export_format, row_count, str(file_path), now),
            )
            return cursor.lastrowid

    def record_research_run(
        self, source_name: str, query: str, status: str, candidates_found: int, error_message: Optional[str] = None
    ) -> int:
        now = now_iso()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO research_runs (source_name, query, status, candidates_found, created_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (source_name, query, status, candidates_found, now, error_message),
            )
            return cursor.lastrowid

    def get_stats(self) -> dict[str, Any]:
        with get_db_connection(self.db_path) as conn:
            total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            qualified_leads = conn.execute(
                "SELECT COUNT(*) FROM companies c LEFT JOIN qualification_scores s ON c.id = s.company_id WHERE c.status = 'qualified' OR s.total_score >= 8.0"
            ).fetchone()[0]
            review_pending = conn.execute(
                "SELECT COUNT(*) FROM companies WHERE review_status = 'pending' AND status != 'rejected'"
            ).fetchone()[0]
            rejected_leads = conn.execute("SELECT COUNT(*) FROM companies WHERE status = 'rejected'").fetchone()[0]
            signals_count = conn.execute("SELECT COUNT(*) FROM buying_signals").fetchone()[0]
            contacts_count = conn.execute("SELECT COUNT(*) FROM contacts WHERE full_name != 'Unavailable'").fetchone()[0]
            
            seg_rows = conn.execute(
                "SELECT target_segment, COUNT(*) as cnt FROM companies GROUP BY target_segment ORDER BY cnt DESC"
            ).fetchall()
            segments = {r["target_segment"]: r["cnt"] for r in seg_rows}

            run_rows = conn.execute(
                "SELECT source_name, COUNT(*) as run_cnt, SUM(candidates_found) as total_found FROM research_runs GROUP BY source_name"
            ).fetchall()
            source_stats = [dict(r) for r in run_rows]

        return {
            "total_candidates": total_companies,
            "qualified_leads": qualified_leads,
            "review_pending": review_pending,
            "rejected_leads": rejected_leads,
            "signals_recorded": signals_count,
            "contacts_identified": contacts_count,
            "segments": segments,
            "source_runs": source_stats,
        }
