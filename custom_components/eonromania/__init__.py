"""Inițializarea integrării E·ON România."""

import logging
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, DOMAIN_TOKEN_STORE, LICENSE_DATA_KEY, PLATFORMS
from .api import EonApiClient
from .coordinator import EonRomaniaCoordinator
from .license import LicenseManager

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class EonRomaniaRuntimeData:
    """Structură tipizată pentru datele runtime ale integrării."""

    coordinators: dict[str, EonRomaniaCoordinator] = field(default_factory=dict)
    api_client: EonApiClient | None = None


async def async_setup(hass: HomeAssistant, config: dict):
    """Configurează integrarea globală E·ON România."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configurează integrarea pentru o anumită intrare (config entry)."""
    _LOGGER.info("Se configurează integrarea %s (entry_id=%s).", DOMAIN, entry.entry_id)

    hass.data.setdefault(DOMAIN, {})

    # ── Inițializare License Manager (o singură instanță per domeniu) ──
    if LICENSE_DATA_KEY not in hass.data.get(DOMAIN, {}):
        _LOGGER.debug("[EonRomania] Inițializez LicenseManager (prima entry)")
        license_mgr = LicenseManager(hass)
        # IMPORTANT: setăm referința ÎNAINTE de async_load() pentru a preveni
        # race condition-ul: async_load() face await HTTP, ceea ce cedează
        # event loop-ul. Fără această ordine, alte entry-uri concurente ar vedea
        # LICENSE_DATA_KEY ca lipsă și ar crea câte un LicenseManager duplicat,
        # generând N request-uri /check simultane (câte unul per entry).
        hass.data[DOMAIN][LICENSE_DATA_KEY] = license_mgr
        await license_mgr.async_load()
        _LOGGER.debug(
            "[EonRomania] LicenseManager: status=%s, valid=%s, fingerprint=%s...",
            license_mgr.status,
            license_mgr.is_valid,
            license_mgr.fingerprint[:16],
        )

        # Heartbeat periodic — intervalul vine de la server (via valid_until)
        from datetime import timedelta

        from homeassistant.helpers.event import (
            async_track_point_in_time,
            async_track_time_interval,
        )
        from homeassistant.util import dt as dt_util

        interval_sec = license_mgr.check_interval_seconds
        _LOGGER.debug(
            "[EonRomania] Programez heartbeat periodic la fiecare %d secunde (%d ore)",
            interval_sec,
            interval_sec // 3600,
        )

        async def _heartbeat_periodic(_now) -> None:
            """Verifică statusul la server dacă cache-ul a expirat.

            Logică:
            1. Captează is_valid ÎNAINTE de heartbeat
            2. Dacă cache expirat → contactează serverul
            3. Captează is_valid DUPĂ heartbeat
            4. Dacă starea s-a schimbat → reload entries (tranziție curată)
            5. Reprogramează heartbeat-ul la intervalul actualizat de server
            """
            mgr: LicenseManager | None = hass.data.get(DOMAIN, {}).get(
                LICENSE_DATA_KEY
            )
            if not mgr:
                _LOGGER.debug("[EonRomania] Heartbeat: LicenseManager nu există, skip")
                return

            # Captează starea ÎNAINTE de heartbeat
            was_valid = mgr.is_valid

            if mgr.needs_heartbeat:
                _LOGGER.debug("[EonRomania] Heartbeat: cache expirat, verific la server")
                await mgr.async_heartbeat()

                # Captează starea DUPĂ heartbeat
                now_valid = mgr.is_valid

                # Detectează tranziții pe care async_check_status nu le-a prins
                # (ex: server inaccesibil + cache expirat → is_valid devine False)
                if was_valid and not now_valid:
                    _LOGGER.warning(
                        "[EonRomania] Licența a devenit invalidă — reîncarc senzorii"
                    )
                    await mgr._async_reload_entries()
                elif not was_valid and now_valid:
                    _LOGGER.info(
                        "[EonRomania] Licența a redevenit validă — reîncarc senzorii"
                    )
                    await mgr._async_reload_entries()

                # Reprogramează heartbeat-ul la intervalul actualizat de server
                new_interval = mgr.check_interval_seconds
                _LOGGER.debug(
                    "[EonRomania] Heartbeat: reprogramez la %d secunde (%d min)",
                    new_interval,
                    new_interval // 60,
                )
                # Oprește vechiul timer
                cancel_old = hass.data.get(DOMAIN, {}).get("_cancel_heartbeat")
                if cancel_old:
                    cancel_old()
                # Programează noul timer cu intervalul actualizat
                cancel_new = async_track_time_interval(
                    hass,
                    _heartbeat_periodic,
                    timedelta(seconds=new_interval),
                )
                hass.data[DOMAIN]["_cancel_heartbeat"] = cancel_new
            else:
                _LOGGER.debug("[EonRomania] Heartbeat: cache valid, nu e nevoie de verificare")

        cancel_heartbeat = async_track_time_interval(
            hass,
            _heartbeat_periodic,
            timedelta(seconds=interval_sec),
        )
        hass.data[DOMAIN]["_cancel_heartbeat"] = cancel_heartbeat
        _LOGGER.debug("[EonRomania] Heartbeat programat și stocat în hass.data")

        # ── Timer precis la valid_until (zero gap la expirare cache) ──
        def _schedule_cache_expiry_check(mgr_ref: LicenseManager) -> None:
            """Programează un check EXACT la momentul expirării cache-ului.

            Elimină complet fereastra dintre expirarea cache-ului și
            următorul heartbeat periodic. La expirare, contactează
            serverul imediat și declanșează reload dacă starea se schimbă.
            """
            # Anulează timer-ul anterior (dacă există)
            cancel_prev = hass.data.get(DOMAIN, {}).pop(
                "_cancel_cache_expiry", None
            )
            if cancel_prev:
                cancel_prev()

            valid_until = (mgr_ref._status_token or {}).get("valid_until")
            if not valid_until or valid_until <= 0:
                return

            expiry_dt = dt_util.utc_from_timestamp(valid_until)
            # Adaugă 2 secunde ca marjă (evită race condition cu cache check)
            expiry_dt = expiry_dt + timedelta(seconds=2)

            async def _on_cache_expiry(_now) -> None:
                """Callback executat EXACT la expirarea cache-ului."""
                mgr_now: LicenseManager | None = hass.data.get(
                    DOMAIN, {}
                ).get(LICENSE_DATA_KEY)
                if not mgr_now:
                    return

                was_valid = mgr_now.is_valid
                _LOGGER.debug(
                    "[E.ON] Cache expirat — verific imediat la server"
                )
                await mgr_now.async_check_status()
                now_valid = mgr_now.is_valid

                if was_valid != now_valid:
                    if now_valid:
                        _LOGGER.info(
                            "[E.ON] Licența a redevenit validă — reîncarc"
                        )
                    else:
                        _LOGGER.warning(
                            "[E.ON] Licența a devenit invalidă — reîncarc"
                        )
                    await mgr_now._async_reload_entries()

                # Programează următorul check (dacă serverul a dat valid_until nou)
                _schedule_cache_expiry_check(mgr_now)

            cancel_expiry = async_track_point_in_time(
                hass, _on_cache_expiry, expiry_dt
            )
            hass.data[DOMAIN]["_cancel_cache_expiry"] = cancel_expiry

            _LOGGER.debug(
                "[E.ON] Cache expiry timer programat la %s",
                expiry_dt.isoformat(),
            )

        _schedule_cache_expiry_check(license_mgr)


        # ── Notificare re-enable (dacă a fost dezactivată anterior) ──
        was_disabled = hass.data.pop(f"{DOMAIN}_was_disabled", False)
        if was_disabled:
            await license_mgr.async_notify_event("integration_enabled")

        if not license_mgr.is_valid:
            _LOGGER.warning(
                "[EonRomania] Integrarea nu are licență validă. "
                "Senzorii vor afișa 'Licență necesară'."
            )
        elif license_mgr.is_trial_valid:
            _LOGGER.info(
                "[EonRomania] Perioadă de evaluare — %d zile rămase",
                license_mgr.trial_days_remaining,
            )
        else:
            _LOGGER.info(
                "[EonRomania] Licență activă — tip: %s",
                license_mgr.license_type,
            )
    else:
        _LOGGER.debug(
            "[EonRomania] LicenseManager există deja (entry suplimentară)"
        )

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

    is_account_only = entry.data.get("account_only", False) or not selected_contracts

    if not selected_contracts and not is_account_only:
        _LOGGER.error(
            "Nu există contracte selectate pentru %s (entry_id=%s).",
            DOMAIN, entry.entry_id,
        )
        return False

    _LOGGER.debug(
        "Contracte selectate pentru %s (entry_id=%s): %s, interval=%ss, account_only=%s.",
        DOMAIN, entry.entry_id, selected_contracts, update_interval, is_account_only,
    )

    # Un singur client API partajat (un singur cont, un singur token)
    api_client = EonApiClient(session, username, password)

    # Injectăm token-ul salvat — prioritate: hass.data (proaspăt, de la config_flow),
    # apoi config_entry.data (persistent, pentru restart HA)
    token_store = hass.data.get(DOMAIN_TOKEN_STORE, {})
    stored_token = token_store.pop(username.lower(), None)
    if stored_token:
        api_client.inject_token(stored_token)
        _LOGGER.debug(
            "Token injectat din config_flow (proaspăt) pentru %s (entry_id=%s).",
            username, entry.entry_id,
        )
        # Ștergem notificarea de re-autentificare (dacă există)
        from homeassistant.components import persistent_notification
        for contract in selected_contracts:
            persistent_notification.async_dismiss(
                hass, f"eonromania_reauth_{contract}"
            )
    elif entry.data.get("token_data"):
        api_client.inject_token(entry.data["token_data"])
        _LOGGER.debug(
            "Token injectat din config_entry.data (persistent) pentru %s (entry_id=%s).",
            username, entry.entry_id,
        )
    else:
        _LOGGER.debug(
            "Niciun token salvat disponibil pentru %s (entry_id=%s). Se va face login.",
            username, entry.entry_id,
        )
    # Curățăm store-ul dacă e gol
    if DOMAIN_TOKEN_STORE in hass.data and not hass.data[DOMAIN_TOKEN_STORE]:
        hass.data.pop(DOMAIN_TOKEN_STORE, None)

    # Metadatele contractelor (tip utilitate, colectiv/nu)
    contract_metadata = entry.data.get("contract_metadata", {})

    # Creăm câte un coordinator per contract selectat
    coordinators: dict[str, EonRomaniaCoordinator] = {}

    if is_account_only:
        # Cont fără contracte — un singur coordinator pentru date personale
        coordinator = EonRomaniaCoordinator(
            hass,
            api_client=api_client,
            cod_incasare="__account__",
            update_interval=update_interval,
            is_collective=False,
            config_entry=entry,
            account_only=True,
        )

        try:
            await coordinator.async_config_entry_first_refresh()
        except UpdateFailed as err:
            _LOGGER.error(
                "Prima actualizare eșuată pentru date personale (entry_id=%s): %s",
                entry.entry_id, err,
            )
            return False
        except Exception as err:
            _LOGGER.exception(
                "Eroare neașteptată la date personale (entry_id=%s): %s",
                entry.entry_id, err,
            )
            return False

        coordinators["__account__"] = coordinator
    else:
        for cod in selected_contracts:
            meta = contract_metadata.get(cod, {})
            is_collective = meta.get("is_collective", False)

            coordinator = EonRomaniaCoordinator(
                hass,
                api_client=api_client,
                cod_incasare=cod,
                update_interval=update_interval,
                is_collective=is_collective,
                config_entry=entry,
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
        "%s coordinatoare active din %s contracte selectate (entry_id=%s, account_only=%s).",
        len(coordinators), len(selected_contracts), entry.entry_id, is_account_only,
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
        "[EonRomania] ── async_unload_entry ── entry_id=%s",
        entry.entry_id,
    )

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    _LOGGER.debug("[EonRomania] Unload platforme: %s", "OK" if unload_ok else "EȘUAT")

    if unload_ok:
        # runtime_data se curăță automat de HA la unload — nu mai facem pop manual

        # Verifică dacă mai sunt entry-uri active (BUG-03: folosim config_entries, nu hass.data)
        remaining_entries = hass.config_entries.async_entries(DOMAIN)
        # Excludem entry-ul curent (tocmai descărcat)
        entry_ids_ramase = {e.entry_id for e in remaining_entries if e.entry_id != entry.entry_id}

        _LOGGER.debug(
            "[EonRomania] Entry-uri rămase după unload: %d (%s)",
            len(entry_ids_ramase),
            entry_ids_ramase or "niciuna",
        )

        if not entry_ids_ramase:
            _LOGGER.info("[EonRomania] Ultima entry descărcată — curăț domeniul complet")

            # ── Notificare lifecycle (înainte de cleanup!) ──
            mgr = hass.data[DOMAIN].get(LICENSE_DATA_KEY)
            if mgr and not hass.is_stopping:
                if entry.disabled_by:
                    await mgr.async_notify_event("integration_disabled")
                    # Flag pentru async_setup_entry: la re-enable, trimitem "enabled"
                    hass.data[f"{DOMAIN}_was_disabled"] = True
                else:
                    # Salvăm fingerprint-ul pentru async_remove_entry
                    hass.data.setdefault(f"{DOMAIN}_notify", {}).update({
                        "fingerprint": mgr.fingerprint,
                        "license_key": mgr._data.get("license_key", ""),
                    })
                    _LOGGER.debug(
                        "[EonRomania] Fingerprint salvat pentru async_remove_entry"
                    )

            # Oprește heartbeat-ul periodic
            cancel_hb = hass.data[DOMAIN].pop("_cancel_heartbeat", None)
            if cancel_hb:
                cancel_hb()
                _LOGGER.debug("[EonRomania] Heartbeat periodic oprit")

            # Oprește timer-ul de cache expiry
            cancel_ce = hass.data[DOMAIN].pop("_cancel_cache_expiry", None)
            if cancel_ce:
                cancel_ce()
                _LOGGER.debug("[E.ON] Cache expiry timer oprit")

            # Elimină LicenseManager
            hass.data[DOMAIN].pop(LICENSE_DATA_KEY, None)
            _LOGGER.debug("[EonRomania] LicenseManager eliminat")

            # Elimină domeniul complet
            hass.data.pop(DOMAIN, None)
            _LOGGER.debug("[EonRomania] hass.data[%s] eliminat complet", DOMAIN)

            _LOGGER.info("[EonRomania] Cleanup complet — domeniul %s descărcat", DOMAIN)
    else:
        _LOGGER.error("[EonRomania] Unload EȘUAT pentru entry_id=%s", entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Notifică serverul când integrarea e complet eliminată (ștearsă)."""
    _LOGGER.debug(
        "[EonRomania] ── async_remove_entry ── entry_id=%s",
        entry.entry_id,
    )

    # Verifică dacă mai sunt entry-uri rămase
    remaining = hass.config_entries.async_entries(DOMAIN)
    if not remaining:
        notify_data = hass.data.pop(f"{DOMAIN}_notify", None)
        if notify_data and notify_data.get("fingerprint"):
            await _send_lifecycle_event(
                hass,
                notify_data["fingerprint"],
                notify_data.get("license_key", ""),
                "integration_removed",
            )


async def _send_lifecycle_event(
    hass: HomeAssistant, fingerprint: str, license_key: str, action: str
) -> None:
    """Trimite un eveniment lifecycle direct (fără LicenseManager).

    Folosit în async_remove_entry când LicenseManager nu mai există.
    BUG-06: Folosește sesiunea partajată din HA în loc de aiohttp.ClientSession() nouă.
    """
    import hashlib
    import hmac as hmac_lib
    import json
    import time

    import aiohttp

    from .license import INTEGRATION, LICENSE_API_URL

    timestamp = int(time.time())
    payload = {
        "fingerprint": fingerprint,
        "timestamp": timestamp,
        "action": action,
        "license_key": license_key,
        "integration": INTEGRATION,
    }
    data = {k: v for k, v in payload.items() if k != "hmac"}
    msg = json.dumps(data, sort_keys=True).encode()
    payload["hmac"] = hmac_lib.new(
        fingerprint.encode(), msg, hashlib.sha256
    ).hexdigest()

    try:
        session = async_get_clientsession(hass)
        async with session.post(
            f"{LICENSE_API_URL}/notify",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=10),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "EonRomania-HA-Integration/3.0",
            },
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                if not result.get("success"):
                    _LOGGER.warning(
                        "[EonRomania] Server a refuzat '%s': %s",
                        action, result.get("error"),
                    )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("[EonRomania] Nu s-a putut raporta '%s': %s", action, err)


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
        # BUG-04: Păstrează token_data la migrare (evită re-autentificare cu MFA)
        if old_data.get("token_data"):
            new_data["token_data"] = old_data["token_data"]

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
