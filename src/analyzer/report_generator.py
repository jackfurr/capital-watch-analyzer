"""PDF report generation using WeasyPrint."""

import tempfile
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Template
from weasyprint import HTML

from analyzer.config import settings
from analyzer.heuristics import AssetMetrics, PoliticianMetrics, SectorMetrics

logger = structlog.get_logger()

# HTML template for the weekly report
REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Capitol Watch Weekly Report - {{ week_start }} to {{ week_end }}</title>
    <style>
        @page {
            size: letter;
            margin: 1in;
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
        }
        h1 {
            color: #1a365d;
            border-bottom: 3px solid #2c5282;
            padding-bottom: 10px;
        }
        h2 {
            color: #2c5282;
            margin-top: 30px;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 5px;
        }
        h3 {
            color: #4a5568;
        }
        .header-info {
            background: #f7fafc;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .summary-box {
            display: flex;
            gap: 20px;
            margin: 20px 0;
        }
        .summary-item {
            background: #edf2f7;
            padding: 15px;
            border-radius: 5px;
            flex: 1;
            text-align: center;
        }
        .summary-number {
            font-size: 2em;
            font-weight: bold;
            color: #2c5282;
        }
        .summary-label {
            color: #718096;
            font-size: 0.9em;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 0.9em;
        }
        th {
            background: #2c5282;
            color: white;
            padding: 10px;
            text-align: left;
        }
        td {
            padding: 8px 10px;
            border-bottom: 1px solid #e2e8f0;
        }
        tr:nth-child(even) {
            background: #f7fafc;
        }
        .alert {
            background: #fff5f5;
            border-left: 4px solid #c53030;
            padding: 10px 15px;
            margin: 10px 0;
        }
        .alert-medium {
            background: #fffaf0;
            border-left-color: #dd6b20;
        }
        .alert-low {
            background: #f0fff4;
            border-left-color: #38a169;
        }
        .ticker {
            font-family: monospace;
            background: #edf2f7;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.9em;
        }
        .positive {
            color: #38a169;
        }
        .negative {
            color: #c53030;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            font-size: 0.8em;
            color: #718096;
        }
    </style>
