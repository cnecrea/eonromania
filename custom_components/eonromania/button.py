"""Module pentru gestionarea butoanelor în integrarea E·ON România."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EonRomaniaCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Configurează butoanele pentru intrarea dată (config_entry)."""
    _LOGGER.debug(
        "Se inițializează platforma button pentru %s (entry_id=%s).",
        DOMAIN,
        config_entry.entry_id,
    )

    coordinator: EonRomaniaCoordinator = config_entry.runtime_data.coordinator
    async_add_entities([TrimiteIndexButton(coordinator, config_entry)])


class TrimiteIndexButton(CoordinatorEntity[EonRomaniaCoordinator], ButtonEntity):
    """Buton pentru trimiterea indexului."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:counter"
    _attr_translation_key = "trimite_index"

    def __init__(self, coordinator: EonRomaniaCoordinator, config_entry: ConfigEntry):
        """Inițializează butonul."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._cod_incasare = config_entry.data["cod_incasare"]
        self._attr_unique_id = f"{DOMAIN}_trimite_index_{config_entry.entry_id}"
        self._attr_name = "Trimite index"

    @property
    def device_info(self) -> DeviceInfo:
        """Returnează informațiile despre dispozitiv."""
        data = self.coordinator.data.get("dateuser", {}) if self.coordinator.data else {}
        address_obj = data.get("consumptionPointAddress", {}) if isinstance(data, dict) else {}
        street_obj = address_obj.get("street", {}) if isinstance(address_obj, dict) else {}

        street_type = street_obj.get("streetType", {}).get("label", "Strada")
        street_name = street_obj.get("streetName", "Necunoscută")
        street_no = address_obj.get("streetNumber", "N/A")
        apartment = address_obj.get("apartment", "N/A")
        locality_name = address_obj.get("locality", {}).get("localityName", "Necunoscut")

        full_address = f"{street_type} {street_name} {street_no} ap. {apartment}, {locality_name}"

        # Name include cod_incasare în clar (conform cerinței tale).
        # ATENȚIE: dacă pui și adresa aici, Home Assistant îți va lungi entity_id-urile.
        return DeviceInfo(
            identifiers={(DOMAIN, self._cod_incasare)},
            name=f"E·ON România ({self._cod_incasare})",
            manufacturer="Ciprian Nicolae (cnecrea)",
            model="E·ON România",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self):
        """Execută trimiterea indexului."""
        cod_incasare = self._cod_incasare

        try:
            # Obține indexValue din input_number
            gas_meter_state = self.hass.states.get("input_number.gas_meter_reading")
            if not gas_meter_state:
                _LOGGER.error(
                    "Nu există entitatea input_number.gas_meter_reading. Nu se poate trimite indexul (contract=%s).",
                    cod_incasare,
                )
                return

            try:
                index_value = int(float(gas_meter_state.state))
            except (TypeError, ValueError):
                _LOGGER.error(
                    "Valoare invalidă pentru input_number.gas_meter_reading: %s (contract=%s).",
                    gas_meter_state.state,
                    cod_incasare,
                )
                return

            # Obține ablbelnr din datele coordinatorului
            citireindex_data = self.coordinator.data.get("citireindex") if self.coordinator.data else None
            if not citireindex_data or not isinstance(citireindex_data, dict):
                _LOGGER.error(
                    "Nu există datele de citire index (citireindex). Nu se poate trimite indexul (contract=%s).",
                    cod_incasare,
                )
                return

            ablbelnr = None
            devices = citireindex_data.get("indexDetails", {}).get("devices", [])
            for device in devices:
                indexes = device.get("indexes", [])
                if indexes:
                    ablbelnr = indexes[0].get("ablbelnr")
                    break

            if not ablbelnr:
                _LOGGER.error(
                    "Nu a fost găsit ID-ul intern al contorului (ablbelnr/SAP). Nu se poate trimite indexul (contract=%s).",
                    cod_incasare,
                )
                return

            _LOGGER.debug(
                "Se trimite indexul: valoare=%s (contract=%s, ablbelnr=%s).",
                index_value,
                cod_incasare,
                ablbelnr,
            )

            # Apelează metoda din API client (returnează None la eșec)
            result = await self.coordinator.api_client.async_trimite_index(
                account_contract=cod_incasare,
                ablbelnr=ablbelnr,
                index_value=index_value,
            )

            if result is None:
                _LOGGER.error(
                    "Trimiterea indexului a eșuat (contract=%s).",
                    cod_incasare,
                )
                return

            await self.coordinator.async_request_refresh()

            _LOGGER.info(
                "Index trimis cu succes (contract=%s).",
                cod_incasare,
            )

        except Exception:
            _LOGGER.exception(
                "Eroare neașteptată la trimiterea indexului (contract=%s).",
                cod_incasare,
            )
