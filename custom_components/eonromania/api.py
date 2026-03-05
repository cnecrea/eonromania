"""Client API pentru comunicarea cu E·ON România."""

import asyncio
import logging
import time
import json

from aiohttp import ClientSession, ClientTimeout

from .const import (
    API_TIMEOUT,
    AUTH_VERIFY_SECRET,
    HEADERS,
    TOKEN_MAX_AGE,
    TOKEN_REFRESH_THRESHOLD,
    URL_CONSUMPTION_CONVENTION,
    URL_CONTRACT_DETAILS,
    URL_CONTRACTS_DETAILS_LIST,
    URL_CONTRACTS_LIST,
    URL_CONTRACTS_WITH_SUBCONTRACTS,
    URL_GRAPHIC_CONSUMPTION,
    URL_INVOICE_BALANCE,
    URL_INVOICE_BALANCE_PROSUM,
    URL_INVOICES_PROSUM,
    URL_INVOICES_UNPAID,
    URL_LOGIN,
    URL_METER_HISTORY,
    URL_METER_INDEX,
    URL_METER_SUBMIT,
    URL_PAYMENT_LIST,
    URL_REFRESH_TOKEN,
    URL_RESCHEDULING_PLANS,
)
from .helpers import generate_verify_hmac

_LOGGER = logging.getLogger(__name__)


