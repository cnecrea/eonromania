"""Platforma Sensor pentru E·ON România."""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfVolume, UnitOfEnergy
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ATTRIBUTION
from .coordinator import EonRomaniaCoordinator
from .helpers import (
    CONVENTION_MONTH_MAPPING,
    INVOICE_BALANCE_KEY_MAP,
    INVOICE_BALANCE_MONEY_KEYS,
    MONTHS_NUM_RO,
    PORTFOLIO_LABEL,
    READING_TYPE_MAP,
    UNIT_NORMALIZE,
    UTILITY_TYPE_LABEL,
    UTILITY_TYPE_SENSOR_LABEL,
    build_address_consum,
    format_invoice_due_message,
    format_number_ro,
    format_ron,
    get_meter_data,
)

_LOGGER = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Clasă de bază
# ──────────────────────────────────────────────
class EonRomaniaEntity(CoordinatorEntity[EonRomaniaCoordinator], SensorEntity):
    """Clasă de bază pentru entitățile E·ON România."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: EonRomaniaCoordinator, config_entry: ConfigEntry):
        """Inițializare cu coordinator și config_entry."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._cod_incasare = coordinator.cod_incasare
        self._custom_entity_id: str | None = None

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


# ──────────────────────────────────────────────
# async_setup_entry
# ──────────────────────────────────────────────
def _build_sensors_for_coordinator(
    coordinator: EonRomaniaCoordinator,
    config_entry: ConfigEntry,
) -> list[SensorEntity]:
    """Construiește lista de senzori pentru un singur coordinator (contract)."""
    sensors: list[SensorEntity] = []
    cod_incasare = coordinator.cod_incasare

    is_collective = coordinator.is_collective

    # ── 1. Senzori de bază (mereu prezenți) ──
    sensors.append(ContractDetailsSensor(coordinator, config_entry))
    sensors.append(FacturaRestantaSensor(coordinator, config_entry))
    sensors.append(InvoiceBalanceSensor(coordinator, config_entry))

    # Convenție consum — funcționează atât pe individuale cât și pe colective/DUO
    sensors.append(ConventieConsumSensor(coordinator, config_entry))

    # ── 2. Senzori condiționali (pe baza capabilităților detectate) ──
    caps = coordinator.capabilities

    # Prosum — doar dacă utilizatorul are prosum
    if caps and caps.get("has_prosum"):
        sensors.append(FacturaProsumSensor(coordinator, config_entry))
        sensors.append(InvoiceBalanceProsumSensor(coordinator, config_entry))

    # Eșalonare — doar dacă utilizatorul are planuri de eșalonare
    if caps and caps.get("has_rescheduling"):
        sensors.append(ReschedulingPlansSensor(coordinator, config_entry))

    # ── 3. CitireIndexSensor + CitirePermisaSensor (per dispozitiv) ──
    if not is_collective:
        # Contract individual: un singur meter_index
        citireindex_data = coordinator.data.get("meter_index") if coordinator.data else None
        if citireindex_data:
            devices = citireindex_data.get("indexDetails", {}).get("devices", [])
            seen_devices: set[str] = set()

            for device in devices:
                device_number = device.get("deviceNumber", "unknown_device")
                if device_number not in seen_devices:
                    sensors.append(CitireIndexSensor(coordinator, config_entry, device_number))
                    sensors.append(CitirePermisaSensor(coordinator, config_entry, device_number))
                    seen_devices.add(device_number)
                else:
                    _LOGGER.warning("Dispozitiv duplicat ignorat (contract=%s): %s", cod_incasare, device_number)

            if not devices:
                sensors.append(CitireIndexSensor(coordinator, config_entry, device_number=None))
                sensors.append(CitirePermisaSensor(coordinator, config_entry, device_number=None))
    else:
        # Contract colectiv/DUO: meter_index per subcontract
        smi = coordinator.data.get("subcontracts_meter_index") if coordinator.data else None
        subcontracts_list = coordinator.data.get("subcontracts") if coordinator.data else None
        if smi and isinstance(smi, dict):
            for sc_code, mi_data in smi.items():
                if not isinstance(mi_data, dict):
                    continue
                # Determinăm utility_type din lista subcontractelor
                utility_type = None
                if subcontracts_list and isinstance(subcontracts_list, list):
                    for s in subcontracts_list:
                        if isinstance(s, dict) and s.get("accountContract") == sc_code:
                            utility_type = s.get("utilityType")
                            break
                devices = mi_data.get("indexDetails", {}).get("devices", [])
                if devices:
                    seen_devices_duo: set[str] = set()
                    for device in devices:
                        device_number = device.get("deviceNumber", "unknown_device")
                        if device_number not in seen_devices_duo:
                            sensors.append(CitireIndexSensor(
                                coordinator, config_entry, device_number,
                                subcontract_code=sc_code, utility_type=utility_type,
                            ))
                            sensors.append(CitirePermisaSensor(
                                coordinator, config_entry, device_number,
                                subcontract_code=sc_code, utility_type=utility_type,
                            ))
                            seen_devices_duo.add(device_number)
                else:
                    sensors.append(CitireIndexSensor(
                        coordinator, config_entry, device_number=None,
                        subcontract_code=sc_code, utility_type=utility_type,
                    ))
                    sensors.append(CitirePermisaSensor(
                        coordinator, config_entry, device_number=None,
                        subcontract_code=sc_code, utility_type=utility_type,
                    ))

    # ── 4. ArhivaSensor (doar ultimul an) ──
    # (nu se creează pentru contracte colective — endpoint-ul nu funcționează)
    arhiva_data = coordinator.data.get("meter_history") if coordinator.data else None
    if arhiva_data and not is_collective:
        history_list = arhiva_data.get("history", [])
        valid_years = [item.get("year") for item in history_list if item.get("year")]
        if valid_years:
            max_year = max(valid_years)
            sensors.append(ArhivaSensor(coordinator, config_entry, max_year))

    # ── 5. ArhivaPlatiSensor (doar ultimul an) ──
    payments_list = coordinator.data.get("payments", []) if coordinator.data else []
    if payments_list:
        payments_by_year: dict[int, list] = defaultdict(list)
        for payment in payments_list:
            raw_date = payment.get("paymentDate")
            if not raw_date:
                continue
            try:
                year = int(raw_date.split("-")[0])
                payments_by_year[year].append(payment)
            except ValueError:
                continue
        if payments_by_year:
            max_year = max(payments_by_year.keys())
            sensors.append(ArhivaPlatiSensor(coordinator, config_entry, max_year))

    # ── 6. ArhivaComparareConsumAnualGraficSensor (doar ultimul an) ──
    # (nu se creează pentru contracte colective — endpoint-ul nu funcționează)
    comparareanualagrafic_data = coordinator.data.get("graphic_consumption", {}) if (coordinator.data and not is_collective) else {}
    if isinstance(comparareanualagrafic_data, dict) and "consumption" in comparareanualagrafic_data:
        yearly_data: dict[int, dict] = defaultdict(dict)
        for item in comparareanualagrafic_data["consumption"]:
            year = item.get("year")
            month = item.get("month")
            consumption_value = item.get("consumptionValue")
            consumption_day_value = item.get("consumptionValueDayValue")
            if not year or not month or consumption_value is None or consumption_day_value is None:
                continue
            yearly_data[year][month] = {
                "consumptionValue": consumption_value,
                "consumptionValueDayValue": consumption_day_value,
            }

        cleaned_yearly_data = {
            year: monthly_values
            for year, monthly_values in yearly_data.items()
            if any(v["consumptionValue"] > 0 or v["consumptionValueDayValue"] > 0 for v in monthly_values.values())
        }
        if cleaned_yearly_data:
            max_year = max(cleaned_yearly_data.keys())
            sensors.append(ArhivaComparareConsumAnualGraficSensor(coordinator, config_entry, max_year, cleaned_yearly_data[max_year]))

    return sensors


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """Configurează senzorii pentru toate contractele selectate."""
    coordinators: dict[str, EonRomaniaCoordinator] = config_entry.runtime_data.coordinators

    _LOGGER.debug(
        "Inițializare platforma sensor pentru %s (entry_id=%s, contracte=%s).",
        DOMAIN, config_entry.entry_id, list(coordinators.keys()),
    )

    all_sensors: list[SensorEntity] = []

    for cod_incasare, coordinator in coordinators.items():
        sensors = _build_sensors_for_coordinator(coordinator, config_entry)
        _LOGGER.debug(
            "Se adaugă %s senzori pentru contractul %s.", len(sensors), cod_incasare,
        )
        all_sensors.extend(sensors)

    _LOGGER.info(
        "Total %s senzori adăugați pentru %s (entry_id=%s).",
        len(all_sensors), DOMAIN, config_entry.entry_id,
    )

    async_add_entities(all_sensors)


