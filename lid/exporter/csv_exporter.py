"""CSV exporter matching the 23 mandatory columns in Section 14."""

import csv
from pathlib import Path
from typing import Any

EXPORT_COLUMNS = [
    "Company name",
    "Official website",
    "LinkedIn company URL, if verified",
    "Headquarters",
    "Target segment",
    "Employee count or range",
    "Funding stage",
    "Buying signal",
    "Signal date",
    "Signal evidence URL",
    "Founder or CEO",
    "Decision-maker role",
    "LinkedIn profile URL, if verified",
    "Public professional email, if verified",
    "Other legitimate business contact method",
    "Why this company fits Ikaiva",
    "Personalized outreach angle",
    "Qualification score",
    "Score breakdown",
    "Verification status",
    "Missing information",
    "Research date",
    "Human review status",
]


def build_row_dict(lead: dict[str, Any]) -> dict[str, Any]:
    company = lead.get("company", lead)
    contacts = lead.get("contacts", [])
    top_contact = contacts[0] if contacts else {}
    signals = lead.get("signals", [])
    top_signal = signals[0] if signals else {}
    score = lead.get("score") or {}
    outreach = lead.get("outreach") or {}

    # Employee count
    emp_cnt = company.get("employee_count")
    emp_str = str(emp_cnt) if emp_cnt is not None else "Unavailable"

    # Contact fields
    c_name = top_contact.get("full_name") or company.get("contact_name") or "Unavailable"
    c_role = top_contact.get("current_role") or company.get("contact_role") or "Unavailable"
    c_li = top_contact.get("public_linkedin_url") or "Unavailable"
    c_email = top_contact.get("public_business_email") or "Unavailable"

    # Score fields
    q_score = score.get("total_score") if score else company.get("total_score")
    q_score_str = f"{q_score:.1f}" if q_score is not None else "Unscored"
    explanation = score.get("explanation") or ""

    # Outreach fields
    why_fit = outreach.get("why_fit") or ""
    angle = outreach.get("outreach_angle") or ""
    missing_info = outreach.get("missing_verification_questions") or ""

    # Buying signal
    sig_desc = top_signal.get("description") or company.get("latest_signal") or "Unavailable"
    sig_date = top_signal.get("publication_date") or ""
    sig_url = top_signal.get("original_source_url") or ""

    return {
        "Company name": company.get("name") or "Unavailable",
        "Official website": company.get("website_url") or "Unavailable",
        "LinkedIn company URL, if verified": company.get("linkedin_company_url") or "Unavailable",
        "Headquarters": company.get("headquarters") or "Unavailable",
        "Target segment": company.get("target_segment") or "Unavailable",
        "Employee count or range": emp_str,
        "Funding stage": company.get("funding_stage") or "Unavailable",
        "Buying signal": sig_desc,
        "Signal date": sig_date[:10] if sig_date else "Unavailable",
        "Signal evidence URL": sig_url or "Unavailable",
        "Founder or CEO": c_name,
        "Decision-maker role": c_role,
        "LinkedIn profile URL, if verified": c_li,
        "Public professional email, if verified": c_email,
        "Other legitimate business contact method": company.get("public_contact_method") or "Unavailable",
        "Why this company fits Ikaiva": why_fit or "Unavailable",
        "Personalized outreach angle": angle or "Unavailable",
        "Qualification score": q_score_str,
        "Score breakdown": explanation or "Unavailable",
        "Verification status": top_contact.get("verification_status") or company.get("status") or "candidate",
        "Missing information": missing_info or "Unavailable",
        "Research date": (company.get("created_at") or "")[:10] or "Unavailable",
        "Human review status": company.get("review_status") or "pending",
    }


class CSVLeadExporter:
    def export(self, leads: list[dict[str, Any]], output_path: Path | str) -> Path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        with open(out_file, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS)
            writer.writeheader()
            for lead in leads:
                row = build_row_dict(lead)
                writer.writerow(row)

        return out_file
