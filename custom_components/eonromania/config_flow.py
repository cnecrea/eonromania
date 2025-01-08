"""ConfigFlow și OptionsFlow pentru integrarea EON România."""

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL
from .api import EonApiClient

_LOGGER = logging.getLogger(__name__)

class EonRomaniaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestionarea ConfigFlow pentru integrarea EON România."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Pasul inițial pentru configurare."""
        errors = {}

        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]
            cod_incasare = user_input["cod_incasare"]
            update_interval = user_input["update_interval"]

            # Validăm și ajustăm cod_incasare la 12 caractere (dacă e necesar)
            try:
                if len(cod_incasare) < 12:
                    cod_incasare = cod_incasare.zfill(12)  # completează cu zerouri
                elif len(cod_incasare) > 12:
                    raise ValueError("Codul de încasare este prea lung.")
            except ValueError:
                errors["cod_incasare"] = "invalid_cod_incasare"
                _LOGGER.error("Codul de încasare invalid: %s", cod_incasare)

            if not errors:
                # Testăm autentificarea
                session = async_get_clientsession(self.hass)
                api_client = EonApiClient(session, username, password)
                success = await api_client.async_login()

                if success:
                    # Creăm o intrare nouă (config entry)
                    return self.async_create_entry(
                        title=f"E-ON România ({cod_incasare})",
                        data={
                            "username": username,
                            "password": password,
                            "cod_incasare": cod_incasare,
                            "update_interval": update_interval,
                        },
                    )
                else:
                    errors["base"] = "auth_failed"
                    _LOGGER.error("Autentificare eșuată pentru utilizatorul %s", username)

        data_schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Required("cod_incasare"): str,
                vol.Optional("update_interval", default=DEFAULT_UPDATE_INTERVAL): int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Returnează fluxul de opțiuni."""
        return EonRomaniaOptionsFlow(config_entry)


class EonRomaniaOptionsFlow(config_entries.OptionsFlow):
    """Gestionarea OptionsFlow pentru integrarea EON România."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Pasul inițial pentru modificarea opțiunilor."""
        _LOGGER.debug("OptionsFlow inițializat pentru %s", self.config_entry.entry_id)

        if user_input is not None:
            # Actualizăm datele intrării
            _LOGGER.debug("Modificare date: %s", user_input)

            updated_data = {
                "username": user_input["username"],
                "password": user_input["password"],
                "cod_incasare": user_input["cod_incasare"],
            }
            updated_options = {
                "update_interval": user_input["update_interval"]
            }

            # În Home Assistant, config_entry.data e readonly la OptionsFlow,
            # așa că putem muta ceva date în 'options' la nevoie.
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=updated_data,
                options=updated_options
            )
            return self.async_create_entry(title="", data={})

        data_schema = vol.Schema(
            {
                vol.Optional("username", default=self.config_entry.data.get("username", "")): str,
                vol.Optional("password", default=self.config_entry.data.get("password", "")): str,
                vol.Optional("cod_incasare", default=self.config_entry.data.get("cod_incasare", "")): str,
                vol.Optional("update_interval", default=self.config_entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL)): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
