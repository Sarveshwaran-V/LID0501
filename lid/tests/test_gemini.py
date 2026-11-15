"""Tests for Gemini 3.5 Flash Lite sourcing, profile extraction, and strict quota halting."""

import json
from unittest.mock import MagicMock, patch
import pytest
import httpx

from lid.enrichment.gemini_sourcing import (
    DecisionMakerProfile,
    GeminiQuotaExhaustedError,
    GeminiSourcingClient,
)


def test_gemini_extract_decision_maker_profiles_success():
    client = GeminiSourcingClient(api_key="test-key", model="gemini-3.5-flash-lite")

    mock_gemini_output = json.dumps([
        {
            "full_name": "Edo Liberty",
            "current_role": "Founder & CEO",
            "linkedin_profile_url": "https://www.linkedin.com/in/edoliberty",
            "relevance_reason": "Decision-maker for Pinecone's enterprise visual positioning and architecture website",
            "verification_status": "verified",
            "evidence_snippet": "Founder and CEO Edo Liberty announced the serverless architecture launch."
        }
    ])

    with patch.object(client, "_call_gemini", return_value=mock_gemini_output):
        profiles = client.extract_decision_maker_profiles(
            text="Founder and CEO Edo Liberty announced the serverless architecture launch.",
            company_name="Pinecone",
            domain="pinecone.io"
        )

        assert len(profiles) == 1
        p = profiles[0]
        assert p.full_name == "Edo Liberty"
        assert p.current_role == "Founder & CEO"
        assert p.linkedin_profile_url == "https://www.linkedin.com/in/edoliberty"
        assert "Pinecone" in p.relevance_reason
        assert p.verification_status == "verified"


def test_strict_quota_exhaustion_halts_without_fallback():
    client = GeminiSourcingClient(api_key="test-key", model="gemini-3.5-flash-lite")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    mock_resp.text = '{"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota).", "status": "RESOURCE_EXHAUSTED"}}'

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(GeminiQuotaExhaustedError) as exc_info:
            client._call_gemini("Test prompt")

        # Verify error message states execution halted with no fallback
        assert "tokens or quota exhausted" in str(exc_info.value).lower()
        assert "no fallback" in str(exc_info.value).lower()


def test_gemini_enrich_company_and_signals():
    client = GeminiSourcingClient(api_key="test-key", model="gemini-3.5-flash-lite")

    mock_json = json.dumps({
        "company_name": "Lasso Security",
        "website_url": "https://lasso.security",
        "target_segment": "Cybersecurity",
        "headquarters": "Austin, TX",
        "employee_count": 30,
        "employee_count_type": "sourced_estimate",
        "funding_stage": "Seed",
        "signal_type": "Recent Funding Announcement",
        "signal_description": "Raised $6M Seed round to expand LLM application security",
        "confidence_level": "high"
    })

    with patch.object(client, "_call_gemini", return_value=mock_json):
        res = client.enrich_company_and_signals("Lasso Security closes $6M Seed round")
        assert res["company_name"] == "Lasso Security"
        assert res["target_segment"] == "Cybersecurity"
        assert res["employee_count"] == 30
        assert res["funding_stage"] == "Seed"


def test_gemini_bespoke_outreach():
    client = GeminiSourcingClient(api_key="test-key", model="gemini-3.5-flash-lite")

    mock_json = json.dumps({
        "why_fit": "Lasso Security is a high-growth AI security company.",
        "signal_website_relevance": "Need clear landing page explaining LLM security guardrails to enterprise buyers.",
        "outreach_angle": "Translate complex runtime LLM defense into clear executive UI hierarchy.",
        "opening_sentence": "Hi Elad, congratulations on closing the $6M Seed round for Lasso Security...",
        "missing_verification_questions": "Verify employee count."
    })

    with patch.object(client, "_call_gemini", return_value=mock_json):
        outreach = client.generate_bespoke_outreach(
            company_name="Lasso Security",
            target_segment="Cybersecurity",
            signal_description="Raised $6M Seed round",
            profile_name="Elad Schulman",
            profile_role="CEO"
        )
        assert "Elad" in outreach["opening_sentence"]
        assert "Lasso Security" in outreach["why_fit"]
