<a name="top"></a>
# Întrebări frecvente

- [Cum adaug integrarea în Home Assistant?](#cum-adaug-integrarea-în-home-assistant)
- [Am cont DUO. Pot folosi integrarea?](#am-cont-duo-pot-folosi-integrarea)
- [Ce înseamnă „index curent"?](#ce-înseamnă-index-curent)
- [Nu îmi apare indexul curent. De ce?](#nu-îmi-apare-indexul-curent-de-ce)
- [Nu îmi apare senzorul „Citire permisă". De ce?](#nu-îmi-apare-senzorul-citire-permisă-de-ce)
- [Ce înseamnă senzorul „Factură restantă prosumator"?](#ce-înseamnă-senzorul-factură-restantă-prosumator)
- [Nu sunt prosumator. Senzorul de prosumator îmi afișează „Nu" — e normal?](#nu-sunt-prosumator-senzorul-de-prosumator-îmi-afișează-nu--e-normal)
- [De ce entitățile au un nume lung, cu codul de încasare inclus?](#de-ce-entitățile-au-un-nume-lung-cu-codul-de-încasare-inclus)
- [Vreau să trimit indexul automat. De ce am nevoie?](#vreau-să-trimit-indexul-automat-de-ce-am-nevoie)
- [Am un cititor de contor gaz. Cum fac automatizarea?](#am-un-cititor-de-contor-gaz-cum-fac-automatizarea)
- [De ce valorile sunt afișate cu punct și virgulă (1.234,56)?](#de-ce-valorile-sunt-afișate-cu-punct-și-virgulă-123456)
- [Am schimbat opțiunile integrării. Trebuie să restartez?](#am-schimbat-opțiunile-integrării-trebuie-să-restartez)
- [Îmi place proiectul. Cum pot să-l susțin?](#îmi-place-proiectul-cum-pot-să-l-susțin)

---

## Cum adaug integrarea în Home Assistant?

[↑ Înapoi la cuprins](#top)

Ai nevoie de HACS (Home Assistant Community Store) instalat. Dacă nu-l ai, urmează [ghidul oficial HACS](https://hacs.xyz/docs/use).

1. În Home Assistant, mergi la **HACS** → cele **trei puncte** din dreapta sus → **Custom repositories**.
2. Introdu URL-ul: `https://github.com/cnecrea/eonromania` și selectează tipul **Integration**.
3. Apasă **Add**, apoi caută **E-ON România** în HACS și instalează.
4. Repornește Home Assistant.
5. Mergi la **Setări** → **Dispozitive și Servicii** → **Adaugă Integrare** → caută **E·ON România** și urmează pașii de configurare.

---

## Am cont DUO. Pot folosi integrarea?

[↑ Înapoi la cuprins](#top)

Da, dar codul de încasare este diferit de cel afișat pe factura DUO. Iată cum găsești codurile corecte:

1. Autentifică-te în contul tău E·ON.
2. Mergi la **Contul meu** → **Transmitere index**.
3. Selectează contul DUO (click pe nume) — vei vedea serviciile asociate (gaz, electricitate).
4. Fiecare serviciu are un **cod de încasare propriu** care începe cu `2XXXX`. Acela e cel corect.

> **Nu folosi** codul DUO care începe cu `9XXXX` — nu funcționează cu API-ul E·ON.

Dacă vrei ambele servicii monitorizate, adaugă integrarea de două ori, o dată cu fiecare cod de încasare. Integrarea va detecta automat tipul contractului (gaz sau electricitate) și va adapta denumirile senzorilor și entity ID-urile corespunzător.

---

## Ce înseamnă „index curent"?

[↑ Înapoi la cuprins](#top)

E ultima valoare citită sau transmisă a contorului — fie de distribuitor, fie de tine (autocitire), fie estimată de E·ON. Termenul e generic și se aplică atât pentru gaz, cât și pentru energie electrică.

În integrare, senzorul se numește **„Index gaz"** sau **„Index energie electrică"**, în funcție de tipul contractului detectat automat.

---

## Nu îmi apare indexul curent. De ce?

[↑ Înapoi la cuprins](#top)

E normal. Indexul curent apare **doar în perioada de citire** (de obicei câteva zile pe lună). Când nu ești în perioada de citire, API-ul E·ON returnează o listă goală de dispozitive, deci integrarea nu are de unde să extragă date.

Concret, în afara perioadei de citire, răspunsul API arată cam așa:
```json
{
    "readingPeriod": {
        "startDate": "2025-01-20",
        "endDate": "2025-01-28",
        "allowedReading": true,
        "inPeriod": false
    },
    "indexDetails": {
        "devices": []
    }
}
```

Când vine perioada de citire, `devices` se populează cu datele contorului și senzorul își afișează valorile. Nu e nicio problemă cu integrarea — pur și simplu E·ON nu publică aceste date în afara perioadei de citire.

**Notă importantă:** Senzorii de index și citire permisă sunt creați la pornirea integrării. Dacă integrarea a fost pornită în afara perioadei de citire, senzorii vor exista dar vor afișa `0` (index) sau `Nu` (citire permisă). Datele se vor popula automat când începe perioada de citire, fără a fi necesar un restart.

---

## Nu îmi apare senzorul „Citire permisă". De ce?

[↑ Înapoi la cuprins](#top)

Același motiv ca la indexul curent — senzorul „Citire permisă" depinde de aceleași date din API. Dacă nu ești în perioada de citire, senzorul va afișa **Nu** sau nu va avea date disponibile. Consultă secțiunea [Nu îmi apare indexul curent](#nu-îmi-apare-indexul-curent-de-ce) pentru detalii.

---

## Ce înseamnă senzorul „Factură restantă prosumator"?

[↑ Înapoi la cuprins](#top)

Acest senzor monitorizează facturile asociate contractului de **prosumator** (persoane care au panouri fotovoltaice sau alte surse de producție și sunt conectate la rețea).

Entity ID-ul acestui senzor este `sensor.eonromania_00XXXXXXXXXX_factura_prosumator`.

Diferența față de senzorul normal „Factură restantă":
- **Factură restantă** — arată doar dacă ai datorii pe contul de consum obișnuit.
- **Factură restantă prosumator** — arată atât **datoriile**, cât și **creditele** din contractul de prosumator. Dacă ai produs mai mult decât ai consumat, vei vedea un credit. Senzorul afișează și informații despre soldul global, disponibilitatea rambursării și dacă o rambursare este în curs.

---

## Nu sunt prosumator. Senzorul de prosumator îmi afișează „Nu" — e normal?

[↑ Înapoi la cuprins](#top)

Absolut normal. Dacă nu ai contract de prosumator, API-ul E·ON nu returnează date pentru acest endpoint, iar senzorul va afișa **Nu** cu atributul „Nu există facturi disponibile". Poți să-l ignori sau să-l ascunzi din dashboard.

---

## De ce entitățile au un nume lung, cu codul de încasare inclus?

[↑ Înapoi la cuprins](#top)

Integrarea setează manual `entity_id`-ul fiecărei entități, incluzând codul de încasare și tipul contractului. Formatul general este:

- `sensor.eonromania_{cod_incasare}_{tip_senzor}`
- `button.eonromania_{cod_incasare}_{tip_buton}`

De exemplu, pentru un contract de gaz cu codul `001234567890`:
- `sensor.eonromania_001234567890_index_gaz`
- `sensor.eonromania_001234567890_date_contract`
- `button.eonromania_001234567890_trimite_index_gaz`

Avantajul principal: dacă ai mai multe coduri de încasare (de exemplu, gaz + electricitate pe cont DUO), fiecare entitate are un ID unic, fără conflicte.

---

## Vreau să trimit indexul automat. De ce am nevoie?

[↑ Înapoi la cuprins](#top)

Două lucruri:

**1. Hardware pe contor** — Un senzor capabil să citească impulsurile contorului (contact reed / magnetic, de regulă). Trebuie să fie compatibil cu contorul tău și să nu necesite modificări permanente ale acestuia. Senzorul trimite impulsurile către Home Assistant, unde sunt convertite într-o valoare numerică stocată în `input_number.gas_meter_reading`.

**2. Integrarea configurată** — Butonul „Trimite index gaz" (`button.eonromania_00XXXXXXXXXX_trimite_index_gaz`) din integrare citește valoarea din `input_number.gas_meter_reading` și o trimite către API-ul E·ON. Poți apăsa butonul manual sau dintr-o automatizare.

> **Atenție:** Butonul caută exact entitatea `input_number.gas_meter_reading`. Dacă aceasta nu există sau are o valoare invalidă, trimiterea va eșua. Verifică în loguri dacă întâmpini probleme.

---

## Am un cititor de contor gaz. Cum fac automatizarea?

[↑ Înapoi la cuprins](#top)

Dacă ai hardware-ul instalat și valoarea se actualizează în `input_number.gas_meter_reading`, poți folosi o automatizare ca aceasta:

```yaml
alias: "GAZ: Transmitere index automat"
description: >-
  Trimite o notificare dimineața și apasă butonul de trimitere index la prânz,
  în ziua 9 a fiecărei luni.
triggers:
  - trigger: time
    at: "09:00:00"
  - trigger: time
    at: "12:00:00"
conditions:
  - condition: template
    value_template: "{{ now().day == 9 }}"
actions:
  - choose:
      - alias: "Notificare la ora 09:00"
        conditions:
          - condition: template
            value_template: "{{ trigger.now.hour == 9 }}"
        sequence:
          - action: notify.mobile_app_telefonul_meu
            data:
              title: "E·ON GAZ — Index de transmis"
              message: >-
                Noul index pentru luna curentă este de
                {{ states('input_number.gas_meter_reading') | float | round(0) | int }}.
      - alias: "Trimitere index la ora 12:00"
        conditions:
          - condition: template
            value_template: "{{ trigger.now.hour == 12 }}"
        sequence:
          - action: button.press
            target:
              entity_id: button.eonromania_00XXXXXXXXXX_trimite_index_gaz
```

**Ce face:**
- În **ziua 9** a fiecărei luni, la **09:00**, primești o notificare cu indexul curent.
- La **12:00**, integrarea trimite automat indexul către E·ON.

> **⚠️ Important:** Înlocuiește `00XXXXXXXXXX` cu codul tău real de încasare (12 cifre) și `notify.mobile_app_telefonul_meu` cu entity_id-ul serviciului tău de notificare. Entity_id-urile exacte le găsești în **Setări** → **Dispozitive și Servicii** → **E·ON România**.

---

## De ce valorile sunt afișate cu punct și virgulă (1.234,56)?

[↑ Înapoi la cuprins](#top)

Integrarea folosește formatul numeric românesc: punctul separă miile, virgula separă zecimalele. Exemplu: **1.234,56 lei** înseamnă o mie două sute treizeci și patru de lei și cincizeci și șase de bani. E formatul standard folosit în România.

---

## Am schimbat opțiunile integrării. Trebuie să restartez?

[↑ Înapoi la cuprins](#top)

Nu. Integrarea se reîncarcă automat când salvezi modificările din fluxul de opțiuni. Nu este necesar un restart manual al Home Assistant.

De asemenea, dacă modifici credențialele (username, parolă) sau codul de încasare din opțiuni, integrarea validează autentificarea înainte de a salva — dacă noile date sunt greșite, vei primi o eroare și configurația existentă rămâne neschimbată.

---

## Îmi place proiectul. Cum pot să-l susțin?

[↑ Înapoi la cuprins](#top)

- ⭐ Oferă un **star** pe [GitHub](https://github.com/cnecrea/eonromania/)
- 🐛 **Raportează probleme** — deschide un [issue](https://github.com/cnecrea/eonromania/issues)
- 🔀 **Contribuie cu cod** — trimite un pull request
- ☕ **Donează** prin [Buy Me a Coffee](https://buymeacoffee.com/cnecrea)
- 📢 **Distribuie** proiectul prietenilor sau comunității tale
