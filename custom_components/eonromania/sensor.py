"""Platforma Sensor pentru EON România."""
import logging
from datetime import datetime
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN, ATTRIBUTION

_LOGGER = logging.getLogger(__name__)

# Configurarea senzorilor pentru fiecare intrare definită în config_entries
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Configurează senzorii pentru o intrare."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    
    # Creăm senzori pentru fiecare dispozitiv în funcție de datele disponibile
    sensors = [
        DateContractSensor(coordinators["dateuser"], config_entry),
    ]

    # Adăugăm senzorul FacturaRestantaSensor
    factura_restanta_data = coordinators.get("facturasold")
    if factura_restanta_data:
        sensors.append(FacturaRestantaSensor(factura_restanta_data, config_entry))

    # Adăugăm senzori pentru fiecare dispozitiv din `indexDetails`
    citireindex_data = coordinators["citireindex"].data
    if citireindex_data:
        devices = citireindex_data.get("indexDetails", {}).get("devices", [])
        _LOGGER.debug("Dispozitive detectate în citireindex_data: %s", devices)  # Log pentru dispozitive
        seen_devices = set()  # Set pentru a preveni duplicările
        for device in devices:
            device_number = device.get("deviceNumber", "unknown_device")
            if device_number not in seen_devices:
                sensors.append(CitireIndexSensor(coordinators["citireindex"], config_entry, device_number))
                seen_devices.add(device_number)  # Adăugăm device_number în set
            else:
                _LOGGER.warning("Dispozitiv duplicat ignorat: %s", device_number)
    
    # Gestionăm senzorii de arhivă
    arhiva_data = coordinators["arhiva"].data
    if arhiva_data:
        for year_data in arhiva_data.get("history", []):
            year = year_data.get("year")
            if year:
                sensors.append(ArhivaSensor(coordinators["arhiva"], config_entry, year))

    async_add_entities(sensors)