# ══════════════════════════════════════════════
# SENZORI NOI
# ══════════════════════════════════════════════


# ──────────────────────────────────────────────
# ContractDetailsSensor (înlocuiește DateContractSensor)
# ──────────────────────────────────────────────
class ContractDetailsSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor contractului."""

    _attr_icon = "mdi:file-document-edit-outline"
    _attr_translation_key = "date_contract"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Date contract"
        self._attr_unique_id = f"{DOMAIN}_date_contract_{self._cod_incasare}"
        self._custom_entity_id = f"sensor.{DOMAIN}_{self._cod_incasare}_date_contract"

    @property
    def native_value(self):
        data = self.coordinator.data.get("contract_details") if self.coordinator.data else None
        if not data:
            return None
        return data.get("accountContract")

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}

        data = self.coordinator.data.get("contract_details")
        if not isinstance(data, dict):
            return {}

        is_collective = self.coordinator.data.get("is_collective", False)

        if is_collective:
            return self._build_collective_attributes(data)
        return self._build_individual_attributes(data)

    def _build_individual_attributes(self, data: dict) -> dict[str, Any]:
        """Construiește atributele pentru un contract individual (gaz sau curent)."""
        attributes: dict[str, Any] = {}

        # ─────────────────────────────
        # Date generale contract
        # ─────────────────────────────
        if data.get("accountContract"):
            attributes["Cod încasare"] = data["accountContract"]

        if data.get("consumptionPointCode"):
            attributes["Cod loc de consum (NLC)"] = data["consumptionPointCode"]

        if data.get("pod"):
            attributes["CLC - Cod punct de măsură"] = data["pod"]

        if data.get("distributorName"):
            attributes["Operator de Distribuție (OD)"] = data["distributorName"]

        # ─────────────────────────────
        # Prețuri
        # ─────────────────────────────
        price_data = data.get("supplierAndDistributionPrice")
        if isinstance(price_data, dict):

            if price_data.get("contractualPrice") is not None:
                attributes["Preț final (fără TVA)"] = f"{price_data['contractualPrice']} lei"

            if price_data.get("contractualPriceWithVat") is not None:
                attributes["Preț final (cu TVA)"] = f"{price_data['contractualPriceWithVat']} lei"

            components = price_data.get("priceComponents")
            if isinstance(components, dict):

                if components.get("supplierPrice") is not None:
                    attributes["Preț furnizare"] = f"{components['supplierPrice']} lei/kWh"

                if components.get("distributionPrice") is not None:
                    attributes["Tarif reglementat distribuție"] = f"{components['distributionPrice']} lei/kWh"

                if components.get("transportPrice") is not None:
                    attributes["Tarif reglementat transport"] = f"{components['transportPrice']} lei/kWh"

            if price_data.get("pcs") is not None:
                attributes["PCS"] = str(price_data["pcs"])

        # ─────────────────────────────
        # Adresă (folosește helperul!)
        # ─────────────────────────────
        address_obj = data.get("consumptionPointAddress")
        if isinstance(address_obj, dict):
            formatted_address = build_address_consum(address_obj)
            if formatted_address:
                attributes["Adresă consum"] = formatted_address

        # ─────────────────────────────
        # Date verificare / revizie
        # ─────────────────────────────
        if data.get("verificationExpirationDate"):
            attributes["Următoarea verificare a instalației"] = data["verificationExpirationDate"]

        if data.get("revisionStartDate"):
            attributes["Data inițierii reviziei"] = data["revisionStartDate"]

        if data.get("revisionExpirationDate"):
            attributes["Următoarea revizie tehnică"] = data["revisionExpirationDate"]

        attributes["attribution"] = ATTRIBUTION

        return attributes

    def _build_collective_attributes(self, data: dict) -> dict[str, Any]:
        """Construiește atributele pentru un contract colectiv/DUO (gaz + curent)."""
        attributes: dict[str, Any] = {}

        # ─────────────────────────────
        # Date contract colectiv (din contract_details)
        # ─────────────────────────────
        if data.get("accountContract"):
            attributes["Cod încasare (DUO)"] = data["accountContract"]

        attributes["Tip contract"] = "Colectiv / DUO (gaz + curent)"

        if data.get("contractName"):
            attributes["Nume contract"] = data["contractName"]

        # Adresă de corespondență (din contractul principal)
        mailing = data.get("mailingAddress")
        if isinstance(mailing, dict):
            formatted = build_address_consum(mailing)
            if formatted:
                attributes["Adresă de corespondență"] = formatted

        # ─────────────────────────────
        # Subcontracte din list-with-subcontracts
        # (acum e o listă plată de sub-contracte, extrasă din subContracts[])
        # ─────────────────────────────
        subcontracts = self.coordinator.data.get("subcontracts")
        subcontracts_details = self.coordinator.data.get("subcontracts_details")

        if subcontracts and isinstance(subcontracts, list):
            attributes["────"] = ""
            attributes["Număr subcontracte"] = len(subcontracts)

            for idx, sub in enumerate(subcontracts, start=1):
                if not isinstance(sub, dict):
                    continue

                sub_ac = sub.get("accountContract", "N/A")
                utility = sub.get("utilityType", "")
                utility_label = UTILITY_TYPE_LABEL.get(utility, utility or "Necunoscut")

                prefix = utility_label
                attributes[f"{prefix} — Cod încasare"] = sub_ac

                if sub.get("consumptionPointCode"):
                    attributes[f"{prefix} — Cod loc consum (NLC)"] = sub["consumptionPointCode"]

                if sub.get("pod"):
                    attributes[f"{prefix} — Cod punct măsură (POD)"] = sub["pod"]

                sub_addr = sub.get("consumptionPointAddress")
                if isinstance(sub_addr, dict):
                    formatted_sub = build_address_consum(sub_addr)
                    if formatted_sub:
                        attributes[f"{prefix} — Adresă consum"] = formatted_sub

        # ─────────────────────────────
        # Detalii subcontracte din contracts-details-list
        # (structură plată: fiecare element are prețuri, citiri contor, date revizie etc.)
        # ─────────────────────────────
        if subcontracts_details and isinstance(subcontracts_details, list):
            for detail in subcontracts_details:
                if not isinstance(detail, dict):
                    continue

                detail_ac = detail.get("accountContract", "N/A")
                # Preferăm portfolioName (GN/EE) dacă e prezent, altfel utilityType
                portfolio = detail.get("portfolioName", "")
                utility = detail.get("utilityType", "")
                if portfolio and portfolio in PORTFOLIO_LABEL:
                    utility_label = PORTFOLIO_LABEL[portfolio]
                elif utility in UTILITY_TYPE_LABEL:
                    utility_label = UTILITY_TYPE_LABEL[utility]
                else:
                    utility_label = portfolio or utility or "Necunoscut"

                prefix = utility_label

                attributes[f"──── {utility_label} ────"] = ""

                attributes[f"{prefix} — Cod încasare"] = detail_ac

                if detail.get("distributorName"):
                    attributes[f"{prefix} — Operator Distribuție (OD)"] = detail["distributorName"]

                if detail.get("contractName"):
                    attributes[f"{prefix} — Nume contract"] = detail["contractName"]

                if detail.get("productName"):
                    attributes[f"{prefix} — Produs"] = detail["productName"]

                if detail.get("consumptionPointCode"):
                    attributes[f"{prefix} — Cod loc consum (NLC)"] = detail["consumptionPointCode"]

                if detail.get("pod"):
                    attributes[f"{prefix} — Cod punct măsură (POD)"] = detail["pod"]

                # Prețuri subcontract
                price_data = detail.get("supplierAndDistributionPrice")
                if isinstance(price_data, dict):
                    if price_data.get("contractualPrice") is not None:
                        attributes[f"{prefix} — Preț final (fără TVA)"] = f"{price_data['contractualPrice']} lei"

                    if price_data.get("contractualPriceWithVat") is not None:
                        attributes[f"{prefix} — Preț final (cu TVA)"] = f"{price_data['contractualPriceWithVat']} lei"

                    components = price_data.get("priceComponents")
                    if isinstance(components, dict):
                        if components.get("supplierPrice") is not None:
                            attributes[f"{prefix} — Preț furnizare"] = f"{components['supplierPrice']} lei"
                        if components.get("distributionPrice") is not None:
                            attributes[f"{prefix} — Tarif distribuție"] = f"{components['distributionPrice']} lei"
                        if components.get("transportPrice") is not None:
                            attributes[f"{prefix} — Tarif transport"] = f"{components['transportPrice']} lei"

                    if price_data.get("pcs") is not None:
                        attributes[f"{prefix} — PCS"] = str(price_data["pcs"])

                # Citiri contor (meterReadings)
                meter_readings = detail.get("meterReadings")
                if isinstance(meter_readings, list) and meter_readings:
                    for mr in meter_readings:
                        if not isinstance(mr, dict):
                            continue
                        meter_num = mr.get("meterNumber", "")
                        if mr.get("currentIndex") is not None:
                            attributes[f"{prefix} — Index actual ({meter_num})"] = format_number_ro(mr["currentIndex"])
                        if mr.get("oldIndex") is not None:
                            attributes[f"{prefix} — Index vechi ({meter_num})"] = format_number_ro(mr["oldIndex"])
                        reading_type = mr.get("readingType", "")
                        if reading_type:
                            attributes[f"{prefix} — Tip citire ({meter_num})"] = READING_TYPE_MAP.get(reading_type, reading_type)

                # Adresă consum subcontract
                sub_addr = detail.get("consumptionPointAddress")
                if isinstance(sub_addr, dict):
                    formatted_sub = build_address_consum(sub_addr)
                    if formatted_sub:
                        attributes[f"{prefix} — Adresă consum"] = formatted_sub

                # Verificare / revizie instalație
                if detail.get("verificationExpirationDate"):
                    attributes[f"{prefix} — Verificare instalație"] = detail["verificationExpirationDate"]

                if detail.get("revisionExpirationDate"):
                    attributes[f"{prefix} — Revizie tehnică"] = detail["revisionExpirationDate"]

                if detail.get("revisionStartDate"):
                    attributes[f"{prefix} — Dată inițiere revizie"] = detail["revisionStartDate"]

        attributes["attribution"] = ATTRIBUTION

        return attributes


# ──────────────────────────────────────────────
# InvoiceBalanceSensor
# ──────────────────────────────────────────────
class InvoiceBalanceSensor(EonRomaniaEntity):
    """Senzor pentru soldul facturii per contract."""

    _attr_icon = "mdi:currency-eur"
    _attr_translation_key = "sold_factura"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Sold factură"
        self._attr_unique_id = f"{DOMAIN}_sold_factura_{self._cod_incasare}"
        self._custom_entity_id = f"sensor.{DOMAIN}_{self._cod_incasare}_sold_factura"

    @property
    def native_value(self):
        data = self.coordinator.data.get("invoice_balance") if self.coordinator.data else None
        if not data or not isinstance(data, dict):
            return "Nu"
        balance = data.get("balance", data.get("total", data.get("totalBalance")))
        if balance is not None and float(balance) > 0:
            return "Da"
        return "Nu"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data.get("invoice_balance") if self.coordinator.data else None
        if not data:
            return {"attribution": ATTRIBUTION}

        attributes = {}
        if isinstance(data, dict):
            for key, value in data.items():
                if value is None:
                    continue
                label = INVOICE_BALANCE_KEY_MAP.get(key, key)
                if isinstance(value, (int, float)) and key in INVOICE_BALANCE_MONEY_KEYS:
                    attributes[label] = f"{format_ron(float(value))} lei"
                elif isinstance(value, bool) or (isinstance(value, str) and value.lower() in ("true", "false")):
                    bool_val = value if isinstance(value, bool) else value.lower() == "true"
                    attributes[label] = "Da" if bool_val else "Nu"
                else:
                    attributes[label] = value
        attributes["attribution"] = ATTRIBUTION
        return attributes


# ──────────────────────────────────────────────
# InvoiceBalanceProsumSensor
# ──────────────────────────────────────────────
class InvoiceBalanceProsumSensor(EonRomaniaEntity):
    """Senzor pentru soldul facturii prosumator."""

    _attr_icon = "mdi:solar-power-variant"
    _attr_translation_key = "sold_prosumator"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Sold prosumator"
        self._attr_unique_id = f"{DOMAIN}_sold_prosumator_{self._cod_incasare}"
        self._custom_entity_id = f"sensor.{DOMAIN}_{self._cod_incasare}_sold_prosumator"

    @property
    def native_value(self):
        data = self.coordinator.data.get("invoice_balance_prosum") if self.coordinator.data else None
        if not data or not isinstance(data, dict):
            return "Nu"
        balance = float(data.get("balance", 0))
        if balance > 0:
            return "Da"
        return "Nu"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data.get("invoice_balance_prosum") if self.coordinator.data else None
        if not data or not isinstance(data, dict):
            return {"attribution": ATTRIBUTION}
        attributes = {}
        balance = float(data.get("balance", 0))
        if balance > 0:
            attributes["Sold"] = f"{format_ron(balance)} lei (datorie)"
        elif balance < 0:
            attributes["Sold"] = f"{format_ron(abs(balance))} lei (credit)"
        else:
            attributes["Sold"] = "0,00 lei"
        if data.get("refund"):
            attributes["Rambursare disponibilă"] = "Da"
        if data.get("refundInProcess"):
            attributes["Rambursare în proces"] = "Da"
        if data.get("date"):
            attributes["Data sold"] = data.get("date")
        attributes["attribution"] = ATTRIBUTION
        return attributes


# ──────────────────────────────────────────────
# ReschedulingPlansSensor
# ──────────────────────────────────────────────
class ReschedulingPlansSensor(EonRomaniaEntity):
    """Senzor pentru planurile de eșalonare."""

    _attr_icon = "mdi:calendar-clock"
    _attr_translation_key = "rescheduling_plans"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Planuri eșalonare"
        self._attr_unique_id = f"{DOMAIN}_rescheduling_plans_{self._cod_incasare}"
        self._custom_entity_id = f"sensor.{DOMAIN}_{self._cod_incasare}_rescheduling_plans"

    @property
    def native_value(self):
        data = self.coordinator.data.get("rescheduling_plans") if self.coordinator.data else None
        if not data or not isinstance(data, list):
            return 0
        return len(data)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data.get("rescheduling_plans") if self.coordinator.data else None
        if not data or not isinstance(data, list):
            return {"attribution": ATTRIBUTION}
        attributes = {}
        for idx, plan in enumerate(data, start=1):
            attributes[f"Plan {idx}"] = str(plan)
        attributes["attribution"] = ATTRIBUTION
        return attributes


# ══════════════════════════════════════════════
# SENZORI EXISTENȚI (ACTUALIZAȚI)
# ══════════════════════════════════════════════


# ──────────────────────────────────────────────
# CitireIndexSensor
# ──────────────────────────────────────────────
class CitireIndexSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor despre indexul curent."""

    def __init__(self, coordinator, config_entry, device_number, subcontract_code=None, utility_type=None):
        super().__init__(coordinator, config_entry)
        self.device_number = device_number
        self._subcontract_code = subcontract_code

        if subcontract_code and utility_type:
            # Mod DUO: tipul utilității vine din subcontract
            label_info = UTILITY_TYPE_SENSOR_LABEL.get(utility_type)
            if label_info:
                _, name, icon, tkey = label_info
            else:
                name = "Index"
                icon = "mdi:gauge"
                tkey = "index_curent"
            self._attr_name = name
            self._attr_icon = icon
            self._attr_translation_key = tkey
            self._attr_unique_id = f"{DOMAIN}_index_curent_{subcontract_code}"
            self._custom_entity_id = f"sensor.{DOMAIN}_{subcontract_code}_{tkey}"
        else:
            # Mod individual: determinat din unitatea de măsură
            um = coordinator.data.get("um", "m3") if coordinator.data else "m3"
            is_gaz = um.lower().startswith("m")
            self._attr_name = "Index gaz" if is_gaz else "Index energie electrică"
            self._attr_icon = "mdi:gauge" if is_gaz else "mdi:lightning-bolt"
            self._attr_translation_key = "index_gaz" if is_gaz else "index_energie_electrica"
            self._attr_unique_id = f"{DOMAIN}_index_curent_{self._cod_incasare}"
            self._custom_entity_id = (
                f"sensor.{DOMAIN}_{self._cod_incasare}_index_gaz"
                if is_gaz
                else f"sensor.{DOMAIN}_{self._cod_incasare}_index_energie_electrica"
            )

    @property
    def native_unit_of_measurement(self) -> str:
        if self._subcontract_code:
            # DUO: determinăm din utility_type stocat la init
            return UnitOfVolume.CUBIC_METERS if "gaz" in self._attr_name.lower() else UnitOfEnergy.KILO_WATT_HOUR
        um = self.coordinator.data.get("um", "m3") if self.coordinator.data else "m3"
        return UnitOfVolume.CUBIC_METERS if um.lower().startswith("m") else UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self):
        citireindex_data = get_meter_data(
            self.coordinator.data, self._subcontract_code or self._cod_incasare,
            is_subcontract=bool(self._subcontract_code),
        )
        if not citireindex_data:
            return 0
        devices = citireindex_data.get("indexDetails", {}).get("devices", [])
        if not devices:
            return 0
        for dev in devices:
            if dev.get("deviceNumber") == self.device_number:
                indexes = dev.get("indexes", [])
                if indexes:
                    current_value = indexes[0].get("currentValue")
                    if current_value is not None:
                        return int(current_value)
                    old_value = indexes[0].get("oldValue")
                    if old_value is not None:
                        return int(old_value)
        return 0

    @property
    def extra_state_attributes(self):
        citireindex_data = get_meter_data(
            self.coordinator.data, self._subcontract_code or self._cod_incasare,
            is_subcontract=bool(self._subcontract_code),
        )
        if not citireindex_data:
            return {}

        index_details = citireindex_data.get("indexDetails", {})
        devices = index_details.get("devices", [])
        reading_period = citireindex_data.get("readingPeriod", {})

        if not devices:
            return {"În curs de actualizare": ""}

        for dev in devices:
            if dev.get("deviceNumber") == self.device_number:
                indexes = dev.get("indexes", [])
                if not indexes:
                    continue

                first_index = indexes[0]
                attributes = {}

                if dev.get("deviceNumber") is not None:
                    attributes["Numărul dispozitivului"] = dev.get("deviceNumber")
                if first_index.get("ablbelnr") is not None:
                    attributes["Numărul ID intern citire contor"] = first_index.get("ablbelnr")
                if reading_period.get("startDate") is not None:
                    attributes["Data de începere a următoarei citiri"] = reading_period.get("startDate")
                if reading_period.get("endDate") is not None:
                    attributes["Data de final a citirii"] = reading_period.get("endDate")
                if reading_period.get("allowedReading") is not None:
                    attributes["Autorizat să citească contorul"] = "Da" if reading_period.get("allowedReading") else "Nu"
                if reading_period.get("allowChange") is not None:
                    attributes["Permite modificarea citirii"] = "Da" if reading_period.get("allowChange") else "Nu"
                if reading_period.get("smartDevice") is not None:
                    attributes["Dispozitiv inteligent"] = "Da" if reading_period.get("smartDevice") else "Nu"

                crt_reading_type = reading_period.get("currentReadingType")
                if crt_reading_type is not None:
                    reading_type_labels = {"01": "Citire distribuitor", "02": "Autocitire", "03": "Estimare"}
                    attributes["Tipul citirii curente"] = reading_type_labels.get(crt_reading_type, "Necunoscut")

                if first_index.get("minValue") is not None:
                    attributes["Citire anterioară"] = first_index.get("minValue")
                if first_index.get("oldValue") is not None:
                    attributes["Ultima citire validată"] = first_index.get("oldValue")
                if first_index.get("currentValue") is not None:
                    attributes["Index propus pentru facturare"] = first_index.get("currentValue")
                if first_index.get("sentAt") is not None:
                    attributes["Trimis la"] = first_index.get("sentAt")
                if first_index.get("canBeChangedTill") is not None:
                    attributes["Poate fi modificat până la"] = first_index.get("canBeChangedTill")

                attributes["attribution"] = ATTRIBUTION
                return attributes

        return {}


