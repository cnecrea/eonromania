import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from .api import EonApiClient

_LOGGER = logging.getLogger(__name__)

class EonRomaniaCoordinator(DataUpdateCoordinator):
    """Coordinator care se ocupă de toate datele E-ON România."""

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

    async def _async_update_data(self):
        """Obține date de la API."""
        # E posibil să facem un singur request dacă exista un endpoint
        # unificat, dar cum nu avem, le facem pe fiecare în parte:

        dateuser_data = await self.api_client.async_fetch_dateuser_data(self.cod_incasare)
        citireindex_data = await self.api_client.async_fetch_citireindex_data(self.cod_incasare)
        conventieconsum_data = await self.api_client.async_fetch_conventieconsum_data(self.cod_incasare)
        comparareanualagrafic_data = await self.api_client.async_fetch_comparareanualagrafic_data(self.cod_incasare)
        arhiva_data = await self.api_client.async_fetch_arhiva_data(self.cod_incasare)
        facturasold_data = await self.api_client.async_fetch_facturasold_data(self.cod_incasare)

        # Apel nou pentru plățile paginate
        payments_data = await self.api_client.async_fetch_payments_data(self.cod_incasare)

        # Apeluri pentru facturile de prosumator
        facturasold_prosum_data = await self.api_client.async_fetch_facturasold_prosum_data(self.cod_incasare)
        facturasold_prosum_balance_data = await self.api_client.async_fetch_facturasold_prosum_balance_data(self.cod_incasare)

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
        }
