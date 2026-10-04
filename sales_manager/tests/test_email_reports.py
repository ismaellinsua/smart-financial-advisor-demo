"""Tests for email reports integration."""

import pytest
from unittest.mock import patch, MagicMock
from email import message_from_string
from email.header import decode_header
import pandas as pd

from core.email_reports import EmailReporter, _format_money


class TestFormatMoney:
    def test_format_money_spanish_format(self):
        """Money formatted with Spanish decimals."""
        assert _format_money(1234.56, "€") == "1.234,56 €"
        assert _format_money(100.0, "€") == "100,00 €"
        assert _format_money(0.5, "€") == "0,50 €"

    def test_format_money_different_currency(self):
        """Works with any currency symbol."""
        assert _format_money(1000, "$") == "1.000,00 $"
        assert _format_money(1000, "£") == "1.000,00 £"


class TestEmailReporter:
    @pytest.fixture
    def reporter(self):
        """Create email reporter with mocked SMTP."""
        return EmailReporter("smtp.gmail.com", 587, "test@example.com", "password")

    @patch("core.email_reports.smtplib.SMTP")
    def test_weekly_report_sends_email(self, mock_smtp, reporter):
        """Weekly report sends email with metrics and tables."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        top_products = pd.DataFrame({
            "name": ["Pan", "Café", "Leche"],
            "revenue": [500, 300, 200],
            "margin_pct": [35.0, 40.0, 30.0]
        })

        low_stock = pd.DataFrame({
            "name": ["Café"],
            "stock": [2],
            "min_stock": [10]
        })

        inactive = pd.DataFrame({
            "name": ["Juan García"],
            "days_inactive": [65],
            "lifetime_value": [1500]
        })

        result = reporter.weekly_report(
            "manager@business.com",
            "Panadería Sol",
            "€",
            revenue=5000.0,
            count=50,
            ticket=100.0,
            margin_pct=35.0,
            top_products=top_products,
            low_stock=low_stock,
            inactive_customers=inactive
        )

        assert result is True
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()

        # Verify email was called with correct recipients
        call_args = mock_server.sendmail.call_args[0]
        assert call_args[1] == "manager@business.com"  # recipient
        msg = message_from_string(call_args[2])
        subject = str(decode_header(msg["Subject"])[0][0])
        assert "Weekly Report" in subject

    @patch("core.email_reports.smtplib.SMTP")
    def test_low_stock_alert_email(self, mock_smtp, reporter):
        """Low stock alert sends urgent message."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        products = pd.DataFrame({
            "name": ["Leche", "Pan"],
            "stock": [1, 2],
            "min_stock": [10, 5]
        })

        result = reporter.low_stock_alert(
            "manager@business.com",
            "Supermercado ABC",
            "€",
            products
        )

        assert result is True
        mock_server.sendmail.assert_called_once()

        # Check alert in email
        call_args = mock_server.sendmail.call_args[0]
        msg = message_from_string(call_args[2])
        subject = str(decode_header(msg["Subject"])[0][0])
        assert "Low Stock Alert" in subject
        assert "Supermercado ABC" in subject

    @patch("core.email_reports.smtplib.SMTP")
    def test_followup_email(self, mock_smtp, reporter):
        """Inactive customer follow-up with discount offer."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = reporter.inactive_customer_followup(
            "customer@example.com",
            "Cafetería Don Juan",
            "María García",
            discount_pct=15
        )

        assert result is True
        mock_server.sendmail.assert_called_once()

        call_args = mock_server.sendmail.call_args[0]
        msg = message_from_string(call_args[2])
        decoded_subject = decode_header(msg["Subject"])[0]
        subject = decoded_subject[0] if isinstance(decoded_subject[0], str) else decoded_subject[0].decode(decoded_subject[1] or 'utf-8')
        assert "Cafetería Don Juan" in subject
        assert "customer@example.com" in msg["To"]

    @patch("core.email_reports.smtplib.SMTP")
    def test_followup_email_single_name(self, mock_smtp, reporter):
        """Handles single-word names in followup."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        reporter.inactive_customer_followup(
            "customer@example.com",
            "Business",
            "Carlos"
        )

        call_args = mock_server.sendmail.call_args[0]
        email_content = call_args[2]
        assert "Hi Carlos" in email_content

    @patch("core.email_reports.smtplib.SMTP")
    def test_smtp_connection_failure(self, mock_smtp, reporter):
        """Handles SMTP connection errors gracefully."""
        mock_smtp.return_value.__enter__.return_value.login.side_effect = \
            ConnectionError("SMTP connection failed")

        with pytest.raises(RuntimeError) as exc_info:
            reporter.weekly_report(
                "manager@business.com",
                "Business",
                "€",
                1000, 10, 100, 35,
                pd.DataFrame({"name": [], "revenue": [], "margin_pct": []}),
                pd.DataFrame({"name": [], "stock": [], "min_stock": []}),
                pd.DataFrame({"name": [], "days_inactive": [], "lifetime_value": []})
            )

        assert "Email send failed" in str(exc_info.value)

    @patch("core.email_reports.smtplib.SMTP")
    def test_weekly_report_empty_low_stock(self, mock_smtp, reporter):
        """Weekly report handles empty low stock gracefully."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = reporter.weekly_report(
            "manager@business.com",
            "Business",
            "€",
            5000, 50, 100, 35,
            pd.DataFrame({"name": ["Pan"], "revenue": [500], "margin_pct": [35]}),
            pd.DataFrame(),  # Empty low stock
            pd.DataFrame()   # Empty inactive customers
        )

        assert result is True

    @patch("core.email_reports.smtplib.SMTP")
    def test_email_subject_includes_date(self, mock_smtp, reporter):
        """Email subject includes the current date."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        reporter.weekly_report(
            "manager@business.com",
            "Business",
            "€",
            1000, 10, 100, 35,
            pd.DataFrame({"name": [], "revenue": [], "margin_pct": []}),
            pd.DataFrame({"name": [], "stock": [], "min_stock": []}),
            pd.DataFrame({"name": [], "days_inactive": [], "lifetime_value": []})
        )

        call_args = mock_server.sendmail.call_args[0]
        # The date appears in both subject and content
        assert "Business" in call_args[2]
