
# E-ON România - Integrare pentru Home Assistant 🏠🇷🇴

Această integrare pentru Home Assistant oferă **monitorizare completă** a datelor contractuale și a indexurilor de consum pentru utilizatorii E-ON România. Integrarea este configurabilă prin interfața UI și permite afișarea datelor despre contract, citirea indexurilor curente și arhivarea datelor istorice. 🚀

## 🌟 Caracteristici

### Senzor `Date contract`:
  - **🔍 Monitorizare Generală**:
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

### Senzor `Index Curent`:
  - **🔍 Monitorizare Date Index**:
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
- **📚 Date Istorice**:
  - Afișează indexurile lunare pentru fiecare an disponibil.
- **📊 Atribute disponibile**:
  - **An**: Anul pentru care se afișează datele.
  - **Indexuri lunare**: Indexurile consumului pentru fiecare lună.

---

## ⚙️ Configurare

### 🛠️ Interfața UI:
1. Adaugă integrarea din meniul **Setări > Dispozitive și Servicii > Adaugă Integrare**.
2. Introdu datele contului E-ON:
   - **Nume utilizator**: username-ul contului tău E-ON.
   - **Parolă**: parola asociată contului tău.
   - **Cod încasare**: dacă codul este format din 10 cifre, de exemplu `2100023241`, trebuie să adaugi două zerouri la început. Rezultatul final ar trebui să fie `002100023241`.
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
    entity_id: sensor.index_curent_002222257503939227
    above: 1000
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Index Ridicat Detectat! ⚡"
      message: "Indexul curent este {{ states('sensor.index_curent_002222257503939227') }}."
mode: single
```

### 🔍 Card pentru Dashboard:
Afișează datele despre contract, indexuri și arhivă pe interfața Home Assistant.

```yaml
type: entities
title: Monitorizare E-ON România
entities:
  - entity: sensor.date_contract
    name: Date Contract
  - entity: sensor.index_curent_002222257503939227
    name: Index Curent
  - entity: sensor.arhiva_2024
    name: Arhivă 2024
```

---

## 🧑‍💻 Contribuții

Contribuțiile sunt binevenite! Simte-te liber să trimiți un pull request sau să raportezi probleme [aici](https://github.com/cnecrea/eonromania/issues).

---

## 🌟 Suport
Dacă îți place această integrare, oferă-i un ⭐ pe [GitHub](https://github.com/cnecrea/eonromania/)! 😊
