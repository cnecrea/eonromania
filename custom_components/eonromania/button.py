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

    entities = []
    for cod_incasare, coordinator in config_entry.runtime_data.coordinators.items():
        entities.append(TrimiteIndexButton(coordinator, config_entry))

    if entities:
        async_add_entities(entities)


class TrimiteIndexButton(CoordinatorEntity[EonRomaniaCoordinator], ButtonEntity):
    """Buton pentru trimiterea indexului."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:counter"
    _attr_translation_key = "trimite_index"

    def __init__(self, coordinator: EonRomaniaCoordinator, config_entry: ConfigEntry):
        """Inițializează butonul."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._cod_incasare = coordinator.cod_incasare
        self._attr_name = f"Trimite index"
        self._attr_unique_id = f"{DOMAIN}_trimite_index_{self._cod_incasare}"
        self._custom_entity_id = f"button.{DOMAIN}_{self._cod_incasare}_trimite_index"

    @property
    def entity_id(self) -> str | None:
        return self._custom_entity_id

    @entity_id.setter
    def entity_id(self, value: str) -> None:
        self._custom_entity_id = value

    @property
    def device_info(self) -> DeviceInfo:
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

            # Obține datele contorului din coordinator
            citireindex_data = self.coordinator.data.get("meter_index") if self.coordinator.data else None
            if not citireindex_data or not isinstance(citireindex_data, dict):
                _LOGGER.error(
                    "Nu există datele de citire index (meter_index). Nu se poate trimite indexul (contract=%s).",
                    cod_incasare,
                )
                return

            # Extrage ablbelnr din primul dispozitiv
            ablbelnr = None
            devices = citireindex_data.get("indexDetails", {}).get("devices", [])
            for device in devices:
                indexes = device.get("indexes", [])
                if indexes:
                    ablbelnr = indexes[0].get("ablbelnr")
                    break

            if not ablbelnr:
                _LOGGER.error(
                    "Nu a fost găsit ID-ul intern al contorului (ablbelnr). Nu se poate trimite indexul (contract=%s).",
                    cod_incasare,
                )
                return

            _LOGGER.debug(
                "Se trimite indexul: valoare=%s (contract=%s, ablbelnr=%s).",
                index_value,
                cod_incasare,
                ablbelnr,
            )

            # Construim payload-ul conform noului format API
            indexes_payload = [
                {
                    "ablbelnr": ablbelnr,
                    "indexValue": index_value,
                }
            ]

            result = await self.coordinator.api_client.async_submit_meter_index(
                account_contract=cod_incasare,
                indexes=indexes_payload,
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
