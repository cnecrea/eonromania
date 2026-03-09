"""
ConfigFlow și OptionsFlow pentru integrarea E·ON România.

Utilizatorul introduce email + parolă, apoi selectează contractele dorite.
Contractele se descoperă automat prin account-contracts/list.
Suportă MFA (Two-Factor Authentication) — dacă e activ, se cere codul OTP.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL
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
                # Login reușit fără MFA — obține contractele
                contracts = await _fetch_contracts_after_login(self._api)
                if contracts:
                    self._contracts_raw = contracts
                    return await self.async_step_select_contracts()
                errors["base"] = "no_data"
                _LOGGER.warning(
                    "Autentificare reușită dar nu s-au găsit contracte (utilizator=%s).",
                    self._username,
                )
            elif self._api.mfa_required:
                # MFA necesar — salvăm tipul și destinatarul ACUM (înainte de async_mfa_complete care le șterge)
                mfa_info = self._api.mfa_data or {}
                self._mfa_type = mfa_info.get("type", "EMAIL")
                if self._mfa_type == "EMAIL":
                    self._mfa_recipient_display = mask_email(self._username)
                else:
                    self._mfa_recipient_display = mfa_info.get("recipient", "—")
                _LOGGER.debug(
                    "MFA necesar pentru %s. Tip=%s, Destinatar=%s.",
                    self._username,
                    self._mfa_type,
                    self._mfa_recipient_display,
                )
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
                # MFA completat — obține contractele
                contracts = await _fetch_contracts_after_login(self._api)
                if contracts:
                    self._contracts_raw = contracts
                    return await self.async_step_select_contracts()
                errors["base"] = "no_data"
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
    """OptionsFlow — modificare setări + selecție contracte."""

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._update_interval: int = DEFAULT_UPDATE_INTERVAL
        self._contracts_raw: list[dict] = []
        self._api: EonApiClient | None = None
        # MFA state — salvat la intrarea în pasul MFA, persistent după async_mfa_complete
        self._mfa_type: str = ""
        self._mfa_recipient_display: str = ""

    async def async_step_init(
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

            if await self._api.async_login():
                contracts = await _fetch_contracts_after_login(self._api)
                if contracts:
                    self._contracts_raw = contracts
                    self._username = username
                    self._password = password
                    self._update_interval = update_interval
                    return await self.async_step_select_contracts()
                errors["base"] = "no_data"
            elif self._api.mfa_required:
                # MFA necesar — salvăm credențialele + info MFA ACUM
                self._username = username
                self._password = password
                self._update_interval = update_interval
                mfa_info = self._api.mfa_data or {}
                self._mfa_type = mfa_info.get("type", "EMAIL")
                if self._mfa_type == "EMAIL":
                    self._mfa_recipient_display = mask_email(username)
                else:
                    self._mfa_recipient_display = mfa_info.get("recipient", "—")
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
            step_id="init", data_schema=schema, errors=errors
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
                contracts = await _fetch_contracts_after_login(self._api)
                if contracts:
                    self._contracts_raw = contracts
                    return await self.async_step_select_contracts()
                errors["base"] = "no_data"
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

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        "username": self._username,
                        "password": self._password,
                        "update_interval": self._update_interval,
                        "select_all": select_all,
                        "selected_contracts": final_selection,
                        "contract_metadata": build_contract_metadata(self._contracts_raw),
                    },
                )

                await self.hass.config_entries.async_reload(
                    self.config_entry.entry_id
                )

                return self.async_create_entry(data={})

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
