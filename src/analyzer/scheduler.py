"""Scheduler for automated report generation."""

import asyncio
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import structlog

from analyzer.api_client import ScraperClient
from analyzer.config import settings
from analyzer.heuristics import HeuristicAnalyzer
from analyzer.report_generator import ReportGenerator

logger = structlog.get_logger()


class WeeklyScheduler:
    """Schedules and runs weekly report generation."""

    def __init__(self) -> None:
        """Initialize the scheduler."""
        self.client = ScraperClient()
        self.analyzer = HeuristicAnalyzer()
        self.generator = ReportGenerator()
        self.logger = structlog.get_logger()

    def get_report_week(self, target_date: date | None = None) -> tuple[date, date]:
        """Calculate the week range for a report.

        By default, generates report for the most recently completed week
        (ending on the configured report day).

        Args:
            target_date: Optional date to calculate week for

        Returns:
            Tuple of (week_start, week_end)
        """
        if target_date is None:
            target_date = date.today()

        # Find the most recent report day
        # settings.weekly_report_day: 0=Monday, 3=Wednesday, etc.
        days_since_report_day = (target_date.weekday() - settings.weekly_report_day) % 7

        if days_since_report_day == 0:
            # Today is report day - use last week
            days_since_report_day = 7

        week_end = target_date - timedelta(days=days_since_report_day)
        week_start = week_end - timedelta(days=6)

        return week_start, week_end

    async def generate_weekly_report(
        self, week_start: date | None = None, week_end: date | None = None
    ) -> Path:
        """Generate the weekly report.

        Args:
            week_start: Optional start date (defaults to calculated week)
            week_end: Optional end date (defaults to calculated week)

        Returns:
            Path to generated PDF
        """
        if week_start is None or week_end is None:
            week_start, week_end = self.get_report_week()

        self.logger.info(
            "Starting weekly report generation",
            week_start=week_start,
            week_end=week_end,
        )

        # Fetch data
        trades = await self.client.get_all_trades_for_period(week_start, week_end)

        if not trades:
            self.logger.warning("No trades found for week", week_start=week_start, week_end=week_end)
            raise ValueError(f"No trades found for week {week_start} to {week_end}")

        self.logger.info("Fetched trades", count=len(trades))

        # Fetch politicians
        pol_result = await self.client.get_politicians(page_size=1000)
        politicians = pol_result.get("items", [])

        # Run analysis
        pol_metrics = self.analyzer.analyze_politicians(trades, politicians)
        asset_metrics = self.analyzer.analyze_assets(trades)
        sector_metrics = self.analyzer.analyze_sectors(trades)
        alerts = self.analyzer.detect_unusual_patterns(trades, politicians)

        self.logger.info(
            "Analysis complete",
            politicians=len(pol_metrics),
            assets=len(asset_metrics),
            sectors=len(sector_metrics),
            alerts=len(alerts),
        )

        # Generate PDF
        output_path = self.generator.generate_from_analysis(
            week_start=week_start,
            week_end=week_end,
            trades=trades,
            politician_metrics=pol_metrics,
            asset_metrics=asset_metrics,
            sector_metrics=sector_metrics,
            alerts=alerts,
        )

        self.logger.info("Weekly report generated", output_path=str(output_path))

        return output_path

    async def run(self) -> Path:
        """Run the scheduled weekly report generation.

        Returns:
            Path to generated PDF
        """
        return await self.generate_weekly_report()


def run_scheduler() -> Path:
    """Entry point for running the scheduler (synchronous wrapper).

    Returns:
        Path to generated PDF
    """
    scheduler = WeeklyScheduler()
    return asyncio.run(scheduler.run())
