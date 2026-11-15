"""Google News RSS discovery adapter for B2B funding and product announcements."""

import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote_plus
import feedparser
import httpx

from lid.config import DEFAULT_TIMEOUT, USER_AGENT
from lid.security import normalize_domain, validate_safe_url
from lid.sources.base import BaseSource, DiscoveryResult


DEFAULT_DISCOVERY_QUERIES = [
    '("Series A" OR "Series B" OR "Seed round") ("developer tools" OR "AI infrastructure")',
    '("raises" OR "funding") ("cybersecurity" OR "cloud security") startup',
    '("launches" OR "releases") ("AI platform" OR "enterprise SaaS" OR "developer infrastructure")',
]


class GoogleNewsRSSSource(BaseSource):
    @property
    def source_name(self) -> str:
        return "google_news_rss"

    @property
    def description(self) -> str:
        return "Public Google News RSS feeds covering B2B funding, launches, and expansions"

    def check_health(self) -> tuple[bool, str]:
        test_url = "https://news.google.com/rss/search?q=technology&hl=en-US&gl=US&ceid=US:en"
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
                res = client.get(test_url)
                if res.status_code == 200:
                    return True, "Reachable"
                return False, f"HTTP status {res.status_code}"
        except Exception as exc:
            return False, f"Connection error: {str(exc)}"

    def _extract_company_and_signal(self, title: str, summary: str = "") -> tuple[str, str, str, str]:
        """Extract candidate company name, signal type, segment, and funding stage from title.
        
        Returns:
            (company_name, signal_type, segment, funding_stage)
        """
        signal_type = "Public Company Announcement"
        stage = "Unavailable"
        segment = "AI Infrastructure"

        title_lower = title.lower()

        # Check stage
        if "seed" in title_lower:
            stage = "Seed"
            signal_type = "Recent Funding Announcement"
        elif "series a" in title_lower:
            stage = "Series A"
            signal_type = "Recent Funding Announcement"
        elif "series b" in title_lower:
            stage = "Series B"
            signal_type = "Recent Funding Announcement"
        elif "funding" in title_lower or "raises" in title_lower or "investment" in title_lower:
            signal_type = "Recent Funding Announcement"
        elif "launch" in title_lower:
            signal_type = "New Product Launch"
        elif "expansion" in title_lower or "enterprise" in title_lower:
            signal_type = "Enterprise Market Expansion"
        elif "appoints" in title_lower or "names ceo" in title_lower or "leadership" in title_lower:
            signal_type = "New Leadership Appointment"

        # Check segment
        if any(term in title_lower for term in ["security", "cyber", "firewall", "auth", "zero trust"]):
            segment = "Cybersecurity"
        elif any(term in title_lower for term in ["developer", "devops", "sdk", "api", "infra", "database"]):
            segment = "Developer Tools"
        elif any(term in title_lower for term in ["ai", "llm", "agent", "machine learning", "model"]):
            segment = "AI Infrastructure"
        else:
            segment = "B2B SaaS"

        # Extract company name: usually first words before verbs like raises, launches, closes, bags, expands, secures
        company_name = ""
        patterns = [
            r"^([A-Z0-9][A-Za-z0-9\.\s&-]{2,30}?)\s+(?:raises|secures|bags|closes|launches|unveils|announces|expands|taps|appoints)",
            r"(?:Startup|Platform|Company)\s+([A-Z0-9][A-Za-z0-9\.\s&-]{2,30}?)\s+(?:raises|launches|secures)",
        ]
        for pat in patterns:
            match = re.search(pat, title)
            if match:
                cand = match.group(1).strip()
                # Clean punctuation
                cand = re.sub(r"[\-:,]$", "", cand).strip()
                if cand and len(cand) > 2 and cand.lower() not in ("how", "why", "what", "new", "the", "top", "this"):
                    company_name = cand
                    break

        if not company_name:
            # Fallback: take text before first colon or dash
            parts = re.split(r"[-:]", title)
            if parts and len(parts[0].split()) <= 4:
                first_part = parts[0].strip()
                if first_part and not first_part.lower().startswith(("how", "why", "exclusive")):
                    company_name = first_part

        if not company_name:
            company_name = "Candidate Tech Company"

        return company_name, signal_type, segment, stage

    def discover(self, query: Optional[str] = None, limit: int = 20) -> list[DiscoveryResult]:
        queries = [query] if query else DEFAULT_DISCOVERY_QUERIES
        results: list[DiscoveryResult] = []

        headers = {"User-Agent": USER_AGENT}

        for q in queries:
            if len(results) >= limit:
                break
            encoded_query = quote_plus(q)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            
            try:
                with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=headers) as client:
                    resp = client.get(rss_url)
                    if resp.status_code != 200:
                        continue
                    feed = feedparser.parse(resp.content)
            except Exception:
                # If network fails or RSS is unavailable, proceed gracefully without crash
                continue

            for entry in feed.entries:
                if len(results) >= limit:
                    break

                raw_title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                link = getattr(entry, "link", "")
                published = getattr(entry, "published", "")
                publisher = "Google News"
                if hasattr(entry, "source") and hasattr(entry.source, "title"):
                    publisher = entry.source.title

                # Extract company name and signals
                company_name, signal_type, segment, stage = self._extract_company_and_signal(raw_title, summary)
                if company_name in ("Candidate Tech Company", ""):
                    continue

                # Clean name: remove source suffix like "- TechCrunch"
                if " - " in company_name:
                    company_name = company_name.split(" - ")[0].strip()

                # Infer candidate website domain
                safe_slug = re.sub(r"[^a-zA-Z0-9]", "", company_name).lower()
                guessed_domain = f"{safe_slug}.com"
                website_url = f"https://{guessed_domain}"

                results.append(
                    DiscoveryResult(
                        company_name=company_name,
                        website_url=website_url,
                        target_segment=segment,
                        headquarters="United States",
                        funding_stage=stage,
                        latest_funding=f"{stage} announcement" if stage != "Unavailable" else None,
                        signal_type=signal_type,
                        signal_description=raw_title,
                        signal_date=published or datetime.now(timezone.utc).isoformat(),
                        signal_url=link,
                        source_name="Google News RSS",
                        confidence_level="medium" if stage != "Unavailable" else "low",
                        uncertainty_notes="Domain heuristically derived from public news headline. Website and employee count require verification.",
                    )
                )

        return results
