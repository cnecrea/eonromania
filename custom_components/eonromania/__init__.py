"""Inițializarea integrării E·ON România."""

import logging
from dataclasses import dataclass
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, PLATFORMS
from .api import EonApiClient
from .coordinator import EonRomaniaCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class EonRomaniaRuntimeData:
    """Structură tipizată pentru datele runtime ale integrării."""

    coordinator: EonRomaniaCoordinator
    api_client: EonApiClient


# Type alias pentru ConfigEntry cu runtime_data tipizat
EonRomaniaConfigEntry: TypeAlias = ConfigEntry[EonRomaniaRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict):
    """Configurează integrarea globală E·ON România, dacă e necesar."""
    _LOGGER.debug("Inițializare globală integrare: %s", DOMAIN)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EonRomaniaConfigEntry):
    """Configurează integrarea pentru o anumită intrare (config entry)."""
    _LOGGER.info("Se configurează integrarea %s (entry_id=%s).", DOMAIN, entry.entry_id)

    # Creăm clientul API
    session = async_get_clientsession(hass)
    username = entry.data["username"]
    password = entry.data["password"]
    cod_incasare = entry.data["cod_incasare"]
    update_interval = entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL)

    # Nu logăm parola; codul de încasare îl logăm în clar (conform cerinței tale).
    _LOGGER.debug(
        "Parametri intrare %s (entry_id=%s): contract=%s, interval=%ss.",
        DOMAIN,
        entry.entry_id,
        cod_incasare,
        update_interval,
    )

    api_client = EonApiClient(session, username, password)

    # Creăm coordinatorul
    coordinator = EonRomaniaCoordinator(
        hass,
        api_client=api_client,
        cod_incasare=cod_incasare,
        update_interval=update_interval,
    )

    # Prima actualizare (important să avem log clar dacă pică aici)
    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        _LOGGER.error(
            "Prima actualizare a datelor E·ON a eșuat (entry_id=%s, contract=%s): %s",
            entry.entry_id,
            cod_incasare,
            err,
        )
        raise
    except Exception as err:
        _LOGGER.exception(
            "Eroare neașteptată la prima actualizare a datelor E·ON (entry_id=%s, contract=%s): %s",
            entry.entry_id,
            cod_incasare,
            err,
        )
        raise

    # Salvăm datele runtime în config entry (pattern modern)
    entry.runtime_data = EonRomaniaRuntimeData(
        coordinator=coordinator,
        api_client=api_client,
    )

    # Încărcăm platformele
    _LOGGER.debug(
        "Se încarcă platformele pentru %s (entry_id=%s): %s",
        DOMAIN,
        entry.entry_id,
        [p.value if hasattr(p, "value") else str(p) for p in PLATFORMS],
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "Integrarea %s este configurată (entry_id=%s, contract=%s).",
        DOMAIN,
        entry.entry_id,
        cod_incasare,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EonRomaniaConfigEntry):
    """Descărcarea intrării din config_entries."""
    cod_incasare = entry.data.get("cod_incasare", "")
    _LOGGER.info(
        "Se descarcă integrarea %s (entry_id=%s, contract=%s).",
        DOMAIN,
        entry.entry_id,
        cod_incasare,
    )

    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        _LOGGER.info(
            "Integrarea %s a fost descărcată (entry_id=%s, contract=%s).",
            DOMAIN,
            entry.entry_id,
            cod_incasare,
        )
    else:
        _LOGGER.warning(
            "Integrarea %s nu a putut fi descărcată complet (entry_id=%s, contract=%s).",
            DOMAIN,
            entry.entry_id,
            cod_incasare,
        )
    return ok
