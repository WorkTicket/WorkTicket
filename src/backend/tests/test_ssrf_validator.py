import pytest

from app.ai.ssrf_validator import validate_url


def test_validate_url_rejects_ip_based():
    with pytest.raises(ValueError, match="IP-based"):
        validate_url("http://192.168.1.1/some-path", label="test")


def test_validate_url_rejects_private_ip():
    with pytest.raises(ValueError, match="IP-based"):
        validate_url("http://10.0.0.1/metadata", label="test")


def test_validate_url_rejects_loopback():
    with pytest.raises(ValueError, match="IP-based"):
        validate_url("http://127.0.0.1/admin", label="test")


def test_validate_url_rejects_non_http():
    with pytest.raises(ValueError, match="Only HTTP"):
        validate_url("ftp://example.com/file", label="test")


def test_validate_url_rejects_no_hostname():
    with pytest.raises(ValueError, match="no hostname"):
        validate_url("http:///path", label="test")
