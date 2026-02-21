# Exemple de carduri Lovelace

Aici găsești exemple concrete de carduri pe care le poți adăuga în dashboard-ul tău Home Assistant. Copiază codul YAML și adaptează entity_id-urile la configurația ta.

> **⚠️ Important:** În toate exemplele de mai jos, înlocuiește `00XXXXXXXXXX` cu codul tău real de încasare (12 cifre). Entity_id-urile exacte le găsești în **Setări** → **Dispozitive și Servicii** → **E·ON România** → click pe dispozitiv.

---

## Card general — toate entitățile

Un card simplu care afișează toți senzorii principali într-o singură listă:

```yaml
type: entities
title: E·ON România
entities:
  - entity: sensor.e_on_romania_00XXXXXXXXXX_date_contract
    name: Date contract
  - entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    name: Index curent
  - entity: sensor.e_on_romania_00XXXXXXXXXX_citire_permisa
    name: Citire permisă
  - entity: sensor.e_on_romania_00XXXXXXXXXX_conventie_consum
    name: Convenție consum
  - entity: sensor.e_on_romania_00XXXXXXXXXX_factura_restanta
    name: Factură restantă
  - entity: sensor.e_on_romania_00XXXXXXXXXX_factura_restanta_prosumator
    name: Factură prosumator
  - entity: button.e_on_romania_00XXXXXXXXXX_trimite_index
    name: Trimite index
```

---

## Card detaliat — Index curent

Afișează toate atributele disponibile pentru indexul curent. Util în perioada de citire:

```yaml
type: entities
title: Index curent — Detalii
entities:
  - entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    name: Valoare index
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Numărul dispozitivului
    name: Numărul dispozitivului
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Tipul citirii curente
    name: Tipul citirii
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Data de începere a următoarei citiri
    name: Începutul perioadei de citire
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Data de final a citirii
    name: Sfârșitul perioadei de citire
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Autorizat să citească contorul
    name: Citire permisă
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Permite modificarea citirii
    name: Permite modificare
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Citire anterioară
    name: Citire anterioară
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Ultima citire validată
    name: Ultima citire validată
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Index propus pentru facturare
    name: Index propus
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Trimis la
    name: Data trimiterii
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_index_curent
    attribute: Poate fi modificat până la
    name: Termen modificare
```

---

## Card detaliat — Date contract

Informații contractuale complete:

```yaml
type: entities
title: Detalii contract E·ON
entities:
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_date_contract
    attribute: Cod încasare
    name: Cod încasare
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_date_contract
    attribute: Cod loc de consum (NLC)
    name: Cod NLC
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_date_contract
    attribute: Operator de Distribuție (OD)
    name: Operator distribuție
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_date_contract
    attribute: Preț final (cu TVA)
    name: Preț final (cu TVA)
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_date_contract
    attribute: Preț furnizare
    name: Preț furnizare
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_date_contract
    attribute: Adresă consum
    name: Adresa
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_date_contract
    attribute: Următoarea verificare a instalației
    name: Verificare instalație
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_date_contract
    attribute: Următoarea revizie tehnică
    name: Revizie tehnică
```

---

## Card — Factură restantă

Afișează starea plăților și detaliile facturilor:

```yaml
type: entities
title: Facturi restante
entities:
  - entity: sensor.e_on_romania_00XXXXXXXXXX_factura_restanta
    name: Factură restantă
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_factura_restanta
    attribute: Total neachitat
    name: Total neachitat
```

---

## Card — Factură prosumator

Pentru utilizatorii cu contract de prosumator:

```yaml
type: entities
title: Prosumator
entities:
  - entity: sensor.e_on_romania_00XXXXXXXXXX_factura_restanta_prosumator
    name: Factură prosumator
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_factura_restanta_prosumator
    attribute: Total neachitat
    name: Total neachitat
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_factura_restanta_prosumator
    attribute: Total credit
    name: Total credit
  - type: attribute
    entity: sensor.e_on_romania_00XXXXXXXXXX_factura_restanta_prosumator
    attribute: Sold total prosumator
    name: Sold prosumator
```

> **Notă:** Atributele „Total credit", „Sold total prosumator" și „Rambursare disponibilă" apar doar când există date relevante de la E·ON. Dacă nu ești prosumator sau nu ai sold, unele atribute vor lipsi — e normal.

---

## Card — Trimitere index cu input_number

Dacă ai un cititor de contor și vrei un card cu câmpul de introducere a indexului și butonul de trimitere:

```yaml
type: vertical-stack
title: Trimitere index gaz
cards:
  - type: entities
    entities:
      - entity: input_number.gas_meter_reading
        name: Index de trimis
      - entity: sensor.e_on_romania_00XXXXXXXXXX_citire_permisa
        name: Citire permisă
  - type: button
    entity: button.e_on_romania_00XXXXXXXXXX_trimite_index
    name: Trimite indexul
    icon: mdi:send
    tap_action:
      action: toggle
```

> **Prerequisite:** Trebuie să ai definit `input_number.gas_meter_reading` în configurația ta. Acesta e actualizat de hardware-ul de pe contor.

---

## Card condiționat — Alertă factură restantă

Afișează un card de alertă doar când ai facturi neachitate:

```yaml
type: conditional
conditions:
  - condition: state
    entity: sensor.e_on_romania_00XXXXXXXXXX_factura_restanta
    state: "Da"
card:
  type: markdown
  content: >-
    ## ⚠️ Ai factură restantă!

    **Total neachitat:** {{ state_attr('sensor.e_on_romania_00XXXXXXXXXX_factura_restanta', 'Total neachitat') }}

    Verifică detaliile în secțiunea Facturi din dashboard.
```

---

## Observații generale

- **Înlocuiește `00XXXXXXXXXX`** cu codul tău real de încasare (12 cifre) în toate exemplele de mai sus.
- **Entity_id-urile sunt generate automat** de Home Assistant din numele dispozitivului + numele senzorului. Formatul tipic este: `sensor.e_on_romania_{cod_incasare}_{nume_senzor}`.
- **Atributele apar doar când E·ON furnizează datele.** Dacă un atribut nu e vizibil, înseamnă că API-ul nu a returnat acea informație — nu e o eroare.
- Dacă întâmpini probleme, consultă [DEBUG.md](./DEBUG.md) pentru activarea logării detaliate.
