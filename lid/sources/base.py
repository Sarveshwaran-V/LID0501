"""Base adapter class for all free discovery sources."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class DiscoveryResult:
    def __init__(
        self,
        company_name: str,
        website_url: str,
        target_segment: str = "Unavailable",
        headquarters: str = "United States",
        employee_count: Optional[int] = None,
        employee_count_type: str = "unavailable",
        funding_stage: str = "Unavailable",
        latest_funding: Optional[str] = None,
        linkedin_company_url: Optional[str] = None,
        contact_name: Optional[str] = None,
        contact_role: Optional[str] = None,
        contact_linkedin: Optional[str] = None,
        signal_type: str = "Public Announcement",
        signal_description: str = "",
        signal_date: str = "",
        signal_url: str = "",
        source_name: str = "",
        confidence_level: str = "high",
        uncertainty_notes: Optional[str] = None,
    ):
        self.company_name = company_name
        self.website_url = website_url
        self.target_segment = target_segment
        self.headquarters = headquarters
        self.employee_count = employee_count
        self.employee_count_type = employee_count_type
        self.funding_stage = funding_stage
        self.latest_funding = latest_funding
        self.linkedin_company_url = linkedin_company_url
        self.contact_name = contact_name
        self.contact_role = contact_role
        self.contact_linkedin = contact_linkedin
        self.signal_type = signal_type
        self.signal_description = signal_description
        self.signal_date = signal_date
        self.signal_url = signal_url
        self.source_name = source_name
        self.confidence_level = confidence_level
        self.uncertainty_notes = uncertainty_notes


class BaseSource(ABC):
    """Abstract interface for all discovery sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the discovery source."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the source."""
        pass

    @abstractmethod
    def check_health(self) -> tuple[bool, str]:
        """Verify if source is currently reachable and available."""
        pass

    @abstractmethod
    def discover(self, query: Optional[str] = None, limit: int = 20) -> list[DiscoveryResult]:
        """Discover candidate companies and buying signals.
        
        Must handle exceptions internally and never crash the CLI.
        """
        pass
