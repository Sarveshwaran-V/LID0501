"""Data models and schemas for LID0501."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def utcnow_str() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Company:
    id: Optional[int] = None
    domain: str = ""
    name: str = ""
    website_url: str = ""
    linkedin_company_url: Optional[str] = None
    headquarters: str = "Unavailable"
    business_category: str = "B2B Software"
    target_segment: str = "Unavailable"
    employee_count: Optional[int] = None
    employee_count_type: str = "unavailable"  # verified, sourced_estimate, unavailable
    funding_stage: str = "Unavailable"
    latest_funding_announcement: Optional[str] = None
    public_contact_method: Optional[str] = None
    status: str = "candidate"  # candidate, qualified, review_required, rejected
    review_status: str = "pending"  # pending, approved, rejected
    rejection_reason: Optional[str] = None
    created_at: str = field(default_factory=utcnow_str)
    updated_at: str = field(default_factory=utcnow_str)


@dataclass
class Contact:
    id: Optional[int] = None
    company_id: int = 0
    full_name: str = "Unavailable"
    current_role: str = "Unavailable"
    public_linkedin_url: Optional[str] = None
    public_business_email: Optional[str] = None
    contact_page_url: Optional[str] = None
    role_evidence_source: Optional[str] = None
    verification_status: str = "incomplete"  # verified, sourced_estimate, inference, incomplete
    last_verified_at: Optional[str] = None


@dataclass
class BuyingSignal:
    id: Optional[int] = None
    company_id: int = 0
    signal_type: str = ""
    description: str = ""
    publication_date: str = ""
    original_source_url: str = ""
    source_publisher: str = ""
    retrieval_timestamp: str = field(default_factory=utcnow_str)
    verification_status: str = "verified"  # verified, unverified, sourced_estimate
    confidence_level: str = "high"  # high, medium, low
    uncertainty_notes: Optional[str] = None


@dataclass
class EvidenceSource:
    id: Optional[int] = None
    company_id: int = 0
    source_name: str = ""
    source_url: str = ""
    retrieved_at: str = field(default_factory=utcnow_str)
    raw_snippet: Optional[str] = None


@dataclass
class QualificationScore:
    id: Optional[int] = None
    company_id: int = 0
    total_score: float = 0.0
    icp_fit_score: float = 0.0
    buying_signal_score: float = 0.0
    commercial_opportunity_score: float = 0.0
    decision_maker_score: float = 0.0
    commercial_plausibility_score: float = 0.0
    personalization_evidence_score: float = 0.0
    classification: str = "Below 7: Research further or reject"
    explanation: str = ""
    scored_at: str = field(default_factory=utcnow_str)


@dataclass
class OutreachNote:
    id: Optional[int] = None
    company_id: int = 0
    why_fit: str = ""
    relevant_buying_signal: str = ""
    signal_website_relevance: str = ""
    outreach_angle: str = ""
    opening_sentence: str = ""
    missing_verification_questions: str = ""
    generated_at: str = field(default_factory=utcnow_str)


@dataclass
class ManualNote:
    id: Optional[int] = None
    company_id: int = 0
    note_text: str = ""
    created_at: str = field(default_factory=utcnow_str)


@dataclass
class SuppressionRecord:
    id: Optional[int] = None
    domain: str = ""
    company_name: Optional[str] = None
    reason: str = "User opt-out"
    created_at: str = field(default_factory=utcnow_str)


@dataclass
class ExportHistory:
    id: Optional[int] = None
    export_format: str = "csv"
    row_count: int = 0
    file_path: str = ""
    exported_at: str = field(default_factory=utcnow_str)


@dataclass
class ResearchRun:
    id: Optional[int] = None
    source_name: str = ""
    query: str = ""
    status: str = "running"
    candidates_found: int = 0
    created_at: str = field(default_factory=utcnow_str)
    error_message: Optional[str] = None
