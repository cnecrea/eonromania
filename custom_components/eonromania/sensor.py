"""Platforma Sensor pentru E·ON România."""

import logging
from collections import defaultdict
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ATTRIBUTION
from .coordinator import EonRomaniaCoordinator

_LOGGER = logging.getLogger(__name__)

# Mapping luni EN -> RO (pentru FacturaRestantaSensor)
MONTHS_EN_RO = {
    "January": "ianuarie",
    "February": "februarie",
    "March": "martie",
    "April": "aprilie",
    "May": "mai",
    "June": "iunie",
    "July": "iulie",
    "August": "august",
    "September": "septembrie",
    "October": "octombrie",
    "November": "noiembrie",
    "December": "decembrie",
}

# Mapping luni numeric -> RO
MONTHS_NUM_RO = {
    1: "ianuarie",
    2: "februarie",
    3: "martie",
    4: "aprilie",
    5: "mai",
    6: "iunie",
    7: "iulie",
    8: "august",
    9: "septembrie",
    10: "octombrie",
    11: "noiembrie",
    12: "decembrie",
}

# Mapping tipuri citire
READING_TYPE_MAP = {
    "01": "citit distribuitor",
    "02": "autocitit",
    "03": "estimat",
}


def format_ron(value: float) -> str:
    """Formatează o valoare numerică în format românesc (1.234,56)."""
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------------
# Clasă de bază pentru toate entitățile E·ON România
# ------------------------------------------------------------------------
class EonRomaniaEntity(CoordinatorEntity[EonRomaniaCoordinator], SensorEntity):
    """Clasă de bază pentru entitățile E·ON România."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EonRomaniaCoordinator, config_entry: ConfigEntry):
        """Inițializare cu coordinator și config_entry."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._cod_incasare = config_entry.data["cod_incasare"]

    @property
    def device_info(self) -> DeviceInfo:
        """Returnează informațiile despre dispozitiv — comun tuturor entităților."""
        # IMPORTANT: NU include adresa în numele device-ului.
        # Dacă incluzi adresa aici, Home Assistant îți va lungi entity_id-urile.
        return DeviceInfo(
            identifiers={(DOMAIN, self._cod_incasare)},
            name=f"E·ON România ({self._cod_incasare})",
            manufacturer="Ciprian Nicolae (cnecrea)",
            model="E·ON România",
            entry_type=DeviceEntryType.SERVICE,
        )


# ------------------------------------------------------------------------
# async_setup_entry
# ------------------------------------------------------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """Configurează senzorii pentru intrarea dată (config_entry)."""
    coordinator: EonRomaniaCoordinator = config_entry.runtime_data.coordinator
    cod_incasare = config_entry.data.get("cod_incasare", "")

    sensors: list[SensorEntity] = []

    _LOGGER.debug(
        "Inițializare platforma sensor pentru %s (entry_id=%s, contract=%s).",
        DOMAIN,
        config_entry.entry_id,
        cod_incasare,
    )

    # 1. Senzori de bază
    sensors.append(DateContractSensor(coordinator, config_entry))
    sensors.append(ConventieConsumSensor(coordinator, config_entry))
    sensors.append(FacturaRestantaSensor(coordinator, config_entry))
    sensors.append(FacturaProsumSensor(coordinator, config_entry))

    # 2. CitireIndexSensor și CitirePermisaSensor
    citireindex_data = coordinator.data.get("citireindex") if coordinator.data else None
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
                _LOGGER.warning(
                    "Dispozitiv duplicat ignorat (contract=%s): %s",
                    cod_incasare,
                    device_number,
                )

        if not devices:
            _LOGGER.info(
                "Nu există dispozitive în citireindex_data; se adaugă senzori fără device_number (contract=%s).",
                cod_incasare,
            )
            sensors.append(CitireIndexSensor(coordinator, config_entry, device_number=None))
            sensors.append(CitirePermisaSensor(coordinator, config_entry, device_number=None))

    # 3. ArhivaSensor
    arhiva_data = coordinator.data.get("arhiva") if coordinator.data else None
    if arhiva_data:
        history_list = arhiva_data.get("history", [])
        for item in history_list:
            year = item.get("year")
            if year:
                sensors.append(ArhivaSensor(coordinator, config_entry, year))

    # 4. ArhivaPlatiSensor (plăți grupate pe ani)
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

    # 5. ArhivaComparareConsumAnualGraficSensor
    comparareanualagrafic_data = coordinator.data.get("comparareanualagrafic", {}) if coordinator.data else {}
    if isinstance(comparareanualagrafic_data, dict) and "consumption" in comparareanualagrafic_data:
        yearly_data: dict[int, dict] = defaultdict(dict)

        for item in comparareanualagrafic_data["consumption"]:
            year = item.get("year")
            month = item.get("month")
            consumption_value = item.get("consumptionValue")
            consumption_day_value = item.get("consumptionValueDayValue")

            if (
                not year
                or not month
                or consumption_value is None
                or consumption_day_value is None
            ):
                _LOGGER.warning(
                    "Intrare invalidă în comparareanualagrafic (contract=%s): %s",
                    cod_incasare,
                    item,
                )
                continue

            yearly_data[year][month] = {
                "consumptionValue": consumption_value,
                "consumptionValueDayValue": consumption_day_value,
            }

        # Eliminăm anii cu consum zero pe toate lunile
        cleaned_yearly_data = {
            year: monthly_values
            for year, monthly_values in yearly_data.items()
            if any(
                v["consumptionValue"] > 0 or v["consumptionValueDayValue"] > 0
                for v in monthly_values.values()
            )
        }

        for year, monthly_values in cleaned_yearly_data.items():
            sensors.append(
                ArhivaComparareConsumAnualGraficSensor(
                    coordinator, config_entry, year, monthly_values
                )
            )

    _LOGGER.debug(
        "Se adaugă %s senzori pentru %s (entry_id=%s, contract=%s).",
        len(sensors),
        DOMAIN,
        config_entry.entry_id,
        cod_incasare,
    )

    # 6. Înregistrăm senzorii
    async_add_entities(sensors)


