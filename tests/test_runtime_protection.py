import pytest

from app.runtime import RequestLoadController


@pytest.mark.asyncio
async def test_request_load_controller_rejects_when_queue_wait_expires():
    controller = RequestLoadController(max_concurrent_requests=1, queue_timeout_seconds=0.05)

    assert await controller.acquire() is True
    assert await controller.acquire() is False

    await controller.release()


@pytest.mark.asyncio
async def test_request_load_controller_tracks_in_flight_requests():
    controller = RequestLoadController(max_concurrent_requests=2, queue_timeout_seconds=0.05)

    assert await controller.acquire() is True
    snapshot = controller.snapshot()
    assert snapshot.in_flight == 1
    assert snapshot.available_slots == 1

    await controller.release()
    snapshot = controller.snapshot()
    assert snapshot.in_flight == 0