# ──────────────────────────────────────────────
# CitirePermisaSensor
# ──────────────────────────────────────────────
class CitirePermisaSensor(EonRomaniaEntity):
    """Senzor pentru verificarea permisiunii de citire a indexului."""

    _attr_translation_key = "citire_permisa"

    def __init__(self, coordinator, config_entry, device_number, subcontract_code=None, utility_type=None):
        super().__init__(coordinator, config_entry)
        self.device_number = device_number
        self._subcontract_code = subcontract_code

        if subcontract_code and utility_type:
            # Mod DUO
            ut_labels = {"01": "electricitate", "02": "gaz"}
            ut_label = ut_labels.get(utility_type, "")
            suffix = f" {ut_label}" if ut_label else ""
            self._attr_name = f"Citire permisă{suffix}"
            self._attr_unique_id = f"{DOMAIN}_citire_permisa_{subcontract_code}"
            self._custom_entity_id = f"sensor.{DOMAIN}_{subcontract_code}_citire_permisa"
        else:
            self._attr_name = "Citire permisă"
            self._attr_unique_id = f"{DOMAIN}_citire_permisa_{self._cod_incasare}"
            self._custom_entity_id = f"sensor.{DOMAIN}_{self._cod_incasare}_citire_permisa"

    @property
    def native_value(self):
        citireindex_data = get_meter_data(
            self.coordinator.data, self._subcontract_code or self._cod_incasare,
            is_subcontract=bool(self._subcontract_code),
        )
        if not citireindex_data:
            return "Nu"

        reading_period = citireindex_data.get("readingPeriod", {})

        # 1. Cel mai fiabil indicator: inPeriod (setat de API)
        in_period = reading_period.get("inPeriod")
        if in_period is not None:
            return "Da" if in_period else "Nu"

        # 2. Fallback: allowedReading
        allowed = reading_period.get("allowedReading")
        if allowed is not None:
            return "Da" if allowed else "Nu"

        # 3. Fallback final: verificare manuală pe date
        start_date_str = reading_period.get("startDate")
        end_date_str = reading_period.get("endDate")

        # canBeChangedTill din index poate extinde fereastra
        index_details = citireindex_data.get("indexDetails", {})
        devices = index_details.get("devices", [])
        can_be_changed_till_str = None
        if devices:
            indexes = devices[0].get("indexes", [])
            if indexes:
                can_be_changed_till_str = indexes[0].get("canBeChangedTill")

        try:
            today = dt_util.now().replace(tzinfo=None)
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else None
            # Limita superioară: canBeChangedTill dacă există, altfel endDate
            upper_str = can_be_changed_till_str or end_date_str
            upper_date = None
            if upper_str:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        upper_date = datetime.strptime(upper_str, fmt)
                        break
                    except ValueError:
                        continue

            if start_date and upper_date:
                if start_date <= today <= upper_date:
                    return "Da"
                return "Nu"
            if start_date and today >= start_date:
                return "Da"
            return "Nu"
        except Exception as e:
            _LOGGER.exception(
                "Eroare la determinarea stării CitirePermisa (contract=%s): %s",
                self._subcontract_code or self._cod_incasare, e,
            )
            return "Eroare"

    @property
    def extra_state_attributes(self):
        citireindex_data = get_meter_data(
            self.coordinator.data, self._subcontract_code or self._cod_incasare,
            is_subcontract=bool(self._subcontract_code),
        )
        if not citireindex_data:
            return {}

        reading_period = citireindex_data.get("readingPeriod", {})
        index_details = citireindex_data.get("indexDetails", {})
        devices = index_details.get("devices", [])

        if not devices:
            return {"În curs de actualizare": ""}

        for dev in devices:
            if dev.get("deviceNumber") == self.device_number:
                indexes = dev.get("indexes", [{}])[0]
                can_be_changed_till = indexes.get("canBeChangedTill")
                # Dacă canBeChangedTill e null, folosim endDate din readingPeriod
                deadline = can_be_changed_till or reading_period.get("endDate")

                attributes = {}
                attributes["ID intern citire contor (SAP)"] = indexes.get("ablbelnr", "Necunoscut")
                attributes["Indexul poate fi trimis până la"] = deadline or "Perioada nu a fost stabilită"

                start_date = reading_period.get("startDate")
                end_date = reading_period.get("endDate")
                if start_date and end_date:
                    attributes["Perioadă transmitere index"] = f"{start_date} — {end_date}"

                in_period = reading_period.get("inPeriod")
                if in_period is not None:
                    attributes["În perioadă de citire"] = "Da" if in_period else "Nu"

                allowed = reading_period.get("allowedReading")
                if allowed is not None:
                    attributes["Citire autorizată"] = "Da" if allowed else "Nu"

                attributes["Cod încasare"] = self._subcontract_code or self._cod_incasare
                return attributes
        return {}

    @property
    def icon(self):
        value = self.native_value
        if value == "Da":
            return "mdi:clock-check-outline"
        if value == "Nu":
            return "mdi:clock-alert-outline"
        return "mdi:cog-stop-outline"