# ------------------------------------------------------------------------
# DateContractSensor
# ------------------------------------------------------------------------
class DateContractSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor contractului."""

    _attr_icon = "mdi:file-document-edit-outline"
    _attr_translation_key = "date_contract"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{DOMAIN}_date_contract_{config_entry.entry_id}"
        self._attr_name = "Date contract"

    @property
    def native_value(self):
        """Returnează starea senzorului."""
        data = self.coordinator.data.get("dateuser") if self.coordinator.data else None
        if not data:
            return None
        return data.get("accountContract")

    @property
    def extra_state_attributes(self):
        """Atribute adiționale."""
        data = self.coordinator.data.get("dateuser") if self.coordinator.data else None
        if not data:
            return {}

        attributes = {
            "Cod încasare": data.get("accountContract"),
            "Cod loc de consum (NLC)": data.get("consumptionPointCode"),
            "CLC - Cod punct de măsură": data.get("pod"),
            "Operator de Distribuție (OD)": data.get("distributorName"),
            "Preț final (fără TVA)": f"{data.get('supplierAndDistributionPrice', {}).get('contractualPrice')} lei",
            "Preț final (cu TVA)": f"{data.get('supplierAndDistributionPrice', {}).get('contractualPriceWithVat')} lei",
            "Preț furnizare": f"{data.get('supplierAndDistributionPrice', {}).get('priceComponents', {}).get('supplierPrice')} lei/kWh",
            "Tarif reglementat distribuție": f"{data.get('supplierAndDistributionPrice', {}).get('priceComponents', {}).get('distributionPrice')} lei/kWh",
            "Tarif reglementat transport": f"{data.get('supplierAndDistributionPrice', {}).get('priceComponents', {}).get('transportPrice')} lei/kWh",
            "PCS": str(data.get("supplierAndDistributionPrice", {}).get("pcs")),
        }

        address_obj = data.get("consumptionPointAddress", {})
        street_obj = address_obj.get("street", {})
        street_type = street_obj.get("streetType", {}).get("label")
        street_name = street_obj.get("streetName")
        street_no = address_obj.get("streetNumber")
        apartment = address_obj.get("apartment")
        locality_name = address_obj.get("locality", {}).get("localityName")

        full_address = f"{street_type} {street_name} {street_no} ap. {apartment}, {locality_name}"
        attributes["Adresă consum"] = full_address

        attributes["Următoarea verificare a instalației"] = data.get("verificationExpirationDate")
        attributes["Data inițierii reviziei"] = data.get("revisionStartDate")
        attributes["Următoarea revizie tehnică"] = data.get("revisionExpirationDate")

        attributes["attribution"] = ATTRIBUTION
        return attributes


# ------------------------------------------------------------------------
# CitireIndexSensor
# ------------------------------------------------------------------------
class CitireIndexSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor despre indexul curent."""

    _attr_icon = "mdi:gauge"
    _attr_translation_key = "index_curent"

    def __init__(self, coordinator, config_entry, device_number):
        super().__init__(coordinator, config_entry)
        self.device_number = device_number

        # IMPORTANT: unique_id trebuie să fie unic pe device_number
        suffix = str(device_number) if device_number is not None else "none"
        self._attr_unique_id = f"{DOMAIN}_index_curent_{config_entry.entry_id}_{suffix}"
        self._attr_name = "Index curent"

    @property
    def native_value(self):
        """Returnează starea senzorului."""
        citireindex_data = self.coordinator.data.get("citireindex") if self.coordinator.data else None
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
        """Returnează atributele suplimentare ale senzorului."""
        citireindex_data = self.coordinator.data.get("citireindex") if self.coordinator.data else None
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
                    reading_type_labels = {
                        "01": "Citire distribuitor",
                        "02": "Autocitire",
                        "03": "Estimare",
                    }
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


