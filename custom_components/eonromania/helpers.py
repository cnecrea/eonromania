"""Funcții și constante utilitare pentru integrarea E·ON România."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from homeassistant.helpers.selector import SelectOptionDict


# ══════════════════════════════════════════════
# Mapping-uri luni și tipuri citire
# ══════════════════════════════════════════════

MONTHS_EN_RO: dict[str, str] = {
    "January": "ianuarie",
    "February": "februarie",
    "March": "martie",
    "April": "aprilie",
    "May": "mai",
    "June": "iunie",
    "July": "iulie",
    "August": "august",
    "September": "septembrie",
    "October": "octombrie",
    "November": "noiembrie",
    "December": "decembrie",
}

MONTHS_NUM_RO: dict[int, str] = {
    1: "ianuarie",
    2: "februarie",
    3: "martie",
    4: "aprilie",
    5: "mai",
    6: "iunie",
    7: "iulie",
    8: "august",
    9: "septembrie",
    10: "octombrie",
    11: "noiembrie",
    12: "decembrie",
}

READING_TYPE_MAP: dict[str, str] = {
    "01": "citit distribuitor",
    "02": "autocitit",
    "03": "estimat",
}

# ══════════════════════════════════════════════
# Mapping-uri orașe
# ══════════════════════════════════════════════
COUNTY_CODE_MAP: dict[str, str] = {
    "AB": "Alba",
    "AR": "Arad",
    "AG": "Argeș",
    "BC": "Bacău",
    "BH": "Bihor",
    "BN": "Bistrița-Năsăud",
    "BT": "Botoșani",
    "BR": "Brăila",
    "BV": "Brașov",
    "B": "București",
    "BZ": "Buzău",
    "CS": "Caraș-Severin",
    "CL": "Călărași",
    "CJ": "Cluj",
    "CT": "Constanța",
    "CV": "Covasna",
    "DB": "Dâmbovița",
    "DJ": "Dolj",
    "GL": "Galați",
    "GR": "Giurgiu",
    "GJ": "Gorj",
    "HR": "Harghita",
    "HD": "Hunedoara",
    "IL": "Ialomița",
    "IS": "Iași",
    "IF": "Ilfov",
    "MM": "Maramureș",
    "MH": "Mehedinți",
    "MS": "Mureș",
    "NT": "Neamț",
    "OT": "Olt",
    "PH": "Prahova",
    "SM": "Satu Mare",
    "SJ": "Sălaj",
    "SB": "Sibiu",
    "SV": "Suceava",
    "TR": "Teleorman",
    "TM": "Timiș",
    "TL": "Tulcea",
    "VS": "Vaslui",
    "VL": "Vâlcea",
    "VN": "Vrancea",
}

# ══════════════════════════════════════════════
# Mapping-uri traducere atribute API → română
# ══════════════════════════════════════════════

INVOICE_BALANCE_KEY_MAP: dict[str, str] = {
    "balance": "Sold",
    "total": "Total",
    "totalBalance": "Sold total",
    "invoiceValue": "Valoare factură",
    "issuedValue": "Valoare emisă",
    "balanceValue": "Sold rămas",
    "paidValue": "Sumă achitată",
    "maturityDate": "Data scadenței",
    "invoiceNumber": "Număr factură",
    "emissionDate": "Data emiterii",
    "paymentDate": "Data plății",
    "currency": "Monedă",
    "status": "Stare",
    "type": "Tip",
    "accountContract": "Cod încasare",
    "refund": "Rambursare disponibilă",
    "date": "Data sold",
    "refundInProcess": "Rambursare în curs",
    "hasGuarantee": "Garanție activă",
    "hasUnpaidGuarantee": "Garanție neachitată",
    "balancePay": "Sold de plată",
    "refundDocumentsRequired": "Documente rambursare necesare",
    "isAssociation": "Asociație",
}

INVOICE_BALANCE_MONEY_KEYS: set[str] = {
    "balance",
    "total",
    "totalBalance",
    "invoiceValue",
    "issuedValue",
    "balanceValue",
    "paidValue",
}


# ══════════════════════════════════════════════
# Funcții de formatare
# ══════════════════════════════════════════════

def format_ron(value: float) -> str:
    """Formatează o valoare numerică în format românesc (1.234,56)."""
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def format_number_ro(value: float | int | str) -> str:
    """Formatează un număr cu separatorul zecimal românesc (virgulă).

    Exemple:
        4.029   → '4,029'
        124.91  → '124,91'
        11.9    → '11,9'
        0.424   → '0,424'
        100     → '100'
        100.0   → '100'
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        return str(value)
    if num == int(num):
        return str(int(num))
    text = str(num)
    return text.replace(".", ",")


