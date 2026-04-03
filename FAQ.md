<a name="top"></a>
# Întrebări frecvente

- [Cum adaug integrarea în Home Assistant?](#cum-adaug-integrarea-în-home-assistant)
- [Am cont DUO. Pot folosi integrarea?](#am-cont-duo-pot-folosi-integrarea)
- [Ce senzori primesc pentru un contract DUO?](#ce-senzori-primesc-pentru-un-contract-duo)
- [Ce înseamnă „index curent"?](#ce-înseamnă-index-curent)
- [Nu îmi apare indexul curent. De ce?](#nu-îmi-apare-indexul-curent-de-ce)
- [Nu îmi apare senzorul „Citire permisă". De ce?](#nu-îmi-apare-senzorul-citire-permisă-de-ce)
- [Senzorul „Citire permisă" arată „Nu" deși sunt în perioada de citire. De ce?](#senzorul-citire-permisă-arată-nu-deși-sunt-în-perioada-de-citire-de-ce)
- [Ce înseamnă senzorul „Factură restantă prosumator"?](#ce-înseamnă-senzorul-factură-restantă-prosumator)
- [Nu sunt prosumator. Senzorul de prosumator îmi afișează „Nu" — e normal?](#nu-sunt-prosumator-senzorul-de-prosumator-îmi-afișează-nu--e-normal)
- [Ce înseamnă senzorul „Sold factură"?](#ce-înseamnă-senzorul-sold-factură)
- [De ce entitățile au un nume lung, cu codul de încasare inclus?](#de-ce-entitățile-au-un-nume-lung-cu-codul-de-încasare-inclus)
- [Pot monitoriza mai multe contracte simultan?](#pot-monitoriza-mai-multe-contracte-simultan)
- [Vreau să trimit indexul automat. De ce am nevoie?](#vreau-să-trimit-indexul-automat-de-ce-am-nevoie)
- [Am un cititor de contor gaz. Cum fac automatizarea?](#am-un-cititor-de-contor-gaz-cum-fac-automatizarea)
- [De ce valorile sunt afișate cu punct și virgulă (1.234,56)?](#de-ce-valorile-sunt-afișate-cu-punct-și-virgulă-123456)
- [Am schimbat opțiunile integrării. Trebuie să restartez?](#am-schimbat-opțiunile-integrării-trebuie-să-restartez)
- [Trebuie să șterg și readaug integrarea la actualizare?](#trebuie-să-șterg-și-readaug-integrarea-la-actualizare)
- [Ce e licența și de ce am nevoie de ea?](#ce-e-licența-și-de-ce-am-nevoie-de-ea)
- [Am introdus licența dar senzorii tot arată „Licență necesară". De ce?](#am-introdus-licența-dar-senzorii-tot-arată-licență-necesară-de-ce)
- [Îmi place proiectul. Cum pot să-l susțin?](#îmi-place-proiectul-cum-pot-să-l-susțin)

---

## Cum adaug integrarea în Home Assistant?

[↑ Înapoi la cuprins](#top)

Ai nevoie de HACS (Home Assistant Community Store) instalat. Dacă nu-l ai, urmează [ghidul oficial HACS](https://hacs.xyz/docs/use).

1. În Home Assistant, mergi la **HACS** → cele **trei puncte** din dreapta sus → **Custom repositories**.
2. Introdu URL-ul: `https://github.com/cnecrea/eonromania` și selectează tipul **Integration**.
3. Apasă **Add**, apoi caută **E·ON România** în HACS și instalează.
4. Repornește Home Assistant.
5. Mergi la **Setări** → **Dispozitive și Servicii** → **Adaugă Integrare** → caută **E·ON România** și urmează pașii de configurare.

Detalii complete în [SETUP.md](./SETUP.md).

---

## Am cont DUO. Pot folosi integrarea?

[↑ Înapoi la cuprins](#top)

Da. Integrarea detectează automat contractele colective/DUO și le tratează corespunzător.

Iată cum procedezi:

1. Adaugă integrarea cu email-ul și parola contului E·ON Myline.
2. La pasul 2 (selectare contracte), vei vedea toate contractele cu adresele complete — inclusiv contractul DUO etichetat cu `(Colectiv/DUO)`.
3. Selectează-l.

Integrarea va:
- Descoperi automat subcontractele (gaz + electricitate) prin endpoint-ul `account-contracts/list`
- Obține detalii, index contor, și convenție consum **per subcontract**, în paralel
- Crea senzori dedicați per subcontract (Index gaz, Index energie electrică, Citire permisă gaz, Citire permisă electricitate)
- Afișa în Date contract toate detaliile DUO: subcontracte, prețuri, OD, NLC, POD, citiri contor

---

## Ce senzori primesc pentru un contract DUO?

[↑ Înapoi la cuprins](#top)

Un contract DUO generează:

**Senzori de bază** (pe contractul colectiv):
- Date contract — cu atribute detaliate per subcontract (gaz + electricitate)
- Sold factură, Sold prosumator, Factură restantă, Factură prosumator
- Convenție consum — cu valori lunare per utilitate (gaz separat, electricitate separat)

**Senzori per subcontract** (pe codurile individuale de gaz și electricitate):
- Index gaz / Index energie electrică — valoarea indexului per subcontract
- Citire permisă gaz / Citire permisă electricitate — starea perioadei de citire per subcontract

Entity ID-urile senzorilor per subcontract folosesc codul subcontractului, nu codul colectiv. Exemplu: `sensor.eonromania_002100234567_index_gaz`.

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
        "startDate": "2026-03-20",
        "endDate": "2026-03-28",
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

## Senzorul „Citire permisă" arată „Nu" deși sunt în perioada de citire. De ce?

[↑ Înapoi la cuprins](#top)

Acest lucru a fost corectat în versiunea curentă. Senzorul folosește acum indicatorul `readingPeriod.inPeriod` direct de la API (cel mai fiabil), cu fallback pe `readingPeriod.allowedReading` și apoi pe calculul manual cu `startDate` / `endDate`.

Dacă senzorul tot arată „Nu" deși ești în perioada de citire:
1. Verifică atributele secundare ale senzorului — ar trebui să vezi „În perioadă de citire: Da" și „Citire autorizată: Da"
2. Dacă atributele lipsesc, API-ul E·ON nu furnizează date pentru acel contract — posibil contract inactiv
3. Activează debug logging ([DEBUG.md](DEBUG.md)) și verifică răspunsul endpoint-ului `meter_index`

---

## Ce înseamnă senzorul „Factură restantă prosumator"?

[↑ Înapoi la cuprins](#top)

Acest senzor monitorizează facturile asociate contractului de **prosumator** (persoane care au panouri fotovoltaice sau alte surse de producție și sunt conectate la rețea).

Entity ID-ul acestui senzor este `sensor.eonromania_{cod}_factura_prosumator`.

Diferența față de senzorul normal „Factură restantă":
- **Factură restantă** — arată doar dacă ai datorii pe contul de consum obișnuit.
- **Factură restantă prosumator** — arată atât **datoriile**, cât și **creditele** din contractul de prosumator. Dacă ai produs mai mult decât ai consumat, vei vedea un credit. Senzorul afișează și informații despre soldul global, disponibilitatea rambursării și dacă o rambursare este în curs.

---

## Nu sunt prosumator. Senzorul de prosumator îmi afișează „Nu" — e normal?

[↑ Înapoi la cuprins](#top)

Absolut normal. Dacă nu ai contract de prosumator, API-ul E·ON nu returnează date pentru acest endpoint, iar senzorul va afișa **Nu** cu atributul „Nu există facturi disponibile". Poți să-l ignori sau să-l ascunzi din dashboard.

---

## Ce înseamnă senzorul „Sold factură"?

[↑ Înapoi la cuprins](#top)

Senzorul „Sold factură" (`sensor.eonromania_{cod}_sold_factura`) indică dacă ai un sold de plată activ:

- **Da** — ai o sumă de plată (datorie). Verifică atributele pentru detalii.
- **Nu** — nu ai sold de plată (zero sau credit).

Atributele sunt traduse automat din API în română:

- **Sold** — suma totală de plată sau credit (format românesc: 1.234,56 lei)
- **Sold de plată** — Da/Nu (indică dacă ai de plătit)
- **Rambursare disponibilă** — Da/Nu (dacă poți solicita rambursare)
- **Garanție activă** — Da/Nu
- **Data sold** — data la care a fost calculat soldul

Valorile booleene (true/false) sunt traduse automat în Da/Nu, iar sumele sunt afișate în format românesc.

---

## De ce entitățile au un nume lung, cu codul de încasare inclus?

[↑ Înapoi la cuprins](#top)

Integrarea setează manual `entity_id`-ul fiecărei entități, incluzând codul de încasare și tipul contractului. Formatul general este:

- `sensor.eonromania_{cod_incasare}_{tip_senzor}`
- `button.eonromania_{cod_incasare}_{tip_buton}`

De exemplu, pentru un contract de gaz cu codul `004412345678`:
- `sensor.eonromania_004412345678_index_gaz`
- `sensor.eonromania_004412345678_date_contract`
- `sensor.eonromania_004412345678_sold_factura`
- `button.eonromania_004412345678_trimite_index_gaz`

Avantajul principal: dacă ai mai multe contracte monitorizate simultan, fiecare entitate are un ID unic, fără conflicte.

---

## Pot monitoriza mai multe contracte simultan?

[↑ Înapoi la cuprins](#top)

Da. Integrarea suportă **multi-contract**. Un singur cont E·ON poate monitoriza oricâte coduri de încasare dorești, inclusiv contracte DUO.

La pasul de configurare, selectezi contractele dorite (sau le selectezi pe toate). Fiecare contract generează un device separat cu senzorii proprii, iar datele se actualizează în paralel.

---

## Vreau să trimit indexul automat. De ce am nevoie?

[↑ Înapoi la cuprins](#top)

Două lucruri:

**1. Hardware pe contor** — Un senzor capabil să citească impulsurile contorului (contact reed / magnetic, de regulă). Trebuie să fie compatibil cu contorul tău și să nu necesite modificări permanente ale acestuia. Senzorul trimite impulsurile către Home Assistant, unde sunt convertite într-o valoare numerică stocată în `input_number`.

**2. Integrarea configurată** — Butoanele de trimitere index din integrare citesc valoarea din `input_number` corespunzător și o trimit către API-ul E·ON:

- **Gaz**: butonul `Trimite index gaz` (`button.eonromania_{cod}_trimite_index_gaz`) citește din `input_number.gas_meter_reading`
- **Electricitate**: butonul `Trimite index energie electrică` (`button.eonromania_{cod}_trimite_index_energie_electrica`) citește din `input_number.energy_meter_reading`

La contractele DUO, ambele butoane sunt create automat (câte unul per subcontract). La contractele individuale, apare un singur buton corespunzător tipului de utilitate.

> **Atenție:** Butoanele caută exact entitățile `input_number.gas_meter_reading` și/sau `input_number.energy_meter_reading`. Dacă acestea nu există sau au valori invalide, trimiterea va eșua. Verifică în loguri dacă întâmpini probleme.

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
              entity_id: button.eonromania_004412345678_trimite_index_gaz
```

**Ce face:**
- În **ziua 9** a fiecărei luni, la **09:00**, primești o notificare cu indexul curent.
- La **12:00**, integrarea trimite automat indexul către E·ON.

> **⚠️ Important:** Înlocuiește `004412345678` cu codul tău real de încasare (12 cifre) și `notify.mobile_app_telefonul_meu` cu entity_id-ul serviciului tău de notificare. Entity_id-urile exacte le găsești în **Setări** → **Dispozitive și Servicii** → **E·ON România**.

---

## De ce valorile sunt afișate cu punct și virgulă (1.234,56)?

[↑ Înapoi la cuprins](#top)

Integrarea folosește formatul numeric românesc: punctul separă miile, virgula separă zecimalele. Exemplu: **1.234,56 lei** înseamnă o mie două sute treizeci și patru de lei și cincizeci și șase de bani. E formatul standard folosit în România.

De asemenea, în senzorul „Arhivă consum", valorile de consum și mediu zilnic folosesc virgula ca separator zecimal (ex: **4,029 m³** în loc de **4.029 m³**), pentru a evita confuzia cu separatorul de mii.

---

## Am schimbat opțiunile integrării. Trebuie să restartez?

[↑ Înapoi la cuprins](#top)

Nu. Integrarea se reîncarcă automat când salvezi modificările din fluxul de opțiuni. Nu este necesar un restart manual al Home Assistant.

De asemenea, dacă modifici credențialele (username, parolă) din opțiuni, integrarea validează autentificarea înainte de a salva — dacă noile date sunt greșite, vei primi o eroare și configurația existentă rămâne neschimbată.

---

## Trebuie să șterg și readaug integrarea la actualizare?

[↑ Înapoi la cuprins](#top)

De regulă nu. Setările sunt stocate în baza de date HA, nu în fișiere. Actualizarea suprascrie doar codul.

**Excepție v3.0.0:** Dacă actualizezi de la v1/v2 la v3, integrarea include migrare automată care convertește formatul vechi (un singur cod de încasare) în formatul nou (listă de contracte). Nu trebuie să faci nimic manual. Dacă totuși apar probleme, șterge integrarea și readaug-o.

---

## Ce e licența și de ce am nevoie de ea?

[↑ Înapoi la cuprins](#top)

Integrarea folosește un sistem de licențiere server-side (v3.3) cu semnături Ed25519 și HMAC-SHA256. Fără o licență validă, integrarea afișează doar senzorul „Licență necesară" și nu creează senzori sau butoane funcționale.

Licența se achiziționează de la: [hubinteligent.org/donate?ref=eonromania](https://hubinteligent.org/donate?ref=eonromania)

După achiziție, introdu cheia de licență din OptionsFlow:
1. **Setări** → **Dispozitive și Servicii** → **E·ON România** → **Configurare**
2. Selectează **Licență**
3. Completează câmpul „Cheie licență"
4. Salvează

---

## Am introdus licența dar senzorii tot arată „Licență necesară". De ce?

[↑ Înapoi la cuprins](#top)

Câteva cauze posibile:

1. **Licența nu a fost validată** — verifică logurile pentru mesaje cu `LICENSE`
2. **Serverul de licențe nu este accesibil** — dacă HA nu are acces la internet, validarea eșuează
3. **Cheie greșită** — verifică că ai copiat cheia corect, fără spații suplimentare
4. **Restartare necesară** — în rare cazuri, un restart al HA poate rezolva problema

Activează debug logging ([DEBUG.md](DEBUG.md)) și caută mesaje legate de licență.

---

## Îmi place proiectul. Cum pot să-l susțin?

[↑ Înapoi la cuprins](#top)

- ⭐ Oferă un **star** pe [GitHub](https://github.com/cnecrea/eonromania/)
- 🐛 **Raportează probleme** — deschide un [issue](https://github.com/cnecrea/eonromania/issues)
- 🔀 **Contribuie cu cod** — trimite un pull request
- ☕ **Donează** prin [Buy Me a Coffee](https://buymeacoffee.com/cnecrea)
- 📢 **Distribuie** proiectul prietenilor sau comunității tale