# ──────────────────────────────────────────────
# FacturaRestantaSensor
# ──────────────────────────────────────────────
class FacturaRestantaSensor(EonRomaniaEntity):
    """Senzor pentru afișarea soldului restant al facturilor."""

    _attr_icon = "mdi:invoice-text-arrow-left"
    _attr_translation_key = "factura_restanta"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Factură restantă"
        self._attr_unique_id = f"{DOMAIN}_factura_restanta_{self._cod_incasare}"
        self._custom_entity_id = f"sensor.{DOMAIN}_{self._cod_incasare}_factura_restanta"

    @property
    def native_value(self):
        data = self.coordinator.data.get("invoices_unpaid") if self.coordinator.data else None
        if not data or not isinstance(data, list):
            return "Nu"
        return "Da" if any(item.get("issuedValue", 0) > 0 for item in data) else "Nu"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data.get("invoices_unpaid") if self.coordinator.data else None
        if not data or not isinstance(data, list):
            return {
                "Total neachitat": "0,00 lei",
                "Detalii": "Nu există facturi disponibile",
                "attribution": ATTRIBUTION,
            }

        attributes = {}
        total_sold = 0.0

        for idx, item in enumerate(data, start=1):
            issued_value = float(item.get("issuedValue", 0))
            balance_value = float(item.get("balanceValue", 0))
            display_value = issued_value if issued_value == balance_value else balance_value

            if display_value > 0:
                total_sold += display_value
                raw_date = item.get("maturityDate", "Necunoscut")
                try:
                    msg = format_invoice_due_message(display_value, raw_date)
                    attributes[f"Factură {idx}"] = msg
                except ValueError:
                    attributes[f"Factură {idx}"] = "Data scadenței necunoscută"

        attributes["Total neachitat"] = f"{format_ron(total_sold)} lei" if total_sold > 0 else "0,00 lei"
        attributes["attribution"] = ATTRIBUTION
        return attributes


