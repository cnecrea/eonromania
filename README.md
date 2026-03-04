![logo-main](https://github.com/user-attachments/assets/5841ec01-81c9-4c25-8373-b09d9ba11fe6)

# E·ON România — Integrare Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/cnecrea/eonromania)](https://github.com/cnecrea/eonromania/releases)
![Total descărcări pentru toate versiunile](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cnecrea/eonromania/main/statistici/shields/descarcari.json)
![Descărcări pentru ultima versiune](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cnecrea/eonromania/main/statistici/shields/ultima_release.json)


Integrare custom pentru [Home Assistant](https://www.home-assistant.io/) care monitorizează datele contractuale, consumul și facturile prin API-ul [E·ON România](https://www.eon.ro/) (aplicația mobilă E·ON Myline).

Oferă senzori dedicați per cod de încasare pentru contract, index curent, sold, facturi, plăți, istoric citiri, convenție consum, citire permisă, și un buton de trimitere index.

---

## Ce face integrarea

- **Descoperire automată** a contractelor asociate contului E·ON Myline
- **Selectare granulară** a contractelor pe care vrei să le monitorizezi (checkbox-uri cu adrese complete)
- **11 senzori + 1 buton** per contract selectat — fiecare contract devine un device dedicat
- **Multi-contract** — un singur cont E·ON poate monitoriza mai multe coduri de încasare simultan
- **Sold și facturi** — sold curent, facturi restante, prosumator, cu sume în format românesc (1.234,56 lei)
- **Istoric citiri** — indexuri lunare cu tip citire (autocitit / estimat / citit distribuitor)
- **Arhivă plăți** — plățile efectuate pe an, cu total anual
- **Arhivă consum** — consum lunar și mediu zilnic per an, cu separatorul zecimal românesc (virgulă)
- **Adrese normalizate** — formatare corectă din datele API în format românesc
- **Mapping județe** — coduri scurte (AB, BV, CJ) convertite automat în denumiri complete (Alba, Brașov, Cluj)
- **Reconfigurare fără reinstalare** — OptionsFlow pentru modificarea credențialelor și selecției contractelor

---

## Sursa datelor

Datele vin prin API-ul aplicației mobile E·ON Myline (`api2.eon.ro`), care expune endpoint-uri REST pentru:

| Endpoint | Descriere |
|----------|-----------|
| contract-details | Detalii contract (prețuri, adresă, PCS) |
| invoices/list | Facturi neachitate |
| invoices/list-prosum | Facturi prosumator |
| invoice-balance | Sold factură |
| invoice-balance-prosum | Sold prosumator |
| rescheduling-plans | Planuri de eșalonare |
| graphic-consumption | Grafic consum anual (arhivă consum) |
| meter-reading/index | Index curent contor |
| meter-reading/history | Istoric citiri contor |
| consumption-convention | Convenție consum |
| payments/payment-list | Istoric plăți |

Autentificarea se face cu email + parolă + semnătură HMAC-MD5 (mobile-login). Token-ul expirat (401) este reînnoit automat.

---

## Instalare

### HACS (recomandat)

1. Deschide HACS în Home Assistant
2. Click pe cele 3 puncte (⋮) din colțul dreapta sus → **Custom repositories**
3. Adaugă URL-ul: `https://github.com/cnecrea/eonromania`
4. Categorie: **Integration**
5. Click **Add** → găsește „E·ON România" → **Install**
6. Restartează Home Assistant

### Manual

1. Copiază folderul `custom_components/eonromania/` în directorul `config/custom_components/` din Home Assistant
2. Restartează Home Assistant

---

## Configurare

### Pasul 1 — Adaugă integrarea

1. **Setări** → **Dispozitive și Servicii** → **Adaugă Integrare**
2. Caută „**E·ON România**"
3. Completează formularul:

| Câmp | Descriere | Implicit |
|------|-----------|----------|
| **Email** | Adresa de email a contului E·ON Myline | — |
| **Parolă** | Parola contului E·ON Myline | — |
| **Interval actualizare** | Secunde între interogările API | `3600` (1 oră) |

### Pasul 2 — Selectează contractele

După autentificare, contractele sunt descoperite automat. Fiecare contract apare cu adresa completă normalizată:

```
Strada Exemplu 10, ap. 5, Cluj-Napoca, jud. Cluj ➜ 002103870166 (Gaz)
Bulevardul Unirii 20, București ➜ 001234567890 (Electricitate)
```

Selectezi individual sau bifezi „Selectează toate contractele".

### Pasul 3 — Reconfigurare (opțional)

Toate setările pot fi modificate după instalare, fără a șterge integrarea:

1. **Setări** → **Dispozitive și Servicii** → click pe **E·ON România**
2. Click pe **Configurare** (⚙️)
3. Modifică setările dorite → **Salvează**
4. Integrarea se reîncarcă automat cu noile setări

Detalii complete în [SETUP.md](SETUP.md).

---

## Entități create

Integrarea creează un **device** per contract selectat. Sub fiecare device se creează senzori și un buton.

Cu 2 contracte selectate = 2 device-uri × (11+ senzori + 1 buton) = **24+ entități** total.

### Senzori

| Entitate | Descriere | Valoare principală |
|----------|-----------|-------------------|
| `Date contract` | Detalii contract (prețuri, adresă, PCS) | Cod încasare |
| `Sold factură` | Sold curent (tradus în română) | Suma în lei |
| `Sold prosumator` | Sold prosumator | Suma în lei |
| `Index gaz` / `Index energie electrică` | Index contor (doar în perioada de citire) | Valoare index |
| `Citire permisă` | Autocitire activă? | Da / Nu |
| `Factură restantă` | Facturi neachitate cu calcul zile scadență | Da / Nu |
| `Factură restantă prosumator` | Facturi prosumator (datorii + credite) | Da / Nu |
| `Convenție consum` | Consum lunar convenit | Da / Nu |
| `Planuri eșalonare` | Planuri de eșalonare (condiționat) | Număr planuri |
| `{an} → Arhivă index gaz` / `energie electrică` | Indexuri lunare per an | Număr citiri |
| `{an} → Arhivă plăți` | Plăți lunare per an | Număr plăți |
| `{an} → Arhivă consum gaz` / `energie electrică` | Consum lunar + mediu zilnic per an | Total consum |

### Buton

| Entitate | Descriere |
|----------|-----------|
| `Trimite index` | Trimite indexul contorului către API-ul E·ON |

---

### Senzor: Date contract

**Valoare principală**: codul de încasare

**Atribute**:
```yaml
Cod încasare: "002103870166"
Cod loc de consum (NLC): "..."
CLC - Cod punct de măsură: "..."
Operator de Distribuție (OD): "..."
Preț final (fără TVA): "..."
Preț final (cu TVA): "..."
Preț furnizare: "..."
Tarif reglementat distribuție: "..."
Tarif reglementat transport: "..."
PCS (Potențial caloric superior): "..."
Adresă consum: "Strada Exemplu 10, ap. 5, Cluj-Napoca, jud. Cluj"
Următoarea verificare a instalației: "..."
Data inițierii reviziei: "..."
Următoarea revizie tehnică: "..."
```

### Senzor: Sold factură

**Valoare principală**: suma soldului în lei

**Atribute** (traduse automat din API în română):
```yaml
Sold: "934,07 lei"
Rambursare disponibilă: "Nu"
Data sold: "04.03.2026"
Rambursare în curs: "Nu"
Garanție activă: "Nu"
Garanție neachitată: "Nu"
Sold de plată: "Da"
Documente rambursare necesare: "Nu"
Asociație: "Nu"
```

### Senzor: Index gaz / Index energie electrică

**Valoare principală**: valoarea indexului curent

**Atribute**:
```yaml
Numărul dispozitivului: "..."
Numărul ID intern citire contor: "..."
Data de începere a următoarei citiri: "..."
Data de final a citirii: "..."
Autorizat să citească contorul: "Da / Nu"
Permite modificarea citirii: "Da / Nu"
Dispozitiv inteligent: "Da / Nu"
Tipul citirii curente: "citit distribuitor / autocitit / estimat"
Citire anterioară: "..."
Ultima citire validată: "..."
Index propus pentru facturare: "..."
```

### Senzor: Factură restantă

**Valoare principală**: Da / Nu

**Atribute** (când există restanțe):
```yaml
Factură 1: "125,50 lei — scadentă în 3 zile"
Factură 2: "98,20 lei — termen depășit cu 15 zile"
Total neachitat: "223,70 lei"
```

### Senzor: Arhivă consum gaz / energie electrică

**Valoare principală**: consum total anual

**Atribute** (cu separatorul zecimal românesc):
```yaml
Consum lunar ianuarie: "124,91 m3"
Consum lunar februarie: "91,45 m3"
...
────: ""
Consum mediu zilnic în ianuarie: "4,029 m3"
Consum mediu zilnic în februarie: "3,048 m3"
...
```

### Buton: Trimite index

Trimite indexul contorului către API-ul E·ON (endpoint meter-reading/index).

**Cerințe**:
- `input_number.gas_meter_reading` — definit de utilizator
- Perioada de citire activă (senzorul „Citire permisă" = Da)

---

## Exemple de automatizări

### Notificare factură restantă

```yaml
automation:
  - alias: "Notificare factură restantă E·ON"
    trigger:
      - platform: state
        entity_id: sensor.eonromania_002103870166_factura_restanta
        to: "Da"
    action:
      - service: notify.mobile_app_telefonul_meu
        data:
          title: "Factură restantă E·ON"
          message: >
            Ai {{ state_attr('sensor.eonromania_002103870166_factura_restanta', 'Total neachitat') }}
            de plătit.
```

### Card pentru Dashboard

```yaml
type: entities
title: E·ON România
entities:
  - entity: sensor.eonromania_002103870166_date_contract
    name: Contract
  - entity: sensor.eonromania_002103870166_sold_factura
    name: Sold factură
  - entity: sensor.eonromania_002103870166_citire_permisa
    name: Citire permisă
  - entity: sensor.eonromania_002103870166_factura_restanta
    name: Factură restantă
  - entity: sensor.eonromania_002103870166_conventie_consum
    name: Convenție consum
```

---

## Structura fișierelor

```
custom_components/eonromania/
├── __init__.py          # Setup/unload integrare (runtime_data pattern, multi-contract)
├── api.py               # Manager API — login HMAC-MD5, GET/POST cu retry pe 401
├── button.py            # Buton trimitere index per contract
├── config_flow.py       # ConfigFlow + OptionsFlow (autentificare, selecție contracte)
├── const.py             # Constante, URL-uri API
├── coordinator.py       # DataUpdateCoordinator — fetch paralel (11 endpoint-uri per contract)
├── helpers.py           # Funcții utilitare, mapping județe, formatare adrese, traduceri
├── manifest.json        # Metadata integrare
├── sensor.py            # 11 clase senzor cu clasă de bază comună
├── strings.json         # Traduceri implicite (engleză)
└── translations/
    └── ro.json          # Traduceri române
```

---

## Cerințe

- **Home Assistant** 2024.x sau mai nou (pattern `entry.runtime_data`)
- **HACS** (opțional, pentru instalare ușoară)
- **Cont E·ON Myline** activ cu email + parolă

Nu necesită dependențe externe (nu instalează pachete pip/npm).

---

## Limitări cunoscute

1. **O singură instanță per cont** — dacă încerci să adaugi același email de două ori, vei primi eroare „Acest cont E·ON este deja configurat".

2. **Senzorii de index și citire permisă** — apar cu date doar în perioada de citire. În rest, afișează `0` sau `Nu`.

3. **Trimitere index** — butonul necesită `input_number.gas_meter_reading` definit manual de utilizator. Nu se creează automat.

4. **Planuri eșalonare** — senzorul apare doar dacă API-ul returnează date de eșalonare.

---

## ☕ Susține dezvoltatorul

Dacă ți-a plăcut această integrare și vrei să sprijini munca depusă, **invită-mă la o cafea**! 🫶
Nu costă nimic, iar contribuția ta ajută la dezvoltarea viitoare a proiectului. 🙌

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Susține%20dezvoltatorul-orange?style=for-the-badge&logo=buy-me-a-coffee)](https://buymeacoffee.com/cnecrea)

---

## 🧑‍💻 Contribuții

Contribuțiile sunt binevenite! Simte-te liber să trimiți un pull request sau să raportezi probleme [aici](https://github.com/cnecrea/eonromania/issues).

---

## 🌟 Suport
Dacă îți place această integrare, oferă-i un ⭐ pe [GitHub](https://github.com/cnecrea/eonromania/)! 😊


## Licență

[MIT](LICENSE)
