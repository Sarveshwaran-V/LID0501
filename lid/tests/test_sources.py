"""Tests for discovery sources, CSV importer, and extraction robustness."""

from pathlib import Path
import pytest
from bs4 import BeautifulSoup
from lid.enrichment.extractor import WebInfoExtractor
from lid.sources.csv_importer import CSVImporter
from lid.sources.google_news_rss import GoogleNewsRSSSource
from lid.sources.linkedin_stub import LinkedInOfficialAdapter


def test_csv_importer(tmp_path: Path):
    csv_file = tmp_path / "leads.csv"
    csv_content = """company_name,website_url,target_segment,headquarters,employee_count,funding_stage,founder_or_ceo,signal_type,signal_description
Lasso Security,https://lasso.security,Cybersecurity,Austin TX,25,Seed,Elad Schulman,Recent Funding Announcement,Raised $6M Seed round
"""
    csv_file.write_text(csv_content, encoding="utf-8")

    importer = CSVImporter()
    results = importer.import_csv(csv_file)
    assert len(results) == 1
    r = results[0]
    assert r.company_name == "Lasso Security"
    assert r.website_url == "https://lasso.security"
    assert r.target_segment == "Cybersecurity"
    assert r.employee_count == 25
    assert r.funding_stage == "Seed"
    assert r.contact_name == "Elad Schulman"


def test_google_news_title_parsing():
    source = GoogleNewsRSSSource()
    title = "Acme Corp raises $15M Series A for developer tooling platform - TechCrunch"
    company, signal, segment, stage = source._extract_company_and_signal(title)
    assert company == "Acme Corp"
    assert stage == "Series A"
    assert signal == "Recent Funding Announcement"
    assert segment == "Developer Tools"

    cyber_title = "CyberShield secures $8M to expand cloud workload firewall"
    company2, signal2, segment2, stage2 = source._extract_company_and_signal(cyber_title)
    assert company2 == "CyberShield"
    assert segment2 == "Cybersecurity"


def test_web_info_extractor():
    extractor = WebInfoExtractor()
    html = """
    <html>
      <head><title>SecureFlow | Cloud Zero Trust Security Platform</title></head>
      <body>
        <h1>Enterprise Cloud Security and Threat Detection</h1>
        <p>Meet our executive leadership:</p>
        <p>David Vance, Founder & CEO</p>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    meta = extractor.extract_metadata(soup)
    assert "SecureFlow" in meta["title"]
    assert len(meta["headings"]) >= 1

    segment = extractor.detect_segment(html)
    assert segment == "Cybersecurity"

    leadership = extractor.extract_leadership_candidates(soup)
    assert len(leadership) >= 1
    assert leadership[0]["full_name"] == "David Vance"
    assert "CEO" in leadership[0]["current_role"]


def test_linkedin_stub_health():
    stub = LinkedInOfficialAdapter()
    is_ok, msg = stub.check_health()
    assert is_ok is False
    assert "Unconfigured" in msg
    assert stub.discover() == []
