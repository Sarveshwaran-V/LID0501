"""Tests for SQLite database schema, repository, deduplication, and suppression."""

from pathlib import Path
import pytest
from lid.db.database import init_db
from lid.db.models import Company, Contact, BuyingSignal, EvidenceSource
from lid.db.repository import LeadRepository


@pytest.fixture
def test_repo(tmp_path: Path):
    db_file = tmp_path / "test_leads.db"
    init_db(db_file)
    return LeadRepository(db_file)


def test_upsert_company_and_deduplication(test_repo: LeadRepository):
    # Insert new company with sourced estimate
    c1 = Company(
        domain="pinecone.io",
        name="Pinecone",
        website_url="https://pinecone.io",
        target_segment="AI Infrastructure",
        headquarters="San Francisco, CA",
        employee_count=100,
        employee_count_type="sourced_estimate",
        funding_stage="Series B",
    )
    cid1, is_new1 = test_repo.upsert_company(c1)
    assert is_new1 is True
    assert cid1 > 0

    # Insert duplicate with uppercase and path and attempt to overwrite with unverified count
    c2 = Company(
        domain="https://WWW.PINECONE.IO/company",
        name="Pinecone Inc",
        website_url="https://pinecone.io/company",
        headquarters="San Francisco, CA",
        employee_count=120,
        employee_count_type="unavailable",
        funding_stage="Series B",
    )
    cid2, is_new2 = test_repo.upsert_company(c2)
    assert is_new2 is False
    assert cid2 == cid1

    # Verify merged data: existing sourced estimate (100) was preserved
    fetched = test_repo.get_company_by_id(cid1)
    assert fetched["name"] == "Pinecone"
    assert fetched["employee_count"] == 100


def test_suppression_and_opt_out(test_repo: LeadRepository):
    assert test_repo.is_suppressed("opted-out.com") is False
    test_repo.add_suppression("opted-out.com", "Opted Out Inc", "Competitor request")
    assert test_repo.is_suppressed("https://www.opted-out.com/home") is True


def test_contacts_and_signals_relationship(test_repo: LeadRepository):
    c = Company(domain="permithq.com", name="Permit", website_url="https://permithq.com")
    cid, _ = test_repo.upsert_company(c)

    # Add contact
    contact = Contact(
        company_id=cid,
        full_name="Jane Doe",
        current_role="Founder & CEO",
        verification_status="verified",
    )
    cont_id = test_repo.add_contact(contact)
    assert cont_id > 0

    # Add signals (including duplicate signal check)
    sig1 = BuyingSignal(
        company_id=cid,
        signal_type="Recent Funding Announcement",
        description="Raised $10M Series A",
        publication_date="2026-01-10",
        original_source_url="https://techcrunch.com/permit-series-a",
        source_publisher="TechCrunch",
    )
    sig_id1 = test_repo.add_buying_signal(sig1)
    sig_id2 = test_repo.add_buying_signal(sig1)  # Duplicate
    assert sig_id1 == sig_id2

    # Query full dossier
    dossier = test_repo.get_full_lead_dossier(cid)
    assert len(dossier["contacts"]) == 1
    assert dossier["contacts"][0]["full_name"] == "Jane Doe"
    assert len(dossier["signals"]) == 1
    assert dossier["signals"][0]["signal_type"] == "Recent Funding Announcement"


def test_human_review_workflow(test_repo: LeadRepository):
    c = Company(domain="reviewtest.com", name="Review Test", website_url="https://reviewtest.com")
    cid, _ = test_repo.upsert_company(c)

    test_repo.update_company_review(cid, "approved")
    updated = test_repo.get_company_by_id(cid)
    assert updated["review_status"] == "approved"
    assert updated["status"] == "qualified"

    test_repo.update_company_review(cid, "rejected", "Out of ICP region")
    updated_rej = test_repo.get_company_by_id(cid)
    assert updated_rej["review_status"] == "rejected"
    assert updated_rej["status"] == "rejected"
    assert updated_rej["rejection_reason"] == "Out of ICP region"
