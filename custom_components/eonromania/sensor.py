"""Platforma Sensor pentru E·ON România."""

import logging
from collections import defaultdict
from datetime import datetime

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
    MONTHS_EN_RO,
    MONTHS_NUM_RO,
    READING_TYPE_MAP,
    INVOICE_BALANCE_KEY_MAP,
    INVOICE_BALANCE_MONEY_KEYS,
    format_ron,
    format_number_ro,
    build_address_consum,
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

    # ── 1. Senzori de bază (mereu prezenți) ──
    sensors.append(ContractDetailsSensor(coordinator, config_entry))
    sensors.append(ConventieConsumSensor(coordinator, config_entry))
    sensors.append(FacturaRestantaSensor(coordinator, config_entry))
    sensors.append(FacturaProsumSensor(coordinator, config_entry))
    sensors.append(InvoiceBalanceSensor(coordinator, config_entry))
    sensors.append(InvoiceBalanceProsumSensor(coordinator, config_entry))

    # ── 2. Senzori condiționali (date disponibile) ──
    if coordinator.data:
        if coordinator.data.get("rescheduling_plans"):
            sensors.append(ReschedulingPlansSensor(coordinator, config_entry))

        pass  # placeholder for future conditional sensors

    # ── 3. CitireIndexSensor + CitirePermisaSensor (per dispozitiv) ──
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

    # ── 4. ArhivaSensor (per an) ──
    arhiva_data = coordinator.data.get("meter_history") if coordinator.data else None
    if arhiva_data:
        history_list = arhiva_data.get("history", [])
        for item in history_list:
            year = item.get("year")
            if year:
                sensors.append(ArhivaSensor(coordinator, config_entry, year))

    # ── 5. ArhivaPlatiSensor (per an) ──
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
        for year in payments_by_year:
            sensors.append(ArhivaPlatiSensor(coordinator, config_entry, year))

    # ── 6. ArhivaComparareConsumAnualGraficSensor (per an) ──
    comparareanualagrafic_data = coordinator.data.get("graphic_consumption", {}) if coordinator.data else {}
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
        for year, monthly_values in cleaned_yearly_data.items():
            sensors.append(ArhivaComparareConsumAnualGraficSensor(coordinator, config_entry, year, monthly_values))

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
        data = self.coordinator.data.get("contract_details") if self.coordinator.data else None
        if not isinstance(data, dict):
            return {}

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
        if not data:
            return None
        if isinstance(data, dict):
            balance = data.get("balance", data.get("total", data.get("totalBalance")))
            if balance is not None:
                return round(float(balance), 2)
        return None

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
            return None
        balance = data.get("balance", 0)
        return round(float(balance), 2) if balance else 0

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


