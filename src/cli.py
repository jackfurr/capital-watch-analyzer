"""CLI entry point for the analyzer."""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

import structlog
import typer
from rich.console import Console
from rich.table import Table

from analyzer.api_client import ScraperClient, ScraperAPIError
from analyzer.config import settings
from analyzer.distributor import Distributor, EmailDistributor
from analyzer.heuristics import HeuristicAnalyzer
from analyzer.report_generator import ReportGenerator
from analyzer.scheduler import WeeklyScheduler
from analyzer.ticker_normalizer import TickerNormalizer

app = typer.Typer(
    name="capital-watch-analyzer",
    help="Analyze Senate trading data and generate reports",
    rich_markup_mode="rich",
)
console = Console()
logger = structlog.get_logger()


def setup_logging() -> None:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.log_json else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@app.command()
def health() -> None:
    """Check API connectivity."""
    setup_logging()

    async def check() -> None:
        client = ScraperClient()
        try:
            result = await client.health_check()
            console.print("[green]API is healthy[/green]")
            console.print_json(data=result)
        except ScraperAPIError as e:
            console.print(f"[red]API error: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(check())


@app.command()
def analyze(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to analyze"),
    output: Path = typer.Option(None, "--output", "-o", help="Output file for results (JSON)"),
) -> None:
    """Run analysis on recent trades."""
    setup_logging()

    async def run() -> None:
        client = ScraperClient()
        analyzer = HeuristicAnalyzer()

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        console.print(f"Analyzing trades from {start_date} to {end_date}...")

        try:
            # Fetch data
            with console.status("Fetching trades..."):
                trades = await client.get_all_trades_for_period(start_date, end_date)

            if not trades:
                console.print("[yellow]No trades found for this period[/yellow]")
                return

            console.print(f"Found {len(trades)} trades")

            # Fetch politicians
            with console.status("Fetching politicians..."):
                pol_result = await client.get_politicians(page_size=1000)
                politicians = pol_result.get("items", [])

            # Run analysis
            with console.status("Analyzing politicians..."):
                pol_metrics = analyzer.analyze_politicians(trades, politicians)

            with console.status("Analyzing assets..."):
                asset_metrics = analyzer.analyze_assets(trades)

            with console.status("Analyzing sectors..."):
                sector_metrics = analyzer.analyze_sectors(trades)

            with console.status("Detecting patterns..."):
                alerts = analyzer.detect_unusual_patterns(trades, politicians)

            # Display results
            console.print("\n[bold]Top Active Politicians:[/bold]")
            table = Table("Name", "Trades", "Purchases", "Sales", "Volume Range")
            for m in pol_metrics[:10]:
                volume = f"${m.total_volume_min:,.0f} - ${m.total_volume_max:,.0f}"
                table.add_row(m.politician_name, str(m.total_trades), str(m.purchase_count), str(m.sale_count), volume)
            console.print(table)

            console.print("\n[bold]Top Traded Assets:[/bold]")
            table = Table("Name", "Ticker", "Trades", "Politicians", "Net Flow")
            for m in asset_metrics[:10]:
                ticker = m.ticker or "N/A"
                net = f"+{m.net_flow}" if m.net_flow > 0 else str(m.net_flow)
                table.add_row(m.asset_name[:40], ticker, str(m.total_trades), str(m.politician_count), net)
            console.print(table)

            console.print("\n[bold]Sector Activity:[/bold]")
            table = Table("Sector", "Trades", "Politicians", "Net Flow")
            for m in sector_metrics[:10]:
                net = f"+{m.net_flow}" if m.net_flow > 0 else str(m.net_flow)
                table.add_row(m.sector, str(m.total_trades), str(m.politician_count), net)
            console.print(table)

            if alerts:
                console.print("\n[bold yellow]Alerts:[/bold yellow]")
                table = Table("Type", "Severity", "Message")
                for alert in alerts[:10]:
                    color = {"high": "red", "medium": "yellow", "low": "green"}.get(alert["severity"], "white")
                    table.add_row(alert["type"], f"[{color}]{alert['severity']}[/{color}]", alert["message"][:60])
                console.print(table)

            # Save to file if requested
            if output:
                import json
                results = {
                    "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                    "politicians": [vars(m) for m in pol_metrics],
                    "assets": [vars(m) for m in asset_metrics],
                    "sectors": [vars(m) for m in sector_metrics],
                    "alerts": alerts,
                }
                output.write_text(json.dumps(results, indent=2, default=str))
                console.print(f"\n[green]Results saved to {output}[/green]")

        except ScraperAPIError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run())