# ------------------------------------------------------------------------
# CitirePermisaSensor
# ------------------------------------------------------------------------
class CitirePermisaSensor(EonRomaniaEntity):
    """Senzor pentru verificarea permisiunii de citire a indexului."""

    _attr_translation_key = "citire_permisa"

    def __init__(self, coordinator, config_entry, device_number):
        super().__init__(coordinator, config_entry)
        self.device_number = device_number

        # IMPORTANT: unique_id trebuie să fie unic pe device_number
        suffix = str(device_number) if device_number is not None else "none"
        self._attr_unique_id = f"{DOMAIN}_citire_permisa_{config_entry.entry_id}_{suffix}"
        self._attr_name = "Citire permisă"

    @property
    def native_value(self):
        """Determină starea senzorului în funcție de datele curente."""
        citireindex_data = self.coordinator.data.get("citireindex") if self.coordinator.data else None
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
            today = datetime.now()
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
                "Eroare la determinarea stării senzorului CitirePermisa (contract=%s, device_number=%s): %s",
                self._cod_incasare,
                self.device_number,
                e,
            )
            return "Eroare"

    @property
    def extra_state_attributes(self):
        """Afișează informații suplimentare despre senzor."""
        citireindex_data = self.coordinator.data.get("citireindex") if self.coordinator.data else None
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
        """Returnează iconița în funcție de starea senzorului."""
        value = self.native_value
        if value == "Da":
            return "mdi:clock-check-outline"
        if value == "Nu":
            return "mdi:clock-alert-outline"
        return "mdi:cog-stop-outline"


# ------------------------------------------------------------------------
# FacturaRestantaSensor
# ------------------------------------------------------------------------
class FacturaRestantaSensor(EonRomaniaEntity):
    """Senzor pentru afișarea soldului restant al facturilor."""

    _attr_icon = "mdi:invoice-text-arrow-left"
    _attr_translation_key = "factura_restanta"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{DOMAIN}_factura_restanta_{config_entry.entry_id}"
        self._attr_name = "Factură restantă"

    @property
    def native_value(self):
        """Returnează starea principală (Da/Nu)."""
        data = self.coordinator.data.get("facturasold") if self.coordinator.data else None
        if not data or not isinstance(data, list):
            return "Nu"
        return "Da" if any(item.get("issuedValue", 0) > 0 for item in data) else "Nu"

    @property
    def extra_state_attributes(self):
        """Atribute adiționale."""
        data = self.coordinator.data.get("facturasold") if self.coordinator.data else None
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

                    days_until_due = (parsed_date - datetime.now()).days
                    if days_until_due < 0:
                        day_unit = "zi" if abs(days_until_due) == 1 else "zile"
                        msg = (
                            f"Restanță de {format_ron(display_value)} lei, termen depășit cu "
                            f"{abs(days_until_due)} {day_unit}"
                        )
                    elif days_until_due == 0:
                        msg = (
                            f"De achitat astăzi, {datetime.now().strftime('%d.%m.%Y')}: "
                            f"{format_ron(display_value)} lei"
                        )
                    else:
                        day_unit = "zi" if days_until_due == 1 else "zile"
                        msg = (
                            f"Următoarea sumă de {format_ron(display_value)} lei este scadentă "
                            f"pe luna {month_name_ro} ({days_until_due} {day_unit})"
                        )

                    attributes[f"Factură {idx}"] = msg

                except ValueError:
                    attributes[f"Factură {idx}"] = "Data scadenței necunoscută"

        attributes["---------------"] = ""
        attributes["Total neachitat"] = f"{format_ron(total_sold)} lei" if total_sold > 0 else "0,00 lei"
        attributes["attribution"] = ATTRIBUTION

        return attributes




