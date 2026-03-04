"""
ConfigFlow și OptionsFlow pentru integrarea E·ON România.

Utilizatorul introduce email + parolă, apoi selectează contractele dorite.
Contractele se descoperă automat prin account-contracts/list.
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
    build_contract_options,
    resolve_selection,
)

_LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------------
# ConfigFlow
# ------------------------------------------------------------------

class EonRomaniaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ConfigFlow — autentificare + selecție contracte."""

    VERSION = 3

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._update_interval: int = DEFAULT_UPDATE_INTERVAL
        self._contracts_raw: list[dict] = []

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
            api = EonApiClient(session, self._username, self._password)

            if await api.async_login():
                contracts = await api.async_fetch_contracts_list()

                if contracts and isinstance(contracts, list) and len(contracts) > 0:
                    self._contracts_raw = contracts
                    return await self.async_step_select_contracts()

                errors["base"] = "no_data"
                _LOGGER.warning(
                    "Autentificare reușită dar nu s-au găsit contracte (utilizator=%s).",
                    self._username,
                )
            else:
                errors["base"] = "auth_failed"

        schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Optional(
                    "update_interval", default=DEFAULT_UPDATE_INTERVAL
                ): int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
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
            api = EonApiClient(session, username, password)

            if await api.async_login():
                contracts = await api.async_fetch_contracts_list()

                if contracts and isinstance(contracts, list) and len(contracts) > 0:
                    self._contracts_raw = contracts
                    self._username = username
                    self._password = password
                    self._update_interval = update_interval
                    return await self.async_step_select_contracts()

                errors["base"] = "no_data"
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
                ): int,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
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
