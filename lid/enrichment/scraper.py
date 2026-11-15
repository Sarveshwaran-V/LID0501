"""Polite, safe public web retriever with SSRF protection and timeouts."""

from typing import Optional
from bs4 import BeautifulSoup
import httpx

from lid.config import DEFAULT_TIMEOUT, USER_AGENT
from lid.security import validate_safe_url


class SafeWebScraper:
    """Safely retrieves public web pages with strict SSRF controls and timeouts."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_page_soup(self, url: str) -> tuple[Optional[BeautifulSoup], Optional[str]]:
        """Fetch URL and return BeautifulSoup object, or None if failed.
        
        Returns:
            (soup, final_url_or_error)
        """
        is_safe, error = validate_safe_url(url)
        if not is_safe:
            return None, f"Security check failed: {error}"

        try:
            with httpx.Client(
                timeout=self.timeout,
                headers=self.headers,
                follow_redirects=True,
                max_redirects=3,
            ) as client:
                response = client.get(url)
                if response.status_code != 200:
                    return None, f"HTTP status {response.status_code}"
                
                # Verify final redirected URL is also safe
                final_safe, final_err = validate_safe_url(str(response.url))
                if not final_safe:
                    return None, f"Redirect target rejected: {final_err}"

                soup = BeautifulSoup(response.text, "html.parser")
                return soup, str(response.url)
        except Exception as exc:
            return None, f"Fetch error: {str(exc)}"