# ------------------------------------------------------------------------
# FacturaProsumSensor
# ------------------------------------------------------------------------
class FacturaProsumSensor(EonRomaniaEntity):
    """Senzor pentru afișarea soldului restant al facturilor de prosumator."""

    _attr_icon = "mdi:invoice-text-arrow-left"
    _attr_translation_key = "factura_prosum"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{DOMAIN}_factura_prosum_{config_entry.entry_id}"
        self._attr_name = "Factură restantă prosumator"

    @property
    def native_value(self):
        """Returnează starea principală (Da/Nu)."""
        data = self.coordinator.data.get("facturasold_prosum") if self.coordinator.data else None
        if not data or not isinstance(data, list):
            # Dacă lista de facturi nu există, verificăm balance-ul
            balance_data = self.coordinator.data.get("facturasold_prosum_balance") if self.coordinator.data else None
            if balance_data and isinstance(balance_data, dict):
                balance = float(balance_data.get("balance", 0))
                # Pentru prosumatori, balance pozitiv = datorie, balance negativ = credit
                return "Da" if balance > 0 else "Nu"
            return "Nu"
        # Verificăm dacă există cel puțin o factură cu valoare pozitivă (datorie)
        return "Da" if any(float(item.get("issuedValue", 0)) > 0 for item in data) else "Nu"

    @property
    def extra_state_attributes(self):
        """Atribute adiționale."""
        data = self.coordinator.data.get("facturasold_prosum") if self.coordinator.data else None
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

            # Determinăm valoarea care trebuie afișată
            display_value = issued_value if issued_value == balance_value else balance_value

            raw_date = item.get("maturityDate", "Necunoscut")
            invoice_number = item.get("invoiceNumber", "N/A")
            invoice_type = item.get("type", "Necunoscut")

            try:
                parsed_date = datetime.strptime(raw_date, "%d.%m.%Y")
                month_name_en = parsed_date.strftime("%B")
                month_name_ro = MONTHS_EN_RO.get(month_name_en, "necunoscut")

                if display_value > 0:
                    # Datorie (valoare pozitivă)
                    total_sold += display_value
                    days_until_due = (parsed_date - datetime.now()).days
                    if days_until_due < 0:
                        day_unit = "zi" if abs(days_until_due) == 1 else "zile"
                        msg = (
                            f"Restanță de {format_ron(display_value)} lei, termen depășit cu "
                            f"{abs(days_until_due)} {day_unit}"
                        )
                    elif days_until_due == 0:
                        msg = (
                            f"De achitat astăzi, {datetime.now().strftime('%d.%m.%Y')}: "
                            f"{format_ron(display_value)} lei"
                        )
                    else:
                        day_unit = "zi" if days_until_due == 1 else "zile"
                        msg = (
                            f"Următoarea sumă de {format_ron(display_value)} lei este scadentă "
                            f"pe luna {month_name_ro} ({days_until_due} {day_unit})"
                        )
                    attributes[f"Factură {idx} ({invoice_number})"] = msg
                elif display_value < 0:
                    # Credit (valoare negativă — prosumatorul a produs mai mult)
                    total_credit += abs(display_value)
                    msg = (
                        f"Credit de {format_ron(abs(display_value))} lei pentru {invoice_type.lower()} "
                        f"(scadentă {raw_date})"
                    )
                    attributes[f"Credit {idx} ({invoice_number})"] = msg
                else:
                    # Valoare zero
                    attributes[f"Factură {idx} ({invoice_number})"] = f"Fără sold (scadentă {raw_date})"

            except ValueError:
                if display_value > 0:
                    attributes[f"Factură {idx} ({invoice_number})"] = (
                        f"Datorie de {format_ron(display_value)} lei (data necunoscută)"
                    )
                elif display_value < 0:
                    attributes[f"Credit {idx} ({invoice_number})"] = (
                        f"Credit de {format_ron(abs(display_value))} lei (data necunoscută)"
                    )

        # Adăugăm informații despre balance-ul de prosumator dacă există
        balance_data = self.coordinator.data.get("facturasold_prosum_balance") if self.coordinator.data else None
        if balance_data and isinstance(balance_data, dict):
            balance = float(balance_data.get("balance", 0))
            refund = balance_data.get("refund", False)
            refund_in_process = balance_data.get("refundInProcess", False)
            balance_date = balance_data.get("date", "Necunoscut")

            if balance != 0:
                if balance > 0:
                    attributes["Sold total prosumator"] = f"{format_ron(balance)} lei (datorie)"
                else:
                    attributes["Sold total prosumator"] = f"{format_ron(abs(balance))} lei (credit)"
                    if refund:
                        attributes["Rambursare disponibilă"] = "Da"
                    if refund_in_process:
                        attributes["Rambursare în proces"] = "Da"
                attributes["Data sold"] = balance_date

        attributes["---------------"] = ""
        if total_sold > 0:
            attributes["Total datorie"] = f"{format_ron(total_sold)} lei"
        if total_credit > 0:
            attributes["Total credit"] = f"{format_ron(total_credit)} lei"
        attributes["Total neachitat"] = f"{format_ron(total_sold)} lei" if total_sold > 0 else "0,00 lei"
        attributes["attribution"] = ATTRIBUTION

        return attributes