# ──────────────────────────────────────────────
# FacturaProsumSensor
# ──────────────────────────────────────────────
class FacturaProsumSensor(EonRomaniaEntity):
    """Senzor pentru afișarea soldului restant al facturilor de prosumator."""

    _attr_icon = "mdi:invoice-text-arrow-left"
    _attr_translation_key = "factura_prosumator"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Factură restantă prosumator"
        self._attr_unique_id = f"{DOMAIN}_factura_prosumator_{self._cod_incasare}"
        self._custom_entity_id = f"sensor.{DOMAIN}_{self._cod_incasare}_factura_prosumator"

    @property
    def native_value(self):
        data = self.coordinator.data.get("invoices_prosum") if self.coordinator.data else None
        if not data or not isinstance(data, list):
            balance_data = self.coordinator.data.get("invoice_balance_prosum") if self.coordinator.data else None
            if balance_data and isinstance(balance_data, dict):
                balance = float(balance_data.get("balance", 0))
                return "Da" if balance > 0 else "Nu"
            return "Nu"
        return "Da" if any(float(item.get("issuedValue", 0)) > 0 for item in data) else "Nu"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data.get("invoices_prosum") if self.coordinator.data else None
        if not data or not isinstance(data, list):
            return {
                "Total neachitat": "0,00 lei",
                "Detalii": "Nu există facturi disponibile",
                "attribution": ATTRIBUTION,
            }

        attributes = {}
        total_sold = 0.0
        total_credit = 0.0

        for idx, item in enumerate(data, start=1):
            issued_value = float(item.get("issuedValue", 0))
            balance_value = float(item.get("balanceValue", 0))
            display_value = issued_value if issued_value == balance_value else balance_value
            raw_date = item.get("maturityDate", "Necunoscut")
            invoice_number = item.get("invoiceNumber", "N/A")
            invoice_type = item.get("type", "Necunoscut")

            try:
                if display_value > 0:
                    total_sold += display_value
                    msg = format_invoice_due_message(display_value, raw_date)
                    attributes[f"Factură {idx} ({invoice_number})"] = msg
                elif display_value < 0:
                    total_credit += abs(display_value)
                    msg = f"Credit de {format_ron(abs(display_value))} lei pentru {invoice_type.lower()} (scadentă {raw_date})"
                    attributes[f"Credit {idx} ({invoice_number})"] = msg
                else:
                    attributes[f"Factură {idx} ({invoice_number})"] = f"Fără sold (scadentă {raw_date})"
            except ValueError:
                if display_value > 0:
                    attributes[f"Factură {idx} ({invoice_number})"] = f"Datorie de {format_ron(display_value)} lei"
                elif display_value < 0:
                    attributes[f"Credit {idx} ({invoice_number})"] = f"Credit de {format_ron(abs(display_value))} lei"

        if total_sold > 0:
            attributes["Total datorie"] = f"{format_ron(total_sold)} lei"
        if total_credit > 0:
            attributes["Total credit"] = f"{format_ron(total_credit)} lei"
        attributes["Total neachitat"] = f"{format_ron(total_sold)} lei" if total_sold > 0 else "0,00 lei"
        attributes["attribution"] = ATTRIBUTION
        return attributes


