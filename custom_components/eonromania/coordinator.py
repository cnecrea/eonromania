"""DataUpdateCoordinator pentru integrarea E·ON România."""

import asyncio
import logging
from datetime import timedelta

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

    async def _async_update_data(self) -> dict:
        """Obține date de la API — toate apelurile în paralel."""
        cod = self.cod_incasare

        _LOGGER.debug("Începe actualizarea datelor E·ON (contract=%s).", cod)

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
            # Apeluri paralele — 11 endpoint-uri
            # ──────────────────────────────────────
            (
                contract_details,
                invoices_unpaid,
                invoices_prosum,
                invoice_balance,
                invoice_balance_prosum,
                rescheduling_plans,
                graphic_consumption,
                meter_index,
                consumption_convention,
                meter_history,
                payments,
            ) = await asyncio.gather(
                self.api_client.async_fetch_contract_details(cod),
                self.api_client.async_fetch_invoices_unpaid(cod),
                self.api_client.async_fetch_invoices_prosum(cod),
                self.api_client.async_fetch_invoice_balance(cod),
                self.api_client.async_fetch_invoice_balance_prosum(cod),
                self.api_client.async_fetch_rescheduling_plans(cod),
                self.api_client.async_fetch_graphic_consumption(cod),
                self.api_client.async_fetch_meter_index(cod),
                self.api_client.async_fetch_consumption_convention(cod),
                self.api_client.async_fetch_meter_history(cod),
                self.api_client.async_fetch_payments(cod),
            )

        except asyncio.TimeoutError as err:
            _LOGGER.error(
                "Depășire de timp la actualizarea datelor E·ON (contract=%s).", cod
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
        _LOGGER.debug(
            "Actualizare E·ON finalizată (contract=%s). Endpointuri fără date: %s/11.",
            cod,
            none_count,
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
            # Metadate
            "um": um,
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
