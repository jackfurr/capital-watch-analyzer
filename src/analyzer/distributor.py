"""Distribution module for sending reports via email and Discord."""

from dataclasses import dataclass
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import httpx
import structlog

from analyzer.config import settings

logger = structlog.get_logger()


@dataclass
class DistributionResult:
    """Result of a distribution attempt."""

    success: bool
    channel: str
    message: str
    error: str | None = None


class EmailDistributor:
    """Distribute reports via email (SMTP or Brevo API)."""

    def __init__(self) -> None:
        """Initialize the email distributor."""
        self.logger = structlog.get_logger()
        self.brevo_api_key = settings.brevo_api_key

    async def send_via_brevo(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        attachment_path: Path | None = None,
    ) -> DistributionResult:
        """Send email using Brevo API (free tier: 300 emails/day).

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            attachment_path: Optional PDF attachment

        Returns:
            DistributionResult with status
        """
        if not self.brevo_api_key:
            return DistributionResult(
                success=False,
                channel="email",
                message="Brevo API key not configured",
                error="Missing BREVO_API_KEY",
            )

        url = "https://api.brevo.com/v3/smtp/email"

        payload: dict[str, Any] = {
            "sender": {"email": settings.email_from or "reports@capitolwatch.dev"},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_content,
        }

        # Add attachment if provided
        if attachment_path and attachment_path.exists():
            import base64

            content = attachment_path.read_bytes()
            encoded = base64.b64encode(content).decode()

            payload["attachment"] = [
                {
                    "content": encoded,
                    "name": attachment_path.name,
                }
            ]

        headers = {
            "accept": "application/json",
            "api-key": self.brevo_api_key,
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

            self.logger.info(
                "Email sent via Brevo",
                to=to_email,
                subject=subject,
            )

            return DistributionResult(
                success=True,
                channel="email",
                message=f"Email sent to {to_email}",
            )

        except httpx.HTTPStatusError as e:
            self.logger.error(
                "Brevo API error",
                status=e.response.status_code,
                response=e.response.text,
            )
            return DistributionResult(
                success=False,
                channel="email",
                message="Failed to send email",
                error=f"Brevo API error: {e.response.status_code}",
            )
        except Exception as e:
            self.logger.error("Email send failed", error=str(e))
            return DistributionResult(
                success=False,
                channel="email",
                message="Failed to send email",
                error=str(e),
            )

    async def send_report(
        self,
        report_path: Path,
        to_email: str | None = None,
        week_start: str = "",
        week_end: str = "",
    ) -> DistributionResult:
        """Send a PDF report via email.

        Args:
            report_path: Path to the PDF report
            to_email: Recipient email (defaults to settings.email_to)
            week_start: Report period start
            week_end: Report period end

        Returns:
            DistributionResult with status
        """
        recipient = to_email or settings.email_to
        if not recipient:
            return DistributionResult(
                success=False,
                channel="email",
                message="No recipient configured",
                error="Missing email_to",
            )

        subject = f"Capitol Watch Weekly Report - {week_start} to {week_end}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #2c5282;">Capitol Watch Weekly Report</h2>
            <p>Your weekly Senate trading report is attached.</p>
            <p><strong>Report Period:</strong> {week_start} to {week_end}</p>
            <p>
                This report analyzes publicly available Senate financial disclosure data
to identify trading patterns and potential conflicts of interest.
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="font-size: 0.9em; color: #718096;">
                Generated by Capitol Watch Analyzer<br>
                <a href="https://github.com/jackfurr/capital-watch-analyzer">View source on GitHub</a>
            </p>
        </body>
        </html>
        """

        return await self.send_via_brevo(
            to_email=recipient,
            subject=subject,
            html_content=html_content,
            attachment_path=report_path,
        )


class DiscordDistributor:
    """Distribute reports via Discord webhook."""

    def __init__(self) -> None:
        """Initialize the Discord distributor."""
        self.logger = structlog.get_logger()
        self.webhook_url = settings.discord_webhook_url

    async def send_report(
        self,
        report_path: Path,
        week_start: str = "",
        week_end: str = "",
        summary: str = "",
    ) -> DistributionResult:
        """Send report notification to Discord.

        Args:
            report_path: Path to the PDF report
            week_start: Report period start
            week_end: Report period end
            summary: Brief summary of findings

        Returns:
            DistributionResult with status
        """
        if not self.webhook_url:
            return DistributionResult(
                success=False,
                channel="discord",
                message="Discord webhook not configured",
                error="Missing DISCORD_WEBHOOK_URL",
            )

        payload = {
            "content": f"📊 **Capitol Watch Weekly Report**\n\n"
            f"**Period:** {week_start} to {week_end}\n"
            f"{summary}\n\n"
            f"📎 Report: `{report_path.name}`",
            "embeds": [
                {
                    "title": "Report Generated",
                    "description": f"Weekly Senate trading analysis for {week_start} to {week_end}",
                    "color": 0x2c5282,
                    "fields": [
                        {
                            "name": "File",
                            "value": report_path.name,
                            "inline": True,
                        },
                        {
                            "name": "Size",
                            "value": f"{report_path.stat().st_size / 1024:.1f} KB",
                            "inline": True,
                        },
                    ],
                }
            ],
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

            self.logger.info("Discord notification sent", week_start=week_start)

            return DistributionResult(
                success=True,
                channel="discord",
                message="Discord notification sent",
            )

        except httpx.HTTPStatusError as e:
            self.logger.error(
                "Discord webhook error",
                status=e.response.status_code,
            )
            return DistributionResult(
                success=False,
                channel="discord",
                message="Failed to send Discord notification",
                error=f"HTTP {e.response.status_code}",
            )
        except Exception as e:
            self.logger.error("Discord send failed", error=str(e))
            return DistributionResult(
                success=False,
                channel="discord",
                message="Failed to send Discord notification",
                error=str(e),
            )


class Distributor:
    """Main distribution coordinator."""

    def __init__(self) -> None:
        """Initialize all distribution channels."""
        self.email = EmailDistributor()
        self.discord = DiscordDistributor()
        self.logger = structlog.get_logger()

    async def distribute_report(
        self,
        report_path: Path,
        week_start: str = "",
        week_end: str = "",
        summary: str = "",
    ) -> list[DistributionResult]:
        """Distribute report to all configured channels.

        Args:
            report_path: Path to the PDF report
            week_start: Report period start
            week_end: Report period end
            summary: Brief summary for Discord

        Returns:
            List of results for each channel
        """
        results: list[DistributionResult] = []

        # Send email if configured
        if settings.email_to and settings.brevo_api_key:
            result = await self.email.send_report(
                report_path=report_path,
                week_start=week_start,
                week_end=week_end,
            )
            results.append(result)

        # Send Discord notification if configured
        if settings.discord_webhook_url:
            result = await self.discord.send_report(
                report_path=report_path,
                week_start=week_start,
                week_end=week_end,
                summary=summary,
            )
            results.append(result)

        if not results:
            self.logger.warning("No distribution channels configured")
            results.append(
                DistributionResult(
                    success=False,
                    channel="none",
                    message="No distribution channels configured",
                    error="Configure BREVO_API_KEY + EMAIL_TO or DISCORD_WEBHOOK_URL",
                )
            )

        return results
