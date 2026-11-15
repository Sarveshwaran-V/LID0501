"""Typer and Rich command-line interface for LID0501."""

import os
import sys
from pathlib import Path
from typing import Optional
import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from lid import __version__, __project_id__, __nomenclature__
from lid.config import DEFAULT_DB_PATH, DEFAULT_GEMINI_MODEL, GEMINI_API_KEY
from lid.db.database import init_db
from lid.db.models import Company, Contact, BuyingSignal, EvidenceSource, ManualNote, OutreachNote
from lid.db.repository import LeadRepository
from lid.enrichment.contact_research import ContactResearchHelper
from lid.enrichment.gemini_sourcing import GeminiQuotaExhaustedError, GeminiSourcingClient
from lid.exporter.csv_exporter import CSVLeadExporter
from lid.exporter.excel_exporter import ExcelLeadExporter
from lid.scoring.outreach import OutreachAngleGenerator
from lid.scoring.rubric import LeadScorer
from lid.security import normalize_domain
from lid.sources.csv_importer import CSVImporter
from lid.sources.github_api import GitHubPublicSource
from lid.sources.google_news_rss import GoogleNewsRSSSource
from lid.sources.linkedin_stub import LinkedInOfficialAdapter

app = typer.Typer(
    name="lid",
    help=f"{__nomenclature__} ({__project_id__}) - Free B2B Lead Discovery and Qualification Engine for Ikaiva Studio",
    add_completion=False,
)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


def get_repo() -> LeadRepository:
    init_db(DEFAULT_DB_PATH)
    return LeadRepository(DEFAULT_DB_PATH)


@app.callback()
def main_callback():
    """LID0501: Local-first Free B2B Lead Discovery and Qualification Engine."""
    pass


@app.command(name="sources")
def list_sources():
    """Show available discovery sources and their current health status."""
    repo = get_repo()
    sources = [GoogleNewsRSSSource(), GitHubPublicSource(), LinkedInOfficialAdapter()]

    table = Table(title="[bold cyan]LID0501 Discovery Sources[/bold cyan]", box=box.ROUNDED)
    table.add_column("Source Name", style="bold green")
    table.add_column("Type", style="yellow")
    table.add_column("Status", style="magenta")
    table.add_column("Description", style="white")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="Checking source reachability...", total=None)
        for s in sources:
            is_ok, msg = s.check_health()
            status_style = "[green]Available[/green]" if is_ok else f"[yellow]{msg}[/yellow]"
            src_type = "Free Public Feed" if "rss" in s.source_name else ("Free Public API" if "github" in s.source_name else "Official Adapter")
            table.add_row(s.source_name, src_type, status_style, s.description)

    console.print(table)


