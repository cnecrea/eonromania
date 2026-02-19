"""Client API pentru comunicarea cu E·ON România."""

import asyncio
import logging
from aiohttp import ClientSession, ClientTimeout

from .const import API_TIMEOUT, HEADERS_POST, URLS

_LOGGER = logging.getLogger(__name__)


class EonApiClient:
    """Clasă pentru comunicarea cu API-ul E·ON România."""

    def __init__(self, session: ClientSession, username: str, password: str):
        """Inițializează clientul API cu o sesiune de tip ClientSession."""
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None
        self._timeout = ClientTimeout(total=API_TIMEOUT)

    async def async_login(self) -> bool:
        """Obține un token nou de autentificare."""
        payload = {
            "username": self._username,
            "password": self._password,
            "rememberMe": False,
        }

        try:
            async with self._session.post(
                URLS["login"], json=payload, headers=HEADERS_POST, timeout=self._timeout
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._token = data.get("accessToken")
                    _LOGGER.debug("Token obținut cu succes (autentificare reușită).")
                    return True

                text = await resp.text()
                _LOGGER.error(
                    "Eroare la autentificare. Cod HTTP=%s, Răspuns=%s",
                    resp.status,
                    text,
                )
                self._token = None
                return False

        except asyncio.TimeoutError:
            _LOGGER.error(
                "Depășire de timp la conectarea cu API-ul E·ON (autentificare)."
            )
            self._token = None
            return False
        except Exception as e:
            _LOGGER.error("Eroare la conectarea cu API-ul E·ON (autentificare): %s", e)
            self._token = None
            return False

    async def async_fetch_dateuser_data(self, cod_incasare: str):
        """Obține datele utilizatorului (contract)."""
        return await self._request_with_token(
            method="GET",
            url=URLS["dateuser"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea datelor utilizatorului.",
        )

    async def async_fetch_citireindex_data(self, cod_incasare: str):
        """Obține datele despre indexul curent."""
        return await self._request_with_token(
            method="GET",
            url=URLS["citireindex"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea indexului curent.",
        )

    async def async_fetch_conventieconsum_data(self, cod_incasare: str):
        """Obține datele despre convenția de consum."""
        return await self._request_with_token(
            method="GET",
            url=URLS["conventieconsum"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea convenției de consum.",
        )

    async def async_fetch_comparareanualagrafic_data(self, cod_incasare: str):
        """Obține datele despre graficul de comparare anuală."""
        return await self._request_with_token(
            method="GET",
            url=URLS["comparareanualagrafic"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea graficului de comparare anuală.",
        )

    async def async_fetch_arhiva_data(self, cod_incasare: str):
        """Obține date istorice (arhivă)."""
        return await self._request_with_token(
            method="GET",
            url=URLS["arhiva"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea datelor din arhivă.",
        )

    async def async_fetch_facturasold_data(self, cod_incasare: str):
        """Obține datele despre soldul facturilor."""
        return await self._request_with_token(
            method="GET",
            url=URLS["facturasold"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea soldului facturilor.",
        )

    async def async_fetch_payments_data(self, cod_incasare: str):
        """
        Obține toate înregistrările de plăți (paginare) pentru un cont dat.
        Returnează o listă unică, cumulând datele de pe toate paginile.
        """
        if not await self._ensure_token():
            return None

        results: list = []
        page = 1
        retried = False

        while True:
            url = (
                "https://api2.eon.ro/invoices/v1/payments/payment-list"
                f"?accountContract={cod_incasare}&page={page}"
            )
            headers = {**HEADERS_POST, "Authorization": f"Bearer {self._token}"}

            try:
                async with self._session.get(
                    url, headers=headers, timeout=self._timeout
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        chunk = data.get("list", [])
                        results.extend(chunk)
                        retried = False  # reset flag la succes

                        has_next = data.get("hasNext", False)
                        _LOGGER.debug(
                            "Plăți: pagină=%s, are_pagină_următoare=%s, elemente=%s",
                            page,
                            has_next,
                            len(chunk),
                        )

                        if not has_next:
                            break
                        page += 1
                        continue

                    if resp.status == 401 and not retried:
                        _LOGGER.warning(
                            "Token expirat la obținerea plăților (pagină=%s). "
                            "Se reîncearcă autentificarea...",
                            page,
                        )
                        self._token = None
                        if await self.async_login():
                            retried = True
                            continue
                        return results if results else None

                    _LOGGER.error(
                        "Eroare la obținerea plăților (pagină=%s). Cod HTTP=%s, Răspuns=%s",
                        page,
                        resp.status,
                        await resp.text(),
                    )
                    break

            except asyncio.TimeoutError:
                _LOGGER.error(
                    "Depășire de timp la obținerea plăților (pagină=%s).", page
                )
                break
            except Exception as e:
                _LOGGER.error("Eroare la obținerea plăților: %s", e)
                break

        return results

    async def async_trimite_index(
        self, account_contract: str, ablbelnr: str, index_value: int
    ):
        """Trimite indexul către API-ul E·ON."""
        if not account_contract or not ablbelnr or not isinstance(index_value, int):
            _LOGGER.error("Parametri invalizi pentru trimiterea indexului.")
            return None

        if not await self._ensure_token():
            _LOGGER.error(
                "Token invalid sau expirat. Trimiterea indexului nu poate fi efectuată."
            )
            return None

        payload = {
            "accountContract": account_contract,
            "channel": "WEBSITE",
            "indexes": [{"ablbelnr": ablbelnr, "indexValue": index_value}],
        }

        try:
            headers = {**HEADERS_POST, "Authorization": f"Bearer {self._token}"}
            async with self._session.post(
                URLS["trimite_index"],
                json=payload,
                headers=headers,
                timeout=self._timeout,
            ) as resp:
                if resp.status == 200:
                    _LOGGER.debug(
                        "Index trimis cu succes pentru contractul %s.", account_contract
                    )
                    return await resp.json()

                if resp.status == 401:
                    _LOGGER.warning(
                        "Token invalid la trimiterea indexului. "
                        "Se reîncearcă autentificarea și retrimiterea..."
                    )
                    self._token = None
                    if await self.async_login():
                        return await self.async_trimite_index(
                            account_contract, ablbelnr, index_value
                        )
                    _LOGGER.error(
                        "Reautentificare eșuată. Indexul nu a putut fi trimis."
                    )
                    return None

                response_text = await resp.text()
                _LOGGER.error(
                    "Eroare la trimiterea indexului. Cod HTTP=%s, Răspuns=%s",
                    resp.status,
                    response_text,
                )
                return None

        except asyncio.TimeoutError:
            _LOGGER.error(
                "Depășire de timp la trimiterea indexului pentru contractul %s.",
                account_contract,
            )
            return None
        except Exception as e:
            _LOGGER.exception(
                "Eroare la conectarea cu API-ul E·ON la trimiterea indexului: %s", e
            )
            return None

    async def _ensure_token(self) -> bool:
        """Asigură că există un token valid, inițiind autentificarea dacă e necesar."""
        if self._token is None:
            return await self.async_login()
        return True

    async def _request_with_token(self, method: str, url: str, on_error: str):
        """
        Metodă auxiliară care face o cerere folosind token-ul.
        Dacă token-ul nu există, se autentifică. Dacă primim 401, reîncearcă o dată.
        """
        if not await self._ensure_token():
            return None

        # Prima încercare
        resp_data, status = await self._do_request(method, url)
        if status != 401:
            return resp_data

        # Dacă e 401, încercăm reautentificare și apoi reîncercarea cererii
        _LOGGER.warning(
            "%s Cod HTTP=401 -> se reîncearcă autentificarea și apoi cererea.", on_error
        )
        self._token = None
        if not await self.async_login():
            return None

        # Token obținut, refacem cererea
        resp_data, status = await self._do_request(method, url)
        if status == 401:
            _LOGGER.error(
                "%s Reîncercarea cererii a eșuat (Cod HTTP=401). Se abandonează.",
                on_error,
            )
            return None

        return resp_data

    async def _do_request(self, method: str, url: str):
        """
        Efectuează o cerere (GET/POST etc.) cu token-ul curent (dacă există).
        Returnează tuple (resp_data, status).
        """
        headers = {**HEADERS_POST}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with self._session.request(
                method, url, headers=headers, timeout=self._timeout
            ) as resp:
                if resp.status == 200:
                    return (await resp.json()), resp.status

                text = await resp.text()
                _LOGGER.error(
                    "%s %s a eșuat. Cod HTTP=%s, Răspuns=%s",
                    method,
                    url,
                    resp.status,
                    text,
                )
                return None, resp.status

        except asyncio.TimeoutError:
            _LOGGER.error("Depășire de timp la cererea %s %s.", method, url)
            return None, 0
        except Exception as e:
            _LOGGER.error("Eroare la cererea %s %s: %s", method, url, e)
            return None, 0