# ══════════════════════════════════════════════
# Funcții de autentificare
# ══════════════════════════════════════════════

def generate_verify_hmac(username: str, secret: str) -> str:
    """Generează semnătura HMAC-MD5 pentru câmpul verify din mobile-login."""
    return hmac.new(
        secret.encode("utf-8"),
        username.encode("utf-8"),
        hashlib.md5,
    ).hexdigest()


# ══════════════════════════════════════════════
# Funcții pentru config flow (selecție contracte)
# ══════════════════════════════════════════════

def build_address_consum(address_obj: dict) -> str:
    """Construiește adresa completă formatată corect pentru România."""
    if not isinstance(address_obj, dict):
        return ""

    def safe_str(value: Any) -> str:
        return str(value).strip() if value else ""

    def clean_parentheses(text: str) -> str:
        """Elimină orice conținut de tip '(XX)' din text."""
        if "(" in text:
            text = text.split("(")[0]
        return " ".join(text.split())

    parts: list[str] = []

    # ─────────────────────────────
    # Stradă
    # ─────────────────────────────
    street_obj = address_obj.get("street")
    if isinstance(street_obj, dict):

        street_type = safe_str(
            (street_obj.get("streetType") or {}).get("label")
        )
        street_name = safe_str(street_obj.get("streetName"))

        full_street = " ".join(
            filter(None, [street_type, street_name])
        ).strip()

        if full_street:
            # Title doar pe stradă, nu pe tot textul
            full_street = " ".join(word.capitalize() for word in full_street.split())

            nr = safe_str(address_obj.get("streetNumber"))
            if nr:
                parts.append(f"{full_street} {nr}")
            else:
                parts.append(full_street)

    # Apartament
    apartment = safe_str(address_obj.get("apartment"))
    if apartment and apartment != "0":
        parts.append(f"ap. {apartment}")

    # ─────────────────────────────
    # Localitate + județ
    # ─────────────────────────────
    locality_obj = address_obj.get("locality")
    if isinstance(locality_obj, dict):

        raw_city = clean_parentheses(
            safe_str(locality_obj.get("localityName"))
        )

        city = raw_city.strip()

        county_code = safe_str(locality_obj.get("countyCode")).upper()
        county_name = COUNTY_CODE_MAP.get(county_code)

        if city:
            if county_name:
                parts.append(f"{city}, jud. {county_name}")
            else:
                parts.append(city)

    return ", ".join(parts)

def build_contract_options(contracts: list[dict]) -> list[SelectOptionDict]:
    """Construiește lista de opțiuni pentru selectorul de contracte."""
    options: list[SelectOptionDict] = []
    seen: set[str] = set()

    def safe_str(value: Any) -> str:
        return str(value).strip() if value else ""

    for c in contracts or []:
        if not isinstance(c, dict):
            continue

        ac = safe_str(c.get("accountContract"))
        if not ac or ac in seen:
            continue

        seen.add(ac)

        # Adresa — delegată către helper
        addr = c.get("consumptionPointAddress")
        address = build_address_consum(addr) if addr else "Fără adresă"

        # Tip utilitate
        utility = safe_str(c.get("utilityType"))
        utility_label = {
            "01": "Electricitate",
            "02": "Gaz",
        }.get(utility, "")

        # Label final (fără titular)
        label = f"{address} ➜ {ac}"

        if utility_label:
            label += f" ({utility_label})"

        options.append(
            SelectOptionDict(
                value=ac,
                label=label,
            )
        )

    options.sort(key=lambda x: x["label"].lower())

    return options


def extract_all_contracts(contracts: list[dict]) -> list[str]:
    """Extrage toate codurile de contract unice."""
    result: list[str] = []
    for c in contracts:
        if isinstance(c, dict):
            ac = c.get("accountContract", "")
            if ac and ac not in result:
                result.append(ac)
    return result


def resolve_selection(
    select_all: bool,
    selected: list[str],
    contracts: list[dict],
) -> list[str]:
    """Returnează lista finală de contracte."""
    if select_all:
        return extract_all_contracts(contracts)
    return selected