@app.command(name="discover")
def discover(
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Specific source (e.g. google_news_rss, github_public_api)"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Custom search query"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum candidates to discover per source"),
    use_llm: bool = typer.Option(False, "--llm", help="Use Gemini 3.5 Flash Lite to extract full profiles and verified signals"),
):
    """Discover candidate companies from available permitted sources."""
    repo = get_repo()
    scorer = LeadScorer()
    outreach_gen = OutreachAngleGenerator()
    gemini_client = GeminiSourcingClient() if use_llm else None

    sources = []
    if source == "google_news_rss" or not source:
        sources.append(GoogleNewsRSSSource())
    if source == "github_public_api" or not source:
        sources.append(GitHubPublicSource())

    total_discovered = 0
    new_companies = 0
    merged_companies = 0
    profiles_extracted = 0

    mode_title = f"Discovery with Gemini 3.5 Flash Lite" if use_llm else "Free Heuristic Discovery"
    console.print(Panel(f"[bold cyan]{mode_title}[/bold cyan] (Target Limit: {limit} candidates per source)", box=box.ROUNDED))

    for src in sources:
        with Progress(SpinnerColumn(), TextColumn(f"[bold yellow]Running {src.source_name}...[/bold yellow]"), transient=True) as progress:
            progress.add_task(description="Fetching public signals...", total=None)
            try:
                results = src.discover(query=query, limit=limit)
                repo.record_research_run(src.source_name, query or "default", "success", len(results))
            except Exception as e:
                console.print(f"[bold red]Source error for {src.source_name}:[/bold red] {str(e)}")
                repo.record_research_run(src.source_name, query or "default", "failed", 0, str(e))
                continue

        console.print(f"  [green][OK][/green] {src.source_name}: Retrieved [bold]{len(results)}[/bold] public events")
        total_discovered += len(results)

        for res in results:
            dom = normalize_domain(res.website_url)
            if not dom or repo.is_suppressed(dom):
                continue

            # If Gemini is enabled, use Gemini 3.5 Flash Lite to enrich company details & signals
            llm_profiles = []
            if gemini_client and res.signal_description:
                try:
                    llm_data = gemini_client.enrich_company_and_signals(res.signal_description, res.company_name)
                    if llm_data:
                        if llm_data.get("company_name"):
                            res.company_name = llm_data["company_name"]
                        if llm_data.get("target_segment"):
                            res.target_segment = llm_data["target_segment"]
                        if llm_data.get("funding_stage") and llm_data["funding_stage"] != "Unavailable":
                            res.funding_stage = llm_data["funding_stage"]
                        if llm_data.get("employee_count"):
                            res.employee_count = llm_data["employee_count"]
                            res.employee_count_type = llm_data.get("employee_count_type", "sourced_estimate")
                        if llm_data.get("signal_type"):
                            res.signal_type = llm_data["signal_type"]
                        if llm_data.get("signal_description"):
                            res.signal_description = llm_data["signal_description"]

                    # Extract proper decision-maker profiles using Gemini
                    llm_profiles = gemini_client.extract_decision_maker_profiles(
                        res.signal_description, res.company_name, res.website_url
                    )
                except GeminiQuotaExhaustedError as eq:
                    console.print(f"\n[bold red]Gemini Quota Exhausted Error:[/bold red] {str(eq)}")
                    console.print("[red]Execution halted immediately. No fallbacks allowed per strict user configuration.[/red]")
                    raise typer.Exit(code=1)
                except Exception as ex:
                    console.print(f"[yellow]Notice during Gemini extraction for {res.company_name}:[/yellow] {str(ex)}")

            comp = Company(
                domain=dom,
                name=res.company_name,
                website_url=res.website_url,
                target_segment=res.target_segment,
                headquarters=res.headquarters,
                employee_count=res.employee_count,
                employee_count_type=res.employee_count_type,
                funding_stage=res.funding_stage,
                latest_funding_announcement=res.latest_funding,
                linkedin_company_url=res.linkedin_company_url,
                status="candidate",
            )
            comp_id, is_new = repo.upsert_company(comp)
            if is_new:
                new_companies += 1
            else:
                merged_companies += 1

            # Save buying signal
            if res.signal_description:
                sig = BuyingSignal(
                    company_id=comp_id,
                    signal_type=res.signal_type,
                    description=res.signal_description,
                    publication_date=res.signal_date,
                    original_source_url=res.signal_url,
                    source_publisher=res.source_name,
                    confidence_level=res.confidence_level,
                    uncertainty_notes=res.uncertainty_notes,
                )
                repo.add_buying_signal(sig)

            # Record provenance
            repo.add_evidence_source(
                EvidenceSource(
                    company_id=comp_id,
                    source_name=res.source_name,
                    source_url=res.signal_url,
                    raw_snippet=res.signal_description,
                )
            )

            # Save Gemini extracted full profiles
            if llm_profiles:
                for prof in llm_profiles:
                    contact = Contact(
                        company_id=comp_id,
                        full_name=prof.full_name,
                        current_role=prof.current_role,
                        public_linkedin_url=prof.linkedin_profile_url,
                        role_evidence_source=f"Gemini 3.5 Flash Lite ({prof.evidence_snippet[:80]})" if prof.evidence_snippet else "Gemini 3.5 Flash Lite Extraction",
                        verification_status=prof.verification_status,
                    )
                    repo.add_contact(contact)
                    profiles_extracted += 1
            elif res.contact_name:
                contact = Contact(
                    company_id=comp_id,
                    full_name=res.contact_name,
                    current_role=res.contact_role or "Unavailable",
                    public_linkedin_url=res.contact_linkedin,
                    verification_status="sourced_estimate",
                )
                repo.add_contact(contact)

    console.print()
    console.print(Panel(
        f"[bold green]Discovery Complete[/bold green]\n"
        f"- Candidates Discovered: [bold]{total_discovered}[/bold]\n"
        f"- New Companies Stored: [bold]{new_companies}[/bold]\n"
        f"- Duplicates / Merged: [bold]{merged_companies}[/bold]\n"
        f"- Profiles Extracted by Gemini: [bold]{profiles_extracted}[/bold]\n\n"
        f"[dim]Tip: Run 'python -m lid qualify' to score and evaluate candidates against ICP.[/dim]",
        box=box.ROUNDED,
    ))


