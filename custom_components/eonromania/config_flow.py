"""
ConfigFlow și OptionsFlow pentru integrarea E·ON România.

Utilizatorul introduce email + parolă, apoi selectează contractele dorite.
Contractele se descoperă automat prin account-contracts/list.
Suportă MFA (Two-Factor Authentication) — dacă e activ, se cere codul OTP.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, DOMAIN_TOKEN_STORE, CONF_LICENSE_KEY, LICENSE_DATA_KEY, LICENSE_PURCHASE_URL
from . import _signature
from .api import EonApiClient
from .helpers import (
    build_contract_metadata,
    build_contract_options,
    mask_email,
    resolve_selection,
)

_LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helper comun: fetch contracte după autentificare reușită
# ------------------------------------------------------------------

async def _fetch_contracts_after_login(api: EonApiClient) -> list[dict] | None:
    """Obține lista de contracte după autentificare reușită.

    Returnează lista de contracte sau None dacă nu s-au găsit.
    """
    contracts = await api.async_fetch_contracts_list()
    if contracts and isinstance(contracts, list) and len(contracts) > 0:
        return contracts
    return None


def _store_token(hass, username: str, api: EonApiClient) -> None:
    """Salvează token-ul API în hass.data pentru a fi preluat de __init__.py.

    Token-ul este salvat per username (pot exista mai multe conturi).
    """
    token_data = api.export_token_data()
    if token_data is None:
        return
    store = hass.data.setdefault(DOMAIN_TOKEN_STORE, {})
    store[username.lower()] = token_data
    _LOGGER.debug(
        "Token salvat în hass.data pentru %s (access=%s...).",
        username,
        token_data["access_token"][:8] if token_data.get("access_token") else "None",
    )


def _update_and_reload(
    hass, entry: config_entries.ConfigEntry, data: dict[str, Any], **kwargs: Any
) -> None:
    """Salvează intrarea și o reîncarcă o singură dată.

    Listener-ul de update reîncarcă singur intrarea când s-a schimbat
    configurația (fără token). Altfel — ex: doar un token nou după 2FA, sau
    intrarea nu rulează (setup eșuat) — reîncărcăm aici, ca noul token să fie
    folosit. (Înainte: update + reload explicit = două reload-uri.)
    Decizia se ia ÎNAINTE de update: listener-ul pornește imediat.
    """
    runtime = getattr(entry, "runtime_data", None)
    listener_reloads = (
        entry.state is ConfigEntryState.LOADED
        and runtime is not None
        and getattr(runtime, "config_signature", None) != _signature(data, entry.options)
    )
    hass.config_entries.async_update_entry(entry, data=data, **kwargs)
    if not listener_reloads:
        hass.config_entries.async_schedule_reload(entry.entry_id)


_ETICHETE_TIP_LICENTA = {
    # Tipurile emise de WebAPI (LICENSE_DURATION)
    "perpetual": ("perpetuă", "perpetual"),
    "annual": ("anuală", "annual"),
    "semi_annual": ("semestrială", "semi-annual"),
    "monthly": ("lunară", "monthly"),
}


def _eticheta_tip_licenta(tip: str | None, is_ro: bool) -> str:
    """Eticheta afișată pentru tipul de licență primit de la server."""
    if not tip:
        return "necunoscut" if is_ro else "unknown"
    ro, en = _ETICHETE_TIP_LICENTA.get(tip, (tip, tip))
    return ro if is_ro else en


# ------------------------------------------------------------------
# ConfigFlow
# ------------------------------------------------------------------

class EonRomaniaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ConfigFlow — autentificare + MFA (opțional) + selecție contracte."""

    VERSION = 3

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._update_interval: int = DEFAULT_UPDATE_INTERVAL
        self._contracts_raw: list[dict] = []
        self._api: EonApiClient | None = None
        # MFA state — salvat la intrarea în pasul MFA, persistent după async_mfa_complete
        self._mfa_type: str = ""
        self._mfa_alt_type: str = ""
        self._mfa_recipient_display: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pasul 1: Autentificare."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input["username"]
            self._password = user_input["password"]
            self._update_interval = user_input.get(
                "update_interval", DEFAULT_UPDATE_INTERVAL
            )

            await self.async_set_unique_id(self._username.lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            self._api = EonApiClient(session, self._username, self._password)

            if await self._api.async_login():
                # Login reușit fără MFA — salvăm token-ul și obținem contractele
                _store_token(self.hass, self._username, self._api)
                contracts = await _fetch_contracts_after_login(self._api)
                if contracts:
                    self._contracts_raw = contracts
                    return await self.async_step_select_contracts()
                # Nu există contracte — creăm entry fără contracte (doar date personale)
                _LOGGER.info(
                    "Niciun contract găsit pentru %s. Se creează entry cu date personale.",
                    self._username,
                )
                return self._create_entry_no_contracts()
            elif self._api.mfa_required:
                # MFA necesar — salvăm tipul și destinatarul ACUM (înainte de async_mfa_complete care le șterge)
                mfa_info = self._api.mfa_data or {}
                self._mfa_type = mfa_info.get("type", "EMAIL")
                self._mfa_alt_type = mfa_info.get("alternative_type", "")
                if self._mfa_type == "EMAIL":
                    self._mfa_recipient_display = mask_email(self._username)
                else:
                    self._mfa_recipient_display = mfa_info.get("recipient", "—")
                _LOGGER.debug(
                    "MFA necesar pentru %s. Tip=%s, Alt=%s, Destinatar=%s.",
                    self._username,
                    self._mfa_type,
                    self._mfa_alt_type,
                    self._mfa_recipient_display,
                )
                # Dacă există canal alternativ (telefon setat) → lasă userul să aleagă
                if self._mfa_alt_type and self._mfa_alt_type != self._mfa_type:
                    return await self.async_step_mfa_method()
                return await self.async_step_mfa()
            else:
                errors["base"] = "auth_failed"

        schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Optional(
                    "update_interval", default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(int, vol.Range(min=21600)),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_mfa_method(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pasul 1a: Selectare canal MFA (EMAIL sau SMS).

        Afișat doar dacă contul are și telefon setat (alternative_type disponibil).
        Dacă userul alege canalul alternativ, retransmitem codul pe noul canal.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            chosen = user_input.get("mfa_method", self._mfa_type)

            if chosen != self._mfa_type:
                # Userul a ales canalul alternativ → retransmite codul pe noul canal
                _LOGGER.debug(
                    "MFA: Userul a ales canalul alternativ %s (implicit era %s). Retransmit codul.",
                    chosen,
                    self._mfa_type,
                )
                if self._api and await self._api.async_mfa_resend(chosen):
                    self._mfa_type = chosen
                    # Actualizăm recipient-ul din mfa_data (resend poate returna noul recipient)
                    mfa_info = self._api.mfa_data or {}
                    if chosen == "EMAIL":
                        self._mfa_recipient_display = mask_email(self._username)
                    else:
                        self._mfa_recipient_display = mfa_info.get("recipient", "—")
                    _LOGGER.debug(
                        "MFA: Cod retransmis pe %s la %s.",
                        chosen,
                        self._mfa_recipient_display,
                    )
                else:
                    errors["base"] = "mfa_resend_failed"
                    _LOGGER.warning("MFA: Retransmitere cod pe %s eșuată.", chosen)

            if not errors:
                return await self.async_step_mfa()

        # Construiește opțiunile de selecție
        # NOTĂ: mfa_data['recipient'] conține destinatarul metodei IMPLICITE (EMAIL → email mascat).
        # Numărul de telefon NU e disponibil în răspunsul de login — apare abia după resend pe SMS.
        # De aceea, pentru metoda alternativă afișăm doar tipul canalului, fără adresă.
        mfa_info = (self._api.mfa_data or {}) if self._api else {}

        def _build_mfa_label(method_type: str, is_current: bool) -> str:
            """Construiește label-ul pentru o metodă MFA.

            is_current=True: metoda pe care s-a trimis deja codul (avem recipient-ul).
            is_current=False: metoda alternativă (NU avem recipient-ul real).
            """
            if method_type == "EMAIL":
                return f"Email ({mask_email(self._username)})"
            # SMS
            if is_current:
                # Codul a fost deja trimis pe SMS → recipient conține telefonul
                return f"SMS ({mfa_info.get('recipient', 'telefon')})"
            # Alternativă SMS — nu avem telefonul încă
            return "SMS (telefon)"

        current_label = _build_mfa_label(self._mfa_type, is_current=True)
        alt_label = _build_mfa_label(self._mfa_alt_type, is_current=False)

        options_list = [
            {"value": self._mfa_type, "label": current_label},
            {"value": self._mfa_alt_type, "label": alt_label},
        ]

        schema = vol.Schema(
            {
                vol.Required("mfa_method", default=self._mfa_type): SelectSelector(
                    SelectSelectorConfig(
                        options=options_list,
                        multiple=False,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="mfa_method",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pasul 1b: Introducere cod MFA (Two-Factor Authentication)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input.get("code", "").strip()

            if not code:
                errors["base"] = "mfa_invalid_code"
            elif self._api and await self._api.async_mfa_complete(code):
                if self.source == SOURCE_REAUTH:
                    return self._async_finish_reauth()
                # MFA completat — salvăm token-ul și obținem contractele
                _store_token(self.hass, self._username, self._api)
                contracts = await _fetch_contracts_after_login(self._api)
                if contracts:
                    self._contracts_raw = contracts
                    return await self.async_step_select_contracts()
                # Nu există contracte — creăm entry fără contracte (doar date personale)
                _LOGGER.info(
                    "Niciun contract găsit pentru %s (după MFA). Se creează entry cu date personale.",
                    self._username,
                )
                return self._create_entry_no_contracts()
            else:
                errors["base"] = "mfa_failed"

        # Placeholders din variabilele de instanță (setate la intrarea în MFA, persistente)
        placeholders = {
            "mfa_type": "email" if self._mfa_type == "EMAIL" else "SMS",
            "mfa_recipient": self._mfa_recipient_display or "—",
        }

        schema = vol.Schema(
            {
                vol.Required("code"): str,
            }
        )

        return self.async_show_form(
            step_id="mfa",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_select_contracts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pasul 2: Selectare contracte din listă."""
        errors: dict[str, str] = {}

        if user_input is not None:
            select_all = user_input.get("select_all", False)
            selected = user_input.get("selected_contracts", [])

            if not select_all and not selected:
                errors["base"] = "no_contract_selected"
            else:
                final_selection = resolve_selection(
                    select_all, selected, self._contracts_raw
                )

                return self.async_create_entry(
                    title=f"E·ON România ({self._username})",
                    data={
                        "username": self._username,
                        "password": self._password,
                        "update_interval": self._update_interval,
                        "select_all": select_all,
                        "selected_contracts": final_selection,
                        "contract_metadata": build_contract_metadata(self._contracts_raw),
                    },
                )

        contract_options = build_contract_options(self._contracts_raw)

        schema = vol.Schema(
            {
                vol.Optional("select_all", default=False): bool,
                vol.Required(
                    "selected_contracts", default=[]
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=contract_options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_contracts",
            data_schema=schema,
            errors=errors,
        )

    # ─────────────────────────────────────────
    # Reautentificare (sesiune expirată / cod 2FA / parolă schimbată)
    # ─────────────────────────────────────────
    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Pornit de Home Assistant când integrarea nu se mai poate autentifica."""
        self._username = entry_data["username"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Parola (precompletată) → login → cod 2FA dacă e cerut."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            self._password = user_input["password"]
            session = async_get_clientsession(self.hass)
            self._api = EonApiClient(session, self._username, self._password)

            if await self._api.async_login():
                return self._async_finish_reauth()
            if self._api.mfa_required:
                mfa_info = self._api.mfa_data or {}
                self._mfa_type = mfa_info.get("type", "EMAIL")
                self._mfa_alt_type = mfa_info.get("alternative_type", "")
                if self._mfa_type == "EMAIL":
                    self._mfa_recipient_display = mask_email(self._username)
                else:
                    self._mfa_recipient_display = mfa_info.get("recipient", "—")
                if self._mfa_alt_type and self._mfa_alt_type != self._mfa_type:
                    return await self.async_step_mfa_method()
                return await self.async_step_mfa()
            errors["base"] = "auth_failed"

        schema = vol.Schema(
            {
                vol.Required(
                    "password", default=entry.data.get("password", "")
                ): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={"username": mask_email(self._username)},
        )

    def _async_finish_reauth(self) -> ConfigFlowResult:
        """Salvează parola + token-ul nou și reîncarcă intrarea."""
        entry = self._get_reauth_entry()
        _update_and_reload(
            self.hass,
            entry,
            {
                **entry.data,
                "password": self._password,
                "token_data": self._api.export_token_data() if self._api else None,
            },
        )
        return self.async_abort(reason="reauth_successful")

    def _create_entry_no_contracts(self) -> ConfigFlowResult:
        """Creează entry fără contracte (doar senzor date personale).

        Folosit când contul e valid dar nu are niciun contract asociat.
        """
        return self.async_create_entry(
            title=f"E·ON {self._username}",
            data={
                "username": self._username,
                "password": self._password,
                "update_interval": self._update_interval,
                "select_all": False,
                "selected_contracts": [],
                "contract_metadata": {},
                "token_data": self._api.export_token_data() if self._api else None,
                "account_only": True,  # Flag: cont fără contracte
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EonRomaniaOptionsFlow:
        return EonRomaniaOptionsFlow()


# ------------------------------------------------------------------
# OptionsFlow
# ------------------------------------------------------------------

class EonRomaniaOptionsFlow(config_entries.OptionsFlow):
    """OptionsFlow — modificare setări + selecție contracte + licență."""

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._update_interval: int = DEFAULT_UPDATE_INTERVAL
        self._contracts_raw: list[dict] = []
        self._api: EonApiClient | None = None
        # MFA state — salvat la intrarea în pasul MFA, persistent după async_mfa_complete
        self._mfa_type: str = ""
        self._mfa_alt_type: str = ""
        self._mfa_recipient_display: str = ""

    def _save_entry(self, data: dict[str, Any]) -> None:
        """Salvează noua configurație (titlu + unique_id după cont) și reîncarcă o dată."""
        username = data.get("username", "")
        title = (
            f"E·ON {username}" if data.get("account_only")
            else f"E·ON România ({username})"
        )
        _update_and_reload(
            self.hass,
            self.config_entry,
            data,
            title=title,
            unique_id=username.lower(),
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Afișează meniul principal cu opțiunile disponibile."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "settings",
                "licenta",
            ],
        )

    async def async_step_licenta(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Formular pentru activarea / vizualizarea licenței EonRomania."""
        from .license import LicenseManager

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        is_ro = self.hass.config.language == "ro"

        # Obține LicenseManager
        mgr: LicenseManager | None = self.hass.data.get(DOMAIN, {}).get(
            LICENSE_DATA_KEY
        )
        if mgr is None:
            mgr = LicenseManager(self.hass)
            await mgr.async_load()

        # Informații pentru descrierea formularului
        server_status = mgr.status  # 'licensed', 'trial', 'expired', 'unlicensed'

        if server_status == "licensed":
            from datetime import datetime

            tip = _eticheta_tip_licenta(mgr.license_type, True)
            status_lines = [f"✅ Licență activă ({tip})"]

            if mgr.license_key_masked:
                status_lines[0] += f" — {mgr.license_key_masked}"

            # Data activării
            if mgr.activated_at:
                act_date = datetime.fromtimestamp(
                    mgr.activated_at
                ).strftime("%d.%m.%Y %H:%M")
                status_lines.append(f"Activată la: {act_date}")

            # Data expirării
            if mgr.license_expires_at:
                exp_date = datetime.fromtimestamp(
                    mgr.license_expires_at
                ).strftime("%d.%m.%Y %H:%M")
                status_lines.append(f"📅 Expiră la: {exp_date}")
            elif mgr.license_type == "perpetual":
                status_lines.append("Valabilitate: nelimitată (perpetuă)")

            description_placeholders["license_status"] = "\n".join(
                status_lines
            )

        elif server_status == "trial":
            days = mgr.trial_days_remaining
            if is_ro:
                status_lines = [
                    f"⏳ Evaluare — {days} zile rămase",
                    "",
                    f"🛒 Obține licență: {LICENSE_PURCHASE_URL}",
                ]
            else:
                status_lines = [
                    f"⏳ Trial — {days} days remaining",
                    "",
                    f"🛒 Get a license: {LICENSE_PURCHASE_URL}",
                ]
            description_placeholders["license_status"] = "\n".join(status_lines)
        elif server_status == "expired":
            from datetime import datetime

            status_lines = ["❌ Licență expirată"]

            if mgr.activated_at:
                act_date = datetime.fromtimestamp(
                    mgr.activated_at
                ).strftime("%d.%m.%Y")
                status_lines.append(f"Activată la: {act_date}")
            if mgr.license_expires_at:
                exp_date = datetime.fromtimestamp(
                    mgr.license_expires_at
                ).strftime("%d.%m.%Y")
                status_lines.append(f"Expirată la: {exp_date}")

            status_lines.append("")
            if is_ro:
                status_lines.append(
                    f"🛒 Obține licență: {LICENSE_PURCHASE_URL}"
                )
            else:
                status_lines.append(
                    f"🛒 Get a license: {LICENSE_PURCHASE_URL}"
                )

            description_placeholders["license_status"] = "\n".join(
                status_lines
            )
        else:
            if is_ro:
                status_lines = [
                    "❌ Fără licență — funcționalitate blocată",
                    "",
                    f"🛒 Obține licență: {LICENSE_PURCHASE_URL}",
                ]
            else:
                status_lines = [
                    "❌ No license — functionality blocked",
                    "",
                    f"🛒 Get a license: {LICENSE_PURCHASE_URL}",
                ]
            description_placeholders["license_status"] = "\n".join(status_lines)

        if user_input is not None:
            cheie = user_input.get(CONF_LICENSE_KEY, "").strip()

            if not cheie:
                errors["base"] = "license_key_empty"
            elif len(cheie) < 10:
                errors["base"] = "license_key_invalid"
            else:
                # Activare prin API
                result = await mgr.async_activate(cheie)

                if result.get("success"):
                    # Notificare de succes
                    from homeassistant.components import (
                        persistent_notification,
                    )

                    tip_ro = _eticheta_tip_licenta(mgr.license_type, True)

                    persistent_notification.async_create(
                        self.hass,
                        f"Licența E·ON România a fost activată cu succes! "
                        f"Tip: {tip_ro}.",
                        title="Licență activată",
                        notification_id="eonromania_license_activated",
                    )
                    return self.async_create_entry(
                        data=self.config_entry.options
                    )

                # Mapare erori API (codurile WebAPI /activate + erorile locale)
                api_error = result.get("error", "unknown_error")
                error_map = {
                    "invalid_key": "license_key_invalid",
                    "already_used": "license_already_used",
                    "expired_key": "license_key_expired",
                    "fingerprint_mismatch": "license_fingerprint_mismatch",
                    "network_error": "license_network_error",
                    "http_502": "license_network_error",
                    "http_503": "license_network_error",  # server temporar ocupat
                    "http_504": "license_network_error",
                }
                errors["base"] = error_map.get(api_error, "license_server_error")

        schema = vol.Schema(
            {
                vol.Optional(CONF_LICENSE_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        suffix="EONL-XXXX-XXXX-XXXX-XXXX",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="licenta",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pasul 1: Modificare credențiale."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]
            update_interval = user_input.get(
                "update_interval", DEFAULT_UPDATE_INTERVAL
            )

            session = async_get_clientsession(self.hass)
            self._api = EonApiClient(session, username, password)

            conflict = any(
                e.entry_id != self.config_entry.entry_id
                and e.unique_id == username.lower()
                for e in self.hass.config_entries.async_entries(DOMAIN)
            )
            if conflict:
                # Contul e deja configurat într-o altă intrare
                errors["base"] = "already_configured"
            elif await self._api.async_login():
                _store_token(self.hass, username, self._api)
                contracts = await _fetch_contracts_after_login(self._api)
                if contracts:
                    self._contracts_raw = contracts
                    self._username = username
                    self._password = password
                    self._update_interval = update_interval
                    return await self.async_step_select_contracts()
                # Nu există contracte — salvăm ca account_only
                _LOGGER.info(
                    "Niciun contract găsit (options) pentru %s. Se salvează ca account_only.",
                    username,
                )
                new_data = dict(self.config_entry.data)
                new_data.update({
                    "username": username,
                    "password": password,
                    "update_interval": update_interval,
                    "selected_contracts": [],
                    "contract_metadata": {},
                    "account_only": True,
                    "token_data": self._api.export_token_data() if self._api else None,
                })
                self._save_entry(new_data)
                return self.async_create_entry(data=dict(self.config_entry.options))
            elif self._api.mfa_required:
                # MFA necesar — salvăm credențialele + info MFA ACUM
                self._username = username
                self._password = password
                self._update_interval = update_interval
                mfa_info = self._api.mfa_data or {}
                self._mfa_type = mfa_info.get("type", "EMAIL")
                self._mfa_alt_type = mfa_info.get("alternative_type", "")
                if self._mfa_type == "EMAIL":
                    self._mfa_recipient_display = mask_email(username)
                else:
                    self._mfa_recipient_display = mfa_info.get("recipient", "—")
                # Dacă există canal alternativ (telefon setat) → lasă userul să aleagă
                if self._mfa_alt_type and self._mfa_alt_type != self._mfa_type:
                    return await self.async_step_mfa_method()
                return await self.async_step_mfa()
            else:
                errors["base"] = "auth_failed"

        current = self.config_entry.data

        schema = vol.Schema(
            {
                vol.Required(
                    "username", default=current.get("username", "")
                ): str,
                vol.Required(
                    "password", default=current.get("password", "")
                ): str,
                vol.Required(
                    "update_interval",
                    default=current.get("update_interval", DEFAULT_UPDATE_INTERVAL),
                ): vol.All(int, vol.Range(min=21600)),
            }
        )

        return self.async_show_form(
            step_id="settings", data_schema=schema, errors=errors
        )

    async def async_step_mfa_method(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pasul 1a: Selectare canal MFA (EMAIL sau SMS).

        Afișat doar dacă contul are și telefon setat (alternative_type disponibil).
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            chosen = user_input.get("mfa_method", self._mfa_type)

            if chosen != self._mfa_type:
                _LOGGER.debug(
                    "MFA: Userul a ales canalul alternativ %s (implicit era %s). Retransmit codul.",
                    chosen,
                    self._mfa_type,
                )
                if self._api and await self._api.async_mfa_resend(chosen):
                    self._mfa_type = chosen
                    mfa_info = self._api.mfa_data or {}
                    if chosen == "EMAIL":
                        self._mfa_recipient_display = mask_email(self._username)
                    else:
                        self._mfa_recipient_display = mfa_info.get("recipient", "—")
                else:
                    errors["base"] = "mfa_resend_failed"

            if not errors:
                return await self.async_step_mfa()

        # NOTĂ: mfa_data['recipient'] conține destinatarul metodei IMPLICITE.
        # Telefonul NU e disponibil în răspunsul de login — apare abia după resend pe SMS.
        mfa_info = (self._api.mfa_data or {}) if self._api else {}

        def _build_mfa_label(method_type: str, is_current: bool) -> str:
            if method_type == "EMAIL":
                return f"Email ({mask_email(self._username)})"
            if is_current:
                return f"SMS ({mfa_info.get('recipient', 'telefon')})"
            return "SMS (telefon)"

        current_label = _build_mfa_label(self._mfa_type, is_current=True)
        alt_label = _build_mfa_label(self._mfa_alt_type, is_current=False)

        options_list = [
            {"value": self._mfa_type, "label": current_label},
            {"value": self._mfa_alt_type, "label": alt_label},
        ]

        schema = vol.Schema(
            {
                vol.Required("mfa_method", default=self._mfa_type): SelectSelector(
                    SelectSelectorConfig(
                        options=options_list,
                        multiple=False,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="mfa_method",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pasul 1b: Introducere cod MFA."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input.get("code", "").strip()

            if not code:
                errors["base"] = "mfa_invalid_code"
            elif self._api and await self._api.async_mfa_complete(code):
                _store_token(self.hass, self._username, self._api)
                contracts = await _fetch_contracts_after_login(self._api)
                if contracts:
                    self._contracts_raw = contracts
                    return await self.async_step_select_contracts()
                # Nu există contracte — salvăm ca account_only
                _LOGGER.info(
                    "Niciun contract găsit (options MFA) pentru %s. Se salvează ca account_only.",
                    self._username,
                )
                new_data = dict(self.config_entry.data)
                new_data.update({
                    "username": self._username,
                    "password": self._password,
                    "update_interval": self._update_interval,
                    "selected_contracts": [],
                    "contract_metadata": {},
                    "account_only": True,
                    "token_data": self._api.export_token_data() if self._api else None,
                })
                self._save_entry(new_data)
                return self.async_create_entry(data=dict(self.config_entry.options))
            else:
                errors["base"] = "mfa_failed"

        # Placeholders din variabilele de instanță (setate la intrarea în MFA, persistente)
        placeholders = {
            "mfa_type": "email" if self._mfa_type == "EMAIL" else "SMS",
            "mfa_recipient": self._mfa_recipient_display or "—",
        }

        schema = vol.Schema(
            {
                vol.Required("code"): str,
            }
        )

        return self.async_show_form(
            step_id="mfa",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_select_contracts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pasul 2: Modificare selecție contracte."""
        errors: dict[str, str] = {}

        if user_input is not None:
            select_all = user_input.get("select_all", False)
            selected = user_input.get("selected_contracts", [])

            if not select_all and not selected:
                errors["base"] = "no_contract_selected"
            else:
                final_selection = resolve_selection(
                    select_all, selected, self._contracts_raw
                )

                self._save_entry(
                    {
                        "username": self._username,
                        "password": self._password,
                        "update_interval": self._update_interval,
                        "select_all": select_all,
                        "selected_contracts": final_selection,
                        "contract_metadata": build_contract_metadata(self._contracts_raw),
                        "token_data": self._api.export_token_data() if self._api else None,
                    }
                )

                return self.async_create_entry(data=dict(self.config_entry.options))

        current = self.config_entry.data

        schema = vol.Schema(
            {
                vol.Optional(
                    "select_all",
                    default=current.get("select_all", False),
                ): bool,
                vol.Required(
                    "selected_contracts",
                    default=current.get("selected_contracts", []),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=build_contract_options(self._contracts_raw),
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_contracts",
            data_schema=schema,
            errors=errors,
        )
