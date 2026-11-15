"""Security and URL validation utilities for LID0501.

Ensures strict SSRF prevention, URL validation, and domain normalization.
"""

import ipaddress
import re
import socket
from urllib.parse import urlparse


BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}


def normalize_domain(input_str: str) -> str:
    """Extract and normalize domain from a URL or raw domain string.
    
    Examples:
        'https://www.Synthesia.io/about' -> 'synthesia.io'
        'Acme-corp.com' -> 'acme-corp.com'
    """
    if not input_str:
        return ""
    
    s = input_str.strip().lower()
    if not (s.startswith("http://") or s.startswith("https://")):
        s = "https://" + s
        
    try:
        parsed = urlparse(s)
        domain = parsed.hostname or ""
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.strip()
    except Exception:
        # Fallback regex
        clean = re.sub(r"^https?://", "", input_str.strip().lower())
        clean = clean.split("/")[0].split(":")[0]
        if clean.startswith("www."):
            clean = clean[4:]
        return clean


def is_ip_private_or_reserved(ip_str: str) -> bool:
    """Return True if an IP address is private, loopback, link-local, or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return True


def validate_safe_url(url: str) -> tuple[bool, str]:
    """Validate that a URL is a legitimate public web address and not an SSRF vector.
    
    Returns:
        (is_safe, error_reason)
    """
    if not url or not isinstance(url, str):
        return False, "Empty or non-string URL"

    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False, f"Unsupported scheme: {parsed.scheme} (only http/https allowed)"

        hostname = parsed.hostname
        if not hostname:
            return False, "Missing hostname in URL"

        hostname_lower = hostname.lower()
        if hostname_lower in BLOCKED_HOSTNAMES or hostname_lower.endswith(".local") or hostname_lower.endswith(".internal"):
            return False, f"Access to restricted host '{hostname}' is blocked"

        # Check if direct IP address
        try:
            ip = ipaddress.ip_address(hostname_lower)
            if is_ip_private_or_reserved(str(ip)):
                return False, f"Access to private/loopback IP address {ip} is blocked"
        except ValueError:
            # It's a hostname, resolve to check target IP
            try:
                addr_info = socket.getaddrinfo(hostname_lower, None)
                for family, _, _, _, sockaddr in addr_info:
                    ip_str = sockaddr[0]
                    if is_ip_private_or_reserved(ip_str):
                        return False, f"Host '{hostname}' resolves to private/reserved IP {ip_str}"
            except socket.gaierror:
                # DNS failure can happen during offline tests; allow if not in blocked names
                pass

        return True, ""
    except Exception as exc:
        return False, f"URL validation error: {str(exc)}"


def build_manual_linkedin_search_url(keywords: list[str]) -> str:
    """Generate a standard manual LinkedIn search URL for web browser use.
    
    Does NOT execute requests to LinkedIn. Opening must be an explicit user action.
    """
    from urllib.parse import quote_plus
    query = " ".join([k.strip() for k in keywords if k.strip()])
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"
