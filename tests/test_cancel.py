"""Cancellation tests for an already-dispatched (live) alarm."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
import respx
from homeassistant.util import dt as dt_util
from httpx import Response
from noonlight_dispatch import NoonlightConnectionError
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.noonlight.const import (
    STATE_CANCELED,
    STATE_DISPATCHED,
    STATE_IDLE,
)

from .conftest import SANDBOX

_ALARMS = f"{SANDBOX}/dispatch/v1/alarms"
_STATUS_RE = r".*/dispatch/v1/alarms/.*/status"


def _coordinator(hass, entry):
    return entry.runtime_data


async def _dispatch_now(hass, coordinator):
    respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()
    assert coordinator.data["state"] == STATE_DISPATCHED


@respx.mock
async def test_cancel_dispatched_calls_api_then_settles(hass, setup_entry):
    coordinator = _coordinator(hass, setup_entry)
    await _dispatch_now(hass, coordinator)

    cancel = respx.post(url__regex=_STATUS_RE).mock(
        return_value=Response(200, json={"status": "CANCELED"})
    )
    await coordinator.async_cancel("false alarm")
    await hass.async_block_till_done()

    assert cancel.called
    assert coordinator.data["state"] == STATE_CANCELED

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()
    assert coordinator.data["state"] == STATE_IDLE


@respx.mock
async def test_cancel_dispatched_api_failure_propagates(hass, setup_entry):
    """If the cancel call to Noonlight fails, the error is surfaced."""
    coordinator = _coordinator(hass, setup_entry)
    await _dispatch_now(hass, coordinator)

    respx.post(url__regex=_STATUS_RE).mock(
        side_effect=httpx.ConnectError("down")
    )
    with pytest.raises(NoonlightConnectionError):
        await coordinator.async_cancel("oops")


async def test_cancel_when_idle_is_noop(hass, setup_entry):
    coordinator = _coordinator(hass, setup_entry)
    assert coordinator.data["state"] == STATE_IDLE

    await coordinator.async_cancel(None)
    await hass.async_block_till_done()

    assert coordinator.data["state"] == STATE_IDLE
