"""10-point explainable qualification scoring engine for LID0501."""

from typing import Any
from lid.config import (
    ALL_TARGET_SEGMENTS,
    PREFERRED_EMPLOYEE_MAX,
    PREFERRED_EMPLOYEE_MIN,
    PREFERRED_STAGES,
    TARGET_GEOGRAPHY,
)
from lid.db.models import Company, Contact, BuyingSignal, QualificationScore


class LeadScorer:
    """Calculates explainable 10-point qualification score based on transparent rules."""

    def score_company(
        self,
        company: Company,
        contacts: list[Contact],
        signals: list[BuyingSignal],
        manual_notes: list[str] | None = None,
    ) -> QualificationScore:
        explanations: list[str] = []

        # 1. ICP Fit (Max 2.0 pts)
        icp_score = 0.0
        # Geography check
        hq = (company.headquarters or "").lower()
        if any(us_ind in hq for us_ind in ["united states", "usa", "us", "san francisco", "new york", "austin", "seattle", "boston", "california", "texas"]):
            icp_score += 0.8
            explanations.append("ICP: Geography verified/sourced in United States (+0.8)")
        elif hq in ("unavailable", "", None):
            icp_score += 0.4
            explanations.append("ICP: Geography unverified, pending confirmation (+0.4)")
        else:
            explanations.append(f"ICP: Non-US headquarters ({company.headquarters}) (0.0)")

        # Target Segment check
        segment = company.target_segment or ""
        matched_segment = any(seg.lower() in segment.lower() for seg in ALL_TARGET_SEGMENTS)
        if matched_segment:
            icp_score += 0.8
            explanations.append(f"ICP: Target sector '{segment}' directly matches Ikaiva focus (+0.8)")
        elif segment not in ("Unavailable", ""):
            icp_score += 0.4
            explanations.append(f"ICP: Sector '{segment}' has partial B2B relevance (+0.4)")
        else:
            explanations.append("ICP: Sector unavailable/unclassified (0.0)")

        # Company Size check (15 - 200 employees)
        if company.employee_count is not None:
            if PREFERRED_EMPLOYEE_MIN <= company.employee_count <= PREFERRED_EMPLOYEE_MAX:
                icp_score += 0.4
                explanations.append(f"ICP: Employee count ({company.employee_count}) within ideal 15-200 range (+0.4)")
            elif company.employee_count < PREFERRED_EMPLOYEE_MIN:
                icp_score += 0.2
                explanations.append(f"ICP: Early team size ({company.employee_count} < 15) (+0.2)")
            else:
                icp_score += 0.1
                explanations.append(f"ICP: Large org size ({company.employee_count} > 200) (+0.1)")
        else:
            icp_score += 0.2
            explanations.append("ICP: Employee count unavailable (+0.2)")

        icp_score = min(2.0, round(icp_score, 1))

        # 2. Verified Buying Signal (Max 2.0 pts)
        signal_score = 0.0
        verified_signals = [s for s in signals if s.verification_status in ("verified", "high", "medium")]
        if verified_signals:
            top_signal = verified_signals[0]
            if top_signal.signal_type in (
                "Recent Funding Announcement",
                "New Product Launch",
                "Enterprise Market Expansion",
                "Major Feature Release",
            ):
                signal_score = 2.0
                explanations.append(f"Signal: High-priority verified business event: {top_signal.signal_type} (+2.0)")
            else:
                signal_score = 1.5
                explanations.append(f"Signal: Verified public event: {top_signal.signal_type} (+1.5)")
        elif signals:
            signal_score = 1.0
            explanations.append("Signal: Sourced signal requires corroboration (+1.0)")
        else:
            signal_score = 0.0
            explanations.append("Signal: No public buying signals found (0.0)")

        # 3. Credible Commercial Opportunity (Max 2.0 pts)
        opportunity_score = 0.0
        # Ikaiva services: Brand identity, Website interface design, Product positioning & messaging clarity
        # Need signals: Enterprise expansion, new funding round, or product launches
        has_funding = any("funding" in s.signal_type.lower() for s in signals) or company.funding_stage in ("Seed", "Series A", "Series B")
        has_expansion = any("expansion" in s.signal_type.lower() or "enterprise" in s.description.lower() for s in signals)
        has_launch = any("launch" in s.signal_type.lower() or "feature" in s.signal_type.lower() for s in signals)

        if has_expansion and has_funding:
            opportunity_score = 2.0
            explanations.append("Opportunity: Enterprise expansion + funding indicates immediate need for brand maturity and positioning clarity (+2.0)")
        elif has_funding or has_launch:
            opportunity_score = 1.6
            explanations.append("Opportunity: Recent launch/funding warrants website redesign and messaging overhaul (+1.6)")
        elif signals:
            opportunity_score = 1.0
            explanations.append("Opportunity: General B2B growth signal present (+1.0)")
        else:
            opportunity_score = 0.0
            explanations.append("Opportunity: No specific commercial opportunity detected (0.0)")

        # 4. Identified Decision-Maker (Max 1.0 pt)
        dm_score = 0.0
        verified_contacts = [c for c in contacts if c.full_name not in ("Unavailable", "") and c.verification_status == "verified"]
        sourced_contacts = [c for c in contacts if c.full_name not in ("Unavailable", "")]

        if verified_contacts:
            top_dm = verified_contacts[0]
            dm_score = 1.0
            explanations.append(f"Decision-Maker: Verified {top_dm.current_role} ({top_dm.full_name}) identified (+1.0)")
        elif sourced_contacts:
            top_dm = sourced_contacts[0]
            dm_score = 0.7
            explanations.append(f"Decision-Maker: Sourced candidate {top_dm.current_role} ({top_dm.full_name}) awaiting manual LinkedIn verification (+0.7)")
        else:
            dm_score = 0.0
            explanations.append("Decision-Maker: Incomplete, manual search query generated (0.0)")

        # 5. Commercial Plausibility (Max 2.0 pts)
        plausibility_score = 0.0
        # Matching Ikaiva target project value $2,500 - $5,000+
        stage = company.funding_stage or ""
        if any(st.lower() in stage.lower() for st in ["series a", "series b"]):
            plausibility_score = 2.0
            explanations.append(f"Plausibility: {stage} stage aligns well with $2,500–$5,000+ project budget (+2.0)")
        elif any(st.lower() in stage.lower() for st in ["seed", "bootstrapped"]):
            plausibility_score = 1.6
            explanations.append(f"Plausibility: Credible {stage} stage supports project investment (+1.6)")
        elif company.employee_count and company.employee_count >= 15:
            plausibility_score = 1.5
            explanations.append(f"Plausibility: Established team size ({company.employee_count}) indicates commercial budget (+1.5)")
        else:
            plausibility_score = 0.8
            explanations.append("Plausibility: Early/unconfirmed funding status (+0.8)")

        # 6. Personalization Evidence (Max 1.0 pt)
        personalization_score = 0.0
        if signals and signals[0].description and len(signals[0].description) > 20:
            personalization_score = 1.0
            explanations.append("Personalization: Rich factual signal available for customized opening (+1.0)")
        elif company.target_segment not in ("Unavailable", ""):
            personalization_score = 0.5
            explanations.append("Personalization: Moderate domain facts available (+0.5)")
        else:
            personalization_score = 0.0
            explanations.append("Personalization: Limited facts for personalization (0.0)")

        # Calculate Total
        total_score = round(
            icp_score + signal_score + opportunity_score + dm_score + plausibility_score + personalization_score,
            1,
        )
        total_score = min(10.0, total_score)

        # Classification
        if total_score >= 8.0:
            classification = "8–10: High priority"
        elif total_score >= 7.0:
            classification = "7: Potentially qualified; human review required"
        else:
            classification = "Below 7: Research further or reject"

        return QualificationScore(
            company_id=company.id or 0,
            total_score=total_score,
            icp_fit_score=icp_score,
            buying_signal_score=signal_score,
            commercial_opportunity_score=opportunity_score,
            decision_maker_score=dm_score,
            commercial_plausibility_score=plausibility_score,
            personalization_evidence_score=personalization_score,
            classification=classification,
            explanation="; ".join(explanations),
        )
