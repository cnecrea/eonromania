
# E-ON România - Integrare pentru Home Assistant 🏠🇷🇴

Această integrare pentru Home Assistant oferă **monitorizare completă** a datelor contractuale și a indexurilor de consum pentru utilizatorii E-ON România. Integrarea este configurabilă prin interfața UI și permite afișarea datelor despre contract, citirea indexurilor curente și arhivarea datelor istorice. 🚀

## 🌟 Caracteristici

### Senzor `Date contract`:
- **🔍 Monitorizare Generală**:
  - Afișează informații detaliate despre contractul de furnizare energie.
- **📊 Atribute disponibile**:
  - **Cod încasare**: Codul unic al contractului.
  - **Cod loc de consum (NLC)**: Identificatorul locației de consum.
  - **Operator Distribuție (OD)**: Numele operatorului de distribuție.
  - **Prețuri detaliate**: Include prețurile pentru furnizare, transport și distribuție.
  - **Adresă consum**: Adresa locației de consum.

### Senzor `Index curent`:
- **🔍 Monitorizare Index**:
  - Afișează valorile curente ale indexului contorului.
- **📊 Atribute disponibile**:
  - **Număr dispozitiv**: Numărul contorului.
  - **Data de început și final a citirii**: Intervalul de citire.
  - **Ultima citire validată**: Indexul confirmat.
  - **Index propus pentru facturare**: Valoarea actuală a indexului.

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
2. Introdu datele contului E-ON: **nume utilizator**, **parolă**, și **cod încasare**.
3. Specifică intervalul de actualizare (implicit: 3600 secunde).

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