# ------------------------------------------------------------------------
# ConventieConsumSensor
# ------------------------------------------------------------------------
class ConventieConsumSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor de convenție."""

    _attr_icon = "mdi:chart-bar"
    _attr_translation_key = "conventie_consum"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{DOMAIN}_conventie_consum_{config_entry.entry_id}"
        self._attr_name = "Convenție consum"

    @property
    def native_value(self):
        """Returnează starea senzorului."""
        data = self.coordinator.data.get("conventieconsum") if self.coordinator.data else None
        if not data or not isinstance(data, list) or len(data) == 0:
            return None

        convention_line = data[0].get("conventionLine", {})

        months_with_values = sum(
            1
            for key in convention_line
            if key.startswith("valueMonth") and convention_line.get(key, 0) > 0
        )

        return months_with_values

    @property
    def extra_state_attributes(self):
        """Atribute adiționale."""
        data = self.coordinator.data.get("conventieconsum") if self.coordinator.data else None
        if not data or not isinstance(data, list) or len(data) == 0:
            return {}

        convention_line = data[0].get("conventionLine", {})

        month_mapping = {
            "valueMonth1": "ianuarie",
            "valueMonth2": "februarie",
            "valueMonth3": "martie",
            "valueMonth4": "aprilie",
            "valueMonth5": "mai",
            "valueMonth6": "iunie",
            "valueMonth7": "iulie",
            "valueMonth8": "august",
            "valueMonth9": "septembrie",
            "valueMonth10": "octombrie",
            "valueMonth11": "noiembrie",
            "valueMonth12": "decembrie",
        }

        attributes = {
            f"Convenție din luna {month}": f"{convention_line.get(key, 0)} mc"
            for key, month in month_mapping.items()
        }

        attributes["attribution"] = ATTRIBUTION
        return attributes


# ------------------------------------------------------------------------
# ArhivaSensor
# ------------------------------------------------------------------------
class ArhivaSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor istorice ale consumului."""

    _attr_icon = "mdi:clipboard-text-clock"
    _attr_translation_key = "arhiva_index"

    def __init__(self, coordinator, config_entry, year):
        super().__init__(coordinator, config_entry)
        self.year = year
        self._attr_unique_id = f"{DOMAIN}_arhiva_index_{config_entry.entry_id}_{year}"
        self._attr_name = f"Arhivă index · {year}"

    @property
    def native_value(self):
        """Returnează numărul lunilor disponibile în arhivă pentru anul respectiv."""
        arhiva_data = self.coordinator.data.get("arhiva", {}) if self.coordinator.data else {}
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
        """Afișează indexul și metoda de citire pentru fiecare lună."""
        arhiva_data = self.coordinator.data.get("arhiva", {}) if self.coordinator.data else {}
        history_list = arhiva_data.get("history", [])
        year_data = next((y for y in history_list if y.get("year") == self.year), None)

        if not year_data:
            return {}

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
            attributes[f"Index ({reading_type_str}) {month_name}"] = value

        attributes["attribution"] = ATTRIBUTION
        return attributes


