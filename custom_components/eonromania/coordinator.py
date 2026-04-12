"""DataUpdateCoordinator pentru integrarea E·ON România.

Strategia de actualizare:
- Prima actualizare (refresh #0): apelează TOATE endpoint-urile → detectează capabilități
- Refresh-uri ușoare (light): doar endpoint-uri esențiale (5 calls)
- Refresh-uri grele (heavy, la fiecare al 4-lea): + endpoint-uri istorice/opționale
- Capabilitățile se recalibrează la fiecare al 4-lea refresh (~1×/zi la 6h interval)
"""

import asyncio
import logging
from datetime import timedelta
import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EonApiClient
from .const import DOMAIN, LICENSE_DATA_KEY

_LOGGER = logging.getLogger(__name__)

# Fiecare al N-lea refresh este „greu" (include endpoint-uri istorice/paginate)
HEAVY_REFRESH_EVERY = 4  # La 6h interval = heavy la fiecare 24h

# Limită paginare pentru endpoint-urile paginate (payments, invoices_prosum)
MAX_PAGINATED_PAGES = 3


class EonRomaniaCoordinator(DataUpdateCoordinator):
    """Coordinator care se ocupă de toate datele E·ON România."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: EonApiClient,
        cod_incasare: str,
        update_interval: int,
        is_collective: bool = False,
        config_entry: ConfigEntry | None = None,
        account_only: bool = False,
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
        self.account_only = account_only
        self._config_entry = config_entry

        # Capabilități detectate la prima actualizare
        # None = nedeterminate (prima actualizare le va seta)
        self._capabilities: dict[str, bool] | None = None
        self._refresh_counter: int = 0

    @property
    def _is_heavy_refresh(self) -> bool:
        """Determină dacă refresh-ul curent este „greu" (include endpoint-uri istorice)."""
        return self._refresh_counter % HEAVY_REFRESH_EVERY == 0

    def _update_capabilities(
        self,
        invoices_prosum,
        invoice_balance_prosum,
        rescheduling_plans,
        payments,
    ) -> None:
        """Actualizează capabilitățile pe baza datelor primite."""
        # Prosum: are date dacă invoices_prosum e non-empty SAU invoice_balance_prosum are sold
        has_prosum = False
        if invoices_prosum and isinstance(invoices_prosum, list) and len(invoices_prosum) > 0:
            has_prosum = True
        elif invoice_balance_prosum and isinstance(invoice_balance_prosum, dict):
            # Verifică dacă balance_prosum are date reale (nu doar structura goală)
            balance_val = invoice_balance_prosum.get("totalBalance") or invoice_balance_prosum.get("balance")
            if balance_val is not None and balance_val != 0:
                has_prosum = True

        has_rescheduling = bool(
            rescheduling_plans and isinstance(rescheduling_plans, list) and len(rescheduling_plans) > 0
        )

        has_payments = bool(
            payments and isinstance(payments, list) and len(payments) > 0
        )

        self._capabilities = {
            "has_prosum": has_prosum,
            "has_rescheduling": has_rescheduling,
            "has_payments": has_payments,
        }

        _LOGGER.info(
            "[CAPABILITIES] Detectate (contract=%s): prosum=%s, eșalonare=%s, plăți=%s.",
            self.cod_incasare,
            has_prosum,
            has_rescheduling,
            has_payments,
        )

    @property
    def capabilities(self) -> dict[str, bool] | None:
        """Returnează capabilitățile detectate (None dacă nedeterminate încă)."""
        return self._capabilities

    def _cap(self, key: str) -> bool:
        """Verifică o capabilitate. Returnează True dacă nedeterminată (prima dată)."""
        if self._capabilities is None:
            return True  # Prima actualizare: apelează tot
        return self._capabilities.get(key, False)

    async def _async_update_data(self) -> dict:
        """Obține date de la API cu strategie light/heavy.

        Light refresh (frecvent): contract_details, invoice_balance, invoices_unpaid,
            meter_index, consumption_convention
        Heavy refresh (rar): + payments, invoices_prosum, invoice_balance_prosum,
            rescheduling_plans, graphic_consumption, meter_history
        Account-only: doar user-details (fără contracte)
        """
        # Verificare licență — nu fetchuim date dacă licența/trial nu e validă
        license_mgr = self.hass.data.get(DOMAIN, {}).get(LICENSE_DATA_KEY)
        if license_mgr and not license_mgr.is_valid:
            _LOGGER.debug("[EonRomania] Licență invalidă — se omit apelurile API")
            return self.data or {}

        # ── Mod account_only: doar date personale ──
        if self.account_only:
            return await self._async_update_data_account_only()

        cod = self.cod_incasare
        is_heavy = self._is_heavy_refresh

        _LOGGER.debug(
            "Actualizare E·ON (contract=%s, colectiv=%s, refresh=#%s, tip=%s).",
            cod, self.is_collective, self._refresh_counter,
            "HEAVY" if is_heavy else "light",
        )

        try:
            # Asigurăm token valid — refresh_token mai întâi, apoi login complet
            # _ensure_token_valid() folosește refresh_token (fără MFA!) ca prim pas
            if not self.api_client.is_token_likely_valid():
                # Verificăm dacă login-ul e blocat de MFA
                if self.api_client.mfa_blocked:
                    _LOGGER.warning(
                        "Login blocat — MFA necesar. Reconfigurați integrarea (contract=%s).",
                        cod,
                    )
                    self._create_reauth_notification()
                    raise UpdateFailed(
                        "Autentificarea necesită MFA. "
                        "Reconfigurați integrarea din Setări → Dispozitive și servicii → E·ON România."
                    )

                _LOGGER.debug(
                    "Token absent sau probabil expirat. Se asigură token valid (contract=%s).",
                    cod,
                )
                ok = await self.api_client.async_ensure_authenticated()
                if not ok:
                    if self.api_client.mfa_blocked:
                        self._create_reauth_notification()
                    _LOGGER.warning(
                        "Autentificare eșuată la API-ul E·ON (contract=%s).", cod
                    )
                    raise UpdateFailed("Nu s-a putut autentifica la API-ul E·ON.")

            # ──────────────────────────────────────
            # Endpoint-uri ESENȚIALE (la fiecare refresh)
            # ──────────────────────────────────────
            essential_tasks = [
                self.api_client.async_fetch_contract_details(cod),
                self.api_client.async_fetch_invoice_balance(cod),
                self.api_client.async_fetch_invoices_unpaid(cod),
            ]

            (
                contract_details,
                invoice_balance,
                invoices_unpaid,
            ) = await asyncio.gather(*essential_tasks)

            _LOGGER.debug(
                "Date esențiale (contract=%s): contract_details=%s, invoice_balance=%s, "
                "invoices_unpaid=%s (len=%s).",
                cod,
                type(contract_details).__name__ if contract_details else None,
                type(invoice_balance).__name__ if invoice_balance else None,
                type(invoices_unpaid).__name__ if invoices_unpaid else None,
                len(invoices_unpaid) if isinstance(invoices_unpaid, list) else "N/A",
            )

            # ──────────────────────────────────────
            # Endpoint-uri GRELE / OPȚIONALE (doar la heavy refresh)
            # Se reutilizează datele anterioare la light refresh.
            # ──────────────────────────────────────
            prev = self.data or {}

            if is_heavy:
                heavy_tasks = []
                heavy_labels = []

                # Payments — doar dacă are capabilitate sau prima dată
                if self._cap("has_payments"):
                    heavy_tasks.append(
                        self.api_client.async_fetch_payments(cod, max_pages=MAX_PAGINATED_PAGES)
                    )
                    heavy_labels.append("payments")

                # Prosum — doar dacă are capabilitate sau prima dată
                if self._cap("has_prosum"):
                    heavy_tasks.append(
                        self.api_client.async_fetch_invoices_prosum(cod, max_pages=MAX_PAGINATED_PAGES)
                    )
                    heavy_labels.append("invoices_prosum")
                    heavy_tasks.append(
                        self.api_client.async_fetch_invoice_balance_prosum(cod)
                    )
                    heavy_labels.append("invoice_balance_prosum")

                # Rescheduling — doar dacă are capabilitate sau prima dată
                if self._cap("has_rescheduling"):
                    heavy_tasks.append(
                        self.api_client.async_fetch_rescheduling_plans(cod)
                    )
                    heavy_labels.append("rescheduling_plans")

                if heavy_tasks:
                    heavy_results = await asyncio.gather(*heavy_tasks)
                    heavy_map = dict(zip(heavy_labels, heavy_results))
                else:
                    heavy_map = {}

                payments = heavy_map.get("payments")
                invoices_prosum = heavy_map.get("invoices_prosum")
                invoice_balance_prosum = heavy_map.get("invoice_balance_prosum")
                rescheduling_plans = heavy_map.get("rescheduling_plans")

                _LOGGER.debug(
                    "Date grele (contract=%s): %s endpoint-uri apelate (%s).",
                    cod, len(heavy_tasks), ", ".join(heavy_labels),
                )

                # Actualizează capabilitățile (la fiecare heavy refresh)
                self._update_capabilities(
                    invoices_prosum, invoice_balance_prosum,
                    rescheduling_plans, payments,
                )

            else:
                # Light refresh: reutilizăm datele grele din refresh-ul anterior
                payments = prev.get("payments")
                invoices_prosum = prev.get("invoices_prosum")
                invoice_balance_prosum = prev.get("invoice_balance_prosum")
                rescheduling_plans = prev.get("rescheduling_plans")

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
                # Contract individual: meter_index + consumption_convention la fiecare refresh
                # graphic_consumption + meter_history doar la heavy
                meter_essential_tasks = [
                    self.api_client.async_fetch_meter_index(cod),
                    self.api_client.async_fetch_consumption_convention(cod),
                ]

                (
                    meter_index,
                    consumption_convention,
                ) = await asyncio.gather(*meter_essential_tasks)

                if is_heavy:
                    meter_heavy_tasks = [
                        self.api_client.async_fetch_graphic_consumption(cod),
                        self.api_client.async_fetch_meter_history(cod),
                    ]
                    (
                        graphic_consumption,
                        meter_history,
                    ) = await asyncio.gather(*meter_heavy_tasks)
                else:
                    graphic_consumption = prev.get("graphic_consumption")
                    meter_history = prev.get("meter_history")

                _LOGGER.debug(
                    "Date contor (contract=%s): meter_index=%s, consumption_convention=%s, "
                    "graphic_consumption=%s, meter_history=%s.",
                    cod,
                    type(meter_index).__name__ if meter_index else None,
                    type(consumption_convention).__name__ if consumption_convention else None,
                    "fresh" if is_heavy and graphic_consumption else ("cached" if graphic_consumption else None),
                    "fresh" if is_heavy and meter_history else ("cached" if meter_history else None),
                )

            else:
                # Contract colectiv/DUO: subcontracte
                _LOGGER.debug(
                    "Contract colectiv/DUO (contract=%s). Se interoghează subcontractele.",
                    cod,
                )
                raw_subs = await self.api_client.async_fetch_contracts_list(
                    collective_contract=cod
                )

                if raw_subs and isinstance(raw_subs, list):
                    subcontracts = [
                        s for s in raw_subs
                        if isinstance(s, dict) and s.get("accountContract")
                    ]

                    sub_codes = [s["accountContract"] for s in subcontracts]
                    if sub_codes:
                        # Esențiale per subcontract: details + convention + meter_index
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

                        n = len(sub_codes)
                        detail_results = all_results[:n]
                        convention_results = all_results[n:2 * n]
                        meter_index_results = all_results[2 * n:]

                        subcontracts_details = [
                            d for d in detail_results if isinstance(d, dict)
                        ] or None

                        subcontracts_conventions = {}
                        for sc_code, conv_data in zip(sub_codes, convention_results):
                            if conv_data and isinstance(conv_data, list) and len(conv_data) > 0:
                                subcontracts_conventions[sc_code] = conv_data
                        subcontracts_conventions = subcontracts_conventions or None

                        subcontracts_meter_index = {}
                        for sc_code, mi_data in zip(sub_codes, meter_index_results):
                            if mi_data and isinstance(mi_data, dict):
                                subcontracts_meter_index[sc_code] = mi_data
                        subcontracts_meter_index = subcontracts_meter_index or None

                        _LOGGER.debug(
                            "DUO (contract=%s): %s subcontracte, details=%s, conventions=%s, meter_index=%s.",
                            cod, n,
                            len(subcontracts_details) if subcontracts_details else 0,
                            len(subcontracts_conventions) if subcontracts_conventions else 0,
                            len(subcontracts_meter_index) if subcontracts_meter_index else 0,
                        )

                    if not subcontracts:
                        subcontracts = None
                else:
                    _LOGGER.warning(
                        "DUO list (collective) invalid (contract=%s): %s.",
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
                cod, err,
            )
            raise UpdateFailed("Eroare neașteptată la actualizarea datelor E·ON.") from err

        # Verificăm datele esențiale
        if self.is_collective:
            if contract_details is None:
                _LOGGER.error(
                    "Date esențiale indisponibile: contract_details este None (contract colectiv=%s).",
                    cod,
                )
                raise UpdateFailed(
                    "Nu s-au putut obține datele esențiale de la E·ON (contract_details)."
                )
        else:
            if contract_details is None and meter_index is None:
                _LOGGER.error(
                    "Date esențiale indisponibile (contract_details + meter_index sunt None) (contract=%s).",
                    cod,
                )
                raise UpdateFailed(
                    "Nu s-au putut obține datele esențiale de la E·ON (contract_details + meter_index)."
                )

        # Detectează unitatea de măsură
        um = self._detect_unit(graphic_consumption)

        # Incrementăm contorul de refresh
        self._refresh_counter += 1

        # Persistăm token-ul curent în config_entry.data (pentru restart HA)
        self._persist_token()

        # Sumar
        _LOGGER.debug(
            "Actualizare E·ON finalizată (contract=%s, colectiv=%s, refresh=#%s).",
            cod, self.is_collective, self._refresh_counter - 1,
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

    async def _async_update_data_account_only(self) -> dict:
        """Actualizare simplificată: doar user-details (conturi fără contracte)."""
        _LOGGER.debug(
            "Actualizare E·ON account_only (refresh=#%s).",
            self._refresh_counter,
        )

        try:
            # Asigurăm token valid
            if not self.api_client.is_token_likely_valid():
                if self.api_client.mfa_blocked:
                    _LOGGER.warning("Login blocat — MFA necesar (account_only).")
                    self._create_reauth_notification()
                    raise UpdateFailed(
                        "Autentificarea necesită MFA. "
                        "Reconfigurați integrarea din Setări → Dispozitive și servicii → E·ON România."
                    )

                ok = await self.api_client.async_ensure_authenticated()
                if not ok:
                    if self.api_client.mfa_blocked:
                        self._create_reauth_notification()
                    raise UpdateFailed("Nu s-a putut autentifica la API-ul E·ON.")

            user_details = await self.api_client.async_fetch_user_details()

        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.exception("Eroare la actualizare account_only: %s", err)
            raise UpdateFailed("Eroare la obținerea datelor personale.") from err

        if not user_details or not isinstance(user_details, dict):
            raise UpdateFailed("Nu s-au putut obține datele personale (user-details).")

        self._refresh_counter += 1
        self._persist_token()

        _LOGGER.debug(
            "Actualizare account_only finalizată (refresh=#%s, user=%s).",
            self._refresh_counter - 1,
            user_details.get("email", "N/A"),
        )

        return {
            "account_only": True,
            "user_details": user_details,
        }

    def _persist_token(self) -> None:
        """Persistă token-ul curent în config_entry.data pentru restart HA.

        Salvează refresh_token + access_token astfel încât la restart
        coordinatorul poate folosi refresh_token fără a necesita MFA.
        """
        if self._config_entry is None:
            return
        token_data = self.api_client.export_token_data()
        if token_data is None:
            return

        current_data = dict(self._config_entry.data)
        old_token = current_data.get("token_data", {})

        # Actualizăm doar dacă s-a schimbat ceva (evităm scrieri inutile)
        if (
            old_token.get("access_token") == token_data.get("access_token")
            and old_token.get("refresh_token") == token_data.get("refresh_token")
        ):
            return

        current_data["token_data"] = token_data
        self.hass.config_entries.async_update_entry(
            self._config_entry, data=current_data
        )
        _LOGGER.debug(
            "Token persistat în config_entry (contract=%s, access=%s...).",
            self.cod_incasare,
            token_data["access_token"][:8] if token_data.get("access_token") else "None",
        )

    def _create_reauth_notification(self) -> None:
        """Creează o notificare persistentă care cere reconfigurare MFA."""
        from homeassistant.components import persistent_notification

        notification_id = f"eonromania_reauth_{self.cod_incasare}"
        persistent_notification.async_create(
            self.hass,
            message=(
                f"Sesiunea E·ON pentru contractul **{self.cod_incasare}** a expirat "
                f"și este necesară re-autentificarea cu cod MFA.\n\n"
                f"Mergeți la **Setări → Dispozitive și servicii → E·ON România → "
                f"Reconfigurare** pentru a vă re-autentifica.\n\n"
                f"Până la reconfigurare, integrarea NU va mai încerca login "
                f"(pentru a evita trimiterea repetată de email-uri MFA)."
            ),
            title="E·ON România — Autentificare necesară",
            notification_id=notification_id,
        )
        _LOGGER.info(
            "Notificare persistentă creată: reconfigurare necesară (contract=%s).",
            self.cod_incasare,
        )

    @staticmethod
    def _detect_unit(graphic_consumption_data) -> str:
        """Detectează unitatea de măsură: m3 (gaz) sau kWh (electricitate)."""
        if not graphic_consumption_data or not isinstance(graphic_consumption_data, dict):
            return "m3"
        um_raw = graphic_consumption_data.get("um")
        if um_raw:
            return um_raw.lower()
        return "m3"
