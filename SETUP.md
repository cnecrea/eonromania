# Ghid de instalare și configurare — E·ON România

Acest ghid acoperă fiecare pas al instalării și configurării integrării E·ON România pentru Home Assistant. Dacă ceva nu e clar, deschide un [issue pe GitHub](https://github.com/cnecrea/eonromania/issues).

---

## Cerințe preliminare

Înainte de a începe, asigură-te că ai:

- **Home Assistant** versiunea 2024.x sau mai nouă (necesită pattern `entry.runtime_data`)
- **Cont E·ON Myline** activ — cu email și parolă funcționale pe aplicația mobilă E·ON Myline
- **HACS** instalat (opțional, dar recomandat) — [instrucțiuni HACS](https://hacs.xyz/docs/setup/download)

---

## Metoda 1: Instalare prin HACS (recomandat)

### Pasul 1 — Adaugă repository-ul custom

1. Deschide Home Assistant → sidebar → **HACS**
2. Click pe cele 3 puncte (⋮) din colțul dreapta sus
3. Selectează **Custom repositories**
4. În câmpul „Repository" scrie: `https://github.com/cnecrea/eonromania`
5. În câmpul „Category" selectează: **Integration**
6. Click **Add**

### Pasul 2 — Instalează integrarea

1. În HACS, caută „**E·ON România**" sau „**E-ON România**"
2. Click pe rezultat → **Download** (sau **Install**)
3. Confirmă instalarea

### Pasul 3 — Restartează Home Assistant

1. **Setări** → **Sistem** → **Restart**
2. Sau din terminal: `ha core restart`

**Așteptare**: restartul durează 1–3 minute. Nu continua până nu se încarcă complet dashboard-ul.

---

## Metoda 2: Instalare manuală

### Pasul 1 — Descarcă fișierele

1. Mergi la [Releases](https://github.com/cnecrea/eonromania/releases) pe GitHub
2. Descarcă ultima versiune (zip sau tar.gz)
3. Dezarhivează

### Pasul 2 — Copiază folderul

Copiază întregul folder `custom_components/eonromania/` în directorul de configurare al Home Assistant:

```
config/
└── custom_components/
    └── eonromania/
        ├── __init__.py
        ├── api.py
        ├── button.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── helpers.py
        ├── manifest.json
        ├── sensor.py
        ├── strings.json
        └── translations/
            └── ro.json
```

**Atenție**: folderul trebuie să fie exact `eonromania` (litere mici, fără spații).

Dacă folderul `custom_components` nu există, creează-l.

### Pasul 3 — Restartează Home Assistant

La fel ca la Metoda 1.

---

## Configurare inițială

### Pasul 1 — Adaugă integrarea

1. **Setări** → **Dispozitive și Servicii**
2. Click **+ Adaugă Integrare** (butonul albastru, dreapta jos)
3. Caută „**E·ON**" — va apărea „E·ON România"
4. Click pe ea

### Pasul 2 — Completează formularul de autentificare

Vei vedea un formular cu 3 câmpuri:

#### Câmp 1: Adresă de email

- **Ce face**: adresa de email a contului E·ON Myline
- **Format**: email valid (ex: `user@example.com`)
- **Observație**: este și identificatorul unic al integrării — nu poți adăuga același email de două ori

#### Câmp 2: Parolă

- **Ce face**: parola contului E·ON Myline
- **Observație**: stocată criptat în baza de date HA

#### Câmp 3: Interval actualizare (secunde)

- **Ce face**: la câte secunde se reîmprospătează datele de la API
- **Implicit**: `3600` (1 oră)
- **Recomandare**: lasă pe 3600. Datele E·ON nu se schimbă frecvent. Nu se recomandă valori sub 600 secunde.

### Pasul 3 — Selectează contractele

După autentificare reușită, contractele sunt descoperite automat. Vei vedea lista tuturor contractelor asociate contului, cu adrese complete normalizate:

```
Strada Florilor 15, ap. 8, Cluj-Napoca, jud. Cluj ➜ 004412345678 (Gaz)
Bulevardul Independenței 42, Brașov, jud. Brașov ➜ 009900123456 (Colectiv/DUO)
```

Ai două opțiuni:
- **Selectare individuală** — bifezi doar contractele dorite
- **Selectează toate** — bifezi „Selectează toate contractele"

**Observație**: dacă nu selectezi niciun contract și nu bifezi „toate", vei primi eroare: „Selectați cel puțin un contract pentru a continua."

**Contracte DUO**: contractele colective apar cu eticheta `(Colectiv/DUO)`. La selectare, integrarea descoperă automat subcontractele (gaz + electricitate) și creează senzori dedicați per subcontract.

### Pasul 4 — Confirmă

Click **Salvează**. Integrarea se instalează și creează:
- 1 device per contract selectat
- Senzori + butoane de trimitere index per device (1 buton pentru contract individual, 2 butoane pentru DUO)

Prima actualizare durează câteva secunde (interogare API pentru toate endpoint-urile per contract, în paralel).

---

## Reconfigurare (fără reinstalare)

Toate setările pot fi modificate din UI, fără a șterge și readăuga integrarea.

1. **Setări** → **Dispozitive și Servicii**
2. Găsește **E·ON România** → click pe **Configurare** (⚙️)
3. Completează din nou email, parolă, interval
4. La pasul următor, poți modifica selecția contractelor
5. Click **Salvează**
6. Integrarea se reîncarcă automat (nu e nevoie de restart)

**Observație**: la reconfigurare, contractele sunt redescoperite. Dacă au apărut contracte noi, le vei vedea în listă.

**Validare**: dacă modifici credențialele și noile date sunt greșite, vei primi o eroare și configurația existentă rămâne neschimbată.

---

## Referință rapidă — Entity ID-uri

### Senzori comuni (gaz și electricitate):

| Senzor | Entity ID |
|---|---|
| Date contract | `sensor.eonromania_{cod}_date_contract` |
| Sold factură | `sensor.eonromania_{cod}_sold_factura` |
| Sold prosumator | `sensor.eonromania_{cod}_sold_prosumator` |
| Citire permisă | `sensor.eonromania_{cod}_citire_permisa` |
| Convenție consum | `sensor.eonromania_{cod}_conventie_consum` |
| Factură restantă | `sensor.eonromania_{cod}_factura_restanta` |
| Factură prosumator | `sensor.eonromania_{cod}_factura_prosumator` |
| Arhivă plăți (an) | `sensor.eonromania_{cod}_arhiva_plati_{an}` |
| Trimite index gaz | `button.eonromania_{cod}_trimite_index_gaz` |
| Trimite index energie electrică | `button.eonromania_{cod}_trimite_index_energie_electrica` |

### Senzori specifici tipului de contract:

| Senzor | Entity ID (gaz) | Entity ID (electricitate) |
|---|---|---|
| Index | `…_{cod}_index_gaz` | `…_{cod}_index_energie_electrica` |
| Arhivă consum (an) | `…_{cod}_arhiva_consum_gaz_{an}` | `…_{cod}_arhiva_consum_energie_electrica_{an}` |
| Arhivă index (an) | `…_{cod}_arhiva_index_gaz_{an}` | `…_{cod}_arhiva_index_energie_electrica_{an}` |

### Senzori DUO (per subcontract):

| Senzor | Entity ID |
|---|---|
| Index gaz (subcontract) | `sensor.eonromania_{cod_subcontract}_index_gaz` |
| Index electricitate (subcontract) | `sensor.eonromania_{cod_subcontract}_index_energie_electrica` |
| Citire permisă gaz | `sensor.eonromania_{cod_subcontract}_citire_permisa` |
| Citire permisă electricitate | `sensor.eonromania_{cod_subcontract}_citire_permisa` |
| Trimite index gaz (subcontract) | `button.eonromania_{cod_subcontract}_trimite_index_gaz` |
| Trimite index electricitate (subcontract) | `button.eonromania_{cod_subcontract}_trimite_index_energie_electrica` |

---

## Pregătire pentru butoanele Trimite index

Butoanele de trimitere index necesită câte un `input_number` definit manual, în funcție de tipul utilității. Adaugă în `configuration.yaml`:

### Pentru gaz

```yaml
input_number:
  gas_meter_reading:
    name: Index contor gaz
    min: 0
    max: 999999
    step: 1
    mode: box
```

### Pentru electricitate

```yaml
input_number:
  energy_meter_reading:
    name: Index contor energie electrică
    min: 0
    max: 999999
    step: 1
    mode: box
```

> **DUO:** Dacă ai contract DUO, definește **ambele** `input_number` (gaz + electricitate).

Restartează HA după adăugare. Butoanele caută exact entitățile `input_number.gas_meter_reading` și `input_number.energy_meter_reading`.

---

## Exemple de carduri Lovelace

### Card general — toate entitățile

```yaml
type: entities
title: E·ON România
entities:
  - entity: sensor.eonromania_004412345678_date_contract
    name: Date contract
  - entity: sensor.eonromania_004412345678_sold_factura
    name: Sold factură
  - entity: sensor.eonromania_004412345678_index_gaz
    name: Index gaz
  - entity: sensor.eonromania_004412345678_citire_permisa
    name: Citire permisă
  - entity: sensor.eonromania_004412345678_conventie_consum
    name: Convenție consum
  - entity: sensor.eonromania_004412345678_factura_restanta
    name: Factură restantă
  - entity: sensor.eonromania_004412345678_factura_prosumator
    name: Factură prosumator
  - entity: button.eonromania_004412345678_trimite_index_gaz
    name: Trimite index gaz
```

### Card — Sold factură

```yaml
type: entities
title: Sold factură
entities:
  - entity: sensor.eonromania_004412345678_sold_factura
    name: Sold
  - type: attribute
    entity: sensor.eonromania_004412345678_sold_factura
    attribute: Sold de plată
    name: De plată
  - type: attribute
    entity: sensor.eonromania_004412345678_sold_factura
    attribute: Rambursare disponibilă
    name: Rambursare
```

### Card — Factură restantă

```yaml
type: entities
title: Facturi restante
entities:
  - entity: sensor.eonromania_004412345678_factura_restanta
    name: Factură restantă
  - type: attribute
    entity: sensor.eonromania_004412345678_factura_restanta
    attribute: Total neachitat
    name: Total neachitat
```

### Card — Trimitere index gaz cu input_number

```yaml
type: vertical-stack
title: Trimitere index gaz
cards:
  - type: entities
    entities:
      - entity: input_number.gas_meter_reading
        name: Index de trimis
      - entity: sensor.eonromania_004412345678_citire_permisa
        name: Citire permisă
  - type: button
    entity: button.eonromania_004412345678_trimite_index_gaz
    name: Trimite indexul gaz
    icon: mdi:fire
    tap_action:
      action: toggle
```

### Card — Trimitere index electricitate cu input_number

```yaml
type: vertical-stack
title: Trimitere index energie electrică
cards:
  - type: entities
    entities:
      - entity: input_number.energy_meter_reading
        name: Index de trimis
      - entity: sensor.eonromania_002200345678_citire_permisa
        name: Citire permisă electricitate
  - type: button
    entity: button.eonromania_002200345678_trimite_index_energie_electrica
    name: Trimite indexul electricitate
    icon: mdi:flash
    tap_action:
      action: toggle
```

### Card condiționat — Alertă factură restantă

```yaml
type: conditional
conditions:
  - condition: state
    entity: sensor.eonromania_004412345678_factura_restanta
    state: "Da"
card:
  type: markdown
  content: >-
    ## ⚠️ Ai factură restantă!

    **Total neachitat:** {{ state_attr('sensor.eonromania_004412345678_factura_restanta', 'Total neachitat') }}

    Verifică detaliile în secțiunea Facturi din dashboard.
```

---

## Verificare după instalare

### Verifică că device-urile există

1. **Setări** → **Dispozitive și Servicii** → click pe **E·ON România**
2. Ar trebui să vezi un device per contract selectat (ex: „E·ON România (004412345678)")

### Verifică senzorii

1. **Instrumente dezvoltator** → **Stări**
2. Filtrează după `eonromania`
3. Ar trebui să vezi entitățile cu valori (ex: `Da`, `Nu`, `6030`, etc.)

### Verifică logurile (dacă ceva nu merge)

1. **Setări** → **Sistem** → **Jurnale**
2. Caută mesaje cu `eonromania`
3. Pentru detalii, activează debug logging — vezi [DEBUG.md](DEBUG.md)

---

## Dezinstalare

### Prin HACS

1. HACS → găsește „E·ON România" → **Remove**
2. Restartează Home Assistant

### Manual

1. **Setări** → **Dispozitive și Servicii** → E·ON România → **Șterge**
2. Șterge folderul `config/custom_components/eonromania/`
3. Restartează Home Assistant

---

## Observații generale

- **Înlocuiește `004412345678`** cu codul tău real de încasare (12 cifre) în toate exemplele de mai sus.
- **Entity ID-urile sunt setate manual** de integrare pe baza codului de încasare și a tipului de contract. Consultă tabelul de referință de la începutul secțiunii de carduri.
- **Atributele apar doar când E·ON furnizează datele.** Dacă un atribut nu e vizibil, înseamnă că API-ul nu a returnat acea informație — nu e o eroare.
- **Senzorii de index și citire permisă** apar cu date doar în perioada de citire. În rest, afișează `0` sau `Nu`.
- **Contractele DUO** generează senzori de index și citire permisă per subcontract, cu entity ID-uri bazate pe codul subcontractului, nu pe codul colectiv.
- Dacă întâmpini probleme, consultă [DEBUG.md](DEBUG.md) pentru activarea logării detaliate.