class EonApiClient:
    """Clasă pentru comunicarea cu API-ul E·ON România."""

    def __init__(self, session: ClientSession, username: str, password: str):
        """Inițializează clientul API cu o sesiune de tip ClientSession."""
        self._session = session
        self._username = username
        self._password = password

        # Token management
        self._access_token: str | None = None
        self._token_type: str = "Bearer"
        self._expires_in: int = 3600
        self._refresh_token: str | None = None
        self._id_token: str | None = None
        self._uuid: str | None = None
        self._token_obtained_at: float = 0.0

        self._timeout = ClientTimeout(total=API_TIMEOUT)
        self._auth_lock = asyncio.Lock()
        self._token_generation: int = 0

    # ──────────────────────────────────────────
    # Proprietăți publice
    # ──────────────────────────────────────────

    @property
    def has_token(self) -> bool:
        """Verifică dacă există un token setat (nu garantează validitatea)."""
        return self._access_token is not None

    @property
    def uuid(self) -> str | None:
        """Returnează UUID-ul utilizatorului autentificat."""
        return self._uuid

    def is_token_likely_valid(self) -> bool:
        """Verifică dacă tokenul există ȘI nu a depășit durata maximă estimată."""
        if self._access_token is None:
            return False
        age = time.monotonic() - self._token_obtained_at
        # Folosim expires_in din răspunsul API, cu fallback pe TOKEN_MAX_AGE
        effective_max = self._expires_in - TOKEN_REFRESH_THRESHOLD if self._expires_in > TOKEN_REFRESH_THRESHOLD else TOKEN_MAX_AGE
        return age < effective_max

    # ──────────────────────────────────────────
    # Autentificare
    # ──────────────────────────────────────────

    async def async_login(self) -> bool:
        """Obține un token nou de autentificare prin mobile-login (fără lock — se apelează din _ensure_token_valid)."""
        verify = generate_verify_hmac(self._username, AUTH_VERIFY_SECRET)
        payload = {
            "username": self._username,
            "password": self._password,
            "verify": verify,
        }

        _LOGGER.debug("[LOGIN] Trimitere cerere: URL=%s, Payload=%s", URL_LOGIN, json.dumps(payload))

        try:
            async with self._session.post(
                URL_LOGIN, json=payload, headers=HEADERS, timeout=self._timeout
            ) as resp:
                response_text = await resp.text()
                _LOGGER.debug("[LOGIN] Răspuns: Status=%s, Body=%s", resp.status, response_text)

                if resp.status == 200:
                    data = await resp.json()
                    # Debug clar pentru datele primite la login
                    _LOGGER.debug(
                        "[LOGIN] Date primite: type=%s, keys=%s, sample=%s",
                        type(data).__name__,
                        list(data.keys()) if isinstance(data, dict) else "N/A",
                        json.dumps(data, default=str)[:500]  # Limitat pentru a evita loguri uriașe
                    )
                    self._apply_token_data(data)
                    _LOGGER.debug("[LOGIN] Token obținut cu succes (expires_in=%s).", self._expires_in)
                    return True

                _LOGGER.error(
                    "[LOGIN] Eroare autentificare. Cod HTTP=%s, Răspuns=%s",
                    resp.status,
                    response_text,
                )
                self._invalidate_tokens()
                return False

        except asyncio.TimeoutError:
            _LOGGER.error("[LOGIN] Depășire de timp.")
            self._invalidate_tokens()
            return False
        except Exception as e:
            _LOGGER.error("[LOGIN] Eroare: %s", e)
            self._invalidate_tokens()
            return False

    async def async_refresh_token(self) -> bool:
        """Reîmprospătează tokenul de acces folosind refresh_token (fără lock — se apelează din _ensure_token_valid)."""
        if not self._refresh_token:
            _LOGGER.debug("[REFRESH] Nu există refresh_token. Se va face login complet.")
            return False

        payload = {"refreshToken": self._refresh_token}

        _LOGGER.debug("[REFRESH] Trimitere cerere: URL=%s, Payload=%s", URL_REFRESH_TOKEN, json.dumps(payload))

        try:
            async with self._session.post(
                URL_REFRESH_TOKEN, json=payload, headers=HEADERS, timeout=self._timeout
            ) as resp:
                response_text = await resp.text()
                _LOGGER.debug("[REFRESH] Răspuns: Status=%s, Body=%s", resp.status, response_text)

                if resp.status == 200:
                    data = await resp.json()
                    # Debug clar pentru datele primite la refresh
                    _LOGGER.debug(
                        "[REFRESH] Date primite: type=%s, keys=%s, sample=%s",
                        type(data).__name__,
                        list(data.keys()) if isinstance(data, dict) else "N/A",
                        json.dumps(data, default=str)[:500]
                    )
                    self._apply_token_data(data)
                    _LOGGER.debug("[REFRESH] Token reîmprospătat cu succes (expires_in=%s).", self._expires_in)
                    return True

                _LOGGER.warning(
                    "[REFRESH] Eroare la reîmprospătare. Cod HTTP=%s, Răspuns=%s",
                    resp.status,
                    response_text,
                )
                return False

        except asyncio.TimeoutError:
            _LOGGER.error("[REFRESH] Depășire de timp.")
            return False
        except Exception as e:
            _LOGGER.error("[REFRESH] Eroare: %s", e)
            return False

    def _apply_token_data(self, data: dict) -> None:
        """Aplică datele de token din răspunsul API (login sau refresh)."""
        self._access_token = data.get("access_token")
        self._token_type = data.get("token_type", "Bearer")
        self._expires_in = data.get("expires_in", 3600)
        self._refresh_token = data.get("refresh_token")
        self._id_token = data.get("idToken")  # camelCase conform API real
        self._uuid = data.get("uuid")
        self._token_obtained_at = time.monotonic()
        self._token_generation += 1

    def invalidate_token(self) -> None:
        """Invalidează tokenul curent (pentru a forța re-autentificare)."""
        self._access_token = None
        self._token_obtained_at = 0.0

    def _invalidate_tokens(self) -> None:
        """Invalidează toate tokenurile (acces + refresh)."""
        self._access_token = None
        self._refresh_token = None
        self._id_token = None
        self._uuid = None
        self._token_obtained_at = 0.0

    async def _ensure_token_valid(self) -> bool:
        """
        Asigură că există un token valid — refresh sau login complet.

        Thread-safe: folosește _auth_lock pentru a preveni refresh-uri/login-uri
        concurente. Când mai multe request-uri paralele au nevoie de token nou,
        doar primul face refresh/login, restul reutilizează rezultatul.
        """
        # Fast path fără lock: token deja valid
        if self.is_token_likely_valid():
            return True

        async with self._auth_lock:
            # Double-check după ce am obținut lock-ul:
            # alt apel concurent poate fi deja reînnoit tokenul
            if self.is_token_likely_valid():
                _LOGGER.debug("[AUTH] Token deja disponibil (obținut de alt apel concurent).")
                return True

            # Încearcă refresh dacă avem refresh_token
            if self._refresh_token:
                if await self.async_refresh_token():
                    return True
                _LOGGER.debug("[AUTH] Refresh token eșuat. Se încearcă login complet.")

            # Fallback la login complet
            self._invalidate_tokens()
            return await self.async_login()

    # ──────────────────────────────────────────
    # Contracte
    # ──────────────────────────────────────────

    async def async_fetch_contracts_list(self, partner_code: str | None = None, collective_contract: str | None = None, limit: int | None = None):
        """Obține lista contractelor pentru un partener."""
        params = {}
        if partner_code:
            params["partnerCode"] = partner_code
        if collective_contract:
            params["collectiveContract"] = collective_contract
        if limit is not None:
            params["limit"] = str(limit)
        url = URL_CONTRACTS_LIST
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"
        result = await self._request_with_token(
            method="GET",
            url=url,
            label="contracts_list",
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[contracts_list] Date primite: type=%s, len=%s, sample keys=%s, sample content=%s",
            type(result).__name__,
            len(result) if isinstance(result, (list, dict)) else "N/A",
            list(result[0].keys()) if isinstance(result, list) and result else list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_contract_details(self, account_contract: str, include_meter_reading: bool = True):
        """Obține detaliile unui contract specific."""
        url = URL_CONTRACT_DETAILS.format(accountContract=account_contract)
        if include_meter_reading:
            url = f"{url}?includeMeterReading=true"
        result = await self._request_with_token(
            method="GET",
            url=url,
            label=f"contract_details ({account_contract})",
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[contract_details %s] Date primite: type=%s, keys=%s, sample=%s",
            account_contract,
            type(result).__name__,
            list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_contracts_with_subcontracts(self, account_contract: str | None = None):
        """Obține lista contractelor cu subcontracte (pentru contracte colective/DUO).

        Apelează FĂRĂ parametru (returnează toate contractele cu subcontracte
        ale utilizatorului autentificat). Dacă e specificat account_contract,
        rezultatele sunt filtrate local ulterior.
        """
        # Apelăm fără filtru — API-ul returnează toate contractele cu subcontracte
        url = URL_CONTRACTS_WITH_SUBCONTRACTS
        label = f"contracts_with_subcontracts ({account_contract or 'all'})"
        _LOGGER.debug("[%s] URL complet: %s", label, url)
        result = await self._request_with_token(
            method="GET",
            url=url,
            label=label,
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[%s] Date primite: type=%s, len=%s, sample keys=%s, sample content=%s",
            label,
            type(result).__name__,
            len(result) if isinstance(result, (list, dict)) else "N/A",
            list(result[0].keys()) if isinstance(result, list) and result else list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_contracts_details_list(self, account_contracts: list[str]):
        """Obține detaliile mai multor contracte simultan (subcontracte DUO).

        Request body: ContractDetailsRequest — obiect cu accountContracts[] + includeMeterReading.
        Response: List<ElectronicInvoiceStatusResponse>
        """
        if not account_contracts:
            return None
        payload = {
            "accountContracts": account_contracts,
            "includeMeterReading": True,
        }
        label = f"contracts_details_list ({len(account_contracts)} subcontracte)"
        result = await self._request_with_token_post(
            url=URL_CONTRACTS_DETAILS_LIST,
            payload=payload,
            label=label,
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[%s] Date primite: type=%s, len=%s, sample keys=%s, sample content=%s",
            label,
            type(result).__name__,
            len(result) if isinstance(result, (list, dict)) else "N/A",
            list(result[0].keys()) if isinstance(result, list) and result else list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    # ──────────────────────────────────────────
    # Facturi & Plăți
    # ──────────────────────────────────────────

    async def async_fetch_invoices_unpaid(self, account_contract: str, include_subcontracts: bool = False):
        """Obține facturile neachitate."""
        params = f"?accountContract={account_contract}&status=unpaid"
        if include_subcontracts:
            params += "&includeSubcontracts=true"
        result = await self._request_with_token(
            method="GET",
            url=f"{URL_INVOICES_UNPAID}{params}",
            label=f"invoices_unpaid ({account_contract})",
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[invoices_unpaid %s] Date primite: type=%s, len=%s, sample keys=%s, sample content=%s",
            account_contract,
            type(result).__name__,
            len(result) if isinstance(result, (list, dict)) else "N/A",
            list(result[0].keys()) if isinstance(result, list) and result else list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_invoices_prosum(self, account_contract: str):
        """Obține toate facturile de prosumator (paginate)."""
        result = await self._paginated_request(
            base_url=URL_INVOICES_PROSUM,
            params={"accountContract": account_contract},
            list_key="list",
            label=f"invoices_prosum ({account_contract})",
        )
        # Debug clar pentru datele cumulate
        _LOGGER.debug(
            "[invoices_prosum %s] Date cumulate: type=%s, len=%s, sample keys=%s, sample content=%s",
            account_contract,
            type(result).__name__,
            len(result) if isinstance(result, list) else "N/A",
            list(result[0].keys()) if isinstance(result, list) and result else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_invoice_balance(self, account_contract: str, include_subcontracts: bool = False):
        """Obține soldul facturii."""
        params = f"?accountContract={account_contract}"
        if include_subcontracts:
            params += "&includeSubcontracts=true"
        result = await self._request_with_token(
            method="GET",
            url=f"{URL_INVOICE_BALANCE}{params}",
            label=f"invoice_balance ({account_contract})",
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[invoice_balance %s] Date primite: type=%s, keys=%s, sample=%s",
            account_contract,
            type(result).__name__,
            list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_invoice_balance_prosum(self, account_contract: str, include_subcontracts: bool = False):
        """Obține soldul facturii de prosumator."""
        params = f"?accountContract={account_contract}"
        if include_subcontracts:
            params += "&includeSubcontracts=true"
        result = await self._request_with_token(
            method="GET",
            url=f"{URL_INVOICE_BALANCE_PROSUM}{params}",
            label=f"invoice_balance_prosum ({account_contract})",
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[invoice_balance_prosum %s] Date primite: type=%s, keys=%s, sample=%s",
            account_contract,
            type(result).__name__,
            list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_payments(self, account_contract: str):
        """Obține toate înregistrările de plăți (paginate)."""
        result = await self._paginated_request(
            base_url=URL_PAYMENT_LIST,
            params={"accountContract": account_contract},
            list_key="list",
            label=f"payments ({account_contract})",
        )
        # Debug clar pentru datele cumulate
        _LOGGER.debug(
            "[payments %s] Date cumulate: type=%s, len=%s, sample keys=%s, sample content=%s",
            account_contract,
            type(result).__name__,
            len(result) if isinstance(result, list) else "N/A",
            list(result[0].keys()) if isinstance(result, list) and result else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_rescheduling_plans(self, account_contract: str, include_subcontracts: bool = False, status: str | None = None):
        """Obține planurile de eșalonare."""
        params = f"?accountContract={account_contract}"
        if include_subcontracts:
            params += "&includeSubcontracts=true"
        if status:
            params += f"&status={status}"
        result = await self._request_with_token(
            method="GET",
            url=f"{URL_RESCHEDULING_PLANS}{params}",
            label=f"rescheduling_plans ({account_contract})",
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[rescheduling_plans %s] Date primite: type=%s, len=%s, sample keys=%s, sample content=%s",
            account_contract,
            type(result).__name__,
            len(result) if isinstance(result, (list, dict)) else "N/A",
            list(result[0].keys()) if isinstance(result, list) and result else list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_graphic_consumption(self, account_contract: str):
        """Obține graficul consumului facturat."""
        url = URL_GRAPHIC_CONSUMPTION.format(accountContract=account_contract)
        result = await self._request_with_token(
            method="GET",
            url=url,
            label=f"graphic_consumption ({account_contract})",
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[graphic_consumption %s] Date primite: type=%s, keys=%s, sample=%s",
            account_contract,
            type(result).__name__,
            list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    # ──────────────────────────────────────────
    # Citiri Contor & Convenții
    # ──────────────────────────────────────────

    async def async_fetch_meter_index(self, account_contract: str):
        """Obține datele despre indexul curent."""
        url = URL_METER_INDEX.format(accountContract=account_contract)
        result = await self._request_with_token(
            method="GET",
            url=url,
            label=f"meter_index ({account_contract})",
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[meter_index %s] Date primite: type=%s, keys=%s, sample=%s",
            account_contract,
            type(result).__name__,
            list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_meter_history(self, account_contract: str):
        """Obține istoricul citirilor contorului."""
        url = URL_METER_HISTORY.format(accountContract=account_contract)
        result = await self._request_with_token(
            method="GET",
            url=url,
            label=f"meter_history ({account_contract})",
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[meter_history %s] Date primite: type=%s, len=%s, sample keys=%s, sample content=%s",
            account_contract,
            type(result).__name__,
            len(result) if isinstance(result, (list, dict)) else "N/A",
            list(result[0].keys()) if isinstance(result, list) and result else list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_fetch_consumption_convention(self, account_contract: str):
        """Obține convenția de consum curentă."""
        url = URL_CONSUMPTION_CONVENTION.format(accountContract=account_contract)
        result = await self._request_with_token(
            method="GET",
            url=url,
            label=f"consumption_convention ({account_contract})",
        )
        # Debug clar pentru datele primite
        _LOGGER.debug(
            "[consumption_convention %s] Date primite: type=%s, keys=%s, sample=%s",
            account_contract,
            type(result).__name__,
            list(result.keys()) if isinstance(result, dict) else "N/A",
            json.dumps(result, default=str)[:500] if result else "None"
        )
        return result

    async def async_submit_meter_index(
        self, account_contract: str, indexes: list[dict]
    ):
        """Trimite indexul contorului către API-ul E·ON."""
        label = f"submit_meter ({account_contract})"

        if not account_contract or not indexes:
            _LOGGER.error("[%s] Parametri invalizi pentru trimiterea indexului.", label)
            return None

        payload = {
            "accountContract": account_contract,
            "channel": "MOBILE",
            "indexes": indexes,
        }

        if not await self._ensure_token_valid():
            _LOGGER.error("[%s] Token invalid. Trimiterea nu poate fi efectuată.", label)
            return None

        gen_before = self._token_generation
        headers = {**HEADERS, "Authorization": f"{self._token_type} {self._access_token}"}

        _LOGGER.debug("[%s] Trimitere cerere: URL=%s, Payload=%s", label, URL_METER_SUBMIT, json.dumps(payload))

        try:
            async with self._session.post(
                URL_METER_SUBMIT,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            ) as resp:
                response_text = await resp.text()
                _LOGGER.debug("[%s] Răspuns: Status=%s, Body=%s", label, resp.status, response_text)

                if resp.status == 200:
                    data = await resp.json()
                    # Debug clar pentru datele primite la submit
                    _LOGGER.debug(
                        "[%s] Date primite: type=%s, keys=%s, sample=%s",
                        label,
                        type(data).__name__,
                        list(data.keys()) if isinstance(data, dict) else "N/A",
                        json.dumps(data, default=str)[:500] if data else "None"
                    )
                    _LOGGER.debug("[%s] Index trimis cu succes.", label)
                    return data

                if resp.status == 401:
                    # Verifică dacă alt apel a reînnoit deja tokenul
                    if self._token_generation != gen_before:
                        _LOGGER.debug("[%s] Token reînnoit de alt apel. Se reîncearcă.", label)
                    else:
                        _LOGGER.warning("[%s] Token invalid (401). Se reîncearcă...", label)
                        self.invalidate_token()
                        if not await self._ensure_token_valid():
                            _LOGGER.error("[%s] Reautentificare eșuată.", label)
                            return None

                    headers_retry = {**HEADERS, "Authorization": f"{self._token_type} {self._access_token}"}
                    async with self._session.post(
                        URL_METER_SUBMIT,
                        json=payload,
                        headers=headers_retry,
                        timeout=self._timeout,
                    ) as resp_retry:
                        response_text_retry = await resp_retry.text()
                        _LOGGER.debug("[%s] Reîncercare: Status=%s, Body=%s", label, resp_retry.status, response_text_retry)
                        if resp_retry.status == 200:
                            data_retry = await resp_retry.json()
                            # Debug clar pentru datele primite la retry
                            _LOGGER.debug(
                                "[%s] Date primite (retry): type=%s, keys=%s, sample=%s",
                                label,
                                type(data_retry).__name__,
                                list(data_retry.keys()) if isinstance(data_retry, dict) else "N/A",
                                json.dumps(data_retry, default=str)[:500] if data_retry else "None"
                            )
                            _LOGGER.debug("[%s] Index trimis cu succes (după reautentificare).", label)
                            return data_retry
                        _LOGGER.error("[%s] Reîncercare eșuată. Cod HTTP=%s", label, resp_retry.status)
                        return None

                _LOGGER.error("[%s] Eroare. Cod HTTP=%s, Răspuns=%s", label, resp.status, response_text)
                return None

        except asyncio.TimeoutError:
            _LOGGER.error("[%s] Depășire de timp.", label)
            return None
        except Exception as e:
            _LOGGER.exception("[%s] Eroare: %s", label, e)
            return None

    # ──────────────────────────────────────────
    # Metode interne
    # ──────────────────────────────────────────

    async def _request_with_token(self, method: str, url: str, label: str = "request"):
        """
        Cerere cu gestionare automată a tokenului.

        1. Asigură token valid (protejat de _auth_lock)
        2. Execută cererea
        3. La 401: verifică dacă alt apel a reînnoit deja tokenul, altfel refresh/login + reîncearcă
        """
        if not await self._ensure_token_valid():
            _LOGGER.error("[%s] Nu s-a putut obține un token valid.", label)
            return None

        # Memorează generația tokenului înainte de request
        gen_before = self._token_generation

        # Prima încercare
        resp_data, status = await self._do_request(method, url, label)
        if status != 401:
            return resp_data

        # 401 → verifică dacă alt apel concurent a reînnoit deja tokenul
        if self._token_generation != gen_before:
            _LOGGER.debug("[%s] Cod HTTP=401, dar tokenul a fost deja reînnoit (gen %s→%s). Se reîncearcă.", label, gen_before, self._token_generation)
        else:
            # Tokenul nu a fost reînnoit — forțăm refresh/login
            _LOGGER.warning("[%s] Cod HTTP=401 → se reîncearcă cu refresh token.", label)
            self.invalidate_token()
            if not await self._ensure_token_valid():
                _LOGGER.error("[%s] Reautentificare eșuată.", label)
                return None

        # A doua încercare
        resp_data, status = await self._do_request(method, url, label)
        if status == 401:
            _LOGGER.error("[%s] A doua încercare eșuată (401). Se abandonează.", label)
            return None

        return resp_data

    async def _request_with_token_post(self, url: str, payload, label: str = "request_post"):
        """
        Cerere POST cu body JSON și gestionare automată a tokenului.

        Similar cu _request_with_token, dar trimite payload JSON.
        """
        if not await self._ensure_token_valid():
            _LOGGER.error("[%s] Nu s-a putut obține un token valid.", label)
            return None

        gen_before = self._token_generation

        # Prima încercare
        resp_data, status = await self._do_request("POST", url, label, json_payload=payload)
        if status != 401:
            return resp_data

        # 401 → verifică dacă alt apel concurent a reînnoit deja tokenul
        if self._token_generation != gen_before:
            _LOGGER.debug("[%s] Cod HTTP=401, dar tokenul a fost deja reînnoit (gen %s→%s). Se reîncearcă.", label, gen_before, self._token_generation)
        else:
            _LOGGER.warning("[%s] Cod HTTP=401 → se reîncearcă cu refresh token.", label)
            self.invalidate_token()
            if not await self._ensure_token_valid():
                _LOGGER.error("[%s] Reautentificare eșuată.", label)
                return None

        # A doua încercare
        resp_data, status = await self._do_request("POST", url, label, json_payload=payload)
        if status == 401:
            _LOGGER.error("[%s] A doua încercare eșuată (401). Se abandonează.", label)
            return None

        return resp_data

    async def _do_request(self, method: str, url: str, label: str = "request", json_payload=None):
        """Efectuează o cerere HTTP cu tokenul curent. Returnează (data, status)."""
        headers = {**HEADERS}
        if self._access_token:
            headers["Authorization"] = f"{self._token_type} {self._access_token}"

        _LOGGER.debug("[%s] %s %s, Payload=%s", label, method, url, json.dumps(json_payload) if json_payload else "None")

        try:
            kwargs = {"headers": headers, "timeout": self._timeout}
            if json_payload is not None:
                kwargs["json"] = json_payload

            async with self._session.request(method, url, **kwargs) as resp:
                response_text = await resp.text()

                if resp.status == 200:
                    data = await resp.json()
                    # Debug clar pentru datele primite în _do_request
                    _LOGGER.debug(
                        "[%s] Răspuns OK (200). Dimensiune: %s caractere. Date JSON: type=%s, len=%s, sample keys=%s, sample content=%s",
                        label,
                        len(response_text),
                        type(data).__name__,
                        len(data) if isinstance(data, (list, dict)) else "N/A",
                        list(data[0].keys()) if isinstance(data, list) and data else list(data.keys()) if isinstance(data, dict) else "N/A",
                        json.dumps(data, default=str)[:500] if data else "None"
                    )
                    return data, resp.status

                _LOGGER.error("[%s] Eroare: %s %s → Cod HTTP=%s, Răspuns=%s", label, method, url, resp.status, response_text)
                return None, resp.status

        except asyncio.TimeoutError:
            _LOGGER.error("[%s] Depășire de timp: %s %s.", label, method, url)
            return None, 0
        except Exception as e:
            _LOGGER.error("[%s] Eroare: %s %s → %s", label, method, url, e)
            return None, 0

    async def _paginated_request(
        self,
        base_url: str,
        params: dict,
        list_key: str = "list",
        label: str = "paginated",
    ):
        """Obține toate paginile unui endpoint paginat. Returnează lista cumulată."""
        if not await self._ensure_token_valid():
            _LOGGER.error("[%s] Nu s-a putut obține un token valid.", label)
            return None

        results: list = []
        page = 1
        retried = False

        while True:
            query_parts = [f"{k}={v}" for k, v in params.items()]
            query_parts.append(f"page={page}")
            url = f"{base_url}?{'&'.join(query_parts)}"

            gen_before = self._token_generation
            headers = {**HEADERS, "Authorization": f"{self._token_type} {self._access_token}"}

            _LOGGER.debug("[%s] Pagină %s: %s", label, page, url)

            try:
                async with self._session.get(
                    url, headers=headers, timeout=self._timeout
                ) as resp:
                    response_text = await resp.text()

                    if resp.status == 200:
                        data = await resp.json()
                        # Debug clar pentru datele primite per pagină
                        _LOGGER.debug(
                            "[%s] Pagină %s: Date JSON: type=%s, keys=%s, list len=%s, sample list keys=%s, sample content=%s",
                            label, page,
                            type(data).__name__,
                            list(data.keys()) if isinstance(data, dict) else "N/A",
                            len(data.get(list_key, [])),
                            list(data.get(list_key, [])[0].keys()) if data.get(list_key) and isinstance(data.get(list_key), list) and data.get(list_key) else "N/A",
                            json.dumps(data, default=str)[:500] if data else "None"
                        )
                        chunk = data.get(list_key, [])
                        results.extend(chunk)
                        retried = False

                        has_next = data.get("hasNext", False)
                        _LOGGER.debug(
                            "[%s] Pagină %s: %s elemente, are_următoare=%s.",
                            label, page, len(chunk), has_next,
                        )

                        if not has_next:
                            break
                        page += 1
                        continue

                    if resp.status == 401 and not retried:
                        # Verifică dacă alt apel a reînnoit deja tokenul
                        if self._token_generation != gen_before:
                            _LOGGER.debug("[%s] Token reînnoit de alt apel (pagină %s). Se reîncearcă.", label, page)
                        else:
                            _LOGGER.warning("[%s] Token expirat (pagină %s). Se reîncearcă...", label, page)
                            self.invalidate_token()
                            if not await self._ensure_token_valid():
                                return results if results else None
                        retried = True
                        continue

                    _LOGGER.error("[%s] Eroare: Cod HTTP=%s (pagină %s), Răspuns=%s", label, resp.status, page, response_text)
                    break

            except asyncio.TimeoutError:
                _LOGGER.error("[%s] Depășire de timp (pagină %s).", label, page)
                break
            except Exception as e:
                _LOGGER.error("[%s] Eroare: %s", label, e)
                break

        _LOGGER.debug("[%s] Total: %s elemente din %s pagini.", label, len(results), page)
        return results
