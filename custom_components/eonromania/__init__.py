"""Inițializarea integrării E·ON România."""

import json
import asyncio
import logging
from dataclasses import dataclass, field

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, DOMAIN_TOKEN_STORE, LICENSE_DATA_KEY, LICENSE_PURCHASE_URL, PLATFORMS
from .api import EonApiClient
from .coordinator import EonRomaniaCoordinator
from .license import LicenseManager

_LOGGER = logging.getLogger(__name__)

# Stările în care o intrare încă folosește managerul de licențe
_STARI_ACTIVE = (
    ConfigEntryState.LOADED,
    ConfigEntryState.SETUP_IN_PROGRESS,
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.UNLOAD_IN_PROGRESS,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class EonRomaniaRuntimeData:
    """Structură tipizată pentru datele runtime ale integrării."""

    coordinators: dict[str, EonRomaniaCoordinator] = field(default_factory=dict)
    api_client: EonApiClient | None = None
    # Configurația (fără token-ul E·ON) la momentul setup-ului — vezi _async_update_options
    config_signature: str = ""


def _signature(data, options) -> str:
    """Amprenta configurației care contează pentru reload.

    `token_data` e exclus: coordinatorul salvează token-ul E·ON în entry.data
    după fiecare reîmprospătare, iar asta NU trebuie să reîncarce integrarea.
    """
    data = {k: v for k, v in data.items() if k != "token_data"}
    return json.dumps([data, dict(options)], sort_keys=True, default=str)


def _config_signature(entry: ConfigEntry) -> str:
    return _signature(entry.data, entry.options)


async def async_setup(hass: HomeAssistant, config: dict):
    """Configurează integrarea globală E·ON România."""
    return True


def _update_license_notifications(hass: HomeAssistant, mgr: LicenseManager) -> None:
    """Creează sau șterge notificările de expirare licență/trial."""
    if mgr.is_valid:
        ir.async_delete_issue(hass, DOMAIN, "trial_expired")
        ir.async_delete_issue(hass, DOMAIN, "license_expired")
        persistent_notification.async_dismiss(hass, "eonromania_license_expired")
        return

    if mgr.has_license:
        issue_id = "license_expired"
        notif_title = "E.ON România — Licența a expirat"
        notif_message = (
            "Licența pentru integrarea **E.ON România** a expirat.\n\n"
            "Senzorii sunt dezactivați până la reînnoirea licenței.\n\n"
            f"[Reînnoiește licența]({LICENSE_PURCHASE_URL})"
        )
    else:
        issue_id = "trial_expired"
        notif_title = "E.ON România — Licența de probă a expirat"
        notif_message = (
            "Perioada de evaluare gratuită pentru integrarea **E.ON România** s-a încheiat.\n\n"
            "Senzorii sunt dezactivați până la obținerea unei licențe.\n\n"
            f"[Obține o licență acum]({LICENSE_PURCHASE_URL})"
        )

    other_id = "license_expired" if issue_id == "trial_expired" else "trial_expired"
    ir.async_delete_issue(hass, DOMAIN, other_id)

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        is_persistent=True,
        learn_more_url=LICENSE_PURCHASE_URL,
        severity=ir.IssueSeverity.WARNING,
        translation_key=issue_id,
        translation_placeholders={"learn_more_url": LICENSE_PURCHASE_URL},
    )

    persistent_notification.async_create(
        hass,
        notif_message,
        title=notif_title,
        notification_id="eonromania_license_expired",
    )

    _LOGGER.debug("[EON] Notificare expirare creată: %s", issue_id)


def _cleanup_domain(hass: HomeAssistant) -> None:
    """Oprește verificarea licenței și eliberează datele domeniului."""
    domain_data = hass.data.pop(DOMAIN, None) or {}
    cancel_check = domain_data.pop("_cancel_license_check", None)
    if cancel_check:
        cancel_check()


