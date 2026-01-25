"""Tests for health check endpoints.

Tests /health, /ready, and /live endpoints with mocked MongoDB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from quart import Quart


@pytest.fixture
def mock_storage() -> AsyncMock:
    """Create a mock storage with configurable connection status."""
    storage = AsyncMock()
    storage.check_connection = AsyncMock(return_value=True)
    storage.connect = AsyncMock()
    storage.close = AsyncMock()
    return storage


@pytest.fixture
def app_with_mock(mock_storage: AsyncMock) -> Generator[tuple[Quart, AsyncMock], None, None]:
    """Create test application with mocked storage.

    Yields (app, mock_storage) tuple to keep the patch active during the test.
    """
    from src.app import create_app

    with (
        patch("src.app.get_storage", return_value=mock_storage),
        patch("src.app.create_orchestrator") as mock_create,
    ):
        mock_orchestrator = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_create.return_value = (mock_orchestrator, mock_pipeline)

        test_app = create_app()
        test_app.pipeline = mock_pipeline  # type: ignore[attr-defined]
        yield test_app, mock_storage


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok_when_mongo_connected(
        self, app_with_mock: tuple[Any, AsyncMock]
    ) -> None:
        """Health check returns 200 and ok status when MongoDB is connected."""
        app, mock_storage = app_with_mock
        mock_storage.check_connection.return_value = True

        async with app.test_client() as client:
            response = await client.get("/health")

            assert response.status_code == 200
            data = await response.get_json()
            assert data["status"] == "ok"
            assert data["mongodb"] is True

    @pytest.mark.asyncio
    async def test_health_returns_degraded_when_mongo_disconnected(
        self, app_with_mock: tuple[Any, AsyncMock]
    ) -> None:
        """Health check returns 503 and degraded status when MongoDB is down."""
        app, mock_storage = app_with_mock
        mock_storage.check_connection.return_value = False

        async with app.test_client() as client:
            response = await client.get("/health")

            assert response.status_code == 503
            data = await response.get_json()
            assert data["status"] == "degraded"
            assert data["mongodb"] is False


class TestReadinessEndpoint:
    """Tests for /ready endpoint."""

    @pytest.mark.asyncio
    async def test_ready_returns_ok_when_all_checks_pass(
        self, app_with_mock: tuple[Any, AsyncMock]
    ) -> None:
        """Readiness returns 200 when MongoDB and pipeline are ready."""
        app, mock_storage = app_with_mock
        mock_storage.check_connection.return_value = True

        async with app.test_client() as client:
            response = await client.get("/ready")

            assert response.status_code == 200
            data = await response.get_json()
            assert data["mongodb"] is True
            assert data["pipeline"] is True

    @pytest.mark.asyncio
    async def test_ready_returns_503_when_mongo_disconnected(
        self, app_with_mock: tuple[Any, AsyncMock]
    ) -> None:
        """Readiness returns 503 when MongoDB is not connected."""
        app, mock_storage = app_with_mock
        mock_storage.check_connection.return_value = False

        async with app.test_client() as client:
            response = await client.get("/ready")

            assert response.status_code == 503
            data = await response.get_json()
            assert data["mongodb"] is False


class TestLivenessEndpoint:
    """Tests for /live endpoint."""

    @pytest.mark.asyncio
    async def test_live_always_returns_alive(
        self, app_with_mock: tuple[Any, AsyncMock]
    ) -> None:
        """Liveness probe always returns alive status."""
        app, _ = app_with_mock

        async with app.test_client() as client:
            response = await client.get("/live")

            assert response.status_code == 200
            data = await response.get_json()
            assert data["status"] == "alive"


class TestMongoStorageCheckConnection:
    """Tests for MongoStorage.check_connection method."""

    @pytest.mark.asyncio
    async def test_check_connection_returns_true_when_connected(self) -> None:
        """check_connection returns True when ping succeeds."""
        from src.storage.mongo import MongoStorage

        storage = MongoStorage()
        # Mock the client
        storage._client = AsyncMock()
        storage._client.admin.command = AsyncMock(return_value={"ok": 1})

        result = await storage.check_connection()

        assert result is True
        storage._client.admin.command.assert_called_once_with("ping")

    @pytest.mark.asyncio
    async def test_check_connection_returns_false_when_not_initialized(self) -> None:
        """check_connection returns False when client is not initialized."""
        from src.storage.mongo import MongoStorage

        storage = MongoStorage()
        # Client is None by default

        result = await storage.check_connection()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_connection_returns_false_on_error(self) -> None:
        """check_connection returns False when ping raises exception."""
        from src.storage.mongo import MongoStorage

        storage = MongoStorage()
        storage._client = AsyncMock()
        storage._client.admin.command = AsyncMock(side_effect=Exception("Connection lost"))

        result = await storage.check_connection()

        assert result is False