@app.command(name="import")
def import_leads(
    file_path: Path = typer.Argument(..., help="Path to CSV file with leads or URL"),
):
    """Import manually collected candidates or verified LinkedIn records from CSV."""
    repo = get_repo()
    importer = CSVImporter()

    if not file_path.exists():
        console.print(f"[bold red]File not found:[/bold red] {file_path}")
        raise typer.Exit(code=1)

    with Progress(SpinnerColumn(), TextColumn("[yellow]Importing CSV records...[/yellow]"), transient=True) as progress:
        progress.add_task(description="Parsing CSV...", total=None)
        try:
            records = importer.import_csv(file_path)
        except Exception as e:
            console.print(f"[bold red]Import error:[/bold red] {str(e)}")
            raise typer.Exit(code=1)

    new_count = 0
    merged_count = 0

    for r in records:
        dom = normalize_domain(r.website_url)
        if not dom or repo.is_suppressed(dom):
            continue

        comp = Company(
            domain=dom,
            name=r.company_name,
            website_url=r.website_url,
            target_segment=r.target_segment,
            headquarters=r.headquarters,
            employee_count=r.employee_count,
            employee_count_type=r.employee_count_type,
            funding_stage=r.funding_stage,
            latest_funding_announcement=r.latest_funding,
            linkedin_company_url=r.linkedin_company_url,
            status="candidate",
        )
        comp_id, is_new = repo.upsert_company(comp)
        if is_new:
            new_count += 1
        else:
            merged_count += 1

        if r.signal_description:
            sig = BuyingSignal(
                company_id=comp_id,
                signal_type=r.signal_type,
                description=r.signal_description,
                publication_date=r.signal_date,
                original_source_url=r.signal_url,
                source_publisher=r.source_name,
                confidence_level="high",
            )
            repo.add_buying_signal(sig)

        repo.add_evidence_source(
            EvidenceSource(
                company_id=comp_id,
                source_name=r.source_name,
                source_url=r.signal_url,
                raw_snippet=r.signal_description,
            )
        )

        if r.contact_name:
            contact = Contact(
                company_id=comp_id,
                full_name=r.contact_name,
                current_role=r.contact_role or "Unavailable",
                public_linkedin_url=r.contact_linkedin,
                verification_status="verified" if r.contact_linkedin else "sourced_estimate",
            )
            repo.add_contact(contact)

    console.print(Panel(
        f"[bold green]Import Successful[/bold green]\n"
        f"- Records in CSV: [bold]{len(records)}[/bold]\n"
        f"- New Companies Added: [bold]{new_count}[/bold]\n"
        f"- Existing Merged: [bold]{merged_count}[/bold]",
        box=box.ROUNDED,
    ))