def _schedule_license_check(hass: HomeAssistant, mgr: LicenseManager) -> None:
    """Programează următoarea verificare a licenței (un singur timer, reprogramat mereu).

    Momentul vine de la server: imediat după `valid_until`, sau cu backoff
    (60s → 1h) cât timp serverul nu răspunde. La fiecare verificare: /check
    (+ /validate pentru licențe); dacă validitatea s-a schimbat → notificări
    actualizate + reload.
    """
    if hass.is_stopping:
        return  # la oprire sesiunea HTTP se închide — nu mai verificăm
    domain_data = hass.data.get(DOMAIN)
    if domain_data is None or domain_data.get(LICENSE_DATA_KEY) is not mgr:
        return
    cancel_prev = domain_data.pop("_cancel_license_check", None)
    if cancel_prev:
        cancel_prev()

    delay = mgr.check_interval_seconds + (2 if not mgr.needs_heartbeat else 0)

    async def _async_check() -> None:
        try:
            was_valid = mgr.is_valid
            if mgr.needs_heartbeat:
                await mgr.async_heartbeat()
            now_valid = mgr.is_valid
            if hass.data.get(DOMAIN, {}).get(LICENSE_DATA_KEY) is not mgr:
                return  # integrarea a fost descărcată în timpul verificării
            if was_valid != now_valid:
                if now_valid:
                    _LOGGER.info("[EonRomania] Licența a redevenit validă — reîncarc")
                else:
                    _LOGGER.warning("[EonRomania] Licența a devenit invalidă — reîncarc")
                _update_license_notifications(hass, mgr)
                await mgr._async_reload_entries()
        except Exception:  # noqa: BLE001 — timer-ul nu trebuie să se oprească
            _LOGGER.exception("[EonRomania] Eroare la verificarea periodică a licenței")
        finally:
            _schedule_license_check(hass, mgr)

    @callback
    def _on_timer(_now) -> None:
        domain_now = hass.data.get(DOMAIN, {})
        domain_now.pop("_cancel_license_check", None)
        if hass.is_stopping or domain_now.get(LICENSE_DATA_KEY) is not mgr:
            return
        if not any(
            e.state in _STARI_ACTIVE for e in hass.config_entries.async_entries(DOMAIN)
        ):
            # Ex: intrare dezactivată cât era în „setup retry" (HA nu apelează unload)
            _cleanup_domain(hass)
            return
        # Task de fundal: pornirea/oprirea Home Assistant nu așteaptă
        # niciodată serverul de licențe (issue #329).
        hass.async_create_background_task(
            _async_check(), f"{DOMAIN}_license_check"
        )

    domain_data["_cancel_license_check"] = async_call_later(hass, delay, _on_timer)


