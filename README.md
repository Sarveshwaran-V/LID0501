# LID0501 - Free B2B Lead Discovery and Qualification Engine

**Official Project ID:** `LID0501`  
**Human-Readable Nomenclature:** `LID · 05 · 01`  
**Project Folder:** `lid`  
**Application Type:** Local-first, terminal-based Python CLI  
**Target User:** Ikaiva Studio (B2B Brand, Design & Positioning Studio)

---

## 1. Primary Purpose & Scope

LID0501 is a local-first lead discovery and qualification engine designed to automate the manual lead research process for **Ikaiva Studio** with **zero mandatory operating costs** (no paid APIs, no subscriptions, and no paid/hosted LLMs).

> [!NOTE]
> **Boundary with `aud0501`:**
> `aud0501` is reserved for website auditing, visual design critique, automated UX analysis, and conversion review. LID0501 strictly handles prospective company discovery, buying-signal extraction, ICP qualification, and manual outreach dossier preparation.

---

## 2. Ikaiva Studio ICP (Ideal Customer Profile)

- **Geography:** United States headquarters.
- **Target Segments (Discovery Target Ratio):**
  - **60% AI Infrastructure & Developer Tools:** AI infrastructure, foundation platforms, developer tools, developer infrastructure, B2B SaaS.
  - **40% Cybersecurity:** Cloud security, application security, identity & access management, security infrastructure.
- **Preferred Company Size:** 15–200 employees (verified or sourced estimate).
- **Preferred Maturity:** Seed stage, Series A, Series B, or credible bootstrapped/growth companies.
- **Ikaiva Core Services:**
  - Brand strategy
  - Brand identity
  - Website strategy and design
  - Website interface design
  - Product positioning and messaging clarity
- **Target Project Value:** Approximately \$2,500–\$5,000 or higher.

---

## 3. Safe & Ethical LinkedIn Research Workflow

Per Section 5 of the specification, LinkedIn is **never treated as a freely scrapeable database**:
- **No Automated Login / Scraping:** Zero session cookie extraction, zero automated profile crawls, and zero headless browser bypassing.
- **Manual LinkedIn Search Link Generator:** For every qualified lead, the engine synthesizes a targeted search query and browser URL (e.g. `https://www.linkedin.com/search/results/people/?keywords="Company"+Founder+OR+CEO`). Opening and verifying this link remains an explicit user action.
- **User-Provided Imports:** Allows users to import verified LinkedIn URLs and CSV spreadsheets.
- **Extensible Enterprise Stub:** An optional official LinkedIn adapter interface is designed in `lid/sources/linkedin_stub.py` for future partner enterprise API use.

---

## 4. Free Discovery Sources

LID0501 includes modular, independent source adapters:
1. **Google News RSS (`google_news_rss`):** Discovers verifiable funding rounds, enterprise market expansions, and product launches across B2B tech and cybersecurity.
2. **GitHub Public API (`github_public_api`):** Discovers high-momentum open-source developer tools and AI infrastructure repositories, extracting official company URLs, descriptions, and traction signals.
3. **CSV & Manual Importer (`csv_importer`):** Ingests user-provided candidate lists, preserving evidence provenance.
4. **Resilience & SSRF Protection:** Every source adapter features request timeouts, error trapping (never crashes the CLI if a source is unavailable), and strict IP/DNS validation against private/loopback IP address ranges.

---

## 5. Explainable 10-Point Scoring Rubric

Each candidate lead is evaluated against transparent rules:

| Rubric Component | Max Points | Criteria |
| :--- | :--- | :--- |
| **ICP Fit** | 2.0 pts | US geography (+0.8), target sector (+0.8), 15–200 employees (+0.4) |
| **Verified Buying Signal** | 2.0 pts | Verifiable business event within past 90 days (Funding, Launch, Expansion) |
| **Credible Commercial Opportunity**| 2.0 pts | Specific driver for brand/positioning upgrade (new enterprise tier, recent funding, launch) |
| **Identified Decision-Maker** | 1.0 pt | Verified Founder, CEO, VP Marketing, or Head of Brand/Design |
| **Commercial Plausibility** | 2.0 pts | Seed, Series A, Series B stage matching Ikaiva's \$2,500–\$5,000+ project value |
| **Personalization Evidence** | 1.0 pt | Concrete facts available for a tailored opening sentence |
| **Total** | **10.0 pts** | |

### Classification:
- **8–10:** High priority (Qualified lead ready for outreach preparation)
- **7:** Potentially qualified (Human review required)
- **Below 7:** Research further or reject

---

## 6. CLI Commands Reference

Invoke the engine using `python -m lid <command>`:

```bash
# 1. Inspect status of discovery sources
python -m lid sources

# 2. Discover candidates (Optionally with Gemini 3.5 Flash Lite full profile extraction)
python -m lid discover --limit 10
python -m lid discover --limit 10 --llm

# 3. Import manual candidates or verified CSV
python -m lid import sample_leads.csv

# 4. Score candidates against 10-point rubric & generate outreach angles
python -m lid qualify
python -m lid qualify --llm

# 5. Display leads with optional filters
python -m lid show --status qualified
python -m lid show --status all --limit 50

# 6. Inspect full evidence dossier and outreach angle
python -m lid inspect "Pinecone"

# 7. View structured decision-maker profiles & LinkedIn search links
python -m lid search-links "Permit.io"
python -m lid search-links --llm

# 8. Interactive human review (approve / reject / annotate)
python -m lid review

# 9. Export qualified leads to CSV and Excel (23 required columns)
python -m lid export --format both

# 10. View discovery and qualification metrics
python -m lid stats

# 11. Add domain to suppression / opt-out list
python -m lid suppress "competitor.com" --reason "Competitor request"
```

---

## 7. Required Export Format (23 Columns)

Both CSV and Excel (`.xlsx`) exports contain all 23 required fields:
1. `Company name`
2. `Official website`
3. `LinkedIn company URL, if verified`
4. `Headquarters`
5. `Target segment`
6. `Employee count or range`
7. `Funding stage`
8. `Buying signal`
9. `Signal date`
10. `Signal evidence URL`
11. `Founder or CEO`
12. `Decision-maker role`
13. `LinkedIn profile URL, if verified`
14. `Public professional email, if verified`
15. `Other legitimate business contact method`
16. `Why this company fits Ikaiva`
17. `Personalized outreach angle`
18. `Qualification score`
19. `Score breakdown`
20. `Verification status`
21. `Missing information`
22. `Research date`
23. `Human review status`

---

## 8. Setup & Testing

### Installation
```bash
git clone https://github.com/Sarveshwaran-V/LID0501.git
cd LID0501
pip install -r requirements.txt
```

### Running Test Suite
```bash
python -m pytest lid/tests -v
```
All 18 unit and integration tests cover URL safety, SSRF blocking, domain normalization, non-destructive SQLite merging, explainable 10-point rubric scoring, and CSV/Excel export validation.
