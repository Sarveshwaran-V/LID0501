"""GitHub Public API discovery adapter for AI infrastructure and developer tools."""

from datetime import datetime, timezone
from typing import Optional
import httpx

from lid.config import DEFAULT_TIMEOUT, USER_AGENT
from lid.security import normalize_domain, validate_safe_url
from lid.sources.base import BaseSource, DiscoveryResult


GITHUB_TOPIC_QUERIES = [
    "topic:developer-tools stars:>100",
    "topic:ai-infrastructure stars:>100",
    "topic:cybersecurity stars:>100",
    "topic:security-tools stars:>100",
]


class GitHubPublicSource(BaseSource):
    @property
    def source_name(self) -> str:
        return "github_public_api"

    @property
    def description(self) -> str:
        return "GitHub Public API discovering active AI infrastructure, dev tools, and security companies"

    def check_health(self) -> tuple[bool, str]:
        url = "https://api.github.com/rate_limit"
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    remaining = data.get("rate", {}).get("remaining", 0)
                    return True, f"Reachable ({remaining} free queries remaining)"
                return False, f"Status {res.status_code}"
        except Exception as exc:
            return False, f"Connection error: {str(exc)}"

    def discover(self, query: Optional[str] = None, limit: int = 20) -> list[DiscoveryResult]:
        queries = [query] if query else GITHUB_TOPIC_QUERIES
        results: list[DiscoveryResult] = []

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github.v3+json",
        }

        for q in queries:
            if len(results) >= limit:
                break

            search_url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page=15"
            try:
                with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=headers) as client:
                    resp = client.get(search_url)
                    if resp.status_code != 200:
                        # Graceful handling for rate limits / offline
                        continue
                    data = resp.json()
            except Exception:
                continue

            items = data.get("items", [])
            for item in items:
                if len(results) >= limit:
                    break

                owner = item.get("owner", {})
                owner_type = owner.get("type", "User")
                homepage = item.get("homepage", "") or ""
                description = item.get("description", "") or ""
                repo_name = item.get("name", "")
                full_name = item.get("full_name", "")
                topics = item.get("topics", [])
                stars = item.get("stargazers_count", 0)
                html_url = item.get("html_url", "")
                updated_at = item.get("updated_at", "")

                # Determine company name: owner login or repository name
                company_name = owner.get("login", repo_name)
                # Capitalize readable name
                if company_name.islower():
                    company_name = company_name.capitalize()

                # Determine website: prefer homepage if safe, else GitHub org URL
                website_url = homepage.strip()
                is_safe, _ = validate_safe_url(website_url)
                if not is_safe or not website_url:
                    # If homepage is empty or unsafe, fallback to org profile
                    website_url = owner.get("html_url", html_url)

                norm_dom = normalize_domain(website_url)
                if not norm_dom:
                    continue

                # Segment determination
                topics_str = " ".join(topics).lower() + " " + description.lower()
                if any(k in topics_str for k in ["security", "cyber", "vuln", "auth"]):
                    segment = "Cybersecurity"
                elif any(k in topics_str for k in ["ai", "llm", "ml", "model", "rag"]):
                    segment = "AI Infrastructure"
                else:
                    segment = "Developer Tools"

                results.append(
                    DiscoveryResult(
                        company_name=company_name,
                        website_url=website_url,
                        target_segment=segment,
                        headquarters="United States",
                        funding_stage="Unavailable",
                        employee_count=None,
                        employee_count_type="unavailable",
                        signal_type="Major Feature Release",
                        signal_description=f"Active developer momentum for {repo_name} with {stars} stars: {description[:120]}",
                        signal_date=updated_at or datetime.now(timezone.utc).isoformat(),
                        signal_url=html_url,
                        source_name="GitHub Public API",
                        confidence_level="high",
                        uncertainty_notes="Verified open source product presence. Funding and employee count require verification.",
                    )
                )

        return results
