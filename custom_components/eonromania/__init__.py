"""Inițializarea integrării E·ON România."""

import logging
from dataclasses import dataclass, field

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

    coordinators: dict[str, EonRomaniaCoordinator] = field(default_factory=dict)
    api_client: EonApiClient | None = None


async def async_setup(hass: HomeAssistant, config: dict):
    """Configurează integrarea globală E·ON România."""
    _LOGGER.debug("Inițializare globală integrare: %s", DOMAIN)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configurează integrarea pentru o anumită intrare (config entry)."""
    _LOGGER.info("Se configurează integrarea %s (entry_id=%s).", DOMAIN, entry.entry_id)

    session = async_get_clientsession(hass)
    username = entry.data["username"]
    password = entry.data["password"]
    update_interval = entry.data.get("update_interval", DEFAULT_UPDATE_INTERVAL)

    # Compatibilitate: formatul vechi (un singur cod_incasare) vs nou (listă)
    selected_contracts = entry.data.get("selected_contracts", [])
    if not selected_contracts:
        # Formatul vechi — un singur contract
        old_cod = entry.data.get("cod_incasare", "")
        if old_cod:
            selected_contracts = [old_cod]

    if not selected_contracts:
        _LOGGER.error(
            "Nu există contracte selectate pentru %s (entry_id=%s).",
            DOMAIN, entry.entry_id,
        )
        return False

    _LOGGER.debug(
        "Contracte selectate pentru %s (entry_id=%s): %s, interval=%ss.",
        DOMAIN, entry.entry_id, selected_contracts, update_interval,
    )

    # Un singur client API partajat (un singur cont, un singur token)
    api_client = EonApiClient(session, username, password)

    # Metadatele contractelor (tip utilitate, colectiv/nu)
    contract_metadata = entry.data.get("contract_metadata", {})

    # Creăm câte un coordinator per contract selectat
    coordinators: dict[str, EonRomaniaCoordinator] = {}

    for cod in selected_contracts:
        meta = contract_metadata.get(cod, {})
        is_collective = meta.get("is_collective", False)

        coordinator = EonRomaniaCoordinator(
            hass,
            api_client=api_client,
            cod_incasare=cod,
            update_interval=update_interval,
            is_collective=is_collective,
        )

        try:
            await coordinator.async_config_entry_first_refresh()
        except UpdateFailed as err:
            _LOGGER.error(
                "Prima actualizare eșuată (entry_id=%s, contract=%s): %s",
                entry.entry_id, cod, err,
            )
            # Continuăm cu restul contractelor — nu oprim totul pentru unul
            continue
        except Exception as err:
            _LOGGER.exception(
                "Eroare neașteptată la prima actualizare (entry_id=%s, contract=%s): %s",
                entry.entry_id, cod, err,
            )
            continue

        coordinators[cod] = coordinator

    if not coordinators:
        _LOGGER.error(
            "Niciun coordinator inițializat cu succes pentru %s (entry_id=%s).",
            DOMAIN, entry.entry_id,
        )
        return False

    _LOGGER.info(
        "%s coordinatoare active din %s contracte selectate (entry_id=%s).",
        len(coordinators), len(selected_contracts), entry.entry_id,
    )

    # Salvăm datele runtime
    entry.runtime_data = EonRomaniaRuntimeData(
        coordinators=coordinators,
        api_client=api_client,
    )

    # Încărcăm platformele
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listener pentru modificarea opțiunilor
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    _LOGGER.info(
        "Integrarea %s configurată (entry_id=%s, contracte=%s).",
        DOMAIN, entry.entry_id, list(coordinators.keys()),
    )
    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Reîncarcă integrarea când opțiunile se schimbă."""
    _LOGGER.info(
        "Opțiunile integrării %s s-au schimbat (entry_id=%s). Se reîncarcă...",
        DOMAIN, entry.entry_id,
    )
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Descărcarea intrării din config_entries."""
    _LOGGER.info(
        "Se descarcă integrarea %s (entry_id=%s).",
        DOMAIN, entry.entry_id,
    )

    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        _LOGGER.info("Integrarea %s descărcată (entry_id=%s).", DOMAIN, entry.entry_id)
    else:
        _LOGGER.warning(
            "Integrarea %s nu a putut fi descărcată complet (entry_id=%s).",
            DOMAIN, entry.entry_id,
        )
    return ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrare de la versiuni vechi la versiunea curentă."""
    _LOGGER.debug(
        "Migrare config entry %s de la versiunea %s.",
        config_entry.entry_id, config_entry.version,
    )

    if config_entry.version < 3:
        # v1/v2 → v3: convertim cod_incasare la selected_contracts[]
        old_data = dict(config_entry.data)
        old_cod = old_data.get("cod_incasare", "")
        old_interval = old_data.get("update_interval",
                        config_entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL))

        new_data = {
            "username": old_data.get("username", ""),
            "password": old_data.get("password", ""),
            "update_interval": old_interval,
            "select_all": False,
            "selected_contracts": [old_cod] if old_cod else [],
        }

        _LOGGER.info(
            "Migrare entry %s: v%s → v3 (cod_incasare=%s → selected_contracts).",
            config_entry.entry_id, config_entry.version, old_cod,
        )

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options={}, version=3
        )
        return True

    _LOGGER.error(
        "Versiune necunoscută pentru migrare: %s (entry_id=%s).",
        config_entry.version, config_entry.entry_id,
    )
    return False
