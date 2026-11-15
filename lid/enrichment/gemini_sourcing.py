"""Gemini 3.5 Flash Lite LLM sourcing, decision-maker profile extraction, and intelligence engine.

Extracts complete structured profiles (names, roles, LinkedIn URLs, evidence)
with strict halting on token exhaustion (NO fallback).
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional
import httpx

from lid.config import DEFAULT_GEMINI_MODEL, DEFAULT_TIMEOUT, GEMINI_API_BASE_URL, GEMINI_API_KEY


class GeminiQuotaExhaustedError(Exception):
    """Raised when Gemini token quota or rate limit is exhausted.
    
    Per strict instruction: NO fallbacks are executed when tokens are exhausted.
    """
    pass


@dataclass
class DecisionMakerProfile:
    full_name: str
    current_role: str
    linkedin_profile_url: Optional[str] = None
    relevance_reason: str = ""
    verification_status: str = "sourced_estimate"
    evidence_snippet: str = ""


class GeminiSourcingClient:
    """Client for Gemini 3.5 Flash Lite sourcing and structured profile intelligence."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or DEFAULT_GEMINI_MODEL
        self.base_url = GEMINI_API_BASE_URL

    def _call_gemini(
        self,
        prompt: str,
        system_instruction: str = "",
        response_mime_type: str = "application/json",
    ) -> str:
        """Call Google AI Studio Gemini API endpoint with strict quota enforcement."""
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please export GEMINI_API_KEY or provide it in environment."
            )

        endpoint = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"

        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": response_mime_type,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                resp = client.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
        except Exception as exc:
            # Check if network error contains quota or rate limit
            err_str = str(exc)
            if "429" in err_str or "quota" in err_str.lower():
                raise GeminiQuotaExhaustedError(
                    f"Gemini {self.model} token/quota exhausted. Halting without fallback."
                ) from exc
            raise

        # Strict Quota / Rate-limit detection: NO FALLBACK PER USER INSTRUCTION
        if resp.status_code == 429 or "RESOURCE_EXHAUSTED" in resp.text or "Quota exceeded" in resp.text:
            raise GeminiQuotaExhaustedError(
                f"Gemini {self.model} tokens or quota exhausted (HTTP 429 / RESOURCE_EXHAUSTED). "
                f"Halting execution with no fallback per configuration."
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Gemini API error (Status {resp.status_code}): {resp.text}"
            )

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {data}")

        part = candidates[0].get("content", {}).get("parts", [{}])[0]
        text_content = part.get("text", "")
        return text_content.strip()

    def extract_decision_maker_profiles(
        self, text: str, company_name: str, domain: str = ""
    ) -> list[DecisionMakerProfile]:
        """Combs through public announcements, press, or website copy to extract complete structured profiles."""
        system_prompt = (
            "You are an expert executive intelligence researcher for Ikaiva Studio, a design and brand positioning studio. "
            "Your task is to identify and extract legitimate decision-maker profiles from the provided text for the specified company. "
            "Priority targets: Founder, Co-Founder, CEO, VP of Marketing, Head of Brand, Head of Design. "
            "Return a JSON array of profile objects."
        )

        user_prompt = f"""Company: {company_name} (Domain: {domain})
Text content to analyze:
\"\"\"
{text[:4000]}
\"\"\"

Output format must be a valid JSON array of objects:
[
  {{
    "full_name": "Full name of the executive/founder",
    "current_role": "Exact role (e.g. Co-Founder & CEO, VP Marketing)",
    "linkedin_profile_url": "Direct LinkedIn profile URL if mentioned or construct legitimate public handle https://www.linkedin.com/in/firstname-lastname",
    "relevance_reason": "Specific reason why this person is the decision-maker for brand identity, product positioning, or website interface design",
    "verification_status": "verified or sourced_estimate",
    "evidence_snippet": "Exact quote from text corroborating their role"
  }}
]
If no executive is mentioned, return an empty array [].
"""

        raw_json = self._call_gemini(
            prompt=user_prompt,
            system_instruction=system_prompt,
            response_mime_type="application/json",
        )

        try:
            parsed = json.loads(raw_json)
            if not isinstance(parsed, list):
                parsed = [parsed]
        except Exception:
            return []

        profiles: list[DecisionMakerProfile] = []
        for p in parsed:
            name = p.get("full_name", "").strip()
            role = p.get("current_role", "").strip()
            if name and name.lower() not in ("unavailable", "none", "unknown") and len(name.split()) >= 2:
                profiles.append(
                    DecisionMakerProfile(
                        full_name=name,
                        current_role=role or "Founder",
                        linkedin_profile_url=p.get("linkedin_profile_url"),
                        relevance_reason=p.get("relevance_reason", ""),
                        verification_status=p.get("verification_status", "sourced_estimate"),
                        evidence_snippet=p.get("evidence_snippet", ""),
                    )
                )

        return profiles

    def enrich_company_and_signals(
        self, raw_content: str, source_title: str = ""
    ) -> dict[str, Any]:
        """Extracts structured company metadata, target segment, funding, and buying signals."""
        system_prompt = (
            "You are a B2B SaaS and Tech market intelligence specialist for Ikaiva Studio. "
            "Analyze raw news or web snippets to extract structured company details matching Ikaiva's ICP: "
            "Segments: AI Infrastructure, Developer Tools, Cybersecurity, B2B SaaS. "
            "Extract verified facts only. Return a valid JSON object."
        )

        user_prompt = f"""Headline: {source_title}
Content:
\"\"\"
{raw_content[:4000]}
\"\"\"

Extract into this exact JSON structure:
{{
  "company_name": "Official company name",
  "website_url": "https://domain.com",
  "target_segment": "One of: AI Infrastructure, Developer Tools, Cybersecurity, B2B SaaS",
  "headquarters": "City, State or United States",
  "employee_count": integer or null,
  "employee_count_type": "verified, sourced_estimate, or unavailable",
  "funding_stage": "Seed, Series A, Series B, Bootstrapped, or Unavailable",
  "latest_funding_announcement": "Specific funding details or null",
  "signal_type": "Recent Funding Announcement, New Product Launch, Enterprise Market Expansion, or Major Feature Release",
  "signal_description": "Concise factual summary of the business milestone",
  "confidence_level": "high, medium, or low"
}}
"""

        raw_json = self._call_gemini(
            prompt=user_prompt,
            system_instruction=system_prompt,
            response_mime_type="application/json",
        )

        try:
            return json.loads(raw_json)
        except Exception:
            return {}

    def generate_bespoke_outreach(
        self,
        company_name: str,
        target_segment: str,
        signal_description: str,
        profile_name: str,
        profile_role: str,
    ) -> dict[str, str]:
        """Synthesizes high-converting, personalized 2-sentence conversational opening hooks using Gemini."""
        system_prompt = (
            "You are an elite brand and positioning outreach strategist for Ikaiva Studio. "
            "Ikaiva offers: Brand strategy, Brand identity, Website strategy and interface design, Product positioning and messaging clarity. "
            "Write a bespoke, compelling, non-generic outreach hook for the executive."
        )

        user_prompt = f"""Company: {company_name} ({target_segment})
Executive: {profile_name} ({profile_role})
Buying Signal / Milestone: {signal_description}

Generate JSON with:
{{
  "why_fit": "Why this company and milestone fits Ikaiva's core sweet spot",
  "signal_website_relevance": "Why this specific milestone creates an immediate need for brand positioning clarity or website UI polish",
  "outreach_angle": "The commercial strategic angle to pitch",
  "opening_sentence": "A natural, non-fluff, highly tailored opening sentence addressing the executive by first name, referencing their verified milestone, and proposing a fresh positioning perspective.",
  "missing_verification_questions": "Any remaining verification check required"
}}
"""

        raw_json = self._call_gemini(
            prompt=user_prompt,
            system_instruction=system_prompt,
            response_mime_type="application/json",
        )

        try:
            return json.loads(raw_json)
        except Exception:
            return {}
