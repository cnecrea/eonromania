"""Module pentru gestionarea butoanelor în platforma Sensor, utilizată de EON România."""

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.button import ButtonEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """
    Configurează butoanele pentru intrarea dată (config_entry).
    """
    _LOGGER.debug("Setarea platformei button pentru %s", DOMAIN)

    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]

    # Creează și adaugă butoanele
    async_add_entities([TrimiteIndexButton(coordinator, config_entry)])

class TrimiteIndexButton(ButtonEntity):
    """Buton pentru trimiterea indexului."""

    def __init__(self, coordinator, config_entry):
        """Inițializează butonul."""
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._attr_name = "Trimite index"
        self._attr_unique_id = f"{DOMAIN}_trimite_index_{config_entry.entry_id}"
        self._custom_entity_id = f"button.{DOMAIN}_trimite_index_{config_entry.data['cod_incasare']}"

    @property
    def entity_id(self):
        """Returnează ID-ul entității."""
        return self._custom_entity_id

    @property
    def icon(self):
        return "mdi:counter"

    @entity_id.setter
    def entity_id(self, value):
        """Setează ID-ul entității."""
        _LOGGER.debug("ID personalizat configurat: %s", value)
        self._custom_entity_id = value

    @property
    def device_info(self):
        # Construiește adresa completă (full_address)
        data = self.coordinator.data.get("dateuser", {})
        address_obj = data.get("consumptionPointAddress", {})
        street_obj = address_obj.get("street", {})
        street_type = street_obj.get("streetType", {}).get("label", "Strada")
        street_name = street_obj.get("streetName", "Necunoscută")
        street_no = address_obj.get("streetNumber", "N/A")
        apartment = address_obj.get("apartment", "N/A")
        locality_name = address_obj.get("locality", {}).get("localityName", "Necunoscut")

        full_address = f"{street_type} {street_name} {street_no} ap. {apartment}, {locality_name}"

        return {
            "identifiers": {(DOMAIN, self.config_entry.data['cod_incasare'])},
            "name": f"E-ON România - {full_address} ({self.config_entry.data['cod_incasare']})",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }

    async def async_press(self):
        """Execută trimiterea indexului."""
        cod_incasare = self.config_entry.data.get("cod_incasare", "necunoscut")
        try:
            # Obține indexValue din input_number
            gas_meter_state = self.coordinator.hass.states.get("input_number.gas_meter_reading")
            if not gas_meter_state:
                _LOGGER.error("Entitatea input_number.gas_meter_reading nu este definită.")
                return

            index_value = int(float(gas_meter_state.state))
            # Obține ablbelnr din datele coordinatorului
            citireindex_data = self.coordinator.data.get("citireindex")
            if not citireindex_data:
                _LOGGER.error("Nu s-au găsit date pentru citireindex.")
                return

            ablbelnr = None
            devices = citireindex_data.get("indexDetails", {}).get("devices", [])
            for device in devices:
                indexes = device.get("indexes", [])
                if indexes:
                    ablbelnr = indexes[0].get("ablbelnr")
                    break

            if not ablbelnr:
                _LOGGER.error("ID intern citire contor (SAP) nu a fost găsit.")
                return

            # Apelează metoda din API client
            await self.coordinator.api_client.async_trimite_index(
                account_contract=cod_incasare,
                ablbelnr=ablbelnr,
                index_value=index_value,
            )

            await self.coordinator.async_request_refresh()
            _LOGGER.info("Indexul a fost trimis cu succes pentru codul de încasare %s", cod_incasare)
        except Exception as e:
            _LOGGER.error("Eroare la trimiterea indexului pentru codul de încasare %s: %s", cod_incasare, e)
