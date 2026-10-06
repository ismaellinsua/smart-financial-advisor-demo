"""Receives Stripe's webhooks (POST /stripe/webhook) and applies them to the business directory.

Runs next to Streamlit inside the container, behind Caddy, only when STRIPE_WEBHOOK_SECRET is set. Every request
must carry Stripe's signature; each event is applied once (Stripe may deliver the same one more than once). With
STRIPE_SECRET_KEY too, a subscription notice is a cue to read the subscriptions from Stripe as they are now, so late or
out-of-order notices cannot bring back an old state.
"""

import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sales_manager"))

from core import logs  # noqa: E402
from core.billing import BillingError, Stripe, verify_webhook  # noqa: E402

log = logs.get("webhook")

PATH = "/stripe/webhook"
MAX_BODY = 512 * 1024


def make_handler(secret: str, directory_factory, stripe=None):
    directory = {}

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, text: str) -> None:
            body = text.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802 - http.server's naming
            if self.path.split("?")[0] != PATH:
                return self._reply(404, "not found")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if not 0 < length <= MAX_BODY:
                return self._reply(413 if length > MAX_BODY else 400, "bad request")
            payload = self.rfile.read(length)
            try:
                event = verify_webhook(payload, self.headers.get("Stripe-Signature", ""), secret)
            except BillingError:
                return self._reply(400, "invalid signature")
            try:
                if "d" not in directory:
                    directory["d"] = directory_factory()
                outcome = directory["d"].process_event(event, stripe)
            except Exception as exc:  # noqa: BLE001 - Stripe retries any non-2xx answer later
                log.error("webhook_failed id=%s error=%s", event.get("id"), type(exc).__name__)
                return self._reply(500, "retry later")
            log.info("webhook id=%s type=%s outcome=%s", event["id"], event.get("type"), outcome)
            return self._reply(200, outcome)

        def do_GET(self):  # noqa: N802
            self._reply(405, "method not allowed")

        def log_message(self, *args):  # requests are logged above, without headers or bodies
            pass

    return Handler


def main() -> None:
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    url = os.environ["DATABASE_URL"]

    def directory():
        from core.tenants import Directory

        return Directory(url)

    key = os.environ.get("STRIPE_SECRET_KEY", "")
    stripe = Stripe(key, os.environ.get("STRIPE_PRICE_ID", "")) if key else None
    port = int(os.environ.get("WEBHOOK_PORT", "8502"))
    ThreadingHTTPServer(("127.0.0.1", port), make_handler(secret, directory, stripe)).serve_forever()


if __name__ == "__main__":
    main()
