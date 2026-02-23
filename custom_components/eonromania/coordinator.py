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
            name="EonRomaniaCoordinator",
            update_interval=timedelta(seconds=update_interval),
        )
        self.api_client = api_client
        self.cod_incasare = cod_incasare

    async def _async_update_data(self) -> dict:
        """Obține date de la API — toate apelurile în paralel."""
        cod_incasare = self.cod_incasare

        _LOGGER.debug("Începe actualizarea datelor E·ON (contract=%s).", cod_incasare)

        try:
            # Login inteligent înainte de apelurile paralele:
            # - Dacă nu avem token deloc → login obligatoriu
            # - Dacă tokenul e probabil expirat (>55 min) → login proactiv
            # - Dacă tokenul e proaspăt → îl reutilizăm
            # Astfel evităm 9 cereri eșuate + 9 retry-uri la token expirat.
            if not self.api_client.is_token_likely_valid():
                _LOGGER.debug(
                    "Token absent sau probabil expirat. Se face login proactiv (contract=%s).",
                    cod_incasare,
                )
                self.api_client.invalidate_token()
                ok = await self.api_client.async_login()
                if not ok:
                    _LOGGER.warning(
                        "Autentificare eșuată la API-ul E·ON (contract=%s).", cod_incasare
                    )
                    raise UpdateFailed("Nu s-a putut autentifica la API-ul E·ON.")

            (
                dateuser_data,
                citireindex_data,
                conventieconsum_data,
                comparareanualagrafic_data,
                arhiva_data,
                facturasold_data,
                payments_data,
                facturasold_prosum_data,
                facturasold_prosum_balance_data,
            ) = await asyncio.gather(
                self.api_client.async_fetch_dateuser_data(cod_incasare),
                self.api_client.async_fetch_citireindex_data(cod_incasare),
                self.api_client.async_fetch_conventieconsum_data(cod_incasare),
                self.api_client.async_fetch_comparareanualagrafic_data(cod_incasare),
                self.api_client.async_fetch_arhiva_data(cod_incasare),
                self.api_client.async_fetch_facturasold_data(cod_incasare),
                self.api_client.async_fetch_payments_data(cod_incasare),
                self.api_client.async_fetch_facturasold_prosum_data(cod_incasare),
                self.api_client.async_fetch_facturasold_prosum_balance_data(cod_incasare),
            )

        except asyncio.TimeoutError as err:
            _LOGGER.error(
                "Depășire de timp la actualizarea datelor E·ON (contract=%s).",
                cod_incasare,
            )
            raise UpdateFailed("Depășire de timp la actualizarea datelor E·ON.") from err

        except UpdateFailed:
            raise

        except Exception as err:
            _LOGGER.exception(
                "Eroare neașteptată la actualizarea datelor E·ON (contract=%s): %s",
                cod_incasare,
                err,
            )
            raise UpdateFailed("Eroare neașteptată la actualizarea datelor E·ON.") from err

        # Verificăm dacă datele esențiale sunt disponibile
        if dateuser_data is None and citireindex_data is None:
            _LOGGER.error(
                "Date esențiale indisponibile de la E·ON (dateuser + citireindex sunt None) (contract=%s).",
                cod_incasare,
            )
            raise UpdateFailed(
                "Nu s-au putut obține datele esențiale de la E·ON (dateuser + citireindex)."
            )

        # Detectează unitatea de măsură din graficul de consum anual.
        # "m3" = gaz, "kWh" = curent electric.
        # Dacă câmpul lipsește din răspuns, fallback pe "m3".
        um = "m3"
        if isinstance(comparareanualagrafic_data, dict):
            um_raw = comparareanualagrafic_data.get("um")
            if um_raw:
                um = um_raw.lower()  # normalizează: 'M3' -> 'm3', 'KWH' -> 'kwh'
            else:
                _LOGGER.debug(
                    "Câmpul 'um' lipsește din comparareanualagrafic (contract=%s). "
                    "Se folosește valoarea implicită: '%s'. "
                    "Structura răspunsului: %s",
                    cod_incasare,
                    um,
                    list(comparareanualagrafic_data.keys()),
                )

        _LOGGER.debug(
            "Unitate de măsură detectată: '%s' (contract=%s).",
            um,
            cod_incasare,
        )

        # Debug scurt, util: câte endpointuri au venit cu None
        none_count = sum(
            x is None
            for x in (
                dateuser_data,
                citireindex_data,
                conventieconsum_data,
                comparareanualagrafic_data,
                arhiva_data,
                facturasold_data,
                payments_data,
                facturasold_prosum_data,
                facturasold_prosum_balance_data,
            )
        )
        _LOGGER.debug(
            "Actualizare E·ON finalizată (contract=%s). Endpointuri fără date: %s/9.",
            cod_incasare,
            none_count,
        )

        return {
            "dateuser": dateuser_data,
            "citireindex": citireindex_data,
            "conventieconsum": conventieconsum_data,
            "comparareanualagrafic": comparareanualagrafic_data,
            "arhiva": arhiva_data,
            "facturasold": facturasold_data,
            "payments": payments_data,
            "facturasold_prosum": facturasold_prosum_data,
            "facturasold_prosum_balance": facturasold_prosum_balance_data,
            "um": um,
        }
