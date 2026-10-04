"""Email reports: weekly summaries, alerts and customer follow-ups."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pandas as pd
from . import clock


def _format_money(value: float, currency: str = "€") -> str:
    """Format number as currency."""
    text = f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} {currency}"


class EmailReporter:
    """Send business reports and alerts via email."""

    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str):
        """Initialize SMTP connection.

        For Gmail: smtp_host='smtp.gmail.com', smtp_port=587
        username: your email, password: app password (not regular password)
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    def _send(self, to_email: str, subject: str, html_body: str, text_body: str = ""):
        """Send email via SMTP."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.username
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.username, to_email, msg.as_string())
            return True
        except Exception as e:
            raise RuntimeError(f"Email send failed: {e}")

    def weekly_report(self, to_email: str, business_name: str, currency: str,
                     revenue: float, count: int, ticket: float, margin_pct: float,
                     top_products: pd.DataFrame, low_stock: pd.DataFrame,
                     inactive_customers: pd.DataFrame) -> bool:
        """Send weekly business summary."""

        # Top products table
        products_rows = ""
        for _, row in top_products.head(5).iterrows():
            products_rows += f"""
            <tr>
                <td style="padding:8px">{row.get('name', '')}</td>
                <td style="padding:8px;text-align:right">{_format_money(row.get('revenue', 0), currency)}</td>
                <td style="padding:8px;text-align:right">{row.get('margin_pct', 0):.1f}%</td>
            </tr>"""

        # Low stock alerts
        stock_rows = ""
        for _, row in low_stock.head(5).iterrows():
            stock_rows += f"""
            <tr>
                <td style="padding:8px">{row.get('name', '')}</td>
                <td style="padding:8px;text-align:right">{int(row.get('stock', 0))} units</td>
                <td style="padding:8px;text-align:right">{int(row.get('min_stock', 0))} min</td>
            </tr>"""

        # Inactive customers
        customer_rows = ""
        for _, row in inactive_customers.head(5).iterrows():
            customer_rows += f"""
            <tr>
                <td style="padding:8px">{row.get('name', '')}</td>
                <td style="padding:8px;text-align:right">{int(row.get('days_inactive', 0))} days</td>
                <td style="padding:8px;text-align:right">{_format_money(row.get('lifetime_value', 0), currency)}</td>
            </tr>"""

        html = f"""
        <html>
        <body style="font-family:Arial,sans-serif;color:#333;background:#f5f5f5">
        <div style="max-width:600px;margin:0 auto;background:white;padding:20px;border-radius:8px">
            <h1 style="color:#1F4E79">{business_name} · Weekly Report</h1>
            <p style="color:#666">Week ending {clock.now().strftime('%Y-%m-%d')}</p>

            <!-- Key Metrics -->
            <div style="background:#f9f9f9;padding:15px;border-radius:6px;margin:20px 0">
                <h2 style="margin-top:0;font-size:18px">Key Metrics</h2>
                <table style="width:100%;border-collapse:collapse">
                    <tr><td><strong>Revenue</strong></td><td style="text-align:right">{_format_money(revenue, currency)}</td></tr>
                    <tr><td><strong>Sales Count</strong></td><td style="text-align:right">{count}</td></tr>
                    <tr><td><strong>Avg Ticket</strong></td><td style="text-align:right">{_format_money(ticket, currency)}</td></tr>
                    <tr><td><strong>Margin</strong></td><td style="text-align:right">{margin_pct:.1f}%</td></tr>
                </table>
            </div>

            <!-- Top Products -->
            <h2 style="font-size:16px;border-bottom:2px solid #1F4E79;padding-bottom:8px">Top 5 Products</h2>
            <table style="width:100%;border-collapse:collapse">
                <thead style="background:#f0f0f0">
                    <tr><th style="padding:8px;text-align:left">Product</th><th style="padding:8px">Revenue</th><th style="padding:8px">Margin</th></tr>
                </thead>
                <tbody>{products_rows}</tbody>
            </table>

            <!-- Low Stock Alerts -->
            {f'''<h2 style="font-size:16px;border-bottom:2px solid #d9534f;padding-bottom:8px;margin-top:20px">⚠️ Low Stock Alerts</h2>
            <table style="width:100%;border-collapse:collapse">
                <thead style="background:#fff3cd">
                    <tr><th style="padding:8px;text-align:left">Product</th><th style="padding:8px">Current</th><th style="padding:8px">Minimum</th></tr>
                </thead>
                <tbody>{stock_rows}</tbody>
            </table>''' if not low_stock.empty else ''}

            <!-- Inactive Customers -->
            {f'''<h2 style="font-size:16px;border-bottom:2px solid #5cb85c;padding-bottom:8px;margin-top:20px">👥 Inactive Customers (60+ days)</h2>
            <table style="width:100%;border-collapse:collapse">
                <thead style="background:#e8f5e9">
                    <tr><th style="padding:8px;text-align:left">Customer</th><th style="padding:8px">Days Inactive</th><th style="padding:8px">Lifetime Value</th></tr>
                </thead>
                <tbody>{customer_rows}</tbody>
            </table>''' if not inactive_customers.empty else ''}

            <hr style="margin:20px 0;border:none;border-top:1px solid #ddd">
            <p style="color:#666;font-size:12px">NirKanA · Automated Business Report</p>
        </div>
        </body>
        </html>"""

        return self._send(
            to_email,
            f"{business_name} · Weekly Report {clock.now().strftime('%Y-%m-%d')}",
            html
        )

    def low_stock_alert(self, to_email: str, business_name: str, currency: str,
                       products: pd.DataFrame) -> bool:
        """Send urgent low stock alert."""
        rows = ""
        for _, row in products.iterrows():
            rows += f"""
            <tr>
                <td style="padding:8px">{row.get('name', '')}</td>
                <td style="padding:8px;text-align:right">{int(row.get('stock', 0))}</td>
                <td style="padding:8px;text-align:right">{int(row.get('min_stock', 0))}</td>
            </tr>"""

        html = f"""
        <html>
        <body style="font-family:Arial,sans-serif;color:#333">
        <div style="max-width:500px;margin:0 auto;background:#fff3cd;padding:20px;border:2px solid #ff9800;border-radius:8px">
            <h1 style="color:#d9534f;margin-top:0">⚠️ Low Stock Alert</h1>
            <p>The following products are below minimum stock at <strong>{business_name}</strong>:</p>
            <table style="width:100%;border-collapse:collapse">
                <thead style="background:#fff">
                    <tr><th style="padding:8px;text-align:left;border-bottom:2px solid #ff9800">Product</th>
                        <th style="padding:8px;border-bottom:2px solid #ff9800">Current</th>
                        <th style="padding:8px;border-bottom:2px solid #ff9800">Min</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <p style="margin-top:15px;color:#666"><small>This is an automated alert. Disable in settings.</small></p>
        </div>
        </body>
        </html>"""

        return self._send(to_email, f"⚠️ Low Stock Alert · {business_name}", html)

    def inactive_customer_followup(self, to_email: str, business_name: str,
                                  customer_name: str, discount_pct: int = 10) -> bool:
        """Send personalized re-engagement message."""
        first = customer_name.split()[0] if customer_name else "Valued Customer"

        html = f"""
        <html>
        <body style="font-family:Arial,sans-serif;color:#333;background:#f5f5f5">
        <div style="max-width:500px;margin:0 auto;background:white;padding:30px;border-radius:8px">
            <p style="font-size:16px">Hi {first},</p>

            <p style="color:#666">It's been a while since we last saw you at <strong>{business_name}</strong>.
            We miss having you here and would love to welcome you back!</p>

            <div style="background:#f0f8ff;padding:20px;border-left:4px solid #1F4E79;margin:20px 0">
                <p style="margin:0"><strong>Special Offer for You</strong></p>
                <p style="margin:10px 0 0;font-size:20px;color:#d9534f"><strong>{discount_pct}% OFF</strong> your next purchase</p>
                <p style="margin:5px 0 0;color:#666">Show this email in-store or mention "COMEBACK"</p>
            </div>

            <p style="color:#666">What's new at {business_name}?</p>
            <ul style="color:#666">
                <li>New products you'll love</li>
                <li>Updated menu & services</li>
                <li>Loyalty rewards program</li>
            </ul>

            <p style="color:#666">See you soon!</p>
            <p>Best regards,<br><strong>{business_name} Team</strong></p>

            <hr style="border:none;border-top:1px solid #ddd;margin:20px 0">
            <p style="color:#999;font-size:11px;margin:0">This is an automated message. If you received this by mistake, please disregard.</p>
        </div>
        </body>
        </html>"""

        return self._send(to_email, f"We miss you at {business_name}!", html)
