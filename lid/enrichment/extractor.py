"""Structured information extractor from public website HTML."""

import re
from typing import Any, Optional
from bs4 import BeautifulSoup

from lid.config import AI_DEVTOOLS_SEGMENTS, CYBERSECURITY_SEGMENTS


class WebInfoExtractor:
    """Extracts factual business metadata, segments, and contacts from public pages."""

    def extract_metadata(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract title, description, and key meta tags."""
        result: dict[str, Any] = {
            "title": "",
            "description": "",
            "og_title": "",
            "og_description": "",
            "headings": [],
        }

        if not soup:
            return result

        # Title
        if soup.title and soup.title.string:
            result["title"] = soup.title.string.strip()

        # Meta description
        desc_tag = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        if desc_tag and desc_tag.get("content"):
            result["description"] = desc_tag["content"].strip()

        # OG tags
        og_t = soup.find("meta", attrs={"property": "og:title"})
        if og_t and og_t.get("content"):
            result["og_title"] = og_t["content"].strip()

        og_d = soup.find("meta", attrs={"property": "og:description"})
        if og_d and og_d.get("content"):
            result["og_description"] = og_d["content"].strip()

        # Headings (h1, h2)
        headings = []
        for tag in soup.find_all(["h1", "h2"], limit=6):
            text = tag.get_text(separator=" ", strip=True)
            if text and len(text) > 3 and len(text) < 160:
                headings.append(text)
        result["headings"] = headings

        return result

    def detect_segment(self, text: str) -> str:
        """Classify into Ikaiva target segments based on clear keywords."""
        t_low = text.lower()

        # Cybersecurity checks
        cyber_hits = sum(1 for kw in ["cybersecurity", "cloud security", "threat detection", "zero trust", "soc 2", "identity security", "application security", "endpoint security", "penetration testing", "vulnerability"] if kw in t_low)
        
        # AI / DevTools checks
        ai_hits = sum(1 for kw in ["ai infrastructure", "llm", "foundation model", "machine learning", "agentic", "vector database", "gpu", "rag"] if kw in t_low)
        dev_hits = sum(1 for kw in ["developer tools", "devops", "sdk", "api platform", "code intelligence", "compiler", "ci/cd", "observability", "kubernetes"] if kw in t_low)

        if cyber_hits >= 2:
            return "Cybersecurity"
        if ai_hits >= 2:
            return "AI Infrastructure"
        if dev_hits >= 2:
            return "Developer Tools"
        if cyber_hits == 1:
            return "Cybersecurity"
        if ai_hits == 1:
            return "AI Infrastructure"
        if dev_hits == 1:
            return "Developer Tools"
        if "saas" in t_low or "b2b" in t_low or "platform" in t_low:
            return "B2B SaaS"

        return "Unavailable"

    def extract_leadership_candidates(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        """Look for executive names in team / about sections."""
        candidates: list[dict[str, str]] = []
        if not soup:
            return candidates

        text = soup.get_text(" ", strip=True)

        # Regex for "Name, Founder & CEO" or "Name - Co-Founder"
        role_patterns = [
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[-–,|]\s*(Co-Founder\s+&?\s*CEO|Founder\s+&?\s*CEO|Co-Founder|Founder|CEO|Head of Marketing|VP of Marketing|Head of Brand|Head of Design)",
            r"(Co-Founder\s+&?\s*CEO|Founder\s+&?\s*CEO|Co-Founder|Founder|CEO|Head of Marketing|VP of Marketing)\s*[-–,|:]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
        ]

        for pat in role_patterns:
            matches = re.findall(pat, text)
            for m in matches:
                if len(m) == 2:
                    # Determine which is name and which is role
                    p1, p2 = m[0].strip(), m[1].strip()
                    if any(r in p1.lower() for r in ["founder", "ceo", "marketing", "brand", "design"]):
                        role, name = p1, p2
                    else:
                        name, role = p1, p2

                    # Filter false positives
                    if len(name.split()) >= 2 and not any(w in name.lower() for w in ["the", "our", "meet", "about", "team", "read", "join", "privacy", "contact"]):
                        candidates.append({
                            "full_name": name,
                            "current_role": role,
                            "verification_status": "sourced_estimate",
                            "role_evidence_source": "Public Company Website",
                        })
                        if len(candidates) >= 3:
                            return candidates

        return candidates