@app.command(name="qualify")
def qualify_leads(
    company_name: Optional[str] = typer.Option(None, "--company", "-c", help="Qualify specific company by name or domain"),
    force: bool = typer.Option(False, "--force", "-f", help="Re-score all candidates even if previously scored"),
    use_llm: bool = typer.Option(False, "--llm", help="Use Gemini 3.5 Flash Lite for bespoke outreach angles"),
):
    """Score candidates using the 10-point transparent rubric and generate outreach angles."""
    repo = get_repo()
    scorer = LeadScorer()
    outreach_gen = OutreachAngleGenerator()
    gemini_client = GeminiSourcingClient() if use_llm else None

    if company_name:
        cand = repo.get_company_by_domain_or_name(company_name)
        if not cand:
            console.print(f"[bold red]Company not found:[/bold red] {company_name}")
            raise typer.Exit(code=1)
        target_ids = [cand["id"]]
    else:
        all_comps = repo.get_all_companies(limit=500)
        target_ids = [c["id"] for c in all_comps]

    qualified_count = 0
    review_count = 0
    rejected_count = 0

    mode_label = " (with Gemini 3.5 Flash Lite)" if use_llm else ""
    with Progress(SpinnerColumn(), TextColumn(f"[yellow]Evaluating leads against ICP rubric{mode_label}...[/yellow]"), transient=True) as progress:
        progress.add_task(description="Scoring...", total=len(target_ids))

        for cid in target_ids:
            dossier = repo.get_full_lead_dossier(cid)
            if not dossier:
                continue

            comp_dict = dossier["company"]
            comp = Company(**comp_dict)
            contacts = [Contact(**c) for c in dossier["contacts"]]
            signals = [BuyingSignal(**s) for s in dossier["signals"]]
            notes = [n["note_text"] for n in dossier["notes"]]

            # Run 10-point rubric
            score = scorer.score_company(comp, contacts, signals, notes)
            repo.save_qualification_score(score)

            # Generate outreach angle note (Rule-based foundation)
            outreach = outreach_gen.generate_note(comp, contacts, signals)

            # If Gemini is enabled, synthesize bespoke non-templated outreach hooks
            if gemini_client and signals:
                try:
                    top_c = contacts[0] if contacts else None
                    c_name = top_c.full_name if top_c and top_c.full_name != "Unavailable" else "the leadership team"
                    c_role = top_c.current_role if top_c and top_c.current_role != "Unavailable" else "Founder & CEO"
                    bespoke = gemini_client.generate_bespoke_outreach(
                        company_name=comp.name,
                        target_segment=comp.target_segment,
                        signal_description=signals[0].description,
                        profile_name=c_name,
                        profile_role=c_role,
                    )
                    if bespoke and bespoke.get("opening_sentence"):
                        outreach = OutreachNote(
                            company_id=cid,
                            why_fit=bespoke.get("why_fit", outreach.why_fit),
                            relevant_buying_signal=outreach.relevant_buying_signal,
                            signal_website_relevance=bespoke.get("signal_website_relevance", outreach.signal_website_relevance),
                            outreach_angle=bespoke.get("outreach_angle", outreach.outreach_angle),
                            opening_sentence=bespoke.get("opening_sentence", outreach.opening_sentence),
                            missing_verification_questions=bespoke.get("missing_verification_questions", outreach.missing_verification_questions),
                        )
                except GeminiQuotaExhaustedError as eq:
                    console.print(f"\n[bold red]Gemini Quota Exhausted Error:[/bold red] {str(eq)}")
                    console.print("[red]Execution halted immediately. No fallbacks allowed per strict user configuration.[/red]")
                    raise typer.Exit(code=1)
                except Exception as ex:
                    console.print(f"[yellow]Notice during Gemini outreach generation for {comp.name}:[/yellow] {str(ex)}")

            repo.save_outreach_note(outreach)

            if score.total_score >= 8.0:
                qualified_count += 1
            elif score.total_score >= 7.0:
                review_count += 1
            else:
                rejected_count += 1

    console.print(Panel(
        f"[bold green]Qualification Complete[/bold green]\n"
        f"- Total Processed: [bold]{len(target_ids)}[/bold]\n"
        f"- High Priority Leads (Score 8-10): [bold green]{qualified_count}[/bold green]\n"
        f"- Potentially Qualified / Review Required (Score 7): [bold yellow]{review_count}[/bold yellow]\n"
        f"- Below 7 (Research further / reject): [dim]{rejected_count}[/dim]\n\n"
        f"[dim]Run 'python -m lid show' or 'python -m lid inspect <company>' to review leads.[/dim]",
        box=box.ROUNDED,
    ))


