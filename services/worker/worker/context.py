import ipaddress
import logging
import re
import socket
from typing import Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Accept either full URLs or bare domains (we will normalize bare domains to https://)
URL_REGEX = r"(?:https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?" 

# Block internal/private IP ranges to prevent SSRF
BLOCKED_CIDRS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),  # Link-local
    ipaddress.ip_network('::1/128'),  # IPv6 localhost
    ipaddress.ip_network('fe80::/10'),  # IPv6 link-local
]

MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5MB limit


def _normalize_url(raw: str) -> str:
    raw = raw.strip().rstrip(").,;\"")
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"https://{raw}"


def _is_safe_url(url: str) -> bool:
    """Check if URL is safe to fetch (not internal/private IP)"""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Resolve hostname to IP
        ip_str = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip_str)
        
        # Check if IP is in blocked ranges
        for cidr in BLOCKED_CIDRS:
            if ip_obj in cidr:
                logger.warning(f"Blocked internal IP: {url} resolves to {ip_str}")
                return False
        
        return True
    except (socket.gaierror, ValueError) as e:
        logger.warning(f"Could not resolve {url}: {e}")
        return False


def _dedup_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it in seen:
            continue
        seen.add(it)
        out.append(it)
    return out


def extract_and_fetch_context(text: str) -> tuple[str, list[str]]:
    """Find URLs/domains in text, fetch them, and append extracted page text.

    Returns:
    - augmented prompt (original + fetched content)
    - list of fetched source URLs
    """
    raw_matches = re.findall(URL_REGEX, text)
    if not raw_matches:
        return text, []

    urls = _dedup_keep_order([_normalize_url(m) for m in raw_matches])

    sources: list[str] = []
    context_parts: list[str] = []

    for url in urls:
        try:
            # SSRF protection: block internal IPs
            if not _is_safe_url(url):
                logger.warning(f"Skipping unsafe URL: {url}")
                continue
            
            # Fetch with streaming to enforce size limit
            resp = requests.get(
                url,
                timeout=10,
                stream=True,
                allow_redirects=True,
                headers={"user-agent": "chriseon/0.1 (+local dev)"},
            )
            resp.raise_for_status()
            
            # Read content with size limit
            content = b""
            for chunk in resp.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > MAX_CONTENT_SIZE:
                    logger.warning(f"Content too large from {url}, truncating")
                    break
            
            text = content.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(text, "html.parser")
            for node in soup(["script", "style", "nav", "footer", "noscript"]):
                node.extract()

            clean_text = soup.get_text(separator=" ", strip=True)
            clean_text = clean_text[:12000]

            if not clean_text:
                continue

            context_parts.append(
                f"\n--- CONTENT FROM {url} ---\n{clean_text}\n--- END CONTENT ---\n"
            )
            sources.append(url)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            continue

    if not context_parts:
        return text, []

    # Put context AFTER the user's question to emphasize query priority
    augmented_prompt = text
    augmented_prompt += "\n\n--- REFERENCE CONTEXT (use only if relevant to answer the question above) ---"
    augmented_prompt += "\n" + "\n".join(context_parts)
    augmented_prompt += "\n--- END REFERENCE CONTEXT ---\n"
    return augmented_prompt, sources
