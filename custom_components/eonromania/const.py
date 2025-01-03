# Constante pentru integrarea EON România

DOMAIN = "eonromania"

DEFAULT_USER = "username"
DEFAULT_PASS = "password"
COD_INCASARE = "COD_INCASARE"

DEFAULT_UPDATE = 3600  # Interval de actualizare în secunde (1 oră)

HEADERS_POST = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Ocp-Apim-Subscription-Key": "674e9032df9d456fa371e17a4097a5b8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}

PAYLOAD_LOGIN = {
    "username": DEFAULT_USER,
    "password": DEFAULT_PASS,
}

# URL-uri
URL_LOGIN = "https://api2.eon.ro/users/v1/userauth/login"
URL_DATEUSER = "https://api2.eon.ro/partners/v2/account-contracts/{cod_incasare}"
URL_CITIREINDEX = "https://api2.eon.ro/meterreadings/v1/meter-reading/{cod_incasare}/index"
URL_ARHIVA = "https://api2.eon.ro/meterreadings/v1/meter-reading/{cod_incasare}/history"
URL_FACTURASOLD = "https://api2.eon.ro/invoices/v1/invoices/invoice-balance?accountContract={cod_incasare}"
URL_FACTURASOLD_PROSUM = "https://api2.eon.ro/invoices/v1/invoices/invoice-balance-prosum?accountContract={cod_incasare}"

ATTRIBUTION = "Date furnizate de E-ON România"