@app.command(name="show")
def show_leads(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter: qualified, review_required, candidate, rejected, all"),
    min_score: Optional[float] = typer.Option(None, "--min-score", "-m", help="Minimum total score"),
    segment: Optional[str] = typer.Option(None, "--segment", help="Filter by segment"),
    limit: int = typer.Option(25, "--limit", "-l", help="Number of leads to display"),
):
    """Display stored leads and their qualification scores."""
    repo = get_repo()
    filter_status = None if status == "all" else (status or "qualified")
    leads = repo.get_all_companies(status=filter_status, min_score=min_score, segment=segment, limit=limit)

    if not leads:
        console.print(f"[yellow]No leads found matching criteria (status='{filter_status}', min_score={min_score}).[/yellow]")
        return

    table = Table(
        title=f"[bold cyan]LID0501 Leads Portfolio ({len(leads)} displayed)[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold blue",
    )
    table.add_column("ID", justify="right", style="dim", width=4)
    table.add_column("Company", style="bold white", width=18)
    table.add_column("Domain / Website", style="cyan", width=22)
    table.add_column("Segment", style="magenta", width=18)
    table.add_column("Score", justify="center", style="bold yellow", width=7)
    table.add_column("Status", justify="center", width=15)
    table.add_column("Review", justify="center", width=10)
    table.add_column("Decision-Maker", style="green", width=18)

    for l in leads:
        sc = l.get("total_score")
        score_display = f"{sc:.1f}" if sc is not None else "[dim]--[/dim]"
        st = l.get("status", "candidate")
        if st == "qualified":
            st_styled = "[bold green]qualified[/bold green]"
        elif st == "review_required":
            st_styled = "[bold yellow]review_req[/bold yellow]"
        elif st == "rejected":
            st_styled = "[dim red]rejected[/dim red]"
        else:
            st_styled = "[dim]candidate[/dim]"

        rev = l.get("review_status", "pending")
        rev_styled = "[green]approved[/green]" if rev == "approved" else ("[red]rejected[/red]" if rev == "rejected" else "[yellow]pending[/yellow]")

        dm = l.get("contact_name") or "Unavailable"
        if l.get("contact_role") and l.get("contact_role") != "Unavailable":
            dm = f"{dm} ({l.get('contact_role')})"

        table.add_row(
            str(l["id"]),
            l["name"][:18],
            l["domain"][:22],
            l["target_segment"][:18],
            score_display,
            st_styled,
            rev_styled,
            dm[:18],
        )

    console.print(table)


