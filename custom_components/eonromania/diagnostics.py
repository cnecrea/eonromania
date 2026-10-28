"""
Diagnosticare pentru integrarea E·ON România.

Exportă informații de diagnostic pentru support tickets:
- Licență (fingerprint trunchiat, status, cheie mascată)
- Contracte: stare, capabilități, actualizări, subcontracte DUO
- Structura datelor primite de la E·ON (câmpuri, număr de elemente, perioade) — FĂRĂ valori
- Entitățile intrării: active, dezactivate, indisponibile sau orfane

Diagnosticul se atașează la issue-uri publice, deci nu conține sume, indexuri, adrese, nume,
email-uri sau numere de contor. Codurile de încasare apar doar cu ultimele 4 cifre.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .const import DOMAIN, LICENSE_DATA_KEY
from .coordinator import HEAVY_REFRESH_EVERY
from .helpers import UTILITY_BUTTON_CONFIG

# Liste de facturi / plăți: câmpul cu data după care se calculează perioada
_LIST_DATE_FIELDS = {
    "invoices_unpaid": "emissionDate",
    "invoices_archive": "emissionDate",
    "invoices_prosum": "emissionDate",
    "payments": "paymentDate",
}
# Răspunsuri din care se arată doar numele câmpurilor (valorile sunt sume sau date personale)
_KEYS_ONLY = ("contract_details", "details", "invoice_balance", "invoice_balance_prosum",
              "consumption_convention", "conventions")


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Returnează datele de diagnostic pentru E·ON România."""

    # ── Licență (fingerprint TRUNCHIAT + cheie mascată) ──
    # Fingerprint-ul complet NU apare în diagnostic: diagnosticele se atașează la
    # issue-uri publice, iar serverul de licențe acceptă cereri semnate cu fingerprint.
    license_mgr = hass.data.get(DOMAIN, {}).get(LICENSE_DATA_KEY)
    licenta_info: dict[str, Any] = {}
    if license_mgr:
        licenta_info = {
            "fingerprint": license_mgr.fingerprint[:16] + "...",
            "status": license_mgr.status,
            "license_key": license_mgr.license_key_masked,
            "is_valid": license_mgr.is_valid,
            "license_type": license_mgr.license_type,
        }

    # ── Contracte și coordinatoare ──
    runtime = getattr(entry, "runtime_data", None)
    coordinators = dict(getattr(runtime, "coordinators", None) or {})

    # Toate codurile cunoscute (contracte + subcontracte) — se mască peste tot, și în entity ID-uri
    coduri: set[str] = {str(c) for c in entry.data.get("selected_contracts", []) or []}
    for cod, coordinator in coordinators.items():
        coduri.add(str(cod))
        data = coordinator.data if isinstance(coordinator.data, dict) else {}
        for sc in data.get("subcontracts") or []:
            if isinstance(sc, dict) and sc.get("accountContract"):
                coduri.add(str(sc["accountContract"]))
    masca = _Masca(coduri)

    contracte: dict[str, Any] = {}
    for cod, coordinator in coordinators.items():
        try:
            contracte[masca.cod(cod)] = _contract(coordinator, masca)
        except Exception as err:  # noqa: BLE001 — un contract cu date neașteptate nu strică tot diagnosticul
            contracte[masca.cod(cod)] = {"eroare_diagnostic": type(err).__name__}

    try:
        versiune_integrare = str((await async_get_integration(hass, DOMAIN)).version)
    except Exception:  # noqa: BLE001
        versiune_integrare = None

    # ── Config entry (fără date sensibile) ──
    return {
        "intrare": {
            "titlu": masca.text(entry.title.replace(
                entry.data.get("username", "") or "\0",
                _mascheaza_email(entry.data.get("username", "")),
            )),
            "versiune": entry.version,
            "versiune_integrare": versiune_integrare,
            "versiune_home_assistant": HA_VERSION,
            "domeniu": DOMAIN,
            "username": _mascheaza_email(entry.data.get("username", "")),
            "update_interval": entry.data.get("update_interval"),
            "selected_contracts": [masca.cod(c) for c in entry.data.get("selected_contracts", []) or []],
        },
        "licenta": licenta_info,
        "contracte": contracte,
        "entitati": _entitati(hass, entry, masca),
    }


# ══════════════════════════════════════════════
# Contracte
# ══════════════════════════════════════════════

