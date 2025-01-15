![logo-main](https://github.com/user-attachments/assets/5841ec01-81c9-4c25-8373-b09d9ba11fe6)

# E-ON România - Integrare pentru Home Assistant 🏠🇷🇴

Această integrare pentru Home Assistant oferă **monitorizare completă** a datelor contractuale și a indexurilor de consum pentru utilizatorii E-ON România. Integrarea este configurabilă prin interfața UI și permite afișarea datelor despre contract, citirea indexurilor curente și arhivarea datelor istorice. 🚀

## 🌟 Caracteristici

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
      - **Verificare instalație**: Data următoarei verificări tehnice a instalației.
      - **Data inițierii reviziei**: Data la care începe următoarea revizie tehnică.
      - **Revizie tehnică**: Data expirării următoarei revizii tehnice.

### Senzor `Index curent`:
  - **🔍 Monitorizare date index**:
      - Afișează informații detaliate despre indexul curent al contorului.
  - **📊 Atribute disponibile**:
      - **Numărul dispozitivului**: ID-ul dispozitivului asociat contorului.
      - **Data de început a citirii**: Data de început a perioadei de citire.
      - **Data de final a citirii**: Data de final a perioadei de citire.
      - **Citirea contorului permisă**: Indică dacă citirea poate fi realizată în perioada curentă.
      - **Permite modificarea citirii**: Indică dacă indexul citit poate fi modificat.
      - **Dispozitiv inteligent**: Specifică dacă dispozitivul este un contor inteligent.
      - **Tipul citirii curente**: Tipul citirii efectuate (de exemplu, autocitire).
      - **Citire anterioară**: Valoarea minimă a citirii anterioare.
      - **Ultima citire validată**: Ultima valoare validată a citirii.
      - **Index propus pentru facturare**: Valoarea indexului propus pentru facturare.
      - **Trimis la**: Data și ora la care a fost transmisă ultima citire.
      - **Poate fi modificat până la**: Data și ora până la care citirea poate fi modificată.

### Senzor `Arhivă`:
- **📚 Date istorice**:
  - Afișează indexurile lunare pentru fiecare an disponibil.
- **📊 Atribute disponibile**:
  - **An**: Anul pentru care se afișează datele.
  - **Indexuri lunare**: Indexurile consumului pentru fiecare lună.


### Senzor `Factură restantă`:
- **📄 Detalii sold**:
  - Afișează dacă există facturi restante.
- **📊 Atribute disponibile**:
  - **Restanțe pe luna [numele lunii]**: Soldul restant pentru luna respectivă.
  - **Total sold**: Suma totală a soldului restant, afișată în lei.



### Senzor `Citire permisă`:
- **🔍 Verificare perioadă trimitere**:
    - Afișează dacă perioada de trimitere a indexului este activă.
- **📊 Atribute disponibile**:
    - **ID intern citire contor (SAP)**: Identificator unic pentru punctul de măsurare.
    - **Perioada permisă pentru trimitere**: Intervalul de timp în care indexul poate fi transmis.
    - **Cod încasare**: Codul unic al contractului.
- **🔄 Starea senzorului**:
    - **Da**: Trimiterea indexului este permisă.
    - **Nu**: Trimiterea indexului nu este permisă.
    - **Indisponibil**: Datele nu sunt disponibile.


### Buton `Trimite index`:
- **🔘 Buton interactiv**:
    - Permite trimiterea indexului către API-ul E-ON România, utilizabil atât prin interfața Home Assistant, cât și prin automatizări.
- **📊 Funcționalități**:
    - Determină valoarea indexului din entitatea `input_number.gas_meter_reading`.
    - Validează și trimite indexul folosind endpoint-ul API.


### Senzor `Convenție consum`:
- **📊 Gestionarea consumului lunar**: Afișează detalii despre convenția de consum pe luni, incluzând doar lunile cu valori mai mari de 0.
- **📄 Atribute disponibile**:
  - **Valori lunare ale consumului**: Exemplu: `Convenție pentru luna ianuarie: 10 mc`.
  - **Număr de luni configurate**: Totalul lunilor cu valori > 0.
- **🔄 Starea senzorului**: Reprezintă numărul de luni configurate. Exemplu: `3` (pentru 3 luni configurate).
- **🎯 Exemplu de afișare**:

```text
Stare principală: 3
Atribute:
  Convenție pentru luna ianuarie: 10 mc
  Convenție pentru luna februarie: 5 mc
  Convenție pentru luna martie: 15 mc
```

---

## ⚙️ Configurare

### 🛠️ Interfața UI:
1. Adaugă integrarea din meniul **Setări > Dispozitive și Servicii > Adaugă Integrare**.
2. Introdu datele contului E-ON:
   - **Nume utilizator**: username-ul contului tău E-ON.
   - **Parolă**: parola asociată contului tău.
   - ~~**Cod încasare**: dacă codul este format din 10 cifre, de exemplu `2100023241`, trebuie să adaugi două zerouri la început. Rezultatul final ar trebui să fie `002100023241`.~~
   - **Cod încasare**: Se găsește pe factura ta
     - Nu mai este nevoie să introduci manual 00 înaintea codului de încasare! Dacă codul tău este format din 10 cifre (de exemplu `2100023241`), funcția de corectare implementată va adăuga automat două zerouri la început. Rezultatul final va deveni `002100023241`, astfel încât autentificarea să fie corectă și fără erori.
3. Specifică intervalul de actualizare (implicit: 3600 secunde).

### Observații:
- Verifică datele de autentificare înainte de salvare.
- Asigură-te că formatul codului de încasare este corect pentru a evita problemele de conectare.

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

### 🔔 Automatizare pentru Index:
Creează o automatizare pentru a primi notificări când indexul curent depășește o valoare specificată.

```yaml
alias: Notificare Index Ridicat
description: Notificare dacă indexul depășește 1000
trigger:
  - platform: numeric_state
    entity_id: sensor.eonromania_index_curent_00XXXXXXXXXX
    above: 1000
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Index Ridicat Detectat! ⚡"
      message: "Indexul curent este {{ states('sensor.eonromania_index_curent_00XXXXXXXXXX') }}."
mode: single
```

### 🔍 Card pentru Dashboard:
Afișează datele despre contract, indexuri și arhivă pe interfața Home Assistant.

```yaml
type: entities
title: Monitorizare E-ON România
entities:
  - entity: sensor.eonromania_date_contract_00XXXXXXXXXX
    name: Date Contract
  - entity: sensor.eonromania_index_curent_00XXXXXXXXXX
    name: Index Curent
  - entity: sensor.eonromania_arhiva_index_00XXXXXXXXXX_2024
    name: Arhivă 2024
```

---

## ☕ Susține dezvoltatorul

Dacă ți-a plăcut această integrare și vrei să sprijini munca depusă, **invită-mă la o cafea**! 🫶  
Nu costă nimic, iar contribuția ta ajută la dezvoltarea viitoare a proiectului. 🙌  

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Susține%20dezvoltatorul-orange?style=for-the-badge&logo=buy-me-a-coffee)](https://buymeacoffee.com/cnecrea)

Mulțumesc pentru sprijin și apreciez fiecare gest de susținere! 🤗

--- 


## 🧑‍💻 Contribuții

Contribuțiile sunt binevenite! Simte-te liber să trimiți un pull request sau să raportezi probleme [aici](https://github.com/cnecrea/eonromania/issues).

---

## 🌟 Suport
Dacă îți place această integrare, oferă-i un ⭐ pe [GitHub](https://github.com/cnecrea/eonromania/)! 😊
