"""Platforma Sensor pentru EON România."""
import logging
from datetime import datetime
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, ATTRIBUTION

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """
    Configurează senzorii pentru intrarea dată (config_entry).
    
    Pașii generali:
      1. Obținem coordinatorul din hass.data (include datele din API).
      2. Creăm lista locală `sensors`.
      3. Adăugăm senzorii de bază (DateContractSensor, FacturaRestantaSensor).
      4. Identificăm dispozitivele din citireindex_data și creăm senzorii CitireIndexSensor.
      5. Identificăm anii din arhiva_data și creăm senzorii ArhivaSensor.
      6. Identificăm toate plățile (payments), le grupăm pe ani și creăm senzorii PaymentsHistorySensor.
      7. Apelăm `async_add_entities` pentru a înregistra senzorii în Home Assistant.
    """

    # 1. Obține coordinatorul și orice alte date necesare
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]

    # 2. Creăm lista locală de senzori
    sensors = []

    # 3. Adăugăm senzorii de bază
    sensors.append(DateContractSensor(coordinator, config_entry))
    sensors.append(FacturaRestantaSensor(coordinator, config_entry))

    # 4. Gestionăm CitireIndexSensor
    citireindex_data = coordinator.data.get("citireindex")
    if citireindex_data:
        devices = citireindex_data.get("indexDetails", {}).get("devices", [])
        _LOGGER.debug("Dispozitive detectate în citireindex_data: %s", devices)
        seen_devices = set()
        for device in devices:
            device_number = device.get("deviceNumber", "unknown_device")
            if device_number not in seen_devices:
                sensors.append(CitireIndexSensor(coordinator, config_entry, device_number))
                seen_devices.add(device_number)
            else:
                _LOGGER.warning("Dispozitiv duplicat ignorat: %s", device_number)

    # 5. Gestionăm ArhivaSensor
    arhiva_data = coordinator.data.get("arhiva")
    if arhiva_data:
        history_list = arhiva_data.get("history", [])
        for item in history_list:
            year = item.get("year")
            if year:
                sensors.append(ArhivaSensor(coordinator, config_entry, year))

    # 6. Gestionăm PaymentsHistorySensor
    #    6.1. Extragem toate plățile
    payments_list = coordinator.data.get("payments", [])
    if payments_list:
        from collections import defaultdict
        payments_by_year = defaultdict(list)

        #    6.2. Grupăm plățile pe ani
        for payment in payments_list:
            raw_date = payment.get("paymentDate")
            if not raw_date:
                continue
            try:
                year = int(raw_date.split("-")[0])  # extragem anul din ex. "2024-11-27T00:00:00"
                payments_by_year[year].append(payment)
            except ValueError:
                continue

        #    6.3. Pentru fiecare an, creăm un senzor separat
        for year, payment_items in payments_by_year.items():
            sensors.append(ArhivaPlatiSensor(coordinator, config_entry, year))

    # 7. Înregistrăm senzorii în Home Assistant
    async_add_entities(sensors)

# ------------------------------------------------------------------------
# DateContractSensor
# ------------------------------------------------------------------------
class DateContractSensor(CoordinatorEntity, SensorEntity):
    """Senzor pentru afișarea datelor contractului."""

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = "Date contract"
        self._attr_unique_id = f"{DOMAIN}_date_contract_{config_entry.entry_id}"
        self._attr_entity_id = f"sensor.{DOMAIN}_date_contract_{config_entry.data['cod_incasare']}"

    @property
    def state(self):
        """Returnează starea senzorului."""
        data = self.coordinator.data.get("dateuser")
        if not data:
            return None
        return data.get("accountContract")  # Exemplu: "123456789012"

    @property
    def extra_state_attributes(self):
        """Atribute adiționale."""
        data = self.coordinator.data.get("dateuser")
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
        street_no = address_obj.get("streetNumber")  # Corect
        apartment = address_obj.get("apartment")
        locality_name = address_obj.get("locality", {}).get("localityName")

        full_address = f"{street_type} {street_name} {street_no} ap. {apartment}, {locality_name}"
        attributes["Adresă consum"] = full_address

        attributes["Următoarea verificare a instalației"] = data.get("verificationExpirationDate")
        attributes["Data inițierii reviziei"] = data.get("revisionStartDate")
        attributes["Următoarea revizie tehnică"] = data.get("revisionExpirationDate")

        attributes["attribution"] = ATTRIBUTION
        return attributes

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def entity_id(self):
        return self._attr_entity_id

    @entity_id.setter
    def entity_id(self, value):
        self._attr_entity_id = value

    @property
    def icon(self):
        return "mdi:file-document-edit-outline"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "eonromania")},
            "name": "E-ON România",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }


