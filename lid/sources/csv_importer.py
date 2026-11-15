"""CSV and manual lead importer for user-provided company and LinkedIn records."""

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lid.security import normalize_domain, validate_safe_url
from lid.sources.base import DiscoveryResult


class CSVImporter:
    """Imports user-provided CSV records or single manual URLs."""

    def import_csv(self, file_path: Path | str) -> list[DiscoveryResult]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Import file not found: {file_path}")

        results: list[DiscoveryResult] = []
        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Flexible header matching
                norm_row = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items() if k}

                company_name = (
                    norm_row.get("company_name")
                    or norm_row.get("company")
                    or norm_row.get("name")
                    or ""
                )
                website = (
                    norm_row.get("official_website")
                    or norm_row.get("website_url")
                    or norm_row.get("website")
                    or norm_row.get("url")
                    or norm_row.get("domain")
                    or ""
                )
                target_segment = (
                    norm_row.get("target_segment")
                    or norm_row.get("segment")
                    or norm_row.get("category")
                    or "B2B Software"
                )
                headquarters = (
                    norm_row.get("headquarters")
                    or norm_row.get("hq")
                    or norm_row.get("location")
                    or "United States"
                )
                
                # Employee count
                raw_emp = norm_row.get("employee_count") or norm_row.get("employees") or norm_row.get("team_size")
                emp_count = None
                emp_type = "unavailable"
                if raw_emp:
                    digits = "".join([c for c in raw_emp if c.isdigit()])
                    if digits:
                        emp_count = int(digits)
                        emp_type = "sourced_estimate"

                funding_stage = (
                    norm_row.get("funding_stage")
                    or norm_row.get("stage")
                    or "Unavailable"
                )
                latest_funding = norm_row.get("latest_funding") or norm_row.get("latest_known_funding_announcement")
                linkedin_co = norm_row.get("linkedin_company_url") or norm_row.get("company_linkedin")

                # Contact fields
                contact_name = norm_row.get("founder_or_ceo") or norm_row.get("contact_name") or norm_row.get("founder")
                contact_role = norm_row.get("decision_maker_role") or norm_row.get("role") or "Founder"
                contact_li = norm_row.get("linkedin_profile_url") or norm_row.get("contact_linkedin")

                # Signal fields
                signal_type = norm_row.get("signal_type") or norm_row.get("buying_signal") or "User-provided Lead"
                signal_desc = norm_row.get("signal_description") or norm_row.get("notes") or f"Manually imported record for {company_name or website}"
                signal_url = norm_row.get("signal_evidence_url") or norm_row.get("evidence_url") or website
                signal_date = norm_row.get("signal_date") or datetime.now(timezone.utc).isoformat()

                if not company_name and not website:
                    continue

                if not website and company_name:
                    website = f"https://{normalize_domain(company_name)}.com"

                if not company_name and website:
                    company_name = normalize_domain(website).capitalize()

                results.append(
                    DiscoveryResult(
                        company_name=company_name,
                        website_url=website,
                        target_segment=target_segment,
                        headquarters=headquarters,
                        employee_count=emp_count,
                        employee_count_type=emp_type,
                        funding_stage=funding_stage,
                        latest_funding=latest_funding,
                        linkedin_company_url=linkedin_co,
                        contact_name=contact_name,
                        contact_role=contact_role,
                        contact_linkedin=contact_li,
                        signal_type=signal_type,
                        signal_description=signal_desc,
                        signal_date=signal_date,
                        signal_url=signal_url,
                        source_name=f"User CSV Import: {path.name}",
                        confidence_level="high",
                        uncertainty_notes="Imported by user from verified local CSV.",
                    )
                )

        return results

    def import_manual_entry(
        self,
        url_or_domain: str,
        company_name: Optional[str] = None,
        target_segment: Optional[str] = None,
        contact_name: Optional[str] = None,
        contact_role: Optional[str] = None,
        contact_linkedin: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> DiscoveryResult:
        """Create a discovery result from a single manual user input."""
        norm_dom = normalize_domain(url_or_domain)
        if not norm_dom:
            raise ValueError(f"Invalid company URL or domain: {url_or_domain}")

        name = company_name or norm_dom.split(".")[0].capitalize()
        website = f"https://{norm_dom}"
        now = datetime.now(timezone.utc).isoformat()

        return DiscoveryResult(
            company_name=name,
            website_url=website,
            target_segment=target_segment or "Unavailable",
            headquarters="United States",
            funding_stage="Unavailable",
            contact_name=contact_name,
            contact_role=contact_role or "Founder",
            contact_linkedin=contact_linkedin,
            signal_type="User-provided Lead",
            signal_description=notes or f"Manually submitted lead: {name}",
            signal_date=now,
            signal_url=website,
            source_name="Manual User Input",
            confidence_level="high",
            uncertainty_notes="User provided direct company entry.",
        )
