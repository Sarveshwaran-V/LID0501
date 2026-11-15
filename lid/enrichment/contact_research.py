"""Manual LinkedIn research preparation and decision-maker discovery helpers."""

from typing import Optional
from lid.security import build_manual_linkedin_search_url


PRIORITY_ROLES = [
    "Founder",
    "Co-Founder",
    "CEO",
    "Head of Marketing",
    "VP of Marketing",
    "Head of Brand",
    "Head of Design",
]


class ContactResearchHelper:
    """Prepares structured manual LinkedIn search queries and decision-maker roles."""

    @staticmethod
    def suggest_target_role(existing_role: Optional[str] = None) -> str:
        if existing_role and existing_role not in ("Unavailable", ""):
            return existing_role
        return "Founder OR CEO OR 'VP Marketing'"

    @staticmethod
    def build_search_record(
        company_name: str,
        website_url: str,
        contact_name: Optional[str] = None,
        suggested_role: Optional[str] = None,
        verified_linkedin_url: Optional[str] = None,
    ) -> dict[str, str]:
        """Prepare record for manual LinkedIn research."""
        target_role = suggested_role or "Founder OR CEO"
        
        # Build keywords for search
        keywords = [f'"{company_name}"']
        if contact_name and contact_name not in ("Unavailable", ""):
            keywords.append(f'"{contact_name}"')
        else:
            keywords.append(target_role)

        search_url = build_manual_linkedin_search_url(keywords)

        return {
            "company_name": company_name,
            "website_url": website_url,
            "suggested_role": target_role,
            "search_keywords": " ".join(keywords),
            "manual_search_url": search_url,
            "manually_verified_linkedin_url": verified_linkedin_url or "Unavailable",
        }