# ──────────────────────────────────────────────
# ConventieConsumSensor
# ──────────────────────────────────────────────
class ConventieConsumSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor de convenție."""

    _attr_icon = "mdi:chart-bar"
    _attr_translation_key = "conventie_consum"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "Convenție consum"
        self._attr_unique_id = f"{DOMAIN}_conventie_consum_{self._cod_incasare}"
        self._custom_entity_id = f"sensor.{DOMAIN}_{self._cod_incasare}_conventie_consum"

    @property
    def native_value(self):
        is_collective = self.coordinator.data.get("is_collective", False) if self.coordinator.data else False

        if is_collective:
            return self._native_value_collective()
        return self._native_value_individual()

    def _native_value_individual(self):
        data = self.coordinator.data.get("consumption_convention") if self.coordinator.data else None
        if not data or not isinstance(data, list) or len(data) == 0:
            return "Nu"
        convention_line = data[0].get("conventionLine", {})
        months_with_values = sum(
            1 for key in convention_line
            if key.startswith("valueMonth") and convention_line.get(key, 0) > 0
        )
        return "Da" if months_with_values > 0 else "Nu"

    def _native_value_collective(self):
        conventions = self.coordinator.data.get("subcontracts_conventions") if self.coordinator.data else None
        if not conventions or not isinstance(conventions, dict):
            return "Nu"
        # "Da" dacă cel puțin un subcontract are convenție cu valori > 0
        for conv_data in conventions.values():
            if not isinstance(conv_data, list) or not conv_data:
                continue
            convention_line = conv_data[0].get("conventionLine", {})
            if any(
                convention_line.get(key, 0) > 0
                for key in convention_line
                if key.startswith("valueMonth")
            ):
                return "Da"
        return "Nu"

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}

        is_collective = self.coordinator.data.get("is_collective", False)

        if is_collective:
            return self._attributes_collective()
        return self._attributes_individual()

    def _attributes_individual(self):
        data = self.coordinator.data.get("consumption_convention") if self.coordinator.data else None
        if not data or not isinstance(data, list) or len(data) == 0:
            return {}
        convention_line = data[0].get("conventionLine", {})
        um = self.coordinator.data.get("um", "m3") if self.coordinator.data else "m3"
        is_gaz = um.lower().startswith("m")
        unit = "m³" if is_gaz else "kWh"
        attributes = {
            f"Convenție din luna {month}": f"{convention_line.get(key, 0)} {unit}"
            for key, month in CONVENTION_MONTH_MAPPING.items()
        }
        attributes["attribution"] = ATTRIBUTION
        return attributes

    def _attributes_collective(self):
        """Construiește atributele pentru contracte colective/DUO — convenții per subcontract."""
        conventions = self.coordinator.data.get("subcontracts_conventions")
        subcontracts = self.coordinator.data.get("subcontracts")
        if not conventions or not isinstance(conventions, dict):
            return {}

        attributes: dict[str, Any] = {}

        for sc_code, conv_data in conventions.items():
            if not isinstance(conv_data, list) or not conv_data:
                continue

            conv = conv_data[0]
            convention_line = conv.get("conventionLine", {})

            # Detectăm tipul utilității din subcontracte
            utility_label = sc_code
            if subcontracts and isinstance(subcontracts, list):
                for s in subcontracts:
                    if isinstance(s, dict) and s.get("accountContract") == sc_code:
                        ut = s.get("utilityType", "")
                        utility_label = UTILITY_TYPE_LABEL.get(ut, sc_code)
                        break

            # Detectăm unitatea de măsură din convenție (normalizată)
            um_raw = conv.get("unitMeasure", "")
            unit = UNIT_NORMALIZE.get(um_raw, um_raw) if um_raw else "m³"

            attributes[f"──── {utility_label} ────"] = ""

            for key, month in CONVENTION_MONTH_MAPPING.items():
                value = convention_line.get(key, 0)
                attributes[f"{utility_label} — {month}"] = f"{value} {unit}"

            # Date suplimentare convenție
            if conv.get("fromDate"):
                attributes[f"{utility_label} — Valabilă din"] = conv["fromDate"]

            if conv.get("validUntil"):
                attributes[f"{utility_label} — Valabilă până"] = conv["validUntil"]

            price_data = conv.get("accountContractPrice")
            if isinstance(price_data, dict):
                if price_data.get("contractualPrice") is not None:
                    attributes[f"{utility_label} — Preț contractual"] = f"{price_data['contractualPrice']} lei"
                if price_data.get("pcs") is not None:
                    attributes[f"{utility_label} — PCS"] = str(price_data["pcs"])

        attributes["attribution"] = ATTRIBUTION
        return attributes


# ──────────────────────────────────────────────
# ArhivaSensor
# ──────────────────────────────────────────────
class ArhivaSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor istorice ale consumului."""

    def __init__(self, coordinator, config_entry, year):
        super().__init__(coordinator, config_entry)
        self.year = year
        um = coordinator.data.get("um", "m3") if coordinator.data else "m3"
        is_gaz = um.lower().startswith("m")
        self._attr_name = f"{year} → Arhivă index gaz" if is_gaz else f"{year} → Arhivă index energie electrică"
        self._attr_icon = "mdi:clipboard-text-clock" if is_gaz else "mdi:clipboard-text-clock-outline"
        self._attr_translation_key = "arhiva_index_gaz" if is_gaz else "arhiva_index_energie_electrica"
        self._attr_unique_id = f"{DOMAIN}_arhiva_index_{self._cod_incasare}_{year}"
        self._custom_entity_id = (
            f"sensor.{DOMAIN}_{self._cod_incasare}_arhiva_index_gaz_{year}"
            if is_gaz
            else f"sensor.{DOMAIN}_{self._cod_incasare}_arhiva_index_energie_electrica_{year}"
        )

    @property
    def native_value(self):
        arhiva_data = self.coordinator.data.get("meter_history", {}) if self.coordinator.data else {}
        history_list = arhiva_data.get("history", [])
        year_data = next((y for y in history_list if y.get("year") == self.year), None)
        if not year_data:
            return None
        meters = year_data.get("meters", [])
        if not meters:
            return 0
        indexes = meters[0].get("indexes", [])
        if not indexes:
            return 0
        readings = indexes[0].get("readings", [])
        return len(readings)

    @property
    def extra_state_attributes(self):
        arhiva_data = self.coordinator.data.get("meter_history", {}) if self.coordinator.data else {}
        history_list = arhiva_data.get("history", [])
        year_data = next((y for y in history_list if y.get("year") == self.year), None)
        if not year_data:
            return {}
        unit = self.coordinator.data.get("um", "m3") if self.coordinator.data else "m3"
        attributes = {}
        readings_list = []
        for meter in year_data.get("meters", []):
            for index in meter.get("indexes", []):
                for reading in index.get("readings", []):
                    month_num = reading.get("month")
                    month_name = MONTHS_NUM_RO.get(month_num, "Necunoscut")
                    value = int(reading.get("value", 0))
                    reading_type_code = reading.get("readingType", "99")
                    reading_type_str = READING_TYPE_MAP.get(reading_type_code, "Necunoscut")
                    readings_list.append((month_num, reading_type_str, month_name, value))
        readings_list.sort(key=lambda r: r[0])
        for _, reading_type_str, month_name, value in readings_list:
            attributes[f"Index ({reading_type_str}) {month_name}"] = f"{value} {unit}"
        attributes["attribution"] = ATTRIBUTION
        return attributes