@app.command(name="inspect")
def inspect_company(
    company_name: str = typer.Argument(..., help="Company name or domain to inspect"),
):
    """Show the full evidence record, score breakdown, and outreach angle for a company."""
    repo = get_repo()
    comp = repo.get_company_by_domain_or_name(company_name)
    if not comp:
        console.print(f"[bold red]Company not found:[/bold red] {company_name}")
        raise typer.Exit(code=1)

    dossier = repo.get_full_lead_dossier(comp["id"])
    c = dossier["company"]
    score = dossier["score"]
    outreach = dossier["outreach"]
    contacts = dossier["contacts"]
    signals = dossier["signals"]
    evidence = dossier["evidence"]

    # Header Panel
    emp_str = str(c.get("employee_count")) if c.get("employee_count") is not None else "Unavailable"
    console.print(Panel(
        f"[bold cyan]{c['name']}[/bold cyan] ({c['domain']})\n"
        f"- Website: [blue]{c['website_url']}[/blue]\n"
        f"- Segment: [magenta]{c['target_segment']}[/magenta] | HQ: {c['headquarters']}\n"
        f"- Size: {emp_str} ({c['employee_count_type']}) | Stage: {c['funding_stage']}\n"
        f"- Review Status: [bold]{c['review_status']}[/bold] | Lead Status: [bold]{c['status']}[/bold]",
        title=f"Company Dossier (ID: {c['id']})",
        box=box.ROUNDED,
    ))

    # Score Panel
    if score:
        sc_table = Table(box=box.SIMPLE, show_header=False)
        sc_table.add_row("[bold]Total Score:[/bold]", f"[bold yellow]{score['total_score']} / 10.0[/bold yellow] ({score['classification']})")
        sc_table.add_row("ICP Fit:", f"{score['icp_fit_score']} / 2.0")
        sc_table.add_row("Buying Signal:", f"{score['buying_signal_score']} / 2.0")
        sc_table.add_row("Commercial Opportunity:", f"{score['commercial_opportunity_score']} / 2.0")
        sc_table.add_row("Decision-Maker:", f"{score['decision_maker_score']} / 1.0")
        sc_table.add_row("Commercial Plausibility:", f"{score['commercial_plausibility_score']} / 2.0")
        sc_table.add_row("Personalization Evidence:", f"{score['personalization_evidence_score']} / 1.0")
        console.print(Panel(sc_table, title="Explainable Qualification Score", box=box.ROUNDED))
        console.print(f"[dim]Rubric Breakdown: {score['explanation']}[/dim]\n")

    # Outreach Note
    if outreach:
        console.print(Panel(
            f"[bold]1. Why this company fits Ikaiva:[/bold]\n{outreach['why_fit']}\n\n"
            f"[bold]2. Most relevant buying signal:[/bold]\n{outreach['relevant_buying_signal']}\n\n"
            f"[bold]3. Why signal matters to branding/website:[/bold]\n{outreach['signal_website_relevance']}\n\n"
            f"[bold]4. Specific outreach angle:[/bold]\n{outreach['outreach_angle']}\n\n"
            f"[bold green]5. Suggested opening sentence:[/bold green]\n\"{outreach['opening_sentence']}\"\n\n"
            f"[bold red]6. Missing info to verify:[/bold red]\n{outreach['missing_verification_questions']}",
            title="Personalized Outreach Dossier",
            box=box.ROUNDED,
        ))

    # Contacts & Search URL
    li_rec = ContactResearchHelper.build_search_record(
        c["name"], c["website_url"], contacts[0]["full_name"] if contacts else None
    )
    console.print(Panel(
        f"- Suggested Role Target: [bold]{li_rec['suggested_role']}[/bold]\n"
        f"- Manual Search Query: [cyan]{li_rec['search_keywords']}[/cyan]\n"
        f"- Browser Search URL: [underline blue]{li_rec['manual_search_url']}[/underline blue]\n"
        f"[dim](Opening this search link must be an explicit manual user browser action)[/dim]",
        title="Safe Manual LinkedIn Research",
        box=box.ROUNDED,
    ))


@app.command(name="review")
def review_leads():
    """Interactively review, approve, reject, or annotate pending candidate leads."""
    repo = get_repo()
    pending = repo.get_all_companies(review_status="pending", limit=50)

    if not pending:
        console.print("[green]No candidates currently awaiting human review.[/green]")
        return

    console.print(Panel(f"[bold cyan]Human Review Workflow[/bold cyan] ({len(pending)} pending)", box=box.ROUNDED))

    for idx, item in enumerate(pending, start=1):
        cid = item["id"]
        dossier = repo.get_full_lead_dossier(cid)
        c = dossier["company"]
        sc = dossier["score"]
        outreach = dossier["outreach"]

        console.print()
        console.print(f"[bold yellow]Lead {idx}/{len(pending)}:[/bold yellow] [bold white]{c['name']}[/bold white] ({c['domain']})")
        console.print(f"  Segment: {c['target_segment']} | HQ: {c['headquarters']} | Stage: {c['funding_stage']}")
        if sc:
            console.print(f"  Score: [bold yellow]{sc['total_score']} / 10[/bold yellow] ({sc['classification']})")
        if outreach:
            console.print(f"  Angle: [dim]{outreach['outreach_angle']}[/dim]")

        action = Prompt.ask(
            "Action",
            choices=["a", "r", "n", "s", "q"],
            default="s",
            show_choices=False,
            prompt_suffix=" ([bold green]a[/bold green]pprove / [bold red]r[/bold red]eject / [bold cyan]n[/bold cyan]ote / [dim]s[/dim]kip / [dim]q[/dim]uit): ",
        )

        if action == "a":
            repo.update_company_review(cid, "approved")
            console.print(f"  [green][OK] Approved {c['name']} as qualified lead[/green]")
        elif action == "r":
            reason = Prompt.ask("Rejection reason", default="ICP mismatch")
            repo.update_company_review(cid, "rejected", reason)
            console.print(f"  [red][X] Marked {c['name']} as rejected: {reason}[/red]")
        elif action == "n":
            note_text = Prompt.ask("Enter manual note")
            repo.add_manual_note(cid, note_text)
            console.print("  [cyan][OK] Note saved[/cyan]")
        elif action == "q":
            console.print("[dim]Exiting review.[/dim]")
            break
        else:
            console.print("  [dim]Skipped[/dim]")


