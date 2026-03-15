![logo-main](https://github.com/user-attachments/assets/5841ec01-81c9-4c25-8373-b09d9ba11fe6)

# E·ON România — Integrare Home Assistant

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.11%2B-41BDF5?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/cnecrea/eonromania)](https://github.com/cnecrea/eonromania/releases)
[![GitHub Stars](https://img.shields.io/github/stars/cnecrea/eonromania?style=flat&logo=github)](https://github.com/cnecrea/eonromania/stargazers)
[![Instalări](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cnecrea/eonromania/main/statistici/shields/descarcari.json)](https://github.com/cnecrea/eonromania)
[![Ultima versiune](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cnecrea/eonromania/main/statistici/shields/ultima_release.json)](https://github.com/cnecrea/eonromania/releases/latest)

Integrare custom pentru [Home Assistant](https://www.home-assistant.io/) care monitorizează datele contractuale, consumul și facturile prin API-ul [E·ON România](https://www.eon.ro/) (aplicația mobilă E·ON Myline).

Oferă senzori dedicați per cod de încasare pentru contract, index curent, sold, facturi, plăți, istoric citiri, convenție consum, citire permisă, și butoane de trimitere index per utilitate. Suportă complet contracte DUO (colective gaz + electricitate).

---

## Ce face integrarea

- **Descoperire automată** a contractelor asociate contului E·ON Myline
- **Selectare granulară** a contractelor pe care vrei să le monitorizezi (checkbox-uri cu adrese complete)
- **Multi-contract** — un singur cont E·ON poate monitoriza mai multe coduri de încasare simultan
- **Suport complet DUO** — contractele colective (gaz + electricitate sub un singur cod) sunt detectate automat, cu senzori separați per subcontract (index, citire permisă, convenție consum)
- **Senzori dedicați** per contract selectat — fiecare contract devine un device dedicat
- **Sold și facturi** — existență sold (Da/Nu), facturi restante cu detalii în atribute, format românesc (1.234,56 lei)
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
| account-contracts/list | Listă subcontracte (pentru contracte DUO) |
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
2. Caută „**E·ON românia**"
3. Completează formularul:

| Câmp | Descriere | Implicit |
|------|-----------|----------|
| **Email** | Adresa de email a contului E·ON Myline | — |
| **Parolă** | Parola contului E·ON Myline | — |
| **Interval actualizare** | Secunde între interogările API | `3600` (1 oră) |

### Pasul 2 — Selectează contractele

După autentificare, contractele sunt descoperite automat. Fiecare contract apare cu adresa completă normalizată:

```
Strada Florilor 15, ap. 8, Cluj-Napoca, jud. Cluj ➜ 004412345678 (Gaz)
Bulevardul Independenței 42, Brașov, jud. Brașov ➜ 009900123456 (Colectiv/DUO)
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

Integrarea creează un **device** per contract selectat. Sub fiecare device se creează senzori și butoane de trimitere index (câte un buton per utilitate).

### Contract individual (gaz sau electricitate)

| Entitate | Descriere | Valoare principală |
|----------|-----------|-------------------|
| `Date contract` | Detalii contract (prețuri, adresă, PCS) | Cod încasare |
| `Sold factură` | Există sold de plată? | Da / Nu |
| `Sold prosumator` | Există sold prosumator? | Da / Nu |
| `Index gaz` / `Index energie electrică` | Index contor curent | Valoare index |
| `Citire permisă` | Autocitire activă? | Da / Nu |
| `Factură restantă` | Facturi neachitate cu calcul zile scadență | Da / Nu |
| `Factură restantă prosumator` | Facturi prosumator (datorii + credite) | Da / Nu |
| `Convenție consum` | Consum lunar convenit | Da / Nu |
| `Planuri eșalonare` | Planuri de eșalonare (condiționat) | Număr planuri |
| `{an} → Arhivă index gaz` / `energie electrică` | Indexuri lunare per an | Număr citiri |
| `{an} → Arhivă plăți` | Plăți lunare per an | Număr plăți |
| `{an} → Arhivă consum gaz` / `energie electrică` | Consum lunar + mediu zilnic per an | Total consum |

### Contract colectiv / DUO (gaz + electricitate)

Pe lângă senzorii de bază (Date contract, Sold factură, Factură restantă, etc.), contractele DUO generează senzori suplimentari per subcontract:

| Entitate | Descriere | Valoare principală |
|----------|-----------|-------------------|
| `Index gaz` | Index contor gaz (subcontract) | Valoare index |
| `Index energie electrică` | Index contor electricitate (subcontract) | Valoare index |
| `Citire permisă gaz` | Autocitire activă pe gaz? | Da / Nu |
| `Citire permisă electricitate` | Autocitire activă pe electricitate? | Da / Nu |
| `Convenție consum` | Convenție per utilitate (gaz + electricitate) | Da / Nu |

Senzorul `Date contract` pentru DUO afișează în atribute: detalii contract colectiv, subcontracte cu coduri și adrese, plus detalii complete per subcontract (prețuri, contor, OD, NLC, POD).

### Butoane

| Entitate | Descriere | Când apare |
|----------|-----------|------------|
| `Trimite index gaz` | Trimite indexul contorului de gaz din `input_number.gas_meter_reading` | Contract gaz sau DUO (subcontract gaz) |
| `Trimite index energie electrică` | Trimite indexul contorului de electricitate din `input_number.energy_meter_reading` | Contract electricitate sau DUO (subcontract electricitate) |

La contractele individuale apare un singur buton (gaz SAU electricitate, detectat automat). La contractele DUO apar ambele butoane, fiecare trimițând indexul pentru subcontractul corespunzător.

---

### Senzor: Date contract

**Valoare principală**: codul de încasare

**Atribute (contract individual)**:
```yaml
Cod încasare: "004412345678"
Cod loc de consum (NLC): "..."
CLC - Cod punct de măsură: "..."
Operator de Distribuție (OD): "..."
Preț final (fără TVA): "..."
Preț final (cu TVA): "..."
Preț furnizare: "..."
Tarif reglementat distribuție: "..."
Tarif reglementat transport: "..."
PCS: "..."
Adresă consum: "Strada Florilor 15, ap. 8, Cluj-Napoca, jud. Cluj"
Următoarea verificare a instalației: "..."
Data inițierii reviziei: "..."
Următoarea revizie tehnică: "..."
```

**Atribute (contract DUO)**:
```yaml
Cod încasare (DUO): "009900123456"
Tip contract: "Colectiv / DUO (gaz + curent)"
Adresă de corespondență: "..."
────: ""
Număr subcontracte: 2
Gaz — Cod încasare: "002100234567"
Gaz — Cod loc consum (NLC): "..."
Electricitate — Cod încasare: "002200345678"
Electricitate — Cod loc consum (NLC): "..."
──── Gaz Natural ────: ""
Gaz Natural — Cod încasare: "002100234567"
Gaz Natural — Operator Distribuție (OD): "..."
Gaz Natural — Preț final (cu TVA): "..."
Gaz Natural — PCS: "10.657"
──── Energie Electrică ────: ""
Energie Electrică — Cod încasare: "002200345678"
Energie Electrică — Operator Distribuție (OD): "..."
```

### Senzor: Sold factură

**Valoare principală**: Da / Nu (există sold de plată?)

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
Numărul dispozitivului: "01234567/2020"
Numărul ID intern citire contor: "..."
Data de începere a următoarei citiri: "2026-03-01"
Data de final a citirii: "2026-03-07"
Autorizat să citească contorul: "Da"
Permite modificarea citirii: "Da"
Dispozitiv inteligent: "Nu"
Tipul citirii curente: "Autocitire"
Citire anterioară: "6.030"
Ultima citire validată: "6.030"
```

### Senzor: Citire permisă

**Valoare principală**: Da / Nu

Logica de determinare (în ordinea priorității):
1. `readingPeriod.inPeriod` — indicator direct de la API
2. `readingPeriod.allowedReading` — fallback
3. Calcul manual pe `startDate` / `endDate` — fallback final

**Atribute**:
```yaml
ID intern citire contor (SAP): "..."
Indexul poate fi trimis până la: "2026-03-07"
Perioadă transmitere index: "2026-03-01 — 2026-03-07"
În perioadă de citire: "Da"
Citire autorizată: "Da"
Cod încasare: "002100234567"
```

### Senzor: Factură restantă

**Valoare principală**: Da / Nu

**Atribute** (când există restanțe):
```yaml
Factură 1: "125,50 lei — scadentă în 3 zile"
Factură 2: "98,20 lei — termen depășit cu 15 zile"
Total neachitat: "223,70 lei"
```

### Senzor: Convenție consum

**Valoare principală**: Da / Nu

**Atribute (contract individual)**:
```yaml
Convenție din luna ianuarie: "150 m³"
Convenție din luna februarie: "150 m³"
...
```

**Atribute (contract DUO)** — afișate per utilitate:
```yaml
──── Gaz ────: ""
Gaz — ianuarie: "150 m³"
Gaz — februarie: "150 m³"
...
Gaz — Valabilă din: "2025-06-06"
Gaz — Preț contractual: "0.25637 lei"
Gaz — PCS: "10.657"
──── Electricitate ────: ""
Electricitate — ianuarie: "85 kWh"
...
```

### Senzor: Arhivă consum gaz / energie electrică

**Valoare principală**: consum total anual

**Atribute** (cu separatorul zecimal românesc):
```yaml
Consum lunar ianuarie: "124,91 m³"
Consum lunar februarie: "91,45 m³"
...
────: ""
Consum mediu zilnic în ianuarie: "4,029 m³"
Consum mediu zilnic în februarie: "3,048 m³"
...
```

### Butoane: Trimite index gaz / Trimite index energie electrică

Trimite indexul contorului către API-ul E·ON (endpoint meter-reading/index). Fiecare buton folosește propriul `input_number`:

| Buton | input_number necesar | Entity ID (individual) | Entity ID (DUO subcontract) |
|-------|---------------------|----------------------|----------------------------|
| Trimite index gaz | `input_number.gas_meter_reading` | `button.eonromania_{cod}_trimite_index_gaz` | `button.eonromania_{cod_subcontract}_trimite_index_gaz` |
| Trimite index energie electrică | `input_number.energy_meter_reading` | `button.eonromania_{cod}_trimite_index_energie_electrica` | `button.eonromania_{cod_subcontract}_trimite_index_energie_electrica` |

**Cerințe**:
- `input_number.gas_meter_reading` și/sau `input_number.energy_meter_reading` — definite de utilizator în `configuration.yaml`
- Perioada de citire activă (senzorul „Citire permisă" = Da)

---

## Exemple de automatizări

### Notificare factură restantă

```yaml
automation:
  - alias: "Notificare factură restantă E·ON"
    trigger:
      - platform: state
        entity_id: sensor.eonromania_004412345678_factura_restanta
        to: "Da"
    action:
      - service: notify.mobile_app_telefonul_meu
        data:
          title: "Factură restantă E·ON"
          message: >
            Ai {{ state_attr('sensor.eonromania_004412345678_factura_restanta', 'Total neachitat') }}
            de plătit.
```

### Card pentru Dashboard

```yaml
type: entities
title: E·ON România
entities:
  - entity: sensor.eonromania_004412345678_date_contract
    name: Contract
  - entity: sensor.eonromania_004412345678_sold_factura
    name: Sold factură
  - entity: sensor.eonromania_004412345678_citire_permisa
    name: Citire permisă
  - entity: sensor.eonromania_004412345678_factura_restanta
    name: Factură restantă
  - entity: sensor.eonromania_004412345678_conventie_consum
    name: Convenție consum
```

---

## Structura fișierelor

```
custom_components/eonromania/
├── __init__.py          # Setup/unload integrare (runtime_data pattern, multi-contract)
├── api.py               # Manager API — login HMAC-MD5, GET/POST cu retry pe 401
├── button.py            # Butoane trimitere index per utilitate (gaz / electricitate / DUO)
├── config_flow.py       # ConfigFlow + OptionsFlow (autentificare, selecție contracte)
├── const.py             # Constante, URL-uri API
├── coordinator.py       # DataUpdateCoordinator — fetch paralel per contract (inclusiv DUO)
├── helpers.py           # Funcții utilitare, mapping județe, formatare adrese, traduceri
├── manifest.json        # Metadata integrare
├── sensor.py            # Clase senzor cu suport individual + colectiv/DUO
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

3. **Trimitere index** — butoanele necesită `input_number.gas_meter_reading` și/sau `input_number.energy_meter_reading` definite manual de utilizator în `configuration.yaml`. Nu se creează automat.

4. **Planuri eșalonare** — senzorul apare doar dacă API-ul returnează date de eșalonare.

5. **DUO — Arhivă consum și Arhivă index** — aceste senzori nu sunt disponibili pe contractul colectiv (endpoint-urile nu funcționează pe contractul părinte). Datele de index și convenție sunt disponibile per subcontract.

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
