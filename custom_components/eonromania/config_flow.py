"""ConfigFlow și OptionsFlow pentru integrarea E·ON România."""

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL
from .api import EonApiClient

_LOGGER = logging.getLogger(__name__)


class EonRomaniaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestionarea ConfigFlow pentru integrarea E·ON România."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Pasul inițial pentru configurare."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]
            cod_incasare = user_input["cod_incasare"]
            update_interval = user_input.get("update_interval", DEFAULT_UPDATE_INTERVAL)

            # Validăm și ajustăm cod_incasare la 12 caractere (dacă e necesar)
            try:
                if len(cod_incasare) < 12:
                    cod_incasare = cod_incasare.zfill(12)
                elif len(cod_incasare) > 12:
                    raise ValueError("Codul de încasare este prea lung.")
            except ValueError:
                errors["cod_incasare"] = "invalid_cod_incasare"
                _LOGGER.warning(
                    "Cod de încasare invalid (lungime nepermisă). contract=%s",
                    cod_incasare,
                )

            if not errors:
                # Testăm autentificarea (NU logăm parola)
                session = async_get_clientsession(self.hass)
                api_client = EonApiClient(session, username, password)

                try:
                    success = await api_client.async_login()
                except Exception as err:
                    _LOGGER.exception(
                        "Eroare neașteptată la testarea autentificării (utilizator=%s, contract=%s): %s",
                        username,
                        cod_incasare,
                        err,
                    )
                    success = False

                if success:
                    _LOGGER.info(
                        "Autentificare reușită. Se creează intrarea (utilizator=%s, contract=%s).",
                        username,
                        cod_incasare,
                    )

                    # IMPORTANT: update_interval se pune în options, nu în data.
                    return self.async_create_entry(
                        title=f"E·ON România ({cod_incasare})",
                        data={
                            "username": username,
                            "password": password,  # stocat în config entry; NU se loghează
                            "cod_incasare": cod_incasare,
                        },
                        options={
                            "update_interval": update_interval,
                        },
                    )

                errors["base"] = "auth_failed"
                _LOGGER.warning(
                    "Autentificare eșuată (utilizator=%s, contract=%s).",
                    username,
                    cod_incasare,
                )

        data_schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Required("cod_incasare"): str,
                vol.Optional("update_interval", default=DEFAULT_UPDATE_INTERVAL): int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Returnează fluxul de opțiuni."""
        return EonRomaniaOptionsFlow(config_entry)


class EonRomaniaOptionsFlow(config_entries.OptionsFlow):
    """Gestionarea OptionsFlow pentru integrarea E·ON România."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Pasul inițial pentru modificarea opțiunilor."""
        _LOGGER.debug(
            "Inițializare OptionsFlow pentru %s (entry_id=%s).",
            DOMAIN,
            self.config_entry.entry_id,
        )

        if user_input is not None:
            # NU logăm user_input: conține parola.
            _LOGGER.info(
                "Se actualizează opțiunile integrării %s (entry_id=%s, utilizator=%s, contract=%s).",
                DOMAIN,
                self.config_entry.entry_id,
                user_input.get("username", self.config_entry.data.get("username", "")),
                user_input.get("cod_incasare", self.config_entry.data.get("cod_incasare", "")),
            )

            updated_data = {
                "username": user_input.get(
                    "username", self.config_entry.data.get("username", "")
                ),
                "password": user_input.get(
                    "password", self.config_entry.data.get("password", "")
                ),
                "cod_incasare": user_input.get(
                    "cod_incasare", self.config_entry.data.get("cod_incasare", "")
                ),
            }
            updated_options = {
                "update_interval": user_input.get(
                    "update_interval",
                    self.config_entry.options.get(
                        "update_interval", DEFAULT_UPDATE_INTERVAL
                    ),
                ),
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=updated_data,
                options=updated_options,
            )
            return self.async_create_entry(title="", data={})

        data_schema = vol.Schema(
            {
                vol.Optional(
                    "username",
                    default=self.config_entry.data.get("username", ""),
                ): str,
                vol.Optional(
                    "password",
                    default=self.config_entry.data.get("password", ""),
                ): str,
                vol.Optional(
                    "cod_incasare",
                    default=self.config_entry.data.get("cod_incasare", ""),
                ): str,
                vol.Optional(
                    "update_interval",
                    default=self.config_entry.options.get(
                        "update_interval", DEFAULT_UPDATE_INTERVAL
                    ),
                ): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