async def _async_wait_license_loaded(hass: HomeAssistant) -> None:
    """Așteaptă încărcarea managerului de licențe pornită de altă intrare.

    La pornirea HA intrările aceluiași domeniu se configurează în paralel. Fără
    această așteptare, a doua intrare găsea managerul încă neîncărcat (licență
    „invalidă") → fără date, doar „Licență necesară" și senzorii reali scoși din
    registry, până la un reload manual (issue reteleelectrice#15).
    """
    load = hass.data.get(DOMAIN, {}).get("_license_load")
    if load is not None and not load.done():
        try:
            await asyncio.shield(load)
        except Exception as err:
            raise ConfigEntryNotReady("Managerul de licențe nu s-a putut încărca") from err
    if LICENSE_DATA_KEY not in hass.data.get(DOMAIN, {}):
        raise ConfigEntryNotReady("Managerul de licențe nu s-a putut încărca")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configurează integrarea pentru o anumită intrare (config entry)."""
    _LOGGER.info("Se configurează integrarea %s (entry_id=%s).", DOMAIN, entry.entry_id)

    hass.data.setdefault(DOMAIN, {})

    # ── Inițializare License Manager (o singură instanță per domeniu) ──
    if LICENSE_DATA_KEY not in hass.data[DOMAIN]:
        license_mgr = LicenseManager(hass)
        # Referința se setează ÎNAINTE de async_load(): async_load() poate face
        # await HTTP, iar intrările configurate în paralel nu trebuie să creeze
        # manageri duplicați.
        hass.data[DOMAIN][LICENSE_DATA_KEY] = license_mgr
        # Încărcarea e un task comun: intrările configurate în paralel o așteaptă
        # (vezi _async_wait_license_loaded) în loc să folosească managerul neîncărcat.
        load = hass.async_create_task(license_mgr.async_load(), f"{DOMAIN} license load")
        hass.data[DOMAIN]["_license_load"] = load
        try:
            await load
        except Exception:
            hass.data[DOMAIN].pop(LICENSE_DATA_KEY, None)
            hass.data[DOMAIN].pop("_license_load", None)
            raise
        _LOGGER.debug(
            "[EonRomania] LicenseManager: status=%s, valid=%s, fingerprint=%s...",
            license_mgr.status,
            license_mgr.is_valid,
            license_mgr.fingerprint[:16],
        )
        _schedule_license_check(hass, license_mgr)

        # ── Notificare re-enable (dacă a fost dezactivată anterior) ──
        if hass.data.pop(f"{DOMAIN}_was_disabled", False):
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
        await _async_wait_license_loaded(hass)

    license_mgr = hass.data[DOMAIN][LICENSE_DATA_KEY]
    # La FIECARE setup — după activare, reload-ul intrărilor șterge notificările
    # chiar dacă managerul de licențe rămâne același (mai multe conturi).
    _update_license_notifications(hass, license_mgr)

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
    first_error: Exception | None = None

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

        # E·ON indisponibil → ConfigEntryNotReady (HA reîncearcă);
        # sesiune expirată / cod 2FA necesar → ConfigEntryAuthFailed (reautentificare)
        await coordinator.async_config_entry_first_refresh()

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
            except ConfigEntryNotReady as err:
                # Continuăm cu restul contractelor — nu oprim totul pentru unul.
                # (ConfigEntryAuthFailed — sesiune / 2FA — se propagă: e același
                # client pentru toate contractele, iar HA pornește reautentificarea.)
                _LOGGER.error(
                    "Prima actualizare eșuată (entry_id=%s, contract=%s): %s",
                    entry.entry_id, cod, err,
                )
                first_error = first_error or err
                continue

            coordinators[cod] = coordinator

    if not coordinators:
        # E·ON nu răspunde: HA reîncearcă automat (înainte: return False =
        # integrare picată până la reload manual)
        raise ConfigEntryNotReady(
            f"Niciun contract E·ON nu a putut fi actualizat: {first_error}"
        ) from first_error

    _LOGGER.info(
        "%s coordinatoare active din %s contracte selectate (entry_id=%s, account_only=%s).",
        len(coordinators), len(selected_contracts), entry.entry_id, is_account_only,
    )

    # Salvăm datele runtime
    entry.runtime_data = EonRomaniaRuntimeData(
        coordinators=coordinators,
        api_client=api_client,
        config_signature=_config_signature(entry),
    )
    # Autentificare reușită → notificările de reautentificare nu mai sunt valabile
    for cod in coordinators:
        persistent_notification.async_dismiss(hass, f"eonromania_reauth_{cod}")

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
    """Reîncarcă integrarea când configurația s-a schimbat efectiv.

    Listener-ul e apelat la ORICE actualizare a intrării — inclusiv când
    coordinatorul salvează token-ul E·ON după o reîmprospătare. Acelea sunt
    ignorate (înainte: fiecare reîmprospătare de token reîncărca integrarea).
    """
    runtime = getattr(entry, "runtime_data", None)
    if runtime is not None and runtime.config_signature == _config_signature(entry):
        return
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
        # Doar intrările ACTIVE contează (cele dezactivate / descărcate nu folosesc
        # managerul de licențe — altfel acesta și timer-ul nu s-ar opri niciodată).
        entry_ids_ramase = {
            e.entry_id
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id and e.state in _STARI_ACTIVE
        }

        _LOGGER.debug(
            "[EonRomania] Entry-uri active rămase după unload: %d (%s)",
            len(entry_ids_ramase),
            entry_ids_ramase or "niciuna",
        )

        if not entry_ids_ramase:
            _LOGGER.info("[EonRomania] Ultima entry descărcată — curăț domeniul complet")

            # ── Notificare lifecycle (înainte de cleanup!) ──
            mgr = hass.data.get(DOMAIN, {}).get(LICENSE_DATA_KEY)
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

            _cleanup_domain(hass)
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
        # O intrare ștearsă cât era în „setup retry" nu trece prin async_unload_entry
        if DOMAIN in hass.data:
            mgr = hass.data[DOMAIN].get(LICENSE_DATA_KEY)
            if mgr is not None and f"{DOMAIN}_notify" not in hass.data:
                hass.data[f"{DOMAIN}_notify"] = {
                    "fingerprint": mgr.fingerprint,
                    "license_key": mgr._data.get("license_key", ""),
                }
            _cleanup_domain(hass)
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

    from .license import INTEGRATION, LICENSE_API_URL, USER_AGENT

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
                "User-Agent": USER_AGENT,
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