# ──────────────────────────────────────────────
# ArhivaPlatiSensor
# ──────────────────────────────────────────────
class ArhivaPlatiSensor(EonRomaniaEntity):
    """Senzor pentru afișarea istoricului plăților (grupat pe ani)."""

    _attr_icon = "mdi:cash-register"
    _attr_translation_key = "arhiva_plati"

    def __init__(self, coordinator, config_entry, year):
        super().__init__(coordinator, config_entry)
        self.year = year
        self._attr_name = f"{year} → Arhivă plăți"
        self._attr_unique_id = f"{DOMAIN}_arhiva_plati_{self._cod_incasare}_{year}"
        self._custom_entity_id = f"sensor.{DOMAIN}_{self._cod_incasare}_arhiva_plati_{year}"

    @property
    def native_value(self):
        return len(self._payments_for_year())

    @property
    def extra_state_attributes(self):
        attributes = {}
        payments_list = sorted(
            self._payments_for_year(),
            key=lambda p: int(p["paymentDate"][5:7]),
        )
        total_value = sum(p.get("value", 0) for p in payments_list)
        for idx, payment in enumerate(payments_list, start=1):
            raw_date = payment.get("paymentDate", "N/A")
            payment_value = payment.get("value", 0)
            if raw_date != "N/A":
                try:
                    parsed_date = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S")
                    month_name = MONTHS_NUM_RO.get(parsed_date.month, "necunoscut")
                except ValueError:
                    month_name = "necunoscut"
            else:
                month_name = "necunoscut"
            attributes[f"Plată {idx} factură luna {month_name}"] = f"{format_ron(payment_value)} lei"
        attributes["Plăți efectuate"] = len(payments_list)
        attributes["Sumă totală"] = f"{format_ron(total_value)} lei"
        attributes["attribution"] = ATTRIBUTION
        return attributes

    def _payments_for_year(self) -> list:
        all_payments = self.coordinator.data.get("payments", []) if self.coordinator.data else []
        return [p for p in all_payments if p.get("paymentDate", "").startswith(str(self.year))]



