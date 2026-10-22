"""Module pentru gestionarea butoanelor în integrarea E·ON România."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LICENSE_DATA_KEY
from .coordinator import EonRomaniaCoordinator
from .helpers import (
    UTILITY_BUTTON_CONFIG,
    detect_utility_type_individual,
    extract_ablbelnr,
    get_meter_data,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Configurează butoanele pentru intrarea dată (config_entry)."""
    # Verificare licență
    mgr = hass.data.get(DOMAIN, {}).get(LICENSE_DATA_KEY)
    is_license_valid = mgr.is_valid if mgr else False
    if not is_license_valid:
        _LOGGER.debug(
            "Platform button pentru %s nu este inițializată — licență invalidă (entry_id=%s).",
            DOMAIN,
            config_entry.entry_id,
        )
        # Butoanele create anterior ar rămâne orfane („indisponibile") în registry
        registru = er.async_get(hass)
        for entry_reg in er.async_entries_for_config_entry(
            registru, config_entry.entry_id
        ):
            if entry_reg.domain == "button":
                registru.async_remove(entry_reg.entity_id)
        return

    _LOGGER.debug(
        "Se inițializează platforma button pentru %s (entry_id=%s).",
        DOMAIN,
        config_entry.entry_id,
    )

    entities: list[ButtonEntity] = []

    for cod_incasare, coordinator in config_entry.runtime_data.coordinators.items():
        # Cont fără contracte → nu are contoare, nu se creează butoane
        if coordinator.account_only:
            _LOGGER.debug(
                "Coordinator account_only (%s) — nu se creează butoane.", cod_incasare,
            )
            continue

        if coordinator.is_collective:
            # ── Contract colectiv/DUO: un buton per subcontract ──
            subcontracts_list = coordinator.data.get("subcontracts") if coordinator.data else None

            if subcontracts_list and isinstance(subcontracts_list, list):
                for s in subcontracts_list:
                    if not isinstance(s, dict):
                        continue
                    sc_code = s.get("accountContract")
                    utility_type = s.get("utilityType")
                    if not sc_code or not utility_type:
                        continue

                    btn_config = UTILITY_BUTTON_CONFIG.get(utility_type)
                    if not btn_config:
                        _LOGGER.warning(
                            "Tip utilitate necunoscut '%s' pentru subcontract %s (DUO %s). Buton ignorat.",
                            utility_type, sc_code, cod_incasare,
                        )
                        continue

                    entities.append(
                        TrimiteIndexButton(
                            coordinator=coordinator,
                            config_entry=config_entry,
                            account_contract=sc_code,
                            utility_type=utility_type,
                            is_subcontract=True,
                        )
                    )
                    _LOGGER.debug(
                        "Buton DUO creat: %s → %s (contract_principal=%s).",
                        btn_config["label"], sc_code, cod_incasare,
                    )
            else:
                _LOGGER.warning(
                    "Contract DUO fără subcontracte disponibile (contract=%s). Nu se creează butoane.",
                    cod_incasare,
                )
        else:
            # ── Contract individual: un singur buton ──
            utility_type = detect_utility_type_individual(coordinator.data)
            btn_config = UTILITY_BUTTON_CONFIG.get(utility_type)
            if not btn_config:
                _LOGGER.warning(
                    "Tip utilitate necunoscut '%s' pentru contract individual %s. Se folosește fallback gaz.",
                    utility_type, cod_incasare,
                )
                utility_type = "02"

            entities.append(
                TrimiteIndexButton(
                    coordinator=coordinator,
                    config_entry=config_entry,
                    account_contract=cod_incasare,
                    utility_type=utility_type,
                    is_subcontract=False,
                )
            )

    if entities:
        async_add_entities(entities)
        _LOGGER.debug(
            "Platforma button: %s butoane create (entry_id=%s).",
            len(entities), config_entry.entry_id,
        )


class TrimiteIndexButton(CoordinatorEntity[EonRomaniaCoordinator], ButtonEntity):
    """Buton pentru trimiterea indexului — suportă atât contracte individuale cât și DUO."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: EonRomaniaCoordinator,
        config_entry: ConfigEntry,
        account_contract: str,
        utility_type: str,
        is_subcontract: bool = False,
    ):
        """Inițializează butonul.

        Args:
            coordinator: Coordinatorul E·ON pentru contractul principal.
            config_entry: Intrarea de configurare.
            account_contract: Codul de încasare (contract principal sau subcontract).
            utility_type: Tipul utilității ("01" = electricitate, "02" = gaz).
            is_subcontract: True dacă butonul e pentru un subcontract DUO.
        """
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._account_contract = account_contract
        self._utility_type = utility_type
        self._is_subcontract = is_subcontract
        self._cod_incasare = coordinator.cod_incasare  # contractul principal (pentru device)

        # Configurația din mapare
        btn_config = UTILITY_BUTTON_CONFIG.get(utility_type, UTILITY_BUTTON_CONFIG["02"])
        self._input_number_entity = btn_config["input_number"]
        self._attr_name = btn_config["label"]
        self._attr_icon = btn_config["icon"]
        self._attr_translation_key = btn_config["translation_key"]

        # Entity ID și unique_id
        self._attr_unique_id = f"{DOMAIN}_trimite_index_{account_contract}"
        self._custom_entity_id = f"button.{DOMAIN}_{account_contract}_{btn_config['suffix']}"

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
        """Execută trimiterea indexului.

        Orice eșec ridică HomeAssistantError → mesajul apare în interfață
        (înainte erorile ajungeau doar în log și apăsarea părea reușită).
        """
        ac = self._account_contract
        utility_label = UTILITY_BUTTON_CONFIG.get(self._utility_type, {}).get("label", "necunoscut")

        # 1. Citește valoarea din input_number
        input_state = self.hass.states.get(self._input_number_entity)
        if not input_state:
            raise HomeAssistantError(
                f"Nu există entitatea {self._input_number_entity}. "
                f"Nu se poate trimite indexul (contract {ac})."
            )

        try:
            index_value = int(float(input_state.state))
        except (TypeError, ValueError) as err:
            raise HomeAssistantError(
                f"Valoare invalidă pentru {self._input_number_entity}: "
                f"'{input_state.state}'."
            ) from err

        # 2. Obține datele contorului (ablbelnr)
        meter_data = get_meter_data(
            self.coordinator.data, ac, is_subcontract=self._is_subcontract
        )
        ablbelnr = extract_ablbelnr(meter_data)
        if not ablbelnr:
            raise HomeAssistantError(
                f"Nu a fost găsit ID-ul intern al contorului (contract {ac}, "
                f"{utility_label}). Verificați dacă perioada de citire este deschisă."
            )

        _LOGGER.debug(
            "Se trimite indexul: valoare=%s (contract=%s, tip=%s, ablbelnr=%s).",
            index_value, ac, utility_label, ablbelnr,
        )

        # 3. Construim payload-ul și trimitem
        result = await self.coordinator.api_client.async_submit_meter_index(
            account_contract=ac,
            indexes=[{"ablbelnr": ablbelnr, "indexValue": index_value}],
        )
        if result is None:
            raise HomeAssistantError(
                f"E·ON nu a acceptat indexul {index_value} (contract {ac}). "
                "Detalii în jurnalul Home Assistant."
            )

        _LOGGER.info(
            "Index trimis cu succes: valoare=%s (contract=%s, tip=%s).",
            index_value, ac, utility_label,
        )
        # 4. Refresh date
        await self.coordinator.async_request_refresh()
