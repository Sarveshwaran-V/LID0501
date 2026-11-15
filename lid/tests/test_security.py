"""Tests for security, SSRF prevention, and domain normalization."""

import pytest
from lid.security import build_manual_linkedin_search_url, is_ip_private_or_reserved, normalize_domain, validate_safe_url


def test_normalize_domain():
    assert normalize_domain("https://www.Synthesia.io/about") == "synthesia.io"
    assert normalize_domain("http://github.com/topics") == "github.com"
    assert normalize_domain("acme-corp.com") == "acme-corp.com"
    assert normalize_domain("WWW.Example.COM/path?a=1") == "example.com"
    assert normalize_domain("  sub.domain.co.uk/test  ") == "sub.domain.co.uk"


def test_ip_private_check():
    assert is_ip_private_or_reserved("127.0.0.1") is True
    assert is_ip_private_or_reserved("10.0.0.5") is True
    assert is_ip_private_or_reserved("192.168.1.1") is True
    assert is_ip_private_or_reserved("169.254.169.254") is True
    assert is_ip_private_or_reserved("::1") is True
    assert is_ip_private_or_reserved("8.8.8.8") is False


def test_validate_safe_url():
    # Safe public URLs
    is_safe, err = validate_safe_url("https://github.com")
    assert is_safe is True
    assert err == ""

    is_safe, err = validate_safe_url("https://news.google.com/rss")
    assert is_safe is True

    # Blocked SSRF and invalid schemes
    is_safe, err = validate_safe_url("ftp://example.com")
    assert is_safe is False
    assert "scheme" in err.lower()

    is_safe, err = validate_safe_url("http://localhost:8080/admin")
    assert is_safe is False
    assert "blocked" in err.lower()

    is_safe, err = validate_safe_url("http://127.0.0.1:5000/secret")
    assert is_safe is False
    assert "blocked" in err.lower()

    is_safe, err = validate_safe_url("http://169.254.169.254/latest/meta-data")
    assert is_safe is False

    is_safe, err = validate_safe_url("")
    assert is_safe is False


def test_manual_linkedin_search_url():
    url = build_manual_linkedin_search_url(['"Acme Corp"', "Founder"])
    assert url.startswith("https://www.linkedin.com/search/results/people/?keywords=")
    assert "Acme" in url
    assert "Founder" in url