# ──────────────────────────────────────────────
# ArhivaComparareConsumAnualGraficSensor
# ──────────────────────────────────────────────
class ArhivaComparareConsumAnualGraficSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor istorice ale consumului."""

    def __init__(self, coordinator, config_entry, year, monthly_values):
        super().__init__(coordinator, config_entry)
        self._year = year
        self._monthly_values = monthly_values
        um = coordinator.data.get("um", "m3") if coordinator.data else "m3"
        is_gaz = um.lower().startswith("m")
        self._attr_name = f"{year} → Arhivă consum gaz" if is_gaz else f"{year} → Arhivă consum energie electrică"
        self._attr_icon = "mdi:chart-bar" if is_gaz else "mdi:lightning-bolt"
        self._attr_translation_key = "arhiva_consum_gaz" if is_gaz else "arhiva_consum_energie_electrica"
        self._attr_unique_id = f"{DOMAIN}_arhiva_consum_{self._cod_incasare}_{year}"
        self._custom_entity_id = (
            f"sensor.{DOMAIN}_{self._cod_incasare}_arhiva_consum_gaz_{year}"
            if is_gaz
            else f"sensor.{DOMAIN}_{self._cod_incasare}_arhiva_consum_energie_electrica_{year}"
        )

    @property
    def native_value(self):
        total = sum(v["consumptionValue"] for v in self._monthly_values.values())
        return round(total, 2)

    @property
    def native_unit_of_measurement(self):
        return None

    @property
    def extra_state_attributes(self):
        unit = self.coordinator.data.get("um", "m3") if self.coordinator.data else "m3"
        attributes = {"attribution": ATTRIBUTION}
        attributes.update(
            {
                f"Consum lunar {MONTHS_NUM_RO.get(int(month), 'necunoscut')}": f"{format_number_ro(value['consumptionValue'])} {unit}"
                for month, value in sorted(self._monthly_values.items(), key=lambda item: int(item[0]))
            }
        )
        attributes["────"] = ""
        attributes.update(
            {
                f"Consum mediu zilnic în {MONTHS_NUM_RO.get(int(month), 'necunoscut')}": f"{format_number_ro(value['consumptionValueDayValue'])} {unit}"
                for month, value in sorted(self._monthly_values.items(), key=lambda item: int(item[0]))
            }
        )
        return attributes
