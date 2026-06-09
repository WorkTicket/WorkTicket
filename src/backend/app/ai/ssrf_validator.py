import ipaddress
import logging
from urllib.parse import urlparse

from app.config import get_settings

logger = logging.getLogger(__name__)


def validate_url(url: str, label: str = "URL") -> str:
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Only HTTP(S) URLs are allowed for {label}, got: {url[:50]}")
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError(f"{label} has no hostname")
    is_ip = False
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        pass
    if is_ip:
        raise ValueError(f"IP-based {label} blocked (SSRF prevention): {url[:50]}")
    settings = get_settings()
    if not settings.allowed_hosts:
        raise ValueError(f"SSRF protection: allowed_hosts not configured in environment — rejecting {label}")
    allowed_list = [h.strip() for h in settings.allowed_hosts.split(",") if h.strip()]
    if host not in allowed_list:
        raise ValueError(f"Host {host} not in allowed hosts list for {label} (allowed: {allowed_list})")
    return url