# ──────────────────────────────────────────────
# CitireIndexSensor
# ──────────────────────────────────────────────
class CitireIndexSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor despre indexul curent."""

    def __init__(self, coordinator, config_entry, device_number):
        super().__init__(coordinator, config_entry)
        self.device_number = device_number

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
        um = self.coordinator.data.get("um", "m3") if self.coordinator.data else "m3"
        return UnitOfVolume.CUBIC_METERS if um.lower().startswith("m") else UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self):
        citireindex_data = self.coordinator.data.get("meter_index") if self.coordinator.data else None
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
        citireindex_data = self.coordinator.data.get("meter_index") if self.coordinator.data else None
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

    def __init__(self, coordinator, config_entry, device_number):
        super().__init__(coordinator, config_entry)
        self.device_number = device_number
        self._attr_name = "Citire permisă"
        self._attr_unique_id = f"{DOMAIN}_citire_permisa_{self._cod_incasare}"
        self._custom_entity_id = f"sensor.{DOMAIN}_{self._cod_incasare}_citire_permisa"

    @property
    def native_value(self):
        citireindex_data = self.coordinator.data.get("meter_index") if self.coordinator.data else None
        if not citireindex_data:
            return "Nu"

        reading_period = citireindex_data.get("readingPeriod", {})
        index_details = citireindex_data.get("indexDetails", {})
        devices = index_details.get("devices", [])

        if not devices:
            return "Nu"

        start_date_str = reading_period.get("startDate")
        can_be_changed_till_str = None
        if devices:
            indexes = devices[0].get("indexes", [])
            if indexes:
                can_be_changed_till_str = indexes[0].get("canBeChangedTill")

        try:
            today = dt_util.now().replace(tzinfo=None)
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else None
            can_be_changed_till = (
                datetime.strptime(can_be_changed_till_str, "%Y-%m-%d %H:%M:%S")
                if can_be_changed_till_str
                else None
            )
            if start_date and can_be_changed_till:
                if today < start_date:
                    return "Nu"
                if start_date <= today <= can_be_changed_till:
                    return "Da"
                return "Nu"
            return "Nu"
        except Exception as e:
            _LOGGER.exception(
                "Eroare la determinarea stării CitirePermisa (contract=%s): %s",
                self._cod_incasare, e,
            )
            return "Eroare"

    @property
    def extra_state_attributes(self):
        citireindex_data = self.coordinator.data.get("meter_index") if self.coordinator.data else None
        if not citireindex_data:
            return {}
        index_details = citireindex_data.get("indexDetails", {})
        devices = index_details.get("devices", [])
        if not devices:
            return {"În curs de actualizare": ""}
        for dev in devices:
            if dev.get("deviceNumber") == self.device_number:
                indexes = dev.get("indexes", [{}])[0]
                can_be_changed_till = indexes.get("canBeChangedTill")
                return {
                    "ID intern citire contor (SAP)": indexes.get("ablbelnr", "Necunoscut"),
                    "Indexul poate fi trimis până la": can_be_changed_till or "Perioada nu a fost stabilită",
                    "Cod încasare": self._cod_incasare,
                }
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
                    parsed_date = datetime.strptime(raw_date, "%d.%m.%Y")
                    month_name_en = parsed_date.strftime("%B")
                    month_name_ro = MONTHS_EN_RO.get(month_name_en, "necunoscut")
                    days_until_due = (parsed_date.date() - dt_util.now().date()).days
                    if days_until_due < 0:
                        day_unit = "zi" if abs(days_until_due) == 1 else "zile"
                        msg = f"Restanță de {format_ron(display_value)} lei, termen depășit cu {abs(days_until_due)} {day_unit}"
                    elif days_until_due == 0:
                        msg = f"De achitat astăzi, {dt_util.now().strftime('%d.%m.%Y')}: {format_ron(display_value)} lei"
                    else:
                        day_unit = "zi" if days_until_due == 1 else "zile"
                        msg = f"Următoarea sumă de {format_ron(display_value)} lei este scadentă pe luna {month_name_ro} ({days_until_due} {day_unit})"
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
                parsed_date = datetime.strptime(raw_date, "%d.%m.%Y")
                month_name_en = parsed_date.strftime("%B")
                month_name_ro = MONTHS_EN_RO.get(month_name_en, "necunoscut")

                if display_value > 0:
                    total_sold += display_value
                    days_until_due = (parsed_date.date() - dt_util.now().date()).days
                    if days_until_due < 0:
                        day_unit = "zi" if abs(days_until_due) == 1 else "zile"
                        msg = f"Restanță de {format_ron(display_value)} lei, termen depășit cu {abs(days_until_due)} {day_unit}"
                    elif days_until_due == 0:
                        msg = f"De achitat astăzi: {format_ron(display_value)} lei"
                    else:
                        day_unit = "zi" if days_until_due == 1 else "zile"
                        msg = f"Sumă de {format_ron(display_value)} lei scadentă pe {month_name_ro} ({days_until_due} {day_unit})"
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
        data = self.coordinator.data.get("consumption_convention") if self.coordinator.data else None
        if not data or not isinstance(data, list) or len(data) == 0:
            return "Nu"
        convention_line = data[0].get("conventionLine", {})
        months_with_values = sum(
            1 for key in convention_line
            if key.startswith("valueMonth") and convention_line.get(key, 0) > 0
        )
        return "Da" if months_with_values > 0 else "Nu"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data.get("consumption_convention") if self.coordinator.data else None
        if not data or not isinstance(data, list) or len(data) == 0:
            return {}
        convention_line = data[0].get("conventionLine", {})
        um = self.coordinator.data.get("um", "m3") if self.coordinator.data else "m3"
        is_gaz = um.lower().startswith("m")
        unit = "m3" if is_gaz else "kWh"
        month_mapping = {
            "valueMonth1": "ianuarie", "valueMonth2": "februarie", "valueMonth3": "martie",
            "valueMonth4": "aprilie", "valueMonth5": "mai", "valueMonth6": "iunie",
            "valueMonth7": "iulie", "valueMonth8": "august", "valueMonth9": "septembrie",
            "valueMonth10": "octombrie", "valueMonth11": "noiembrie", "valueMonth12": "decembrie",
        }
        attributes = {
            f"Convenție din luna {month}": f"{convention_line.get(key, 0)} {unit}"
            for key, month in month_mapping.items()
        }
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
        month_names = [
            "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
            "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
        ]
        unit = self.coordinator.data.get("um", "m3") if self.coordinator.data else "m3"
        attributes = {"attribution": ATTRIBUTION}
        attributes.update(
            {
                f"Consum lunar {month_names[int(month) - 1]}": f"{format_number_ro(value['consumptionValue'])} {unit}"
                for month, value in sorted(self._monthly_values.items(), key=lambda item: int(item[0]))
            }
        )
        attributes["────"] = ""
        attributes.update(
            {
                f"Consum mediu zilnic în {month_names[int(month) - 1]}": f"{format_number_ro(value['consumptionValueDayValue'])} {unit}"
                for month, value in sorted(self._monthly_values.items(), key=lambda item: int(item[0]))
            }
        )
        return attributes