@app.command()
def generate_report(
    week: str = typer.Option(None, "--week", "-w", help="Week starting date (YYYY-MM-DD)"),
    output_dir: Path = typer.Option(None, "--output-dir", "-o", help="Output directory for PDF"),
) -> None:
    """Generate a weekly PDF report."""
    setup_logging()

    # Determine week range
    if week:
        try:
            week_start = date.fromisoformat(week)
        except ValueError:
            console.print("[red]Invalid date format. Use YYYY-MM-DD[/red]")
            raise typer.Exit(1)
    else:
        # Default to most recent complete week (ending last Sunday)
        today = date.today()
        days_since_sunday = (today.weekday() + 1) % 7
        week_end = today - timedelta(days=days_since_sunday)
        week_start = week_end - timedelta(days=6)

    week_end = week_start + timedelta(days=6)

    console.print(f"Generating report for week of {week_start} to {week_end}...")

    async def run() -> None:
        client = ScraperClient()
        analyzer = HeuristicAnalyzer()
        generator = ReportGenerator(output_dir)

        try:
            # Fetch data
            with console.status("Fetching trades..."):
                trades = await client.get_all_trades_for_period(week_start, week_end)

            if not trades:
                console.print("[yellow]No trades found for this period[/yellow]")
                return

            console.print(f"Found {len(trades)} trades")

            # Fetch politicians
            with console.status("Fetching politicians..."):
                pol_result = await client.get_politicians(page_size=1000)
                politicians = pol_result.get("items", [])

            # Run analysis
            with console.status("Analyzing data..."):
                pol_metrics = analyzer.analyze_politicians(trades, politicians)
                asset_metrics = analyzer.analyze_assets(trades)
                sector_metrics = analyzer.analyze_sectors(trades)
                alerts = analyzer.detect_unusual_patterns(trades, politicians)

            # Generate PDF
            with console.status("Generating PDF..."):
                output_path = generator.generate_from_analysis(
                    week_start=week_start,
                    week_end=week_end,
                    trades=trades,
                    politician_metrics=pol_metrics,
                    asset_metrics=asset_metrics,
                    sector_metrics=sector_metrics,
                    alerts=alerts,
                )

            console.print(f"[green]Report generated: {output_path}[/green]")

        except ScraperAPIError as e:
            console.print(f"[red]API error: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run())


@app.command()
def schedule(
    dry_run: bool = typer.Option(False, "--dry-run", help="Calculate week but don't generate"),
) -> None:
    """Run scheduled weekly report generation."""
    setup_logging()

    async def run() -> None:
        scheduler = WeeklyScheduler()
        week_start, week_end = scheduler.get_report_week()

        console.print(f"Scheduled report week: {week_start} to {week_end}")

        if dry_run:
            console.print("[yellow]Dry run - not generating report[/yellow]")
            return

        try:
            with console.status("Generating scheduled report..."):
                output_path = await scheduler.generate_weekly_report(week_start, week_end)
            console.print(f"[green]Report generated: {output_path}[/green]")
        except ValueError as e:
            console.print(f"[yellow]{e}[/yellow]")
            raise typer.Exit(0)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run())


@app.command()
def normalize(
    name: str = typer.Argument(..., help="Asset name to normalize"),
) -> None:
    """Normalize an asset name to ticker symbol."""
    setup_logging()

    async def run() -> None:
        normalizer = TickerNormalizer(finnhub_api_key=settings.finnhub_api_key)

        console.print(f"Normalizing: [bold]{name}[/bold]")

        with console.status("Looking up ticker..."):
            result = await normalizer.normalize(name)

        if result.ticker:
            console.print(f"[green]Ticker: {result.ticker}[/green]")
            console.print(f"  Name: {result.name}")
            console.print(f"  Sector: {result.sector or 'Unknown'}")
            console.print(f"  Industry: {result.industry or 'Unknown'}")
            console.print(f"  Confidence: {result.confidence:.1f}%")
            console.print(f"  Source: {result.source}")
        else:
            console.print("[yellow]No ticker found[/yellow]")

    asyncio.run(run())


@app.command()
def send_test_email(
    to: str = typer.Option(..., "--to", help="Recipient email address"),
) -> None:
    """Send a test email to verify distribution."""
    setup_logging()

    async def run() -> None:
        distributor = EmailDistributor()

        console.print(f"Sending test email to {to}...")

        result = await distributor.send_via_brevo(
            to_email=to,
            subject="Capitol Watch - Test Email",
            html_content="""
            <html>
            <body>
                <h2>Capitol Watch Test</h2>
                <p>This is a test email from the Capitol Watch Analyzer.</p>
                <p>If you're receiving this, your email distribution is configured correctly!</p>
            </body>
            </html>
            """,
        )

        if result.success:
            console.print(f"[green]{result.message}[/green]")
        else:
            console.print(f"[red]Failed: {result.error}[/red]")
            raise typer.Exit(1)

    asyncio.run(run())


@app.command()
def version() -> None:
    """Show version information."""
    from analyzer import __version__
    console.print(f"Capital Watch Analyzer [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
