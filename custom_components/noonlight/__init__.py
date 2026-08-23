"""The Noonlight emergency-dispatch integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType
from noonlight_dispatch import (
    NoonlightAuthError,
    NoonlightConnectionError,
    NoonlightError,
    NoonlightResponseError,
)

from .const import (
    CONF_ENVIRONMENT,
    DEFAULT_ENVIRONMENT,
    HEARTBEAT_PROBE_ID,
    NON_PRODUCTION_ENVIRONMENTS,
    PLATFORMS,
)
from .coordinator import NoonlightConfigEntry, NoonlightCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Noonlight integration.

    Domain-level services are registered here so they exist even when no
    config entry is loaded; the handlers resolve the target entry at call time.
    """
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: NoonlightConfigEntry
) -> bool:
    """Set up a Noonlight config entry."""
    coordinator = NoonlightCoordinator(hass, entry)
    await coordinator.async_load()
    # Establish initial data; the first refresh is a no-op while idle.
    await coordinator.async_config_entry_first_refresh()

    # Confirm Noonlight is reachable and the token is accepted before we
    # advertise entities. A GET against a bogus alarm id has no side effects:
    # a 404 means reachable+authed, 401 means the token is bad, and a
    # transport error means Noonlight is unreachable (retry later).
    try:
        await coordinator.api.get_alarm_status(HEARTBEAT_PROBE_ID)
    except NoonlightAuthError as err:
        # Production forbids the side-effect-free GET status probe (HTTP 403)
        # even for tokens that can dispatch (POST /alarms). Don't fail setup on
        # it — sandbox permits the read (real auth failures there still block),
        # and production dispatch is confirmed via the test_dispatch action.
        status = getattr(err, "status_code", None)
        environment = entry.data.get(CONF_ENVIRONMENT, DEFAULT_ENVIRONMENT)
        if status == 403 or (status is None and environment not in NON_PRODUCTION_ENVIRONMENTS):
            _LOGGER.warning(
                "Noonlight status probe forbidden during setup on '%s'; "
                "proceeding (production restricts status reads; dispatch via "
                "POST is unaffected — verify with test_dispatch).", environment,
            )
        else:
            raise ConfigEntryAuthFailed("Noonlight rejected the API token") from err
    except NoonlightConnectionError as err:
        raise ConfigEntryNotReady("Cannot reach Noonlight") from err
    except NoonlightResponseError as err:
        if err.status_code != 404:
            raise ConfigEntryNotReady(
                f"Noonlight returned an unexpected response (HTTP {err.status_code})"
            ) from err
    except NoonlightError as err:
        # Any other Noonlight error during the probe: treat as not-ready and
        # retry rather than letting it crash setup.
        raise ConfigEntryNotReady("Could not reach Noonlight") from err

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NoonlightConfigEntry
) -> bool:
    """Unload a Noonlight config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    await entry.runtime_data.async_shutdown()
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: NoonlightConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
