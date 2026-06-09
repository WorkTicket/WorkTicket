from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


def test_prometheus_metrics_requires_auth_when_debug_false():
    """Test that /admin/metrics requires authentication when debug=False"""
    with patch("app.config.get_settings") as mock_settings:
        # Mock settings with debug=False and no metrics token
        mock_settings.return_value.debug = False
        mock_settings.return_value.metrics_access_token = None

        client = TestClient(app)
        response = client.get("/admin/metrics")

        # Should return 403 when debug=False and no token configured
        assert response.status_code == status.HTTP_403_FORBIDDEN


def test_prometheus_metrics_allows_access_when_debug_true():
    """Test that /admin/metrics allows access when debug=True (for backward compatibility)"""
    with patch("app.config.get_settings") as mock_settings:
        # Mock settings with debug=True
        mock_settings.return_value.debug = True
        mock_settings.return_value.metrics_access_token = None

        client = TestClient(app)
        response = client.get("/admin/metrics")

        # Should allow access when debug=True
        assert response.status_code == status.HTTP_200_OK


def test_prometheus_metrics_requires_valid_token_when_configured():
    """Test that /admin/metrics requires valid token when METRICS_ACCESS_TOKEN is set"""
    with patch("app.config.get_settings") as mock_settings:
        # Mock settings with debug=False and metrics token configured
        mock_settings.return_value.debug = False
        mock_settings.return_value.metrics_access_token = "valid-token-123"

        client = TestClient(app)

        # Request without token should be forbidden
        response = client.get("/admin/metrics")
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Request with invalid token should be forbidden
        response = client.get("/admin/metrics", headers={"Authorization": "Bearer invalid-token"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Request with valid token should be allowed
        response = client.get("/admin/metrics", headers={"Authorization": "Bearer valid-token-123"})
        assert response.status_code == status.HTTP_200_OK
