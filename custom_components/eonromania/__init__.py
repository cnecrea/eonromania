"""Inițializarea integrării EON România."""
import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, DEFAULT_UPDATE, URL_DATEUSER, URL_CITIREINDEX, URL_ARHIVA, URL_FACTURASOLD, URL_FACTURASOLD_PROSUM,HEADERS_POST, URL_LOGIN

_LOGGER = logging.getLogger(__name__)

# Configurare generală pentru integrarea EON România
async def async_setup(hass: HomeAssistant, config: dict):
    """Configurează integrarea globală, dacă este necesar."""
    _LOGGER.debug("Inițializarea integrării %s", DOMAIN)
    return True

# Configurare pentru fiecare intrare (entry) adăugată în config_entries
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configurare specifică pentru o intrare din config_entries."""
    _LOGGER.debug("Configurarea intrării pentru %s", DOMAIN)

    # Inițializare Coordinatori pentru fiecare endpoint
    hass.data.setdefault(DOMAIN, {})
    update_interval = timedelta(seconds=entry.data.get("update_interval", DEFAULT_UPDATE))

    dateuser_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_dateuser_coordinator",
        update_method=lambda: _fetch_dateuser_data(hass, entry),
        update_interval=update_interval,
    )

    citireindex_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_citireindex_coordinator",
        update_method=lambda: _fetch_citireindex_data(hass, entry),
        update_interval=update_interval,
    )

    arhiva_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_arhiva_coordinator",
        update_method=lambda: _fetch_arhiva_data(hass, entry),
        update_interval=update_interval,
    )

    # Coordinator pentru soldul facturilor
    facturasold_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_facturasold_coordinator",
        update_method=lambda: _fetch_facturasold_data(hass, entry),
        update_interval=update_interval,
    )
  # Coordinator pentru soldul facturilor prosumator
    facturasold_prosum_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_facturasold_prosum_coordinator",
        update_method=lambda: _fetch_facturasold_prosum_data(hass, entry),
        update_interval=update_interval,
    )
    # Salvăm coordinatorii
    hass.data[DOMAIN][entry.entry_id] = {
        "dateuser": dateuser_coordinator,
        "citireindex": citireindex_coordinator,
        "arhiva": arhiva_coordinator,
        "facturasold": facturasold_coordinator,
        "facturasoldprosum": facturasold_prosum_coordinator,
    }

    # Actualizare inițială
    await dateuser_coordinator.async_config_entry_first_refresh()
    await citireindex_coordinator.async_config_entry_first_refresh()
    await arhiva_coordinator.async_config_entry_first_refresh()
    await facturasold_coordinator.async_config_entry_first_refresh()
    await facturasold_prosum_coordinator.async_config_entry_first_refresh()

    # Adăugarea platformelor (senzori, etc.)
    _LOGGER.debug("Pregătire pentru forward platform setup pentru %s", entry.entry_id)
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    _LOGGER.debug("Forward platform setup complet pentru %s", entry.entry_id)

    return True

# Obține datele utilizatorului
async def _fetch_dateuser_data(hass, entry):
    """Obține datele utilizatorului de la API-ul E-ON România."""
    token = await _fetch_token(hass, entry.data["username"], entry.data["password"])
    if not token:
        _LOGGER.error("Nu s-a putut obține un token valid pentru date utilizator.")
        return None

    url = URL_DATEUSER.format(cod_incasare=entry.data["cod_incasare"])
    headers = HEADERS_POST.copy()
    headers["Authorization"] = f"Bearer {token}"

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            return await response.json()
        else:
            _LOGGER.error(
                "Eroare la obținerea datelor utilizator: Status=%s, Răspuns=%s",
                response.status,
                await response.text(),
            )
            return None

# Obține datele despre indexul curent
async def _fetch_citireindex_data(hass, entry):
    """Obține datele despre indexul curent de la API-ul E-ON România."""
    token = await _fetch_token(hass, entry.data["username"], entry.data["password"])
    if not token:
        _LOGGER.error("Nu s-a putut obține un token valid pentru index curent.")
        return None

    url = URL_CITIREINDEX.format(cod_incasare=entry.data["cod_incasare"])
    headers = HEADERS_POST.copy()
    headers["Authorization"] = f"Bearer {token}"

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            _LOGGER.debug("Răspuns API pentru URL_CITIREINDEX: %s", data)
            return data
        else:
            _LOGGER.error(
                "Eroare la obținerea datelor despre index: Status=%s, Răspuns=%s",
                response.status,
                await response.text(),
            )
            return None

# Obține datele istorice (arhiva)
async def _fetch_arhiva_data(hass, entry):
    """Obține datele istorice de la API-ul E-ON România."""
    token = await _fetch_token(hass, entry.data["username"], entry.data["password"])
    if not token:
        _LOGGER.error("Nu s-a putut obține un token valid pentru arhivă.")
        return None

    url = URL_ARHIVA.format(cod_incasare=entry.data["cod_incasare"])
    headers = HEADERS_POST.copy()
    headers["Authorization"] = f"Bearer {token}"

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            _LOGGER.debug("Răspuns API pentru URL_ARHIVA: %s", data)
            return data
        else:
            _LOGGER.error(
                "Eroare la obținerea datelor din arhivă: Status=%s, Răspuns=%s",
                response.status,
                await response.text(),
            )
            return None

# Obține datele despre soldul facturilor
async def _fetch_facturasold_data(hass, entry):
    """Obține datele despre soldul facturilor de la API-ul E-ON România."""
    token = await _fetch_token(hass, entry.data["username"], entry.data["password"])
    if not token:
        _LOGGER.error("Nu s-a putut obține un token valid pentru soldul facturilor.")
        return None

    url = URL_FACTURASOLD.format(cod_incasare=entry.data["cod_incasare"])
    headers = HEADERS_POST.copy()
    headers["Authorization"] = f"Bearer {token}"

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            _LOGGER.debug("Răspuns API pentru URL_FACTURASOLD: %s", data)
            return data
        else:
            _LOGGER.error(
                "Eroare la obținerea datelor despre soldul facturilor: Status=%s, Răspuns=%s",
                response.status,
                await response.text(),
            )
            return None


# Obține datele despre soldul facturilor de prosumator
async def _fetch_facturasold_prosum_data(hass, entry):
    """Obține datele despre soldul facturilor de la API-ul E-ON România."""
    token = await _fetch_token(hass, entry.data["username"], entry.data["password"])
    if not token:
        _LOGGER.error("Nu s-a putut obține un token valid pentru soldul facturilor.")
        return None

    url = URL_FACTURASOLD_PROSUM.format(cod_incasare=entry.data["cod_incasare"])
    headers = HEADERS_POST.copy()
    headers["Authorization"] = f"Bearer {token}"

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            _LOGGER.debug("Răspuns API pentru URL_FACTURASOLD_PROSUM: %s", data)
            return data
        else:
            _LOGGER.error(
                "Eroare la obținerea datelor despre soldul facturilor: Status=%s, Răspuns=%s",
                response.status,
                await response.text(),
            )
            return None
            
# Obține un token de autentificare
async def _fetch_token(hass, username, password):
    """Obține un token de autentificare de la API-ul E-ON România."""
    payload = {
        "username": username,
        "password": password,
        "rememberMe": False
    }

    headers = HEADERS_POST.copy()

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    async with session.post(URL_LOGIN, json=payload, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            token = data.get("accessToken")
            _LOGGER.debug("Token obținut dinamic: %s", token)
            return token
        else:
            _LOGGER.error(
                "Eroare la obținerea token-ului: Status=%s, Răspuns=%s",
                response.status,
                await response.text(),
            )
            return None

# Descărcarea unei intrări din config_entries
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Elimină o intrare din config_entries."""
    _LOGGER.debug("Descărcarea intrării pentru %s", DOMAIN)
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

# Reîncarcarea unei intrări după reconfigurare
async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reîncarcă o intrare din config_entries după reconfigurare."""
    _LOGGER.debug("Reîncărcarea intrării pentru %s", DOMAIN)
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
