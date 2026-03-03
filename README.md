![logo-main](https://github.com/user-attachments/assets/5841ec01-81c9-4c25-8373-b09d9ba11fe6)

# E-ON România - Integrare pentru Home Assistant 🏠🇷🇴

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/cnecrea/eonromania)](https://github.com/cnecrea/eonromania/releases)
![Total descărcări pentru toate versiunile](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cnecrea/eonromania/main/statistici/shields/descarcari.json)
![Descărcări pentru ultima versiune](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cnecrea/eonromania/main/statistici/shields/ultima_release.json)


Această integrare pentru Home Assistant oferă **monitorizare completă** a datelor contractuale și a indexurilor de consum pentru utilizatorii E-ON România. Integrarea este configurabilă prin interfața UI și permite afișarea datelor despre contract, citirea indexurilor curente, facturile restante (inclusiv prosumator) și arhivarea datelor istorice. 🚀

Integrarea detectează automat tipul contractului (gaz sau energie electrică) și adaptează denumirile senzorilor, unitățile de măsură și entity ID-urile.

## 🌟 Caracteristici

### Senzor `Arhivă consum gaz` / `Arhivă consum energie electrică`:
- **📚 Date istorice**:
  - Afișează consumul total lunar (în m³ pentru gaz, kWh pentru energie electrică).
- **📊 Atribute disponibile**:
  - **Consum lunar**: Cantitatea consumată pentru fiecare lună.
  - **Consum mediu zilnic**: Media zilnică a consumului pentru fiecare lună.
- **🔄 Starea senzorului**: Consumul total anual (valoare numerică).

### Senzor `Arhivă index gaz` / `Arhivă index energie electrică`:
- **📚 Date istorice**:
  - Afișează indexurile lunare pentru fiecare an disponibil.
- **📊 Atribute disponibile**:
  - **Indexuri lunare**: Indexurile consumului pentru fiecare lună, inclusiv metoda de citire (autocitire, estimare, citire distribuitor).

### Senzor `Arhivă plăți`:
- **📚 Date istorice**:
  - Afișează plățile lunare pentru fiecare an disponibil.
- **📊 Atribute disponibile**:
  - **Plăți lunare**: Totalul plăților efectuate pentru fiecare lună în anul selectat.
  - **Plăți efectuate**: Numărul total de plăți din anul respectiv.
  - **Sumă totală**: Suma anuală a tuturor plăților, afișată în format românesc (1.234,56 lei).

### Senzor `Citire permisă`:
- **🔍 Verificare perioadă trimitere**:
    - Afișează dacă perioada de trimitere a indexului este activă.
- **📊 Atribute disponibile**:
    - **ID intern citire contor (SAP)**: Identificator unic pentru punctul de măsurare.
    - **Indexul poate fi trimis până la**: Termenul limită pentru trimiterea indexului.
    - **Cod încasare**: Codul unic al contractului.
- **🔄 Starea senzorului**:
    - **Da**: Trimiterea indexului este permisă.
    - **Nu**: Trimiterea indexului nu este permisă.
    - **Eroare**: Datele nu sunt disponibile sau a apărut o problemă.

### Senzor `Convenție consum`:
- **📊 Gestionarea consumului lunar**: Afișează detalii despre convenția de consum pe luni.
- **📄 Atribute disponibile**:
  - **Valori lunare ale consumului**: Exemplu: `Convenție din luna ianuarie: 10 m3` (sau kWh pentru energie electrică).
- **🔄 Starea senzorului**:
    - **Da**: Există cel puțin o lună configurată cu valori > 0.
    - **Nu**: Nu există valori configurate sau datele nu sunt disponibile.

### Senzor `Date contract`:
  - **🔍 Monitorizare generală**:
      - Afișează informații detaliate despre contractul de furnizare energie.
  - **📊 Atribute disponibile**:
      - **Cod încasare**: Codul unic al contractului.
      - **Cod loc de consum (NLC)**: Identificatorul locației de consum.
      - **CLC - Cod punct de măsură**: Codul unic al punctului de măsurare.
      - **Operator de Distribuție (OD)**: Numele operatorului de distribuție.
      - **Prețuri detaliate**:
        - **Preț final (fără TVA)**: Valoarea finală fără TVA.
        - **Preț final (cu TVA)**: Valoarea finală inclusiv TVA.
        - **Preț furnizare**: Costul pentru furnizarea energiei.
        - **Tarif reglementat distribuție**: Costul distribuției energiei.
        - **Tarif reglementat transport**: Costul transportului energiei.
      - **PCS (Potențial caloric superior)**: Valoarea calorică superioară a energiei.
      - **Adresă consum**: Adresa locației de consum.
      - **Următoarea verificare a instalației**: Data următoarei verificări tehnice.
      - **Data inițierii reviziei**: Data la care începe următoarea revizie tehnică.
      - **Următoarea revizie tehnică**: Data expirării următoarei revizii tehnice.

### Senzor `Factură restantă`:
- **📄 Detalii sold**:
  - Afișează dacă există facturi restante pe contul de consum.
- **📊 Atribute disponibile**:
  - **Factură {nr}**: Detalii despre fiecare factură — sumă, scadență, zile rămase sau depășite.
  - **Total neachitat**: Suma totală a soldului restant, afișată în format românesc (1.234,56 lei).
- **🔄 Starea senzorului**:
    - **Da**: Există cel puțin o factură neachitată.
    - **Nu**: Nu există facturi restante.

### Senzor `Factură restantă prosumator`:
- **📄 Detalii sold prosumator**:
  - Afișează dacă există facturi restante sau credite pe contul de prosumator (panouri fotovoltaice sau alte surse de producție conectate la rețea).
- **📊 Atribute disponibile**:
  - **Factură {nr} ({număr factură})**: Detalii despre fiecare datorie — sumă, scadență, zile rămase sau depășite.
  - **Credit {nr} ({număr factură})**: Creditele acumulate (când ai produs mai mult decât ai consumat).
  - **Sold total prosumator**: Soldul global — datorie sau credit.
  - **Rambursare disponibilă**: Indică dacă poți solicita rambursarea creditului.
  - **Rambursare în proces**: Indică dacă o rambursare este deja în curs de procesare.
  - **Data sold**: Data la care a fost calculat soldul.
  - **Total datorie**: Suma totală a datoriilor.
  - **Total credit**: Suma totală a creditelor.
  - **Total neachitat**: Suma netă de plată, afișată în format românesc (1.234,56 lei).
- **🔄 Starea senzorului**:
    - **Da**: Există cel puțin o factură neachitată (datorie) pe contul de prosumator.
    - **Nu**: Nu există datorii (poate exista credit).
- **💡 Notă**: Dacă nu ești prosumator, senzorul va afișa **Nu** cu atributul „Nu există facturi disponibile" — este un comportament normal.

### Senzor `Index gaz` / `Index energie electrică`:
  - **🔍 Monitorizare date index**:
      - Afișează informații detaliate despre indexul curent al contorului.
      - Denumirea și entity ID-ul se adaptează automat în funcție de tipul contractului.
  - **📊 Atribute disponibile**:
      - **Numărul dispozitivului**: ID-ul dispozitivului asociat contorului.
      - **Numărul ID intern citire contor**: Identificatorul intern SAP.
      - **Data de începere a următoarei citiri**: Data de început a perioadei de citire.
      - **Data de final a citirii**: Data de final a perioadei de citire.
      - **Autorizat să citească contorul**: Indică dacă citirea poate fi realizată în perioada curentă.
      - **Permite modificarea citirii**: Indică dacă indexul citit poate fi modificat.
      - **Dispozitiv inteligent**: Specifică dacă dispozitivul este un contor inteligent.
      - **Tipul citirii curente**: Tipul citirii efectuate (Citire distribuitor, Autocitire, Estimare).
      - **Citire anterioară**: Valoarea minimă a citirii anterioare.
      - **Ultima citire validată**: Ultima valoare validată a citirii.
      - **Index propus pentru facturare**: Valoarea indexului propus pentru facturare.
      - **Trimis la**: Data și ora la care a fost transmisă ultima citire.
      - **Poate fi modificat până la**: Data și ora până la care citirea poate fi modificată.
  - **💡 Notă**: Indexul curent apare doar în perioada de citire. În afara acestei perioade, API-ul E·ON nu publică date și senzorul nu va avea informații. Consultă [FAQ](./FAQ.md) pentru detalii.

### Buton `Trimite index gaz`:
- **🔘 Buton interactiv**:
    - Permite trimiterea indexului către API-ul E-ON România, utilizabil atât prin interfața Home Assistant, cât și prin automatizări.
- **📊 Funcționalități**:
    - Determină valoarea indexului din entitatea `input_number.gas_meter_reading`.
    - Validează și trimite indexul folosind endpoint-ul API.
    - După trimitere, solicită automat actualizarea datelor din coordinator.
- **⚠️ Prerequisite**: Trebuie să existe entitatea `input_number.gas_meter_reading` în configurația ta Home Assistant. Butonul nu va funcționa fără aceasta.


---

## ⚙️ Configurare

### 🛠️ Interfața UI:
1. Adaugă integrarea din meniul **Setări > Dispozitive și Servicii > Adaugă Integrare**.
2. Introdu datele contului E-ON:
   - **Nume utilizator**: username-ul contului tău E-ON.
   - **Parolă**: parola asociată contului tău.
   - **Cod încasare**: Se găsește pe factura ta.
     - Nu mai este nevoie să introduci manual 00 înaintea codului de încasare! Dacă codul tău este format din mai puțin de 12 cifre (de exemplu `2100023241`), funcția de corectare implementată va adăuga automat zerourile necesare la început. Rezultatul final va deveni `002100023241`, astfel încât autentificarea să fie corectă și fără erori.
3. Specifică intervalul de actualizare (implicit: 3600 secunde).

### Observații:
- Verifică datele de autentificare înainte de salvare.
- Asigură-te că formatul codului de încasare este corect pentru a evita problemele de conectare.
- Dacă ai un cont DUO, consultă [FAQ — Am cont DUO](./FAQ.md#am-cont-duo-pot-folosi-integrarea) pentru a găsi codurile de încasare corecte.
- **Modificarea opțiunilor** (credențiale, cod de încasare, interval de actualizare) din fluxul de opțiuni reîncarcă automat integrarea. Nu este necesar un restart manual.
- **La modificarea credențialelor**, integrarea validează autentificarea înainte de a salva — nu riști să blochezi integrarea cu date greșite.

### 🏷️ Denumirea entităților:
Integrarea setează manual `entity_id`-ul fiecărei entități și adaptează automat denumirile în funcție de tipul contractului (gaz sau energie electrică).

**Senzori care depind de tipul contractului:**

| Senzor | Entity ID (gaz) | Entity ID (electricitate) |
|---|---|---|
| Index | `…_index_gaz` | `…_index_energie_electrica` |
| Arhivă consum | `…_arhiva_consum_gaz_{an}` | `…_arhiva_consum_energie_electrica_{an}` |
| Arhivă index | `…_arhiva_index_gaz_{an}` | `…_arhiva_index_energie_electrica_{an}` |

**Senzori comuni (indiferent de tipul contractului):**
- `sensor.eonromania_{cod}_date_contract`
- `sensor.eonromania_{cod}_citire_permisa`
- `sensor.eonromania_{cod}_conventie_consum`
- `sensor.eonromania_{cod}_factura_restanta`
- `sensor.eonromania_{cod}_factura_prosumator`
- `sensor.eonromania_{cod}_arhiva_plati_{an}`
- `button.eonromania_{cod}_trimite_index_gaz`

> **Atenție:** Entity ID-urile exacte le poți verifica în **Setări** → **Dispozitive și Servicii** → **E·ON România** → click pe dispozitiv.

---

## 🚀 Instalare

### 💡 Instalare prin HACS:
1. Adaugă [depozitul personalizat](https://github.com/cnecrea/eonromania) în HACS. 🛠️
2. Caută integrarea **E-ON România** și instaleaz-o. ✅
3. Repornește Home Assistant și configurează integrarea. 🔄

### ✋ Instalare manuală:
1. Clonează sau descarcă [depozitul GitHub](https://github.com/cnecrea/eonromania). 📂
2. Copiază folderul `custom_components/eonromania` în directorul `custom_components` al Home Assistant. 🗂️
3. Repornește Home Assistant și configurează integrarea. 🔧

---

## ✨ Exemple de utilizare

### 🔔 Automatizare pentru factură restantă:
Creează o automatizare pentru a primi notificări când ai facturi neachitate.

```yaml
alias: Notificare factură restantă E·ON
description: Notificare dacă există facturi neachitate
triggers:
  - trigger: state
    entity_id: sensor.eonromania_00XXXXXXXXXX_factura_restanta
    to: "Da"
actions:
  - action: notify.mobile_app_telefonul_meu
    data:
      title: "Factură restantă E·ON ⚡"
      message: >-
        Ai o factură neachitată.
        Total: {{ state_attr('sensor.eonromania_00XXXXXXXXXX_factura_restanta', 'Total neachitat') }}
mode: single
```

### 🔍 Card pentru Dashboard:
Afișează datele principale pe interfața Home Assistant. Exemplul de mai jos e pentru un contract de **gaz** — dacă ai energie electrică, înlocuiește `_index_gaz` cu `_index_energie_electrica`.

```yaml
type: entities
title: E·ON România
entities:
  - entity: sensor.eonromania_00XXXXXXXXXX_date_contract
    name: Date contract
  - entity: sensor.eonromania_00XXXXXXXXXX_index_gaz
    name: Index gaz
  - entity: sensor.eonromania_00XXXXXXXXXX_citire_permisa
    name: Citire permisă
  - entity: sensor.eonromania_00XXXXXXXXXX_factura_restanta
    name: Factură restantă
  - entity: sensor.eonromania_00XXXXXXXXXX_factura_prosumator
    name: Factură prosumator
```

> **⚠️ Important:** Înlocuiește `00XXXXXXXXXX` cu codul tău real de încasare (12 cifre). Entity_id-urile exacte le găsești în **Setări** → **Dispozitive și Servicii** → **E·ON România** → click pe dispozitiv.

Mai multe exemple de carduri și automatizări găsești în [SETUP.md](./SETUP.md).

---

## 📚 Documentație suplimentară

- **[FAQ.md](./FAQ.md)** — Întrebări frecvente: cont DUO, index curent care nu apare, automatizare trimitere index, prosumator.
- **[SETUP.md](./SETUP.md)** — Exemple detaliate de carduri Lovelace pentru fiecare senzor.
- **[DEBUG.md](./DEBUG.md)** — Cum activezi logarea detaliată și cum analizezi problemele.

---

# Întrebări frecvente

Consultă fișierul [FAQ.md](./FAQ.md) pentru ghiduri detaliate și soluții pas cu pas! 😊

---

## ⚠️ Limitări cunoscute

- **Senzorii sunt creați la pornire.** Dacă la momentul pornirii integrării nu ești în perioada de citire, senzorii de index și citire permisă sunt creați fără date de dispozitiv. Datele se populează automat când începe perioada de citire.
- **Butonul „Trimite index gaz" necesită `input_number.gas_meter_reading`.** Această entitate trebuie creată manual; nu este generată de integrare.

---

## ☕ Susține dezvoltatorul

Dacă ți-a plăcut această integrare și vrei să sprijini munca depusă, **invită-mă la o cafea**! 🫶  

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Susține%20dezvoltatorul-orange?style=for-the-badge&logo=buy-me-a-coffee)](https://buymeacoffee.com/cnecrea)

--- 

## 🧑‍💻 Contribuții

Contribuțiile sunt binevenite! Simte-te liber să trimiți un pull request sau să raportezi probleme [aici](https://github.com/cnecrea/eonromania/issues).

---

## 🌟 Suport
Dacă îți place această integrare, oferă-i un ⭐ pe [GitHub](https://github.com/cnecrea/eonromania/)! 😊
