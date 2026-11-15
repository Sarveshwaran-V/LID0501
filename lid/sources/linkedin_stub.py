"""Official LinkedIn API adapter interface stub (for future enterprise use).

Per Section 5C of the specification:
The system operates safely without this integration. Only enabled if official
authorized enterprise API credentials with partner permissions are configured.
"""

from typing import Optional
from lid.sources.base import BaseSource, DiscoveryResult


class LinkedInOfficialAdapter(BaseSource):
    """Optional adapter for official LinkedIn Enterprise APIs (Community Management / Organization API).
    
    Default behavior: Disabled / Unconfigured. The core application runs without it.
    """

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret

    @property
    def source_name(self) -> str:
        return "linkedin_official_api"

    @property
    def description(self) -> str:
        return "Official LinkedIn API adapter (optional future integration; requires partner enterprise credentials)"

    def check_health(self) -> tuple[bool, str]:
        if not self.client_id or not self.client_secret:
            return False, "Unconfigured (no official LinkedIn enterprise partner credentials provided)"
        return True, "Credentials configured"

    def discover(self, query: Optional[str] = None, limit: int = 20) -> list[DiscoveryResult]:
        # Respect platform terms: do not simulate scraping.
        return []
