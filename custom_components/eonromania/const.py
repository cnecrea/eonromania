"""Constante pentru integrarea E·ON România."""

DOMAIN = "eonromania"

# Config default
DEFAULT_USER = "username"
DEFAULT_PASS = "password"
DEFAULT_UPDATE_INTERVAL = 3600  # Interval de actualizare în secunde (1 oră)

# Headere pentru requesturi HTTP
HEADERS_POST = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Ocp-Apim-Subscription-Key": "674e9032df9d456fa371e17a4097a5b8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36",
}

# URL-uri pentru API-ul E-ON
URLS = {
    "login": "https://api2.eon.ro/users/v1/userauth/login",
    "dateuser": "https://api2.eon.ro/partners/v2/account-contracts/{cod_incasare}",
    "citireindex": "https://api2.eon.ro/meterreadings/v1/meter-reading/{cod_incasare}/index",
    "conventieconsum": "https://api2.eon.ro/meterreadings/v1/consumption-convention/{cod_incasare}",
    "comparareanualagrafic": "https://api2.eon.ro/invoices/v1/invoices/graphic-consumption/{cod_incasare}",
    "arhiva": "https://api2.eon.ro/meterreadings/v1/meter-reading/{cod_incasare}/history",
    "facturasold": "https://api2.eon.ro/invoices/v1/invoices/list?accountContract={cod_incasare}&status=unpaid",
    "trimite_index": "https://api2.eon.ro/meterreadings/v1/meter-reading/index",
    "facturasold_prosum_balance": "https://api2.eon.ro/invoices/v1/invoices/invoice-balance-prosum?accountContract={cod_incasare}",
}

# Platforme suportate
PLATFORMS: list[str] = ["sensor", "button"]

# Atribuție
ATTRIBUTION = "Date furnizate de E·ON România"

# Timeout implicit pentru requesturi API (secunde)
API_TIMEOUT = 30