def _contract(coordinator, masca: _Masca) -> dict[str, Any]:
    """Starea unui coordinator și structura datelor lui."""
    counter = getattr(coordinator, "_refresh_counter", None)
    interval = getattr(coordinator, "update_interval", None)
    exc = getattr(coordinator, "last_exception", None)
    data = coordinator.data if isinstance(coordinator.data, dict) else None

    info: dict[str, Any] = {
        "is_collective": getattr(coordinator, "is_collective", False),
        "account_only": getattr(coordinator, "account_only", False),
        "last_update_success": coordinator.last_update_success,
        "ultima_eroare": type(exc).__name__ if exc else None,
        "interval_secunde": int(interval.total_seconds()) if interval else None,
        # câte actualizări au rulat de la pornire; cele complete (istoric, arhive) sunt la fiecare a N-a
        "actualizari_efectuate": counter,
        "urmatoarea_completa": (counter % HEAVY_REFRESH_EVERY == 0) if isinstance(counter, int) else None,
        "capabilitati": getattr(coordinator, "_capabilities", None),
    }
    if data is None:
        info["date"] = None
        return info

    info["unitate_masura"] = data.get("um")
    info["date"] = {key: _rezumat(key, value, masca) for key, value in data.items() if key not in ("um", "is_collective")}
    if data.get("subcontracts"):
        info["subcontracte"] = _subcontracte(data, masca)
    return info


def _subcontracte(data: dict, masca: _Masca) -> list[dict[str, Any]]:
    """Subcontractele DUO: tipul utilității și unitatea fiecăruia."""
    sgc = data.get("subcontracts_graphic_consumption")
    out = []
    for sc in data.get("subcontracts") or []:
        if not isinstance(sc, dict) or not sc.get("accountContract"):
            continue
        cod = sc["accountContract"]
        gc = sgc.get(cod) if isinstance(sgc, dict) else None
        out.append({
            "cod": masca.cod(cod),
            "utilityType": sc.get("utilityType"),
            "unitate_masura": gc.get("um") if isinstance(gc, dict) else None,
        })
    return out


# ══════════════════════════════════════════════
# Rezumatul datelor (structură, fără valori)
# ══════════════════════════════════════════════

def _rezumat(key: str, value: Any, masca: _Masca) -> Any:
    """Rezumatul unei chei din coordinator.data: tip, număr de elemente, nume de câmpuri, perioade."""
    if value is None:
        return None
    if key.startswith("subcontracts_") and isinstance(value, dict):
        # {cod_subcontract: răspuns} — același rezumat ca la contract, cu codul mascat
        return {masca.cod(sc): _rezumat(key.removeprefix("subcontracts_"), v, masca) for sc, v in value.items()}
    if key == "graphic_consumption":
        return _rezumat_consum(value)
    if key == "meter_index":
        return _rezumat_index(value)
    if key == "meter_history":
        return _rezumat_istoric(value)
    if key in _KEYS_ONLY or not isinstance(value, list):
        return _forma(value)

    rez: dict[str, Any] = {"elemente": len(value), "campuri": _campuri(value)}
    date_field = _LIST_DATE_FIELDS.get(key)
    if date_field:
        luni = sorted({m for item in value if isinstance(item, dict) and (m := _luna(item.get(date_field)))})
        rez["perioada"] = f"{luni[0]} … {luni[-1]}" if luni else None
        if date_field == "emissionDate":
            rez["cu_scadenta"] = sum(1 for item in value if isinstance(item, dict) and item.get("maturityDate"))
    return rez


def _rezumat_consum(value: Any) -> Any:
    """graphic-consumption: lunile primite (an-lună), dacă sunt consecutive, rândurile fără lună."""
    if not isinstance(value, dict):
        return _forma(value)
    items = [i for i in value.get("consumption") or [] if isinstance(i, dict)]
    luni = sorted({(y, m) for i in items if (y := _int(i.get("year"))) and (m := _int(i.get("month"))) and 1 <= m <= 12})
    goluri = sum(1 for a, b in zip(luni, luni[1:]) if (b[0] * 12 + b[1]) - (a[0] * 12 + a[1]) != 1)
    return {
        "um": value.get("um"),
        "randuri": len(items),
        "campuri_rand": _campuri(items),
        "luni": len(luni),
        "perioada": f"{luni[0][0]}-{luni[0][1]:02d} … {luni[-1][0]}-{luni[-1][1]:02d}" if luni else None,
        "goluri_in_perioada": goluri,
        "randuri_fara_luna": sum(1 for i in items if not _int(i.get("month"))),
    }


