"""Command-line interface for paper tracker."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .arxiv_client import ArxivClient
from .database import Database
from .models import Paper
from .semantic_scholar_client import SemanticScholarClient


console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="paper-tracker")
def main():
    """Research Paper Tracker - Track LLM inference papers from arXiv."""
    pass


@main.command()
@click.option("--days", default=7, help="Number of days to look back")
@click.option("--max-results", default=100, help="Maximum results to fetch")
@click.option("--dry-run", is_flag=True, help="Don't save to database")
@click.option("--enrich", is_flag=True, help="Enrich with Semantic Scholar data (citations)")
def fetch(days: int, max_results: int, dry_run: bool, enrich: bool):
    """Fetch recent LLM inference papers from arXiv."""
    console.print(f"\n[bold blue]Fetching papers from the last {days} days...[/bold blue]\n")
    
    client = ArxivClient()
    
    with console.status("[bold green]Querying arXiv API..."):
        papers = client.fetch_llm_inference_papers(
            days_back=days,
            max_results=max_results,
        )
    
    console.print(f"[green]✓[/green] Found {len(papers)} papers\n")
    
    if not papers:
        console.print("[yellow]No papers found matching criteria.[/yellow]")
        return
    
    # Enrich with Semantic Scholar data
    if enrich:
        with console.status("[bold green]Enriching with Semantic Scholar data..."):
            s2_client = SemanticScholarClient()
            papers = s2_client.enrich_papers(papers)
        console.print("[green]✓[/green] Added citation data\n")
    
    # Display results
    table = Table(title="Recent LLM Inference Papers")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Authors", style="dim", max_width=25)
    table.add_column("Date", style="green")
    table.add_column("Cat", style="magenta")
    if enrich:
        table.add_column("Cites", style="yellow", justify="right")
    
    for paper in papers[:20]:  # Show first 20
        row = [
            paper.arxiv_id,
            paper.title[:47] + "..." if len(paper.title) > 50 else paper.title,
            paper.authors_str[:22] + "..." if len(paper.authors_str) > 25 else paper.authors_str,
            paper.published.strftime("%Y-%m-%d"),
            paper.primary_category,
        ]
        if enrich:
            row.append(str(paper.citation_count))
        table.add_row(*row)
    
    console.print(table)
    
    if len(papers) > 20:
        console.print(f"\n[dim]... and {len(papers) - 20} more papers[/dim]")
    
    # Save to database
    if not dry_run:
        db = Database()
        new_count, dup_count = db.insert_papers(papers)
        console.print(f"\n[green]✓[/green] Saved {new_count} new papers ({dup_count} duplicates skipped)")
    else:
        console.print("\n[yellow]Dry run - papers not saved to database[/yellow]")


@main.command()
@click.option("--limit", default=50, help="Number of papers to enrich")
def enrich(limit: int):
    """Enrich stored papers with Semantic Scholar citation data."""
    db = Database()
    papers = db.list_papers(limit=limit)
    
    if not papers:
        console.print("[yellow]No papers found. Run 'paper-tracker fetch' first.[/yellow]")
        return
    
    console.print(f"\n[bold blue]Enriching {len(papers)} papers with Semantic Scholar data...[/bold blue]\n")
    
    s2_client = SemanticScholarClient()
    
    with console.status("[bold green]Fetching citation data..."):
        enriched = s2_client.enrich_papers(papers)
    
    # Update database with enriched data
    updated_count = 0
    for paper in enriched:
        if paper.citation_count > 0 or paper.venue:
            if db.update_paper(paper):
                updated_count += 1
    
    console.print(f"[green]✓[/green] Updated {updated_count} papers with citation data\n")
    
    # Show top cited papers
    cited_papers = sorted(enriched, key=lambda p: p.citation_count, reverse=True)[:10]
    
    if any(p.citation_count > 0 for p in cited_papers):
        table = Table(title="Top Cited Papers (from your collection)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="white", max_width=50)
        table.add_column("Citations", style="yellow", justify="right")
        table.add_column("Influential", style="green", justify="right")
        
        for paper in cited_papers:
            if paper.citation_count > 0:
                table.add_row(
                    paper.arxiv_id,
                    paper.title[:47] + "..." if len(paper.title) > 50 else paper.title,
                    str(paper.citation_count),
                    str(paper.influential_citation_count),
                )
        
        console.print(table)


@main.command("list")
@click.option("--limit", default=20, help="Number of papers to show")
@click.option("--days", default=None, type=int, help="Filter by days since publication")
@click.option("--category", default=None, help="Filter by category (e.g., cs.LG)")
@click.option("--sort-citations", is_flag=True, help="Sort by citation count")
def list_papers(limit: int, days: int, category: str, sort_citations: bool):
    """List papers from the local database."""
    db = Database()
    papers = db.list_papers(limit=limit, since_days=days, category=category)
    
    if not papers:
        console.print("[yellow]No papers found. Run 'paper-tracker fetch' first.[/yellow]")
        return
    
    if sort_citations:
        papers = sorted(papers, key=lambda p: p.citation_count, reverse=True)
    
    table = Table(title="Stored Papers")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Authors", style="dim", max_width=22)
    table.add_column("Date", style="green")
    table.add_column("Cat", style="magenta")
    table.add_column("Cites", style="yellow", justify="right")
    
    for paper in papers:
        table.add_row(
            paper.arxiv_id,
            paper.title[:47] + "..." if len(paper.title) > 50 else paper.title,
            paper.authors_str[:19] + "..." if len(paper.authors_str) > 22 else paper.authors_str,
            paper.published.strftime("%Y-%m-%d"),
            paper.primary_category,
            str(paper.citation_count) if paper.citation_count else "-",
        )
    
    console.print(table)


@main.command()
@click.argument("keyword")
@click.option("--limit", default=20, help="Number of results to show")
def search(keyword: str, limit: int):
    """Search papers by keyword in title or abstract."""
    db = Database()
    papers = db.search_papers(keyword, limit=limit)
    
    if not papers:
        console.print(f"[yellow]No papers found matching '{keyword}'[/yellow]")
        return
    
    console.print(f"\n[bold]Found {len(papers)} papers matching '{keyword}':[/bold]\n")
    
    for paper in papers:
        citation_info = f" | [yellow]Citations: {paper.citation_count}[/yellow]" if paper.citation_count else ""
        panel = Panel(
            Text.from_markup(
                f"[bold]{paper.title}[/bold]\n\n"
                f"[dim]{paper.authors_str}[/dim]\n\n"
                f"{paper.abstract[:300]}..."
            ),
            title=f"[cyan]{paper.arxiv_id}[/cyan] | [green]{paper.published.strftime('%Y-%m-%d')}[/green]{citation_info}",
            border_style="blue",
        )
        console.print(panel)
        console.print()


@main.command()
@click.argument("arxiv_id")
def show(arxiv_id: str):
    """Show details for a specific paper."""
    db = Database()
    paper = db.get_paper(arxiv_id)
    
    if not paper:
        # Try fetching from arXiv
        console.print("[yellow]Paper not in database. Fetching from arXiv...[/yellow]")
        client = ArxivClient()
        papers = client.search(query=f"id:{arxiv_id}", max_results=1)
        if papers:
            paper = papers[0]
            db.insert_paper(paper)
        else:
            console.print(f"[red]Paper not found: {arxiv_id}[/red]")
            return
    
    # Build citation info string
    citation_info = ""
    if paper.citation_count:
        citation_info = (
            f"\n\n[bold]Citations:[/bold] {paper.citation_count}"
            f" ([green]{paper.influential_citation_count}[/green] influential)"
        )
    if paper.venue:
        citation_info += f"\n[bold]Venue:[/bold] {paper.venue}"
    
    console.print(Panel(
        Text.from_markup(
            f"[bold cyan]{paper.title}[/bold cyan]\n\n"
            f"[bold]Authors:[/bold] {', '.join(paper.authors)}\n\n"
            f"[bold]Categories:[/bold] {', '.join(paper.categories)}\n\n"
            f"[bold]Published:[/bold] {paper.published.strftime('%Y-%m-%d')}\n"
            f"[bold]Updated:[/bold] {paper.updated.strftime('%Y-%m-%d')}"
            f"{citation_info}\n\n"
            f"[bold]Abstract:[/bold]\n{paper.abstract}\n\n"
            f"[bold]PDF:[/bold] {paper.pdf_url}\n"
            f"[bold]arXiv:[/bold] {paper.arxiv_url}"
        ),
        title=f"[bold]{paper.arxiv_id}[/bold]",
        border_style="green",
    ))


@main.command()
def stats():
    """Show database statistics."""
    db = Database()
    stats = db.get_stats()
    
    console.print(Panel(
        Text.from_markup(
            f"[bold]Total Papers:[/bold] {stats['total_papers']}\n"
            f"[bold]Papers (Last 7 Days):[/bold] {stats['papers_last_7_days']}\n\n"
            f"[bold]Top Categories:[/bold]\n" +
            "\n".join(f"  • {cat}: {count}" for cat, count in stats['top_categories'][:5])
        ),
        title="[bold cyan]Database Statistics[/bold cyan]",
        border_style="blue",
    ))


if __name__ == "__main__":
    main()
