"""Tests for the distributor."""

import pytest
import respx
from httpx import Response

from analyzer.distributor import DiscordDistributor, DistributionResult, EmailDistributor


class TestEmailDistributor:
    """Test email distribution."""

    def test_missing_api_key(self):
        """Test handling of missing API key."""
        distributor = EmailDistributor()
        distributor.brevo_api_key = None

        result = distributor.send_via_brevo(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        assert result.success is False
        assert "Missing BREVO_API_KEY" in result.error

    @respx.mock
    async def test_send_success(self):
        """Test successful email send."""
        route = respx.post("https://api.brevo.com/v3/smtp/email").mock(
            return_value=Response(201, json={"messageId": "test-id"})
        )

        distributor = EmailDistributor()
        distributor.brevo_api_key = "test-key"

        result = await distributor.send_via_brevo(
            to_email="test@example.com",
            subject="Test Subject",
            html_content="<p>Test</p>",
        )

        assert result.success is True
        assert route.called

    @respx.mock
    async def test_send_failure(self):
        """Test failed email send."""
        respx.post("https://api.brevo.com/v3/smtp/email").mock(
            return_value=Response(400, text="Bad Request")
        )

        distributor = EmailDistributor()
        distributor.brevo_api_key = "test-key"

        result = await distributor.send_via_brevo(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        assert result.success is False


class TestDiscordDistributor:
    """Test Discord distribution."""

    def test_missing_webhook(self):
        """Test handling of missing webhook."""
        distributor = DiscordDistributor()
        distributor.webhook_url = None

        result = distributor.send_report(
            report_path="/tmp/test.pdf",
            week_start="2026-03-03",
        )

        assert result.success is False
        assert "Missing DISCORD_WEBHOOK_URL" in result.error

    @respx.mock
    async def test_send_success(self, tmp_path):
        """Test successful Discord notification."""
        route = respx.post("https://discord.com/api/webhooks/test").mock(
            return_value=Response(204)
        )

        distributor = DiscordDistributor()
        distributor.webhook_url = "https://discord.com/api/webhooks/test"

        # Create a test file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        result = await distributor.send_report(
            report_path=test_file,
            week_start="2026-03-03",
            week_end="2026-03-09",
        )

        assert result.success is True
        assert route.called
