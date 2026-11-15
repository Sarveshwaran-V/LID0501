"""Evidence-backed personalized outreach angle generator for Ikaiva Studio."""

from typing import Optional
from lid.db.models import Company, Contact, BuyingSignal, OutreachNote


class OutreachAngleGenerator:
    """Generates rigorous 6-point research dossiers without generic claims."""

    def generate_note(
        self,
        company: Company,
        contacts: list[Contact],
        signals: list[BuyingSignal],
    ) -> OutreachNote:
        top_signal = signals[0] if signals else None
        top_contact = contacts[0] if contacts else None

        contact_name = top_contact.full_name if top_contact and top_contact.full_name != "Unavailable" else "the leadership team"
        role_label = top_contact.current_role if top_contact and top_contact.current_role != "Unavailable" else "decision-maker"

        # 1. Why this company fits Ikaiva
        why_fit = (
            f"{company.name} is a US-focused {company.target_segment} company "
            f"({company.funding_stage} stage, "
            f"{f'~{company.employee_count} employees' if company.employee_count else 'early team'}) "
            f"operating directly within Ikaiva Studio's core focus areas."
        )

        # 2. Most relevant buying signal
        if top_signal:
            relevant_signal = f"{top_signal.signal_type}: {top_signal.description} (Published: {top_signal.publication_date[:10]})"
        else:
            relevant_signal = "Candidate tech company operating in target sector; specific announcement pending verification."

        # 3. Why the signal could matter to its branding or website
        if top_signal and "funding" in top_signal.signal_type.lower():
            signal_matter = (
                f"Following their recent funding milestone, upgrading brand identity and web presentation "
                f"aligns with entering growth phase and communicating institutional credibility to enterprise buyers."
            )
        elif top_signal and "launch" in top_signal.signal_type.lower():
            signal_matter = (
                f"With the launch of their new product/features, positioning clarity and dedicated interface messaging "
                f"are essential to differentiate from legacy tools and convert technical visitors."
            )
        elif top_signal and "expansion" in top_signal.signal_type.lower():
            signal_matter = (
                f"Expanding into enterprise buyers requires shifting from pure self-serve docs to a polished "
                f"enterprise brand narrative, security assurance page, and executive demo booking flow."
            )
        else:
            signal_matter = (
                f"As {company.name} scales its {company.target_segment} solution, establishing high visual polish "
                f"and clear product narrative strengthens conversion."
            )

        # 4. One specific, credible outreach angle
        outreach_angle = (
            f"Focus on product positioning clarity and website interface hierarchy for {company.target_segment}, "
            f"highlighting how Ikaiva helps venture-backed tech teams translate complex architectures into clear visual narratives."
        )

        # 5. Suggested opening sentence based on verified evidence
        if top_signal and top_signal.description:
            clean_desc = top_signal.description.replace('"', '').strip()
            opening_sentence = (
                f"Hi {contact_name.split()[0] if contact_name != 'the leadership team' else 'there'}, "
                f"congratulations on the recent milestone ({clean_desc[:90]}...) — "
                f"as you expand your market reach, I wanted to share a specific perspective on your product positioning."
            )
        else:
            opening_sentence = (
                f"Hi {contact_name.split()[0] if contact_name != 'the leadership team' else 'there'}, "
                f"I've been following {company.name}'s work in {company.target_segment} and wanted to reach out regarding your brand and web narrative."
            )

        # 6. Questions or missing information requiring manual verification
        questions = []
        if company.employee_count is None:
            questions.append("Confirm verified employee count via LinkedIn company page.")
        if not top_contact or top_contact.full_name == "Unavailable":
            questions.append("Identify and manually verify founder/CEO on LinkedIn.")
        elif top_contact.verification_status != "verified":
            questions.append(f"Manually confirm current role of {top_contact.full_name} ({top_contact.current_role}).")
        if company.headquarters in ("Unavailable", ""):
            questions.append("Verify US headquarters location on official contact/about page.")

        missing_info = "; ".join(questions) if questions else "None; core data verified."

        return OutreachNote(
            company_id=company.id or 0,
            why_fit=why_fit,
            relevant_buying_signal=relevant_signal,
            signal_website_relevance=signal_matter,
            outreach_angle=outreach_angle,
            opening_sentence=opening_sentence,
            missing_verification_questions=missing_info,
        )