</head>
<body>
    <h1>Capitol Watch Weekly Report</h1>

    <div class="header-info">
        <strong>Report Period:</strong> {{ week_start }} to {{ week_end }}<br>
        <strong>Generated:</strong> {{ generated_at }}<br>
        <strong>Data Source:</strong> Senate Electronic Financial Disclosures
    </div>

    <h2>Executive Summary</h2>
    <div class="summary-box">
        <div class="summary-item">
            <div class="summary-number">{{ total_trades }}</div>
            <div class="summary-label">Total Trades</div>
        </div>
        <div class="summary-item">
            <div class="summary-number">{{ total_politicians }}</div>
            <div class="summary-label">Active Politicians</div>
        </div>
        <div class="summary-item">
            <div class="summary-number">{{ unique_assets }}</div>
            <div class="summary-label">Unique Assets</div>
        </div>
        <div class="summary-item">
            <div class="summary-number">{{ alerts|length }}</div>
            <div class="summary-label">Alerts</div>
        </div>
    </div>

    {% if alerts %}
    <h2>Alerts & Unusual Patterns</h2>
    {% for alert in alerts %}
    <div class="alert alert-{{ alert.severity }}">
        <strong>{{ alert.type|replace('_', ' ')|title }}:</strong> {{ alert.message }}
    </div>
    {% endfor %}
    {% endif %}

    <h2>Most Active Politicians</h2>
    <table>
        <thead>
            <tr>
                <th>Politician</th>
                <th>Total Trades</th>
                <th>Purchases</th>
                <th>Sales</th>
                <th>Unique Assets</th>
                <th>Est. Volume</th>
            </tr>
        </thead>
        <tbody>
            {% for p in politicians[:15] %}
            <tr>
                <td>{{ p.politician_name }}</td>
                <td>{{ p.total_trades }}</td>
                <td class="positive">{{ p.purchase_count }}</td>
                <td class="negative">{{ p.sale_count }}</td>
                <td>{{ p.unique_assets }}</td>
                <td>${{ "{:,.0f}".format(p.total_volume_min) }} - ${{ "{:,.0f}".format(p.total_volume_max) }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <h2>Most Traded Assets</h2>
    <table>
        <thead>
            <tr>
                <th>Asset</th>
                <th>Ticker</th>
                <th>Total Trades</th>
                <th>Politicians</th>
                <th>Purchases</th>
                <th>Sales</th>
                <th>Net Flow</th>
            </tr>
        </thead>
        <tbody>
            {% for a in assets[:15] %}
            <tr>
                <td>{{ a.asset_name[:50] }}</td>
                <td><span class="ticker">{{ a.ticker or 'N/A' }}</span></td>
                <td>{{ a.total_trades }}</td>
                <td>{{ a.politician_count }}</td>
                <td class="positive">{{ a.purchase_count }}</td>
                <td class="negative">{{ a.sale_count }}</td>
                <td class="{% if a.net_flow > 0 %}positive{% elif a.net_flow < 0 %}negative{% endif %}">
                    {% if a.net_flow > 0 %}+{% endif %}{{ a.net_flow }}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <h2>Sector Analysis</h2>
    <table>
        <thead>
            <tr>
                <th>Sector</th>
                <th>Total Trades</th>
                <th>Politicians</th>
                <th>Purchases</th>
                <th>Sales</th>
                <th>Net Flow</th>
                <th>Top Assets</th>
            </tr>
        </thead>
        <tbody>
            {% for s in sectors[:10] %}
            <tr>
                <td>{{ s.sector }}</td>
                <td>{{ s.total_trades }}</td>
                <td>{{ s.politician_count }}</td>
                <td class="positive">{{ s.purchase_count }}</td>
                <td class="negative">{{ s.sale_count }}</td>
                <td class="{% if s.net_flow > 0 %}positive{% elif s.net_flow < 0 %}negative{% endif %}">
                    {% if s.net_flow > 0 %}+{% endif %}{{ s.net_flow }}
                </td>
                <td>
                    {% for asset in s.top_assets[:3] %}
                        {{ asset.ticker or asset.name[:10] }}{% if not loop.last %}, {% endif %}
                    {% endfor %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="footer">
        <p>
            <strong>About Capitol Watch:</strong> This report analyzes publicly available Senate financial disclosure data
to identify trading patterns and potential conflicts of interest. Data is sourced from the Senate Electronic Financial
Disclosures (eFD) system under the STOCK Act.
        </p>
        <p>
            <strong>Disclaimer:</strong> This report is for informational purposes only. All data is sourced from public
records. Trading activity does not imply wrongdoing. Always verify information with official sources.
        </p>
        <p>
            Generated by Capitol Watch Analyzer v{{ version }} | Report ID: {{ report_id }}
        </p>
    </div>
</body>
</html>
"""


class ReportGenerator:
    """Generates PDF reports from analysis data."""

    def __init__(self, output_dir: Path | None = None) -> None:
        """Initialize the report generator.

        Args:
            output_dir: Directory to save PDFs (defaults to settings.reports_dir)
        """
        self.output_dir = Path(output_dir or settings.reports_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.template = Template(REPORT_TEMPLATE)
        self.logger = structlog.get_logger()

    def generate(
        self,
        week_start: date,
        week_end: date,
        politicians: list[PoliticianMetrics],
        assets: list[AssetMetrics],
        sectors: list[SectorMetrics],
        alerts: list[dict[str, Any]],
        total_trades: int,
    ) -> Path:
        """Generate a PDF report.

        Args:
            week_start: Start date of the report period
            week_end: End date of the report period
            politicians: List of politician metrics
            assets: List of asset metrics
            sectors: List of sector metrics
            alerts: List of alerts
            total_trades: Total number of trades in period

        Returns:
            Path to the generated PDF file
        """
        from analyzer import __version__

        # Prepare template data
        template_data = {
            "week_start": week_start.strftime("%B %d, %Y"),
            "week_end": week_end.strftime("%B %d, %Y"),
            "generated_at": date.today().strftime("%B %d, %Y"),
            "total_trades": total_trades,
            "total_politicians": len(politicians),
            "unique_assets": len(assets),
            "alerts": alerts,
            "politicians": [asdict(p) for p in politicians],
            "assets": [asdict(a) for a in assets],
            "sectors": [asdict(s) for s in sectors],
            "version": __version__,
            "report_id": f"CW-{week_start.strftime('%Y%m%d')}-{week_end.strftime('%Y%m%d')}",
        }

        # Render HTML
        html_content = self.template.render(**template_data)

        # Generate PDF
        output_filename = f"capitol-watch-report-{week_start.isoformat()}.pdf"
        output_path = self.output_dir / output_filename

        self.logger.info(
            "Generating PDF report",
            week_start=week_start,
            week_end=week_end,
            output_path=str(output_path),
        )

        try:
            HTML(string=html_content).write_pdf(str(output_path))
            self.logger.info("PDF generated successfully", output_path=str(output_path))
            return output_path
        except Exception as e:
            self.logger.error("Failed to generate PDF", error=str(e))
            raise

    def generate_from_analysis(
        self,
        week_start: date,
        week_end: date,
        trades: list[dict[str, Any]],
        politician_metrics: list[PoliticianMetrics],
        asset_metrics: list[AssetMetrics],
        sector_metrics: list[SectorMetrics],
        alerts: list[dict[str, Any]],
    ) -> Path:
        """Generate a report from analysis results.

        Args:
            week_start: Start date of the report period
            week_end: End date of the report period
            trades: Raw trade data
            politician_metrics: Analyzed politician metrics
            asset_metrics: Analyzed asset metrics
            sector_metrics: Analyzed sector metrics
            alerts: Detected alerts

        Returns:
            Path to the generated PDF file
        """
        return self.generate(
            week_start=week_start,
            week_end=week_end,
            politicians=politician_metrics,
            assets=asset_metrics,
            sectors=sector_metrics,
            alerts=alerts,
            total_trades=len(trades),
        )