@app.command(name="export")
def export_leads(
    format: str = typer.Option("both", "--format", "-f", help="Export format: csv, excel, or both"),
    status: str = typer.Option("qualified", "--status", "-s", help="Filter: qualified, all, review_required"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Custom output directory or file path"),
):
    """Export qualified leads to CSV and Excel."""
    repo = get_repo()
    filter_status = None if status == "all" else status
    raw_leads = repo.get_all_companies(status=filter_status, limit=1000)

    if not raw_leads:
        console.print(f"[yellow]No leads found to export for status='{status}'.[/yellow]")
        return

    # Load full dossier for each lead
    leads_dossiers = []
    for l in raw_leads:
        d = repo.get_full_lead_dossier(l["id"])
        if d:
            leads_dossiers.append(d)

    out_dir = output if output and output.is_dir() else (output.parent if output else Path("."))
    base_name = output.stem if output and not output.is_dir() else f"ikaiva_qualified_leads_{status}"

    csv_exporter = CSVLeadExporter()
    excel_exporter = ExcelLeadExporter()

    exported_files = []

    if format in ("csv", "both"):
        csv_path = out_dir / f"{base_name}.csv"
        csv_exporter.export(leads_dossiers, csv_path)
        repo.record_export("csv", len(leads_dossiers), str(csv_path))
        exported_files.append(csv_path)

    if format in ("excel", "both"):
        xlsx_path = out_dir / f"{base_name}.xlsx"
        excel_exporter.export(leads_dossiers, xlsx_path)
        repo.record_export("excel", len(leads_dossiers), str(xlsx_path))
        exported_files.append(xlsx_path)

    console.print(Panel(
        f"[bold green]Export Successful[/bold green]\n"
        f"- Total Rows: [bold]{len(leads_dossiers)}[/bold]\n"
        f"- Files Generated:\n" + "\n".join([f"  - [blue]{p.resolve()}[/blue]" for p in exported_files]),
        box=box.ROUNDED,
    ))


@app.command(name="search-links")
def search_links(
    company_name: Optional[str] = typer.Argument(None, help="Company name or domain to generate search links for"),
    use_llm: bool = typer.Option(False, "--llm", help="Use Gemini 3.5 Flash Lite to extract and verify proper profiles"),
):
    """Generate structured LinkedIn decision-maker profiles and verification links."""
    repo = get_repo()
    gemini_client = GeminiSourcingClient() if use_llm else None

    if company_name:
        cand = repo.get_company_by_domain_or_name(company_name)
        if not cand:
            console.print(f"[bold red]Company not found:[/bold red] {company_name}")
            raise typer.Exit(code=1)
        targets = [cand]
    else:
        targets = repo.get_all_companies(status="qualified", limit=20)
        if not targets:
            targets = repo.get_all_companies(limit=10)

    table = Table(title="[bold cyan]LinkedIn Decision-Maker Profiles & Research Links[/bold cyan]", box=box.ROUNDED)
    table.add_column("Company", style="bold white", width=16)
    table.add_column("Identified Person", style="bold green", width=18)
    table.add_column("Exact Role", style="yellow", width=18)
    table.add_column("Direct Profile URL", style="cyan", width=26)
    table.add_column("Manual Search URL", style="blue")

    for t in targets:
        dossier = repo.get_full_lead_dossier(t["id"])
        contacts = dossier.get("contacts", [])
        signals = dossier.get("signals", [])

        # If LLM enabled and no verified contact or explicit request, extract via Gemini 3.5 Flash Lite
        if gemini_client and signals and (not contacts or contacts[0]["full_name"] == "Unavailable"):
            try:
                extracted_profs = gemini_client.extract_decision_maker_profiles(
                    signals[0]["description"], t["name"], t["website_url"]
                )
                for ep in extracted_profs:
                    repo.add_contact(Contact(
                        company_id=t["id"],
                        full_name=ep.full_name,
                        current_role=ep.current_role,
                        public_linkedin_url=ep.linkedin_profile_url,
                        role_evidence_source=f"Gemini 3.5 Flash Lite ({ep.evidence_snippet[:60]})" if ep.evidence_snippet else "Gemini Extraction",
                        verification_status=ep.verification_status,
                    ))
                dossier = repo.get_full_lead_dossier(t["id"])
                contacts = dossier.get("contacts", [])
            except GeminiQuotaExhaustedError as eq:
                console.print(f"\n[bold red]Gemini Quota Exhausted Error:[/bold red] {str(eq)}")
                console.print("[red]Execution halted immediately. No fallbacks allowed per strict user configuration.[/red]")
                raise typer.Exit(code=1)
            except Exception as ex:
                console.print(f"[yellow]Notice during Gemini profile search for {t['name']}:[/yellow] {str(ex)}")

        if contacts and contacts[0]["full_name"] != "Unavailable":
            for c in contacts:
                direct_url = c["public_linkedin_url"] or "[dim]Pending link[/dim]"
                li_rec = ContactResearchHelper.build_search_record(t["name"], t["website_url"], c["full_name"])
                table.add_row(t["name"][:16], c["full_name"][:18], c["current_role"][:18], direct_url[:26], li_rec["manual_search_url"])
        else:
            li_rec = ContactResearchHelper.build_search_record(t["name"], t["website_url"], None)
            table.add_row(t["name"][:16], "[dim]Unidentified[/dim]", li_rec["suggested_role"][:18], "[dim]Unavailable[/dim]", li_rec["manual_search_url"])

    console.print(table)
    console.print("[dim]Profiles and search links generated. Opening external links must remain an explicit user browser action.[/dim]")


@app.command(name="stats")
def show_stats():
    """Show discovery and qualification statistics."""
    repo = get_repo()
    stats = repo.get_stats()

    table = Table(title="[bold cyan]LID0501 Discovery & Qualification Metrics[/bold cyan]", box=box.ROUNDED)
    table.add_column("Metric", style="bold white")
    table.add_column("Count", justify="right", style="bold green")

    table.add_row("Total Candidate Companies", str(stats["total_candidates"]))
    table.add_row("Qualified Leads (Score >= 8.0)", str(stats["qualified_leads"]))
    table.add_row("Awaiting Human Review (Pending)", str(stats["review_pending"]))
    table.add_row("Rejected Leads", str(stats["rejected_leads"]))
    table.add_row("Buying Signals Recorded", str(stats["signals_recorded"]))
    table.add_row("Identified Contacts", str(stats["contacts_identified"]))

    console.print(table)

    # Segment Breakdown
    if stats["segments"]:
        seg_table = Table(title="[bold cyan]Segment Distribution[/bold cyan]", box=box.ROUNDED)
        seg_table.add_column("Segment", style="magenta")
        seg_table.add_column("Count", justify="right", style="yellow")
        for seg, count in stats["segments"].items():
            seg_table.add_row(seg or "Unclassified", str(count))
        console.print(seg_table)


@app.command(name="suppress")
def suppress_domain(
    domain: str = typer.Argument(..., help="Domain to suppress/opt-out"),
    reason: str = typer.Option("User opt-out", "--reason", "-r", help="Reason for suppression"),
):
    """Add a company domain to the suppression/opt-out list."""
    repo = get_repo()
    norm = normalize_domain(domain)
    repo.add_suppression(norm, None, reason)
    console.print(f"[green][OK] Domain '{norm}' added to suppression list. Future discovery and exports will ignore it.[/green]")
