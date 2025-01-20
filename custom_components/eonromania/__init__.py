"""Inițializarea integrării EON România."""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL
from .api import EonApiClient
from .coordinator import EonRomaniaCoordinator
from . import sensor, button


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Configurează integrarea globală EON România, dacă e necesar."""
    _LOGGER.debug("Inițializarea globală a integrării %s", DOMAIN)
    return True

PLATFORMS = ["sensor", "button"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configurează integrarea pentru o anumită intrare (config entry)."""
    _LOGGER.debug("Configurarea intrării pentru %s", DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    # Creăm clientul API
    session = async_get_clientsession(hass)
    username = entry.data["username"]
    password = entry.data["password"]
    cod_incasare = entry.data["cod_incasare"]
    update_interval = entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL)

    api_client = EonApiClient(session, username, password)

    # Creăm un singur DataUpdateCoordinator pentru toate datele
    coordinator = EonRomaniaCoordinator(
        hass,
        api_client=api_client,
        cod_incasare=cod_incasare,
        update_interval=update_interval,
    )

    # Facem prima actualizare
    await coordinator.async_config_entry_first_refresh()

    # Salvăm coordinatorul în hass.data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
    }

    # Încărcăm platformele
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Descărcarea intrării din config_entries."""
    _LOGGER.debug("Descărcarea intrării pentru %s", DOMAIN)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reîncarcă intrarea după reconfigurare."""
    _LOGGER.debug("Reîncărcarea intrării pentru %s", DOMAIN)
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