# ------------------------------------------------------------------------
# CitireIndexSensor
# ------------------------------------------------------------------------
class CitireIndexSensor(CoordinatorEntity, SensorEntity):
    """Senzor pentru afișarea datelor despre indexul curent."""

    def __init__(self, coordinator, config_entry, device_number):
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.device_number = device_number
        self._attr_name = "Index curent"
        self._attr_unique_id = f"{DOMAIN}_index_curent_{config_entry.entry_id}"
        self._attr_entity_id = f"sensor.{DOMAIN}_index_curent_{config_entry.data['cod_incasare']}"

    @property
    def state(self):
        """Returnează starea senzorului."""
        citireindex_data = self.coordinator.data.get("citireindex")
        if not citireindex_data:
            return None

        index_details = citireindex_data.get("indexDetails", {})
        devices = index_details.get("devices", [])
        if not devices:
            return None

        # Căutăm device-ul cu device_number-ul potrivit
        for dev in devices:
            if dev.get("deviceNumber") == self.device_number:
                indexes = dev.get("indexes", [])
                if indexes:
                    # Verificăm mai întâi currentValue
                    current_value = indexes[0].get("currentValue")
                    if current_value is not None:
                        return int(current_value)

                    # Dacă currentValue este None, returnăm oldValue
                    old_value = indexes[0].get("oldValue")
                    if old_value is not None:
                        return int(old_value)
        return None

    @property
    def extra_state_attributes(self):
        citireindex_data = self.coordinator.data.get("citireindex")
        if not citireindex_data:
            return {}

        index_details = citireindex_data.get("indexDetails", {})
        devices = index_details.get("devices", [])
        reading_period = citireindex_data.get("readingPeriod", {})

        # Găsim device-ul potrivit
        for dev in devices:
            if dev.get("deviceNumber") == self.device_number:
                indexes = dev.get("indexes", [])
                if indexes:
                    first_index = indexes[0]
                    attributes = {}

                    # Adăugăm atributele doar dacă nu sunt `null`
                    if dev.get("deviceNumber") is not None:
                        attributes["Numărul dispozitivului"] = dev.get("deviceNumber")
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

                    # Tipul citirii
                    crt_reading_type = reading_period.get("currentReadingType")
                    if crt_reading_type is not None:
                        if crt_reading_type == "01":
                            reading_type_str = "Citire distribuitor"
                        elif crt_reading_type == "02":
                            reading_type_str = "Autocitire"
                        elif crt_reading_type == "03":
                            reading_type_str = "Estimare"
                        else:
                            reading_type_str = "Necunoscut"
                        attributes["Tipul citirii curente"] = reading_type_str

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

                    # Adăugăm sursa
                    attributes["attribution"] = ATTRIBUTION
                    return attributes

        return {}

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def entity_id(self):
        return self._attr_entity_id

    @entity_id.setter
    def entity_id(self, value):
        self._attr_entity_id = value

    @property
    def icon(self):
        return "mdi:gauge"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "eonromania")},
            "name": "E-ON România",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }


