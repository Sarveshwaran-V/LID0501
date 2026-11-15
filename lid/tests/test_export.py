"""Tests for CSV and Excel exports ensuring all 23 required columns are present."""

import csv
from pathlib import Path
import openpyxl
import pytest
from lid.exporter.csv_exporter import CSVLeadExporter, EXPORT_COLUMNS
from lid.exporter.excel_exporter import ExcelLeadExporter


@pytest.fixture
def sample_dossier():
    return {
        "company": {
            "id": 1,
            "name": "Permit.io",
            "domain": "permit.io",
            "website_url": "https://permit.io",
            "linkedin_company_url": "https://www.linkedin.com/company/permit-io",
            "headquarters": "Palo Alto, CA",
            "target_segment": "Developer Tools",
            "employee_count": 45,
            "employee_count_type": "sourced_estimate",
            "funding_stage": "Series A",
            "status": "qualified",
            "review_status": "approved",
            "created_at": "2026-02-15T10:00:00",
        },
        "contacts": [
            {
                "full_name": "Or Weis",
                "current_role": "Co-Founder & CEO",
                "public_linkedin_url": "https://www.linkedin.com/in/orweis",
                "public_business_email": "Unavailable",
                "verification_status": "verified",
            }
        ],
        "signals": [
            {
                "signal_type": "Major Feature Release",
                "description": "Released full-stack authorization policy-as-code",
                "publication_date": "2026-02-01",
                "original_source_url": "https://permit.io/blog/authz-v2",
            }
        ],
        "score": {
            "total_score": 8.8,
            "classification": "8–10: High priority",
            "explanation": "ICP fit: 2.0; Signal: 2.0; Plausibility: 2.0",
        },
        "outreach": {
            "why_fit": "Permit.io is a US-focused Developer Tools company in Series A.",
            "outreach_angle": "Focus on developer interface hierarchy and visual positioning.",
            "missing_verification_questions": "None; core data verified.",
        },
    }


def test_csv_export_columns_and_content(tmp_path: Path, sample_dossier):
    out_csv = tmp_path / "test_export.csv"
    exporter = CSVLeadExporter()
    exporter.export([sample_dossier], out_csv)

    assert out_csv.exists()
    with open(out_csv, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        row = next(reader)

        assert header == EXPORT_COLUMNS
        assert len(header) == 23
        assert row[0] == "Permit.io"
        assert row[1] == "https://permit.io"
        assert row[4] == "Developer Tools"
        assert row[10] == "Or Weis"
        assert row[17] == "8.8"
        assert row[22] == "approved"


def test_excel_export_structure(tmp_path: Path, sample_dossier):
    out_xlsx = tmp_path / "test_export.xlsx"
    exporter = ExcelLeadExporter()
    exporter.export([sample_dossier], out_xlsx)

    assert out_xlsx.exists()
    wb = openpyxl.load_workbook(out_xlsx)
    ws = wb.active
    assert ws.title == "Qualified Leads"

    # Verify headers
    header_vals = [cell.value for cell in ws[1]]
    assert header_vals == EXPORT_COLUMNS

    # Verify first row
    first_row_vals = [cell.value for cell in ws[2]]
    assert first_row_vals[0] == "Permit.io"
    assert first_row_vals[1] == "https://permit.io"
    assert first_row_vals[17] == "8.8"