def _rezumat_index(value: Any) -> Any:
    """meter-reading/index: dispozitivele și câte registre are fiecare (la prosumatori pot fi două)."""
    if not isinstance(value, dict):
        return _forma(value)
    details = value.get("indexDetails") if isinstance(value.get("indexDetails"), dict) else {}
    devices = [d for d in details.get("devices") or [] if isinstance(d, dict)]
    return {
        "campuri": sorted(value.keys()),
        "campuri_indexDetails": sorted(details.keys()),
        "dispozitive": [
            {
                "campuri": sorted(d.keys()),
                "registre": len(d.get("indexes") or []),
                "campuri_registre": _campuri(d.get("indexes") or []),
            }
            for d in devices
        ],
    }


def _rezumat_istoric(value: Any) -> Any:
    """meter-reading/history: pe fiecare an, câte contoare, câte registre are fiecare și câte citiri."""
    if not isinstance(value, dict):
        return _forma(value)
    history = [h for h in value.get("history") or [] if isinstance(h, dict)]
    ani: dict[str, Any] = {}
    for h in history:
        meters = [m for m in h.get("meters") or [] if isinstance(m, dict)]
        indexes = [i for m in meters for i in m.get("indexes") or [] if isinstance(i, dict)]
        ani[str(h.get("year"))] = {
            "contoare": len(meters),
            "registre_pe_contor": [len(m.get("indexes") or []) for m in meters],
            "citiri": sum(len(i.get("readings") or []) for i in indexes),
        }
    return {"campuri": sorted(value.keys()), "ani": ani}


def _forma(value: Any) -> Any:
    """Doar forma: numele câmpurilor la dict, numărul de elemente la listă, tipul în rest."""
    if isinstance(value, dict):
        return {"campuri": sorted(value.keys())}
    if isinstance(value, list):
        return {"elemente": len(value), "campuri": _campuri(value)}
    return type(value).__name__


def _campuri(items: Any) -> list[str]:
    """Reuniunea numelor de câmpuri dintr-o listă de dict-uri."""
    if not isinstance(items, list):
        return []
    return sorted({k for i in items if isinstance(i, dict) for k in i.keys()})


def _luna(raw: Any) -> str | None:
    """„dd.mm.yyyy" sau ISO („yyyy-mm-dd…") → „yyyy-mm"."""
    s = str(raw or "")
    if len(s) >= 10 and s[2] == "." and s[5] == ".":
        return f"{s[6:10]}-{s[3:5]}"
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ══════════════════════════════════════════════
# Entități
# ══════════════════════════════════════════════

def _entitati(hass: HomeAssistant, entry: ConfigEntry, masca: _Masca) -> dict[str, Any]:
    """Entitățile acestei intrări din registru, cu starea lor.

    „orfană" = există în registru, dar integrarea nu o mai creează (ex. senzorul pe anul trecut);
    HA îi păstrează doar o stare restaurată.
    """
    registry = er.async_get(hass)
    entitati: dict[str, dict[str, str]] = {}
    numar: dict[str, int] = {}
    for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
        state = hass.states.get(reg.entity_id)
        if reg.disabled_by:
            stare = "dezactivată"
        elif state is None or state.attributes.get("restored"):
            stare = "orfană"
        elif state.state == "unavailable":
            stare = "indisponibilă"
        else:
            stare = "activă"
        entitati.setdefault(reg.domain, {})[masca.text(reg.entity_id)] = stare
        numar[stare] = numar.get(stare, 0) + 1

    # butoanele „Trimite index" citesc valoarea dintr-un input_number creat de utilizator
    input_numbers = {
        cfg["input_number"]: hass.states.get(cfg["input_number"]) is not None
        for cfg in UTILITY_BUTTON_CONFIG.values()
    } if entitati.get("button") else {}

    return {
        "numar": numar,
        "input_number_pentru_butoane": input_numbers,
        **{domeniu: dict(sorted(lista.items())) for domeniu, lista in sorted(entitati.items())},
    }


# ══════════════════════════════════════════════
# Mascare
# ══════════════════════════════════════════════

class _Masca:
    """Codurile de încasare: „…1234" ca valoare, „x1234" în entity ID-uri și titluri."""

    def __init__(self, coduri: set[str]) -> None:
        # cele mai lungi întâi, ca un cod să nu fie înlocuit parțial de altul
        self._coduri = sorted((c for c in coduri if c), key=len, reverse=True)

    @staticmethod
    def cod(cod: Any) -> str:
        s = str(cod)
        return f"…{s[-4:]}" if len(s) > 4 else s

    def text(self, text: str) -> str:
        for c in self._coduri:
            if len(c) > 4 and c in text:
                text = text.replace(c, f"x{c[-4:]}")
        return text


def _mascheaza_email(email: str) -> str:
    """Maschează email-ul păstrând prima literă și domeniul."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}{'*' * (len(local) - 1)}@{domain}"
