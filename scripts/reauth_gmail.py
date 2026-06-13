"""One-time Gmail OAuth re-consent for `gmail.readonly`.

Session 2 body ingest needs the `gmail.readonly` scope; the refresh tokens in
`.env` only carry `gmail.metadata` (403 on `format=full`). Run this once per
account to mint a fresh refresh token, then paste it into `.env` yourself.

Usage:
    python scripts/reauth_gmail.py

For each account in GMAIL_ACCOUNTS_JSON (or the single GMAIL_REFRESH_TOKEN
account), this:
  1. reads GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET from .env,
  2. starts a loopback HTTP server on port 3456,
  3. prints a Google consent URL (open it in the browser, pick that account),
  4. catches the redirect, exchanges the code for tokens,
  5. PRINTS the refresh_token. It does NOT write .env.

Prereq: in Google Cloud Console -> the OAuth client's "Authorized redirect
URIs", add exactly:  http://localhost:3456/
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
PORT = 3456
REDIRECT_URI = f"http://localhost:{PORT}/"
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing {name} in {ENV_PATH}")
    return value


def _account_hints() -> list[str]:
    """Email addresses to re-consent, in order. '' means 'no hint'."""
    raw = os.environ.get("GMAIL_ACCOUNTS_JSON")
    if raw:
        parsed = json.loads(raw)
        hints: list[str] = []
        for item in parsed:
            hints.append(str(item.get("email") or item.get("account") or ""))
        return hints or [""]
    return [""]


class _CallbackHandler(BaseHTTPRequestHandler):
    # Set by the server loop before serving.
    result: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802 (http.server contract)
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        type(self).result = {k: v[0] for k, v in params.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = "code" in type(self).result
        msg = (
            "Authorization received. Return to the terminal — you can close this tab."
            if ok
            else f"Authorization failed: {type(self).result.get('error', 'unknown')}"
        )
        self.wfile.write(f"<html><body><h3>{msg}</h3></body></html>".encode())

    def log_message(self, *_args) -> None:
        # Silence the default stderr access log.
        return


def _auth_url(client_id: str, state: str, login_hint: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",   # required to receive a refresh_token
        "prompt": "consent",        # force a fresh refresh_token every run
        "state": state,
    }
    if login_hint:
        params["login_hint"] = login_hint
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def _exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode()
    req = urllib.request.Request(TOKEN_ENDPOINT, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed host)
        return json.loads(resp.read().decode())


def _consent_one(client_id: str, client_secret: str, login_hint: str) -> str | None:
    """Run one consent round-trip. Returns the refresh_token or None."""
    state = secrets.token_urlsafe(16)
    url = _auth_url(client_id, state, login_hint)

    who = login_hint or "(no hint — pick the right account)"
    print("\n" + "=" * 72)
    print(f"Account: {who}")
    print("Open this URL in your browser and grant access:\n")
    print(url)
    print("\nWaiting for the redirect on", REDIRECT_URI, "...")

    _CallbackHandler.result = {}
    server = HTTPServer(("127.0.0.1", PORT), _CallbackHandler)
    try:
        # Serve until the callback handler has captured a response.
        while not _CallbackHandler.result:
            server.handle_request()
    finally:
        server.server_close()

    result = _CallbackHandler.result
    if "error" in result:
        print(f"  consent error: {result['error']}")
        return None
    if result.get("state") != state:
        print("  state mismatch (possible CSRF) — discarding.")
        return None
    code = result.get("code")
    if not code:
        print("  no authorization code returned.")
        return None

    tokens = _exchange_code(client_id, client_secret, code)
    refresh = tokens.get("refresh_token")
    granted = tokens.get("scope", "")
    if SCOPE not in granted:
        print(f"  WARNING: granted scopes do not include {SCOPE}: {granted!r}")
    return refresh


def main() -> None:
    load_dotenv(ENV_PATH)
    client_id = _env("GMAIL_CLIENT_ID")
    client_secret = _env("GMAIL_CLIENT_SECRET")

    print(f"Redirect URI in use: {REDIRECT_URI}")
    print("Ensure this exact URI is registered on the OAuth client in Google "
          "Cloud Console before continuing.")

    results: list[tuple[str, str | None]] = []
    for hint in _account_hints():
        try:
            refresh = _consent_one(client_id, client_secret, hint)
        except OSError as exc:
            print(f"  port/server error: {exc}")
            refresh = None
        results.append((hint or "(account)", refresh))

    print("\n" + "=" * 72)
    print("RESULTS — paste these refresh_token values into .env yourself "
          "(GMAIL_ACCOUNTS_JSON or GMAIL_REFRESH_TOKEN). .env was NOT modified.\n")
    for who, refresh in results:
        if refresh:
            print(f"{who}\n  refresh_token: {refresh}\n")
        else:
            print(f"{who}\n  refresh_token: <none — consent failed, re-run>\n")


if __name__ == "__main__":
    sys.exit(main())