# Senzor pentru afișarea datelor contractului utilizatorului
class DateContractSensor(CoordinatorEntity, SensorEntity):
    """Senzor pentru afișarea datelor contractului."""

    def __init__(self, coordinator, config_entry):
        """Inițializează senzorul DateContractSensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = "Date contract"
        self._attr_unique_id = f"{DOMAIN}_date_contract_{self.config_entry.entry_id}"
        self._attr_entity_id = f"sensor.date_contract_{config_entry.data['cod_incasare']}"  # corect


        # Debug pentru inițializare
        _LOGGER.debug(
            "Inițializare DateContractSensor: name=%s, unique_id=%s",
            self._attr_name,
            self._attr_unique_id,
        )

    @property
    def state(self):
        """Returnează starea senzorului."""
        if not self.coordinator.data:
            _LOGGER.debug("Senzor DateContractSensor - Nu există date în coordinator.data.")
            return None

        state_value = self.coordinator.data.get("accountContract")
        _LOGGER.debug("Senzor DateContractSensor - Starea datelor pe senzor: %s", state_value)
        return state_value

    @property
    def extra_state_attributes(self):
        """Returnează atributele adiționale ale senzorului."""
        if not self.coordinator.data:
            _LOGGER.debug("Senzor DateContractSensor - Nu există date în coordinator.data.")
            return {}

        reading_period = self.coordinator.data.get("readingPeriod", {})
        raw_data = self.coordinator.data

        attributes = {
            "Cod încasare": raw_data.get("accountContract"),
            "Cod loc de consum (NLC)": raw_data.get("consumptionPointCode"),
            "CLC - Cod punct de măsură": raw_data.get("pod"),
            "Operator de Distribuție (OD)": raw_data.get("distributorName"),
            "Preț final (fără TVA)": f"{raw_data.get('supplierAndDistributionPrice', {}).get('contractualPrice')} lei",
            "Preț final (cu TVA)": f"{raw_data.get('supplierAndDistributionPrice', {}).get('contractualPriceWithVat')} lei",
            "Preț furnizare": f"{raw_data.get('supplierAndDistributionPrice', {}).get('priceComponents', {}).get('supplierPrice')} lei/kWh",
            "Tarif reglementat distribuție": f"{raw_data.get('supplierAndDistributionPrice', {}).get('priceComponents', {}).get('distributionPrice')} lei/kWh",
            "Tarif reglementat transport": f"{raw_data.get('supplierAndDistributionPrice', {}).get('priceComponents', {}).get('transportPrice')} lei/kWh",
            "PCS": str(raw_data.get("supplierAndDistributionPrice", {}).get("pcs")),
            "Adresă consum": f"{raw_data.get('consumptionPointAddress', {}).get('street', {}).get('streetType', {}).get('label')} {raw_data.get('consumptionPointAddress', {}).get('street', {}).get('streetName')} {raw_data.get('consumptionPointAddress', {}).get('streetNumber')} ap. {raw_data.get('consumptionPointAddress', {}).get('apartment')}, {raw_data.get('consumptionPointAddress', {}).get('locality', {}).get('localityName')}",
            "Următoarea verificare a instalației": raw_data.get("verificationExpirationDate"),
            "Data inițierii reviziei": raw_data.get("revisionStartDate"),
            "Următoarea revizie tehnică": raw_data.get("revisionExpirationDate"),
        }
        _LOGGER.debug("Senzor DateContractSensor - Atribute: %s", attributes)
        attributes["attribution"] = ATTRIBUTION
        return attributes

    @property
    def unique_id(self):
        """Returnează identificatorul unic al senzorului."""
        return f"{DOMAIN}_eonromania_contract_{self.config_entry.data['cod_incasare']}"

    @property
    def entity_id(self):
        """Returnează identificatorul explicit al entității."""
        return self._attr_entity_id

    @entity_id.setter
    def entity_id(self, value):
        """Setează identificatorul explicit al entității."""
        self._attr_entity_id = value

    @property
    def icon(self):
        """Pictograma senzorului."""
        return "mdi:file-document-edit-outline"

    @property
    def device_info(self):
        """Informații despre dispozitiv pentru integrare."""
        return {
            "identifiers": {(DOMAIN, "eonromania")},
            "name": "E-ON România",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }

# Senzor pentru afișarea datelor despre indexul curent
class CitireIndexSensor(CoordinatorEntity, SensorEntity):
    """Senzor pentru afișarea datelor despre indexul curent."""

    def __init__(self, coordinator, config_entry, device_number):
        """Inițializează senzorul CitireIndexSensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.device_number = device_number  # Atribuim device_number

        # Creăm un unique_id unic pentru fiecare dispozitiv
        self._attr_name = "Index curent"
        self._attr_unique_id = f"{DOMAIN}_index_curent_{self.config_entry.entry_id}_{device_number}"
        self._attr_entity_id = f"sensor.index_curent_{self.config_entry.data['cod_incasare']}" # corect


        # Debug pentru inițializare
        _LOGGER.debug(
            "Inițializare CitireIndexSensor: name=%s, unique_id=%s, device_number=%s",
            self._attr_name,
            self._attr_unique_id,
            self.device_number,
        )

    @property
    def state(self):
        """Returnează starea senzorului."""
        if not self.coordinator.data:
            _LOGGER.debug("Senzor CitireIndexSensor - Nu există date în coordinator.data.")
            return None

        # Debug pentru date brute
        _LOGGER.debug("Senzor CitireIndexSensor - Date brute din coordinator.data: %s", self.coordinator.data)

        # Verificăm dacă există secțiunea indexDetails
        index_details = self.coordinator.data.get("indexDetails")
        if not index_details:
            _LOGGER.debug("Senzor CitireIndexSensor - Secțiunea indexDetails lipsește.")
            return None

        # Accesăm dispozitivele
        devices = index_details.get("devices", [])
        if not devices:
            _LOGGER.debug("Senzor CitireIndexSensor - Nu există dispozitive în indexDetails.")
            return None

        # Obținem valoarea curentă a indexului și o convertim în număr întreg
        current_index = devices[0].get("indexes", [{}])[0].get("currentValue")
        current_index = int(current_index) if current_index is not None else None
        _LOGGER.debug("Senzor CitireIndexSensor - Valoarea curentă a indexului: %s", current_index)
        return current_index

    @property
    def extra_state_attributes(self):
        """Returnează atributele adiționale ale senzorului."""
        if not self.coordinator.data:
            _LOGGER.debug("Senzor CitireIndexSensor - Nu există date în coordinator.data.")
            return {}

        # Verificăm dacă există secțiunea indexDetails
        index_details = self.coordinator.data.get("indexDetails")
        if not index_details:
            _LOGGER.debug("Senzor CitireIndexSensor - Secțiunea indexDetails lipsește.")
            return {}

        devices = index_details.get("devices", [])
        if not devices:
            _LOGGER.debug("Senzor CitireIndexSensor - Nu există dispozitive.")
            return {}

        first_device = devices[0]
        first_index = first_device.get("indexes", [{}])[0]
        reading_period = self.coordinator.data.get("readingPeriod", {})

        attributes = {
            "Numărul dispozitivului": first_device.get("deviceNumber"),
            "Data de începere a următoarei citiri": reading_period.get("startDate"),
            "Data de final a citirii": reading_period.get("endDate"),
            "Autorizat să citească contorul": "Da" if reading_period.get("allowedReading") else "Nu",
            "Permite modificarea citirii": "Da" if reading_period.get("allowChange") else "Nu",
            "Dispozitiv inteligent": "Da" if reading_period.get("smartDevice") else "Nu",
            "Tipul citirii curente": (
            "Autocitire" if reading_period.get("currentReadingType") == "02" else "Citire distribuitor" if reading_period.get("currentReadingType") == "01" else  "Estimare" if reading_period.get("currentReadingType") == "03" else "Necunoscut" ),
            "Citire anterioară": first_index.get("minValue"),
            "Ultima citire validată": first_index.get("oldValue"),
            "Index propus pentru facturare": first_index.get("currentValue"),
            "Trimis la": first_index.get("sentAt"),
            "Poate fi modificat până la": first_index.get("canBeChangedTill"),
        }

        _LOGGER.debug("Senzor CitireIndexSensor - Atribute: %s", attributes)
        attributes["attribution"] = ATTRIBUTION
        return attributes

    @property
    def unique_id(self):
        """Returnează identificatorul unic al senzorului."""
        return f"{DOMAIN}_citire_index{self.config_entry.entry_id}_{self.device_number}"

    @property
    def entity_id(self):
        """Returnează identificatorul explicit al entității."""
        return self._attr_entity_id

    @entity_id.setter
    def entity_id(self, value):
        """Setează identificatorul explicit al entității."""
        self._attr_entity_id = value

    @property
    def icon(self):
        """Pictograma senzorului."""
        return "mdi:gauge"

    @property
    def device_info(self):
        """Informații despre dispozitiv pentru integrare."""
        return {
            "identifiers": {(DOMAIN, "eonromania")},
            "name": "E-ON România",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }

# Senzor pentru afișarea facturii neplatite.
# Dicționar pentru mapping-ul lunilor în română
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
# Senzor pentru afișarea facturii neplatite.
class FacturaRestantaSensor(CoordinatorEntity, SensorEntity):
    """Senzor pentru afișarea soldului restant al facturilor."""

    def __init__(self, coordinator, config_entry):
        """Inițializează senzorul FacturaRestantaSensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_factura_restanta_{self.config_entry.entry_id}"
        self._attr_name = "Factură restantă"
        self._entity_id = f"sensor.factura_restanta_{self.config_entry.data['cod_incasare']}"
        self._icon = "mdi:file-document-alert-outline"

    @property
    def state(self):
        """Returnează starea principală a senzorului."""
        data = self.coordinator.data
        if not data or "balancePay" not in data:
            return None

        # Verificăm dacă există cel puțin o factură neachitată
        return "Da" if data.get("balancePay", False) else "Nu"

    @property
    def extra_state_attributes(self):
        """Returnează atributele adiționale ale senzorului."""
        data = self.coordinator.data
        if not data:
            return {}

        attributes = {}
        total_sold = 0  # Inițializăm suma totală

        # Calculăm totalul și adăugăm atribute pentru fiecare factură neachitată
        if isinstance(data, dict):
            for idx, item in enumerate([data], start=1):
                if item.get("balancePay", False):
                    balance = float(item.get("balance", 0))
                    total_sold += balance

                    # Obținem luna din data facturii și traducem în română
                    raw_date = item.get("date", "Necunoscut")
                    try:
                        parsed_date = datetime.strptime(raw_date, "%d.%m.%Y")
                        month_name_en = parsed_date.strftime("%B")  # Obține numele lunii în engleză
                        month_name_ro = MONTHS_RO.get(month_name_en, "necunoscut")

                        # Calculăm zilele rămase până la data scadenței
                        days_until_due = (parsed_date - datetime.now()).days
                        if days_until_due < 0:
                            day_unit = "zi" if abs(days_until_due) == 1 else "zile"
                            due_message = (
                                f"Restanță de {balance:.2f} lei, termen depășit cu {abs(days_until_due)} {day_unit}"
                            )
                        elif days_until_due == 0:
                            due_message = f"De achitat astăzi, {datetime.now().strftime('%d.%m.%Y')}: {balance:.2f} lei"
                        else:
                            day_unit = "zi" if days_until_due == 1 else "zile"
                            due_message = (
                                f"Următoarea sumă de {balance:.2f} lei este scadentă "
                                f"pe luna {month_name_ro} ({days_until_due} {day_unit})"
                            )

                        attributes["Stare plată"] = due_message

                    except ValueError:
                        month_name_ro = "necunoscut"
                        attributes["Plată scadentă"] = "Data scadenței necunoscută"

        # Adăugăm separatorul explicit înainte de total sold
        attributes["---------------"] = ""
        attributes["Total neachitat"] = f"{total_sold:,.2f} lei" if total_sold > 0 else "0.00 lei"
        attributes["attribution"] = ATTRIBUTION

        return attributes

    @property
    def unique_id(self):
        """Returnează identificatorul unic al senzorului."""
        return self._attr_unique_id

    @property
    def entity_id(self):
        """Returnează identificatorul explicit al entității."""
        return self._entity_id

    @entity_id.setter
    def entity_id(self, value):
        """Setează identificatorul explicit al entității."""
        self._attr_entity_id = value

    @property
    def icon(self):
        """Pictograma senzorului."""
        return self._icon

    @property
    def device_info(self):
        """Informații despre dispozitiv pentru integrare."""
        return {
            "identifiers": {(DOMAIN, "eonromania")},
            "name": "E-ON România",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }

# Senzor pentru afișarea facturii prosumator neplatite.
class FacturaProsumatorRestantaSensor(CoordinatorEntity, SensorEntity):
    """Senzor pentru afișarea soldului de prosumator restant al facturilor."""

    def __init__(self, coordinator, config_entry):
        """Inițializează senzorul FacturaProsumatorRestantaSensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_factura_restanta_{self.config_entry.entry_id}"
        self._attr_name = "Factură prosumator restantă"
        self._entity_id = f"sensor.factura_restanta_{self.config_entry.data['cod_incasare']}"
        self._icon = "mdi:file-document-alert-outline"

    @property
    def state(self):
        """Returnează starea principală a senzorului."""
        data = self.coordinator.data
        if not data or "balancePay" not in data:
            return None

        # Verificăm dacă există cel puțin o factură neachitată
        return "Da" if data.get("balancePay", False) else "Nu"

    @property
    def extra_state_attributes(self):
        """Returnează atributele adiționale ale senzorului."""
        data = self.coordinator.data
        if not data:
            return {}

        attributes = {}
        total_sold = 0  # Inițializăm suma totală

        # Calculăm totalul și adăugăm atribute pentru fiecare factură neachitată
        if isinstance(data, dict):
            for idx, item in enumerate([data], start=1):
                if item.get("balancePay", False):
                    balance = float(item.get("balance", 0))
                    total_sold += balance

                    # Obținem luna din data facturii și traducem în română
                    raw_date = item.get("date", "Necunoscut")
                    try:
                        parsed_date = datetime.strptime(raw_date, "%d.%m.%Y")
                        month_name_en = parsed_date.strftime("%B")  # Obține numele lunii în engleză
                        month_name_ro = MONTHS_RO.get(month_name_en, "necunoscut")

                        # Calculăm zilele rămase până la data scadenței
                        days_until_due = (parsed_date - datetime.now()).days
                        if days_until_due < 0:
                            day_unit = "zi" if abs(days_until_due) == 1 else "zile"
                            due_message = (
                                f"Restanță de {balance:.2f} lei, termen depășit cu {abs(days_until_due)} {day_unit}"
                            )
                        elif days_until_due == 0:
                            due_message = f"De achitat astăzi, {datetime.now().strftime('%d.%m.%Y')}: {balance:.2f} lei"
                        else:
                            day_unit = "zi" if days_until_due == 1 else "zile"
                            due_message = (
                                f"Următoarea sumă de {balance:.2f} lei este scadentă "
                                f"pe luna {month_name_ro} ({days_until_due} {day_unit})"
                            )

                        attributes["Stare plată"] = due_message

                    except ValueError:
                        month_name_ro = "necunoscut"
                        attributes["Plată scadentă"] = "Data scadenței necunoscută"

        # Adăugăm separatorul explicit înainte de total sold
        attributes["---------------"] = ""
        attributes["Total neachitat"] = f"{total_sold:,.2f} lei" if total_sold > 0 else "0.00 lei"
        attributes["attribution"] = ATTRIBUTION

        return attributes

    @property
    def unique_id(self):
        """Returnează identificatorul unic al senzorului."""
        return self._attr_unique_id

    @property
    def entity_id(self):
        """Returnează identificatorul explicit al entității."""
        return self._entity_id

    @entity_id.setter
    def entity_id(self, value):
        """Setează identificatorul explicit al entității."""
        self._attr_entity_id = value

    @property
    def icon(self):
        """Pictograma senzorului."""
        return self._icon

    @property
    def device_info(self):
        """Informații despre dispozitiv pentru integrare."""
        return {
            "identifiers": {(DOMAIN, "eonromania")},
            "name": "E-ON România",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }

# Senzor pentru afișarea datelor istorice ale consumului
class ArhivaSensor(CoordinatorEntity, SensorEntity):
    """Senzor pentru afișarea datelor istorice ale consumului."""

    def __init__(self, coordinator, config_entry, year):
        """Inițializează senzorul ArhivaSensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.year = year
        self._attr_name = f"Arhivă - {year}"
        self._attr_unique_id = f"{DOMAIN}_arhiva_{self.config_entry.entry_id}_{self.year}"
        self._attr_entity_id = f"sensor.arhiva_{self.config_entry.data['cod_incasare']}_{self.year}" # corect


        _LOGGER.debug(
            "Inițializare ArhivaSensor: name=%s, unique_id=%s, year=%s",
            self._attr_name,
            self._attr_unique_id,
            self.year,
        )

    @property
    def state(self):
        """Returnează starea senzorului."""
        # Exemplu: Returnăm numărul total al lunilor disponibile pentru anul respectiv
        year_data = next((y for y in self.coordinator.data.get("history", []) if y["year"] == self.year), None)
        if not year_data:
            return None
        return len(year_data.get("meters", [])[0].get("indexes", [])[0].get("readings", []))

    @property
    def extra_state_attributes(self):
        """Returnează atributele adiționale ale senzorului."""
        year_data = next((y for y in self.coordinator.data.get("history", []) if y["year"] == self.year), None)
        if not year_data:
            return {}

        # Harta lunilor și tipurilor de citire
        months_map = {
            1: "ianuarie", 2: "februarie", 3: "martie", 4: "aprilie",
            5: "mai", 6: "iunie", 7: "iulie", 8: "august",
            9: "septembrie", 10: "octombrie", 11: "noiembrie", 12: "decembrie"
        }
        reading_type_map = {
            "01": "Citire distribuitor",
            "02": "Autocitire",
            "03": "Estimare"
        }

        # Structurăm atributele
        attributes = {}
        for meter in year_data.get("meters", []):
            for index in meter.get("indexes", []):
                for reading in index.get("readings", []):
                    month = months_map.get(reading.get("month"), "Necunoscut")
                    value = int(reading.get("value", 0))  # Fără zecimale
                    reading_type = reading_type_map.get(reading.get("readingType"), "Necunoscut")
                    attributes[f"Index {month}"] = value
                    attributes[f"Metodă de citire {month}"] = reading_type

        _LOGGER.debug("Senzor ArhivaSensor - Atribute generate: %s", attributes)
        attributes["attribution"] = ATTRIBUTION
        return attributes

    @property
    def unique_id(self):
        """Returnează identificatorul unic al senzorului."""
        return f"{DOMAIN}_arhiva_{self.config_entry.entry_id}_{self.year}"

    @property
    def entity_id(self):
        """Returnează identificatorul explicit al entității."""
        return self._attr_entity_id

    @entity_id.setter
    def entity_id(self, value):
        """Setează identificatorul explicit al entității."""
        self._attr_entity_id = value

    @property
    def icon(self):
        """Pictograma senzorului."""
        return "mdi:clipboard-text-clock"

    @property
    def device_info(self):
        """Informații despre dispozitiv pentru integrare."""
        return {
            "identifiers": {(DOMAIN, "eonromania")},
            "name": "E-ON România",
            "manufacturer": "Ciprian Nicolae (cnecrea)",
            "model": "E-ON România",
            "entry_type": DeviceEntryType.SERVICE,
        }  