# ------------------------------------------------------------------------
# FacturaRestantaSensor
# ------------------------------------------------------------------------
MONTHS_RO = {
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

class FacturaRestantaSensor(CoordinatorEntity, SensorEntity):
    """Senzor pentru afișarea soldului restant al facturilor."""

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_factura_restanta_{config_entry.entry_id}"
        self._attr_name = "Factură restantă"
        self._attr_entity_id = f"sensor.{DOMAIN}_factura_restanta_{config_entry.data['cod_incasare']}"
        self._icon = "mdi:file-document-alert-outline"

    @property
    def state(self):
        """Returnează starea principală (Da/Nu)."""
        data = self.coordinator.data.get("facturasold")
        if not data or not isinstance(data, list):
            return None
        # Verificăm dacă există cel puțin o factură neachitată
        return "Da" if any(item.get("issuedValue", 0) > 0 for item in data) else "Nu"

    @property
    def state(self):
        """Returnează starea principală (Da/Nu)."""
        # Verificăm dacă `facturasold` există și este o listă
        data = self.coordinator.data.get("facturasold")
        if not data or not isinstance(data, list):
            # Dacă `facturasold` nu există, considerăm că nu sunt facturi neachitate
            return "Nu"
        # Verificăm dacă există cel puțin o factură neachitată
        return "Da" if any(item.get("issuedValue", 0) > 0 for item in data) else "Nu"

    @property
    def extra_state_attributes(self):
        """Atribute adiționale."""
        # Verificăm dacă `facturasold` există și este o listă
        data = self.coordinator.data.get("facturasold")
        if not data or not isinstance(data, list):
            # Dacă `facturasold` nu există, returnăm atribute implicite
            return {
                "Total neachitat": "0.00 lei",
                "Detalii": "Nu există facturi disponibile",
                "attribution": ATTRIBUTION
            }

        attributes = {}
        total_sold = 0.0

        for idx, item in enumerate(data, start=1):
            issued_value = float(item.get("issuedValue", 0))
            balance_value = float(item.get("balanceValue", 0))

            # Determinăm valoarea care trebuie afișată
            display_value = issued_value if issued_value == balance_value else balance_value

            if display_value > 0:
                total_sold += display_value

                raw_date = item.get("maturityDate", "Necunoscut")
                try:
                    parsed_date = datetime.strptime(raw_date, "%d.%m.%Y")
                    month_name_en = parsed_date.strftime("%B")
                    month_name_ro = MONTHS_RO.get(month_name_en, "necunoscut")

                    days_until_due = (parsed_date - datetime.now()).days
                    if days_until_due < 0:
                        day_unit = "zi" if abs(days_until_due) == 1 else "zile"
                        msg = (f"Restanță de {display_value:.2f} lei, termen depășit cu "
                            f"{abs(days_until_due)} {day_unit}")
                    elif days_until_due == 0:
                        msg = (f"De achitat astăzi, {datetime.now().strftime('%d.%m.%Y')}: "
                            f"{display_value:.2f} lei")
                    else:
                        day_unit = "zi" if days_until_due == 1 else "zile"
                        msg = (f"Următoarea sumă de {display_value:.2f} lei este scadentă "
                            f"pe luna {month_name_ro} ({days_until_due} {day_unit})")

                    attributes[f"Factură {idx}"] = msg

                except ValueError:
                    attributes[f"Factură {idx}"] = "Data scadenței necunoscută"

        attributes["---------------"] = ""
        attributes["Total neachitat"] = f"{total_sold:,.2f} lei" if total_sold > 0 else "0.00 lei"
        attributes["attribution"] = ATTRIBUTION

        return attributes

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def entity_id(self):
        return self._attr_entity_id

    @entity_id.setter
    def entity_id(self, value):
        self._attr_entity_id = value

    @property
    def icon(self):
        return self._icon

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "eonromania")},
            "name": "E-ON România",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }


