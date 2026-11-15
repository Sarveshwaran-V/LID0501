"""Tests for 10-point qualification rubric and personalized outreach generator."""

import pytest
from lid.db.models import Company, Contact, BuyingSignal
from lid.scoring.outreach import OutreachAngleGenerator
from lid.scoring.rubric import LeadScorer


def test_high_priority_lead_scoring():
    scorer = LeadScorer()
    company = Company(
        id=1,
        domain="databear.io",
        name="DataBear",
        website_url="https://databear.io",
        target_segment="AI Infrastructure",
        headquarters="San Francisco, CA",
        employee_count=45,
        funding_stage="Series A",
    )
    contacts = [
        Contact(
            company_id=1,
            full_name="Alex Mercer",
            current_role="Founder & CEO",
            verification_status="verified",
        )
    ]
    signals = [
        BuyingSignal(
            company_id=1,
            signal_type="Recent Funding Announcement",
            description="Raised $12M Series A to scale vector query cache engine for enterprise LLM agents",
            publication_date="2026-02-01",
            verification_status="verified",
        )
    ]

    score = scorer.score_company(company, contacts, signals)
    assert score.total_score >= 8.0
    assert score.classification == "8–10: High priority"
    assert score.icp_fit_score == 2.0
    assert score.buying_signal_score == 2.0
    assert score.decision_maker_score == 1.0


def test_review_required_lead_scoring():
    scorer = LeadScorer()
    # Company with partial information: US location unconfirmed, early stage, unverified contact
    company = Company(
        id=2,
        domain="obscuretech.io",
        name="ObscureTech",
        website_url="https://obscuretech.io",
        target_segment="Developer Tools",
        headquarters="Unavailable",
        employee_count=8,  # under 15
        funding_stage="Seed",
    )
    contacts = [
        Contact(
            company_id=2,
            full_name="Sarah Connor",
            current_role="CEO",
            verification_status="sourced_estimate",
        )
    ]
    signals = [
        BuyingSignal(
            company_id=2,
            signal_type="Public Company Announcement",
            description="Announced new open source command line utility",
            publication_date="2026-01-15",
            verification_status="verified",
        )
    ]

    score = scorer.score_company(company, contacts, signals)
    # Score should be in the 7.0 - 7.9 range (Potentially qualified; human review required)
    assert 7.0 <= score.total_score < 8.0
    assert score.classification == "7: Potentially qualified; human review required"


def test_low_fit_scoring():
    scorer = LeadScorer()
    # Non-US company, no verified signal, unverified contact
    company = Company(
        id=3,
        domain="foreigncorp.com",
        name="ForeignCorp",
        website_url="https://foreigncorp.com",
        target_segment="B2C Consumer App",
        headquarters="Berlin, Germany",
        employee_count=500,
        funding_stage="Series D",
    )
    contacts = []
    signals = []

    score = scorer.score_company(company, contacts, signals)
    assert score.total_score < 7.0
    assert score.classification == "Below 7: Research further or reject"


def test_outreach_note_generation():
    generator = OutreachAngleGenerator()
    company = Company(
        id=1,
        domain="vaultguard.io",
        name="VaultGuard",
        website_url="https://vaultguard.io",
        target_segment="Cybersecurity",
        headquarters="Seattle, WA",
        employee_count=60,
        funding_stage="Series A",
    )
    contacts = [
        Contact(
            company_id=1,
            full_name="Elena Rostova",
            current_role="Co-Founder & CEO",
            verification_status="verified",
        )
    ]
    signals = [
        BuyingSignal(
            company_id=1,
            signal_type="Enterprise Market Expansion",
            description="Expanding enterprise cloud zero-trust workload protection",
            publication_date="2026-02-10",
        )
    ]

    note = generator.generate_note(company, contacts, signals)
    assert "VaultGuard" in note.why_fit
    assert "Cybersecurity" in note.why_fit
    assert "Elena" in note.opening_sentence
    assert "zero-trust" in note.opening_sentence or "Enterprise" in note.opening_sentence
    assert "website" in note.signal_website_relevance.lower() or "brand" in note.signal_website_relevance.lower()
    # Confirm it does NOT output generic fluff
    assert "your website needs improvement" not in note.opening_sentence