# ------------------------------------------------------------------------
# ArhivaPlatiSensor
# ------------------------------------------------------------------------
class ArhivaPlatiSensor(EonRomaniaEntity):
    """Senzor pentru afișarea istoricului plăților (grupat pe ani)."""

    _attr_icon = "mdi:cash-register"
    _attr_translation_key = "arhiva_plati"

    def __init__(self, coordinator, config_entry, year):
        super().__init__(coordinator, config_entry)
        self.year = year
        self._attr_unique_id = f"{DOMAIN}_arhiva_plati_{config_entry.entry_id}_{year}"
        self._attr_name = f"Arhivă plăți · {year}"

    @property
    def native_value(self):
        """Returnează numărul de plăți din anul respectiv."""
        return len(self._payments_for_year())

    @property
    def extra_state_attributes(self):
        """Afișează plățile grupate pe lună."""
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

        attributes["---------------"] = ""
        attributes["Plăți efectuate"] = len(payments_list)
        attributes["Sumă totală"] = f"{format_ron(total_value)} lei"
        attributes["attribution"] = ATTRIBUTION
        return attributes

    def _payments_for_year(self) -> list:
        """Filtrează plățile pentru anul curent."""
        all_payments = self.coordinator.data.get("payments", []) if self.coordinator.data else []
        return [p for p in all_payments if p.get("paymentDate", "").startswith(str(self.year))]


# ------------------------------------------------------------------------
# ArhivaComparareConsumAnualGraficSensor
# ------------------------------------------------------------------------
class ArhivaComparareConsumAnualGraficSensor(EonRomaniaEntity):
    """Senzor pentru afișarea datelor istorice ale consumului."""

    _attr_icon = "mdi:chart-bar"
    _attr_translation_key = "arhiva_consum"

    def __init__(self, coordinator, config_entry, year, monthly_values):
        super().__init__(coordinator, config_entry)
        self._year = year
        self._monthly_values = monthly_values
        self._attr_unique_id = f"{DOMAIN}_arhiva_consum_{config_entry.entry_id}_{year}"
        self._attr_name = f"Arhivă consum · {year}"

    @property
    def native_value(self):
        """Returnează consumul total anual cu unitatea din JSON."""
        unit = self.coordinator.data.get("um", "m3") if self.coordinator.data else "m3"
        total = sum(v["consumptionValue"] for v in self._monthly_values.values())
        return f"{total} {unit}"

    @property
    def native_unit_of_measurement(self):
        """Nu setăm o unitate de măsură, astfel încât să nu se genereze grafic."""
        return None

    @property
    def extra_state_attributes(self):
        """Returnează valorile lunare și atribuția."""
        month_names = [
            "ianuarie",
            "februarie",
            "martie",
            "aprilie",
            "mai",
            "iunie",
            "iulie",
            "august",
            "septembrie",
            "octombrie",
            "noiembrie",
            "decembrie",
        ]

        unit = self.coordinator.data.get("um", "m3") if self.coordinator.data else "m3"
        attributes = {"attribution": ATTRIBUTION}

        # Consumul lunar
        attributes.update(
            {
                f"Consum lunar {month_names[int(month) - 1]}": f"{value['consumptionValue']} {unit}"
                for month, value in sorted(self._monthly_values.items(), key=lambda item: int(item[0]))
            }
        )

        attributes["----"] = ""

        # Consumul mediu zilnic
        attributes.update(
            {
                f"Consum mediu zilnic în {month_names[int(month) - 1]}": f"{value['consumptionValueDayValue']} {unit}"
                for month, value in sorted(self._monthly_values.items(), key=lambda item: int(item[0]))
            }
        )

        return attributes