# ------------------------------------------------------------------------
# ArhivaSensor
# ------------------------------------------------------------------------
class ArhivaSensor(CoordinatorEntity, SensorEntity):
    """Senzor pentru afișarea datelor istorice ale consumului."""

    def __init__(self, coordinator, config_entry, year):
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.year = year
        self._attr_name = f"Arhivă index - {year}"
        self._attr_unique_id = f"{DOMAIN}_arhiva_index_{config_entry.entry_id}_{year}"
        self._attr_entity_id = f"sensor.{DOMAIN}_arhiva_index_{config_entry.data['cod_incasare']}_{year}"

    @property
    def state(self):
        """Returnează numărul lunilor disponibile în arhivă pentru anul respectiv."""
        arhiva_data = self.coordinator.data.get("arhiva", {})
        history_list = arhiva_data.get("history", [])
        year_data = next((y for y in history_list if y.get("year") == self.year), None)

        if not year_data:
            return None
        
        # De exemplu, returnăm nr. de citiri din meters -> indexes -> readings
        meters = year_data.get("meters", [])
        if not meters:
            return 0
        # Presupunem că există un singur meter -> un singur index -> multiple readings
        indexes = meters[0].get("indexes", [])
        if not indexes:
            return 0
        readings = indexes[0].get("readings", [])
        return len(readings)

    @property
    def extra_state_attributes(self):
        """Afișează indexul și metoda de citire pentru fiecare lună."""
        arhiva_data = self.coordinator.data.get("arhiva", {})
        history_list = arhiva_data.get("history", [])
        year_data = next((y for y in history_list if y.get("year") == self.year), None)

        if not year_data:
            return {}

        months_map = {
            1: "ianuarie", 2: "februarie", 3: "martie", 4: "aprilie",
            5: "mai", 6: "iunie", 7: "iulie", 8: "august",
            9: "septembrie", 10: "octombrie", 11: "noiembrie", 12: "decembrie"
        }
        reading_type_map = {
            "01": "citit distribuitor",
            "02": "autocitit",
            "03": "estimat"
        }

        attributes = {}
        for meter in year_data.get("meters", []):
            for index in meter.get("indexes", []):
                for reading in index.get("readings", []):
                    month_num = reading.get("month")
                    month_name = months_map.get(month_num, "Necunoscut")
                    value = int(reading.get("value", 0))
                    reading_type_code = reading.get("readingType", "99")
                    reading_type_str = reading_type_map.get(reading_type_code, "Necunoscut")

                    # În loc să stocăm separat indexul și metoda de citire,
                    # concatenăm datele într-o singură cheie:
                    attributes[f"Index ({reading_type_str}) {month_name}"] = value



        attributes["attribution"] = ATTRIBUTION
        return attributes

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def entity_id(self):
        return self._attr_entity_id

    @entity_id.setter
    def entity_id(self, value):
        self._attr_entity_id = value

    @property
    def icon(self):
        return "mdi:clipboard-text-clock"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "eonromania")},
            "name": "E-ON România",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }


# ------------------------------------------------------------------------
# ArhivaPlatiSensor
# ------------------------------------------------------------------------
class ArhivaPlatiSensor(CoordinatorEntity, SensorEntity):
    """Senzor pentru afișarea istoricului plăților (grupat pe ani)."""

    def __init__(self, coordinator, config_entry, year):
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.year = year

        self._attr_name = f"Arhivă plăți - {year}"
        self._attr_unique_id = f"{DOMAIN}_arhiva_plati_{config_entry.entry_id}_{year}"
        self._attr_entity_id = f"sensor.{DOMAIN}_arhiva_plati_{config_entry.data['cod_incasare']}_{year}"

    @property
    def state(self):
        payments_list = self._payments_for_year()
        return len(payments_list)

    @property
    def extra_state_attributes(self):
        """Afișează plățile grupate pe lună."""
        months_map = {
            1: "ianuarie", 2: "februarie", 3: "martie", 4: "aprilie",
            5: "mai", 6: "iunie", 7: "iulie", 8: "august",
            9: "septembrie", 10: "octombrie", 11: "noiembrie", 12: "decembrie"
        }

        attributes = {}
        payments_list = self._payments_for_year()

        # Calculăm totalul plăților
        total_value = sum(p.get("value", 0) for p in payments_list)

        # Adăugăm informații despre fiecare plată
        for idx, payment in enumerate(payments_list, start=1):
            raw_date = payment.get("paymentDate", "N/A")
            payment_value = payment.get("value", 0)

            # Extragem luna din data
            if raw_date != "N/A":
                try:
                    parsed_date = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S")
                    month_name = months_map.get(parsed_date.month, "necunoscut")
                except ValueError:
                    month_name = "necunoscut"
            else:
                month_name = "necunoscut"

            attributes[f"Plată factură luna {month_name}"] = f"{payment_value:.2f} lei"

        attributes["---------------"] = ""
        attributes["Plăți efectuate"] = len(payments_list)
        attributes["Sumă totală"] = f"{total_value:.2f} lei"
        attributes["attribution"] = "Date furnizate de E-ON România"
        return attributes

    def _payments_for_year(self):
        all_payments = self.coordinator.data.get("payments", [])
        filtered = []
        for payment in all_payments:
            raw_date = payment.get("paymentDate", "")
            if raw_date.startswith(str(self.year)):
                filtered.append(payment)
        return filtered

    @property
    def icon(self):
        return "mdi:cash-register"

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def entity_id(self):
        return self._attr_entity_id

    @entity_id.setter
    def entity_id(self, value):
        self._attr_entity_id = value

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "eonromania")},
            "name": "E-ON România",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }
