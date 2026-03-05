"""DataUpdateCoordinator pentru integrarea E·ON România."""

import asyncio
import logging
from datetime import timedelta
import json  # Adăugat pentru dumping JSON în debug

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EonApiClient

_LOGGER = logging.getLogger(__name__)


class EonRomaniaCoordinator(DataUpdateCoordinator):
    """Coordinator care se ocupă de toate datele E·ON România."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: EonApiClient,
        cod_incasare: str,
        update_interval: int,
        is_collective: bool = False,
    ):
        """Inițializează coordinatorul cu parametrii necesari."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"EonRomaniaCoordinator_{cod_incasare}",
            update_interval=timedelta(seconds=update_interval),
        )
        self.api_client = api_client
        self.cod_incasare = cod_incasare
        self.is_collective = is_collective

    async def _async_update_data(self) -> dict:
        """Obține date de la API — toate apelurile în paralel."""
        cod = self.cod_incasare

        _LOGGER.debug(
            "Începe actualizarea datelor E·ON (contract=%s, colectiv=%s).",
            cod, self.is_collective,
        )

        try:
            # Login proactiv dacă tokenul e expirat sau absent
            if not self.api_client.is_token_likely_valid():
                _LOGGER.debug(
                    "Token absent sau probabil expirat. Se face login proactiv (contract=%s).",
                    cod,
                )
                self.api_client.invalidate_token()
                ok = await self.api_client.async_login()
                if not ok:
                    _LOGGER.warning(
                        "Autentificare eșuată la API-ul E·ON (contract=%s).", cod
                    )
                    raise UpdateFailed("Nu s-a putut autentifica la API-ul E·ON.")

            # ──────────────────────────────────────
            # Endpoint-uri comune (funcționează pe orice tip de contract)
            # ──────────────────────────────────────
            common_tasks = [
                self.api_client.async_fetch_contract_details(cod),
                self.api_client.async_fetch_invoices_unpaid(cod),
                self.api_client.async_fetch_invoices_prosum(cod),
                self.api_client.async_fetch_invoice_balance(cod),
                self.api_client.async_fetch_invoice_balance_prosum(cod),
                self.api_client.async_fetch_rescheduling_plans(cod),
                self.api_client.async_fetch_payments(cod),
            ]

            (
                contract_details,
                invoices_unpaid,
                invoices_prosum,
                invoice_balance,
                invoice_balance_prosum,
                rescheduling_plans,
                payments,
            ) = await asyncio.gather(*common_tasks)

            # Debug clar pentru datele comune primite
            _LOGGER.debug(
                "Date comune primite (contract=%s): contract_details=%s, invoices_unpaid=%s (len=%s), "
                "invoices_prosum=%s (len=%s), invoice_balance=%s, invoice_balance_prosum=%s, "
                "rescheduling_plans=%s (len=%s), payments=%s (len=%s).",
                cod,
                type(contract_details).__name__ if contract_details else None,
                type(invoices_unpaid).__name__ if invoices_unpaid else None,
                len(invoices_unpaid) if isinstance(invoices_unpaid, list) else "N/A",
                type(invoices_prosum).__name__ if invoices_prosum else None,
                len(invoices_prosum) if isinstance(invoices_prosum, list) else "N/A",
                type(invoice_balance).__name__ if invoice_balance else None,
                type(invoice_balance_prosum).__name__ if invoice_balance_prosum else None,
                type(rescheduling_plans).__name__ if rescheduling_plans else None,
                len(rescheduling_plans) if isinstance(rescheduling_plans, list) else "N/A",
                type(payments).__name__ if payments else None,
                len(payments) if isinstance(payments, list) else "N/A",
            )

            # Dump detaliat dacă este necesar (poate fi comentat pentru producție)
            # _LOGGER.debug("contract_details JSON: %s", json.dumps(contract_details, default=str))
            # Similar pentru celelalte, dar atenție la date sensibile

            # ──────────────────────────────────────
            # Endpoint-uri specifice tipului de contract
            # ──────────────────────────────────────
            graphic_consumption = None
            meter_index = None
            consumption_convention = None
            meter_history = None
            subcontracts = None
            subcontracts_details = None
            subcontracts_conventions = None
            subcontracts_meter_index = None

            if not self.is_collective:
                # Contract individual: endpoint-uri contor + consum
                meter_tasks = [
                    self.api_client.async_fetch_graphic_consumption(cod),
                    self.api_client.async_fetch_meter_index(cod),
                    self.api_client.async_fetch_consumption_convention(cod),
                    self.api_client.async_fetch_meter_history(cod),
                ]

                (
                    graphic_consumption,
                    meter_index,
                    consumption_convention,
                    meter_history,
                ) = await asyncio.gather(*meter_tasks)

                # Debug clar pentru datele de contor primite
                _LOGGER.debug(
                    "Date contor primite (contract=%s): graphic_consumption=%s, meter_index=%s, "
                    "consumption_convention=%s, meter_history=%s (len=%s).",
                    cod,
                    type(graphic_consumption).__name__ if graphic_consumption else None,
                    type(meter_index).__name__ if meter_index else None,
                    type(consumption_convention).__name__ if consumption_convention else None,
                    type(meter_history).__name__ if meter_history else None,
                    len(meter_history) if isinstance(meter_history, list) else "N/A",
                )

            else:
                # Contract colectiv/DUO: obținem subcontractele prin endpoint-ul
                # GET /account-contracts/list?collectiveContract={cod}
                # (NU list-with-subcontracts care e un selector general)
                _LOGGER.debug(
                    "Contract colectiv/DUO detectat (contract=%s). "
                    "Se interoghează subcontractele via list?collectiveContract.",
                    cod,
                )
                raw_subs = await self.api_client.async_fetch_contracts_list(
                    collective_contract=cod
                )

                _LOGGER.debug(
                    "DUO list (collective) primit (contract=%s): type=%s, len=%s, content=%s.",
                    cod,
                    type(raw_subs).__name__,
                    len(raw_subs) if isinstance(raw_subs, list) else "N/A",
                    json.dumps(raw_subs, default=str, ensure_ascii=False)[:1000]
                    if raw_subs else "None",
                )

                # Răspunsul e o listă plată de contracte (subcontractele DUO)
                # Fiecare element are: accountContract, utilityType, pod, etc.
                if raw_subs and isinstance(raw_subs, list):
                    subcontracts = [
                        s for s in raw_subs
                        if isinstance(s, dict) and s.get("accountContract")
                    ]
                    _LOGGER.debug(
                        "DUO subcontracte extrase (contract=%s): %s, sample keys=%s.",
                        cod, len(subcontracts),
                        list(subcontracts[0].keys()) if subcontracts else "N/A",
                    )

                    # Obținem detaliile complete per subcontract
                    # (GET individual /account-contracts/{ac}?includeMeterReading=true)
                    sub_codes = [s["accountContract"] for s in subcontracts]
                    _LOGGER.debug(
                        "DUO sub_codes (contract=%s): %s coduri → %s.",
                        cod, len(sub_codes), sub_codes,
                    )
                    if sub_codes:
                        # Contract details + consumption convention + meter index
                        # per subcontract, toate în paralel
                        detail_tasks = [
                            self.api_client.async_fetch_contract_details(sc)
                            for sc in sub_codes
                        ]
                        convention_tasks = [
                            self.api_client.async_fetch_consumption_convention(sc)
                            for sc in sub_codes
                        ]
                        meter_index_tasks = [
                            self.api_client.async_fetch_meter_index(sc)
                            for sc in sub_codes
                        ]
                        all_results = await asyncio.gather(
                            *detail_tasks, *convention_tasks, *meter_index_tasks
                        )
                        # Primele N sunt details, următoarele N sunt conventions,
                        # ultimele N sunt meter_index
                        n = len(sub_codes)
                        detail_results = all_results[:n]
                        convention_results = all_results[n:2 * n]
                        meter_index_results = all_results[2 * n:]

                        subcontracts_details = [
                            d for d in detail_results
                            if isinstance(d, dict)
                        ]
                        if not subcontracts_details:
                            subcontracts_details = None

                        # Construim dict {accountContract: convention_data}
                        subcontracts_conventions = {}
                        for sc_code, conv_data in zip(sub_codes, convention_results):
                            if conv_data and isinstance(conv_data, list) and len(conv_data) > 0:
                                subcontracts_conventions[sc_code] = conv_data

                        if not subcontracts_conventions:
                            subcontracts_conventions = None

                        # Construim dict {accountContract: meter_index_data}
                        subcontracts_meter_index = {}
                        for sc_code, mi_data in zip(sub_codes, meter_index_results):
                            if mi_data and isinstance(mi_data, dict):
                                subcontracts_meter_index[sc_code] = mi_data

                        if not subcontracts_meter_index:
                            subcontracts_meter_index = None

                        _LOGGER.debug(
                            "DUO contract_details individuale (contract=%s): %s/%s reușite. "
                            "Convenții: %s/%s reușite. Meter index: %s/%s reușite.",
                            cod,
                            len(subcontracts_details) if subcontracts_details else 0,
                            n,
                            len(subcontracts_conventions) if subcontracts_conventions else 0,
                            n,
                            len(subcontracts_meter_index) if subcontracts_meter_index else 0,
                            n,
                        )
                    if not subcontracts:
                        subcontracts = None
                else:
                    _LOGGER.warning(
                        "DUO list (collective) a returnat None sau structură invalidă (contract=%s): %s.",
                        cod, type(raw_subs).__name__,
                    )

        except asyncio.TimeoutError as err:
            _LOGGER.error(
                "Depășire de timp la actualizarea datelor E·ON (contract=%s): %s.", cod, err
            )
            raise UpdateFailed("Depășire de timp la actualizarea datelor E·ON.") from err

        except UpdateFailed:
            raise

        except Exception as err:
            _LOGGER.exception(
                "Eroare neașteptată la actualizarea datelor E·ON (contract=%s): %s",
                cod,
                err,
            )
            raise UpdateFailed("Eroare neașteptată la actualizarea datelor E·ON.") from err

        # Verificăm dacă datele esențiale sunt disponibile
        if self.is_collective:
            # Pentru contracte colective: e suficient contract_details
            if contract_details is None:
                _LOGGER.error(
                    "Date esențiale indisponibile: contract_details este None (contract colectiv=%s).",
                    cod,
                )
                raise UpdateFailed(
                    "Nu s-au putut obține datele esențiale de la E·ON (contract_details)."
                )
        else:
            # Pentru contracte individuale: trebuie cel puțin unul din cele două
            if contract_details is None and meter_index is None:
                _LOGGER.error(
                    "Date esențiale indisponibile (contract_details + meter_index sunt None) (contract=%s).",
                    cod,
                )
                raise UpdateFailed(
                    "Nu s-au putut obține datele esențiale de la E·ON (contract_details + meter_index)."
                )

        # Detectează unitatea de măsură din graficul de consum anual
        um = self._detect_unit(graphic_consumption)

        # Debug: câte endpointuri au returnat None
        all_results = [
            contract_details, invoices_unpaid, invoices_prosum,
            invoice_balance, invoice_balance_prosum,
            rescheduling_plans, graphic_consumption,
            meter_index, consumption_convention,
            meter_history, payments,
        ]
        none_count = sum(x is None for x in all_results)
        total = 7 if self.is_collective else 11
        _LOGGER.debug(
            "Actualizare E·ON finalizată (contract=%s, colectiv=%s). Endpointuri fără date: %s/%s.",
            cod, self.is_collective, none_count, total,
        )

        return {
            # Contract
            "contract_details": contract_details,
            # Facturi
            "invoices_unpaid": invoices_unpaid,
            "invoices_prosum": invoices_prosum,
            "invoice_balance": invoice_balance,
            "invoice_balance_prosum": invoice_balance_prosum,
            "rescheduling_plans": rescheduling_plans,
            "graphic_consumption": graphic_consumption,
            # Contor
            "meter_index": meter_index,
            "consumption_convention": consumption_convention,
            "meter_history": meter_history,
            # Plăți
            "payments": payments,
            # Subcontracte (doar pentru contracte colective/DUO)
            "subcontracts": subcontracts,
            "subcontracts_details": subcontracts_details,
            "subcontracts_conventions": subcontracts_conventions,
            "subcontracts_meter_index": subcontracts_meter_index,
            # Metadate
            "um": um,
            "is_collective": self.is_collective,
        }

    @staticmethod
    def _detect_unit(graphic_consumption_data) -> str:
        """Detectează unitatea de măsură: m3 (gaz) sau kWh (electricitate)."""
        if not graphic_consumption_data or not isinstance(graphic_consumption_data, dict):
            return "m3"
        um_raw = graphic_consumption_data.get("um")
        if um_raw:
            return um_raw.lower()
        return "m3"
