import asyncio

from atlas_ml_platform.core.shutdown import RequestTracker


async def test_begin_and_end_track_outstanding_requests() -> None:
    tracker = RequestTracker()

    tracker.begin()
    tracker.begin()
    assert tracker.in_flight == 2

    tracker.end()
    assert tracker.in_flight == 1

    tracker.end()
    assert tracker.in_flight == 0


async def test_wait_for_idle_returns_immediately_when_nothing_is_in_flight() -> None:
    tracker = RequestTracker()

    assert await tracker.wait_for_idle(0) is True


async def test_wait_for_idle_returns_false_when_requests_outlive_the_budget() -> None:
    tracker = RequestTracker()
    tracker.begin()

    assert await tracker.wait_for_idle(0) is False

    tracker.end()


async def test_wait_for_idle_resolves_when_the_last_request_finishes() -> None:
    tracker = RequestTracker()
    tracker.begin()
    tracker.begin()

    waiter = asyncio.create_task(tracker.wait_for_idle(1.0))
    await asyncio.sleep(0)

    tracker.end()
    assert waiter.done() is False

    tracker.end()
    assert await waiter is True


async def test_end_without_begin_does_not_drive_the_count_negative() -> None:
    tracker = RequestTracker()

    tracker.end()

    assert tracker.in_flight == 0
    assert await tracker.wait_for_idle(0) is True
