"""
Email validation via DNS MX-lookup and optional SMTP probe.

Validates:
  1. Basic syntax check
  2. MX record existence (DNS)
  3. SMTP connection probe (optional, disabled by default to avoid
     blocking outbound port 25 in cloud environments)
"""

from __future__ import annotations

import re
import smtplib
import socket
from dataclasses import dataclass

import dns.resolver
import structlog

log = structlog.get_logger()

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$")


@dataclass
class EmailValidationResult:
    email: str
    is_valid_syntax: bool = False
    has_mx_record: bool = False
    is_catch_all: bool | None = None
    smtp_reachable: bool | None = None
    validation_method: str = "syntax_only"
    error: str | None = None


def validate_email(email: str, smtp_probe: bool = False) -> EmailValidationResult:
    """
    Validate an email address.

    Args:
        email: The email address to validate.
        smtp_probe: If True, attempt an SMTP connection probe (port 25).
                    Only enable in environments with outbound SMTP access.
    """
    result = EmailValidationResult(email=email)

    # 1. Syntax
    if not _EMAIL_RE.match(email):
        result.error = "invalid_syntax"
        return result
    result.is_valid_syntax = True

    # 2. MX record lookup
    domain = email.split("@")[1]
    try:
        mx_records = dns.resolver.resolve(domain, "MX")
        result.has_mx_record = bool(mx_records)
        result.validation_method = "dns_mx"
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        result.error = "no_mx_record"
        return result
    except Exception as e:
        log.warning("email_validation.dns_error", domain=domain, error=str(e))
        result.error = f"dns_error: {e}"
        return result

    if not result.has_mx_record:
        return result

    # 3. Optional SMTP probe
    if smtp_probe:
        result.smtp_reachable, result.is_catch_all = _smtp_probe(email, mx_records)
        result.validation_method = "smtp_probe"

    return result


def _smtp_probe(email: str, mx_records) -> tuple[bool, bool | None]:
    """
    Attempt an SMTP VRFY/RCPT probe.
    Returns (smtp_reachable, is_catch_all).
    """
    domain = email.split("@")[1]
    # Sort MX records by priority
    sorted_mx = sorted(mx_records, key=lambda r: r.preference)
    mx_host = str(sorted_mx[0].exchange).rstrip(".")

    try:
        with smtplib.SMTP(mx_host, 25, timeout=5) as smtp:
            smtp.ehlo_or_helo_if_needed()
            smtp.mail("")
            code, _ = smtp.rcpt(email)
            # Check if catch-all by testing a random address
            import uuid
            fake = f"{uuid.uuid4().hex[:8]}@{domain}"
            fake_code, _ = smtp.rcpt(fake)
            is_catch_all = fake_code == 250
            return code == 250, is_catch_all
    except (smtplib.SMTPException, socket.timeout, ConnectionRefusedError, OSError):
        return False, None


async def validate_emails_batch(emails: list[str]) -> list[EmailValidationResult]:
    """Validate a list of emails concurrently using asyncio."""
    import asyncio
    from functools import partial

    loop = asyncio.get_event_loop()
    results = await asyncio.gather(
        *[loop.run_in_executor(None, partial(validate_email, email)) for email in emails]
    )
    return list(results)
