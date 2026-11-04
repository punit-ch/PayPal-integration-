
import pytest

import app as flask_app


@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True

    with flask_app.app.test_client() as client:
        yield client


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_unknown_endpoint_returns_404(client):
    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404


def test_capture_unknown_order_returns_404(client):
    response = client.post("/api/orders/UNKNOWN_TEST_ORDER/capture")

    assert response.status_code == 404
    assert "error" in response.get_json()