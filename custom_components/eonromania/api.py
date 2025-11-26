import logging
from aiohttp import ClientSession
from .const import HEADERS_POST, URLS

_LOGGER = logging.getLogger(__name__)

class EonApiClient:
    """Clasă pentru comunicarea cu API-ul EON România."""

    def __init__(self, session: ClientSession, username: str, password: str):
        """Inițializează clientul API cu o sesiune de tip ClientSession."""
        self._session = session
        self._username = username
        self._password = password
        self._token = None

    async def async_login(self) -> bool:
        """Obține un token nou de autentificare."""
        payload = {
            "username": self._username,
            "password": self._password,
            "rememberMe": False
        }

        try:
            async with self._session.post(URLS["login"], json=payload, headers=HEADERS_POST) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._token = data.get("accessToken")
                    _LOGGER.debug("Token obținut: %s", self._token)
                    return True
                else:
                    text = await resp.text()
                    _LOGGER.error(
                        "Eroare la login. Status=%s, Răspuns=%s",
                        resp.status,
                        text
                    )
                    self._token = None
                    return False
        except Exception as e:
            _LOGGER.error("Eroare la conectarea cu API-ul: %s", e)
            self._token = None
            return False

    async def async_fetch_dateuser_data(self, cod_incasare: str):
        """Obține datele utilizatorului (contract)."""
        return await self._request_with_token(
            method="GET",
            url=URLS["dateuser"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea datelor utilizator."
        )

    async def async_fetch_citireindex_data(self, cod_incasare: str):
        """Obține datele despre indexul curent."""
        return await self._request_with_token(
            method="GET",
            url=URLS["citireindex"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea indexului curent."
        )

    async def async_fetch_conventieconsum_data(self, cod_incasare: str):
        """Obține datele despre convenție consum."""
        return await self._request_with_token(
            method="GET",
            url=URLS["conventieconsum"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea convenție consum."
        )

    async def async_fetch_comparareanualagrafic_data(self, cod_incasare: str):
        """Obține datele despre comparare anuala grafic."""
        return await self._request_with_token(
            method="GET",
            url=URLS["comparareanualagrafic"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea comparare anuala grafic."
        )


    async def async_fetch_arhiva_data(self, cod_incasare: str):
        """Obține date istorice (arhiva)."""
        return await self._request_with_token(
            method="GET",
            url=URLS["arhiva"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea datelor din arhivă."
        )

    async def async_fetch_facturasold_data(self, cod_incasare: str):
        """Obține datele despre soldul facturilor."""
        return await self._request_with_token(
            method="GET",
            url=URLS["facturasold"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea soldului facturilor."
        )

    async def async_fetch_facturasold_prosum_balance_data(self, cod_incasare: str):
        """Obține datele despre soldul facturilor de prosumator."""
        return await self._request_with_token(
            method="GET",
            url=URLS["facturasold_prosum_balance"].format(cod_incasare=cod_incasare),
            on_error="Eroare la obținerea soldului facturilor de prosumator."
        )

    async def async_fetch_facturasold_prosum_data(self, cod_incasare: str):
        """
        Obține toate facturile de prosumator (paginate) pentru un cont dat.
        Returnează o listă unică, cumulând datele de pe toate paginile.
        """
        if not await self._ensure_token():
            return None

        results = []
        page = 1
        while True:
            url = (
                f"https://api2.eon.ro/invoices/v1/invoices/list-prosum"
                f"?accountContract={cod_incasare}&page={page}"
            )
            headers = {**HEADERS_POST, "Authorization": f"Bearer {self._token}"}

            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Adunăm toate înregistrările din "list"
                    chunk = data.get("list", [])
                    results.extend(chunk)

                    has_next = data.get("hasNext", False)
                    _LOGGER.debug(
                        "Page=%s, hasNext=%s, items_in_chunk=%s",
                        page, has_next, len(chunk)
                    )

                    if not has_next:
                        # Nu mai există pagini
                        break
                    page += 1
                elif resp.status == 401:
                    # Token invalid sau expirat -> încercăm re-login + retry
                    _LOGGER.error(
                        "Eroare la obținerea datelor despre facturile de prosumator (page=%s). "
                        "Status=%s, Răspuns=%s. Se reîncearcă re-login.",
                        page, resp.status, await resp.text()
                    )
                    # Ne dezautentificăm forțat
                    self._token = None
                    # Încercăm un re-login
                    if await self.async_login():
                        # Dacă reușește login, refacem cererea o singură dată
                        continue
                    else:
                        # Dacă tot eșuează, ne oprim
                        return results if results else None
                else:
                    _LOGGER.error(
                        "Eroare la obținerea datelor despre facturile de prosumator (page=%s). "
                        "Status=%s, Răspuns=%s",
                        page,
                        resp.status,
                        await resp.text()
                    )
                    break

        return results

    async def async_fetch_payments_data(self, cod_incasare: str):
        """
        Obține toate înregistrările de plăți (paginate) pentru un cont dat.
        Returnează o listă unică, cumulând datele de pe toate paginile.
        """
        if not await self._ensure_token():
            return None

        results = []
        page = 1
        while True:
            url = (
                f"https://api2.eon.ro/invoices/v1/payments/payment-list"
                f"?accountContract={cod_incasare}&page={page}"
            )
            headers = {**HEADERS_POST, "Authorization": f"Bearer {self._token}"}

            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Adunăm toate înregistrările din "list"
                    chunk = data.get("list", [])
                    results.extend(chunk)

                    has_next = data.get("hasNext", False)
                    _LOGGER.debug(
                        "Page=%s, hasNext=%s, items_in_chunk=%s",
                        page, has_next, len(chunk)
                    )

                    if not has_next:
                        # Nu mai există pagini
                        break
                    page += 1
                elif resp.status == 401:
                    # Token invalid sau expirat -> încercăm re-login + retry
                    _LOGGER.error(
                        "Eroare la obținerea datelor despre plăți (page=%s). "
                        "Status=%s, Răspuns=%s. Se reîncearcă re-login.",
                        page, resp.status, await resp.text()
                    )
                    # Ne dezautentificăm forțat
                    self._token = None
                    # Încercăm un re-login
                    if await self.async_login():
                        # Dacă reușește login, refacem cererea o singură dată
                        continue
                    else:
                        # Dacă tot eșuează, ne oprim
                        return results if results else None
                else:
                    _LOGGER.error(
                        "Eroare la obținerea datelor despre plăți (page=%s). "
                        "Status=%s, Răspuns=%s",
                        page,
                        resp.status,
                        await resp.text()
                    )
                    break

        return results


    async def async_trimite_index(self, account_contract: str, ablbelnr: str, index_value: int):
        """Trimite indexul către API-ul E-ON."""
        if not account_contract or not ablbelnr or not isinstance(index_value, int):
            _LOGGER.error("Parametrii invalizi pentru trimiterea indexului.")
            return None

        if not await self._ensure_token():
            _LOGGER.error("Token invalid sau expirat. Nu se poate trimite indexul.")
            return None

        payload = {
            "accountContract": account_contract,
            "channel": "WEBSITE",
            "indexes": [{"ablbelnr": ablbelnr, "indexValue": index_value}],
        }

        try:
            headers = {**HEADERS_POST, "Authorization": f"Bearer {self._token}"}
            async with self._session.post(URLS["trimite_index"], json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    _LOGGER.debug("Indexul a fost trimis cu succes pentru %s", account_contract)
                    return await resp.json()
                elif resp.status == 401:
                    _LOGGER.warning("Token invalid. Se încearcă login-ul și retrimiterea indexului.")
                    self._token = None
                    if await self.async_login():
                        return await self.async_trimite_index(account_contract, ablbelnr, index_value)
                    else:
                        _LOGGER.error("Re-login eșuat. Nu se poate trimite indexul.")
                        return None
                else:
                    response_text = await resp.text()
                    _LOGGER.error(
                        "Eroare la trimiterea indexului. Status=%s, Răspuns=%s",
                        resp.status,
                        response_text,
                    )
                    return None
        except Exception as e:
            _LOGGER.exception("Eroare la conectarea cu API-ul: %s", e)
            return None



    async def _ensure_token(self) -> bool:
        """Asigură că avem un token valid, inițiind login dacă e necesar."""
        if self._token is None:
            return await self.async_login()
        return True

    async def _request_with_token(self, method: str, url: str, on_error: str):
        """
        Metodă auxiliară care face un request folosind token-ul.
        Dacă token-ul nu există, face login. Dacă primim 401, reîncearcă o dată.
        """
        if not await self._ensure_token():
            return None

        # Prima încercare
        resp_data, status = await self._do_request(method, url)
        if status != 401:
            # Dacă NU e 401, returnăm direct
            return resp_data

        # Dacă e 401, înseamnă invalid_token; încercăm re-login și re-request
        _LOGGER.error("%s Status=401 -> reîncercăm login și re-request...", on_error)
        self._token = None
        if not await self.async_login():
            # Login eșuat => renunțăm
            return None

        # Token obținut, refacem cererea
        resp_data, status = await self._do_request(method, url)
        if status == 401:
            # Tot 401 => renunțăm
            _LOGGER.error("%s Re-request eșuat. Status=401. Abandonăm.", on_error)
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

        async with self._session.request(method, url, headers=headers) as resp:
            if resp.status == 200:
                return (await resp.json()), resp.status
            else:
                # Poate fi 401 sau alt cod
                text = await resp.text()
                _LOGGER.error("%s: %s, Răspuns=%s", method, url, text)
                return None, resp.status
