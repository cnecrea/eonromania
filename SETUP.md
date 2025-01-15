
# SETUP.md

## 🔧 Configurarea Integrării EON România

Această documentație explică pașii necesari pentru configurarea integrării și utilizarea datelor generate în Lovelace.

---

## 🚀 Instalare Integrare

### 💡 Instalare prin HACS:
1. Adaugă [depozitul personalizat](https://github.com/cnecrea/eonromania) în HACS. 🛠️
2. Caută integrarea **E-ON România** și instaleaz-o. ✅
3. Repornește Home Assistant și configurează integrarea. 🔄

### ✋ Instalare manuală:
1. Clonează sau descarcă [depozitul GitHub](https://github.com/cnecrea/eonromania). 📂
2. Copiază folderul `custom_components/eonromania` în directorul `custom_components` al Home Assistant. 🗂️
3. Repornește Home Assistant și configurează integrarea. 🔧

---

### 🛠️ Adăugare Integrare
1. Accesează **Setări** > **Dispozitive și Servicii**.
2. Apasă pe **Adaugă Integrare** și caută `EON România`.
3. Introdu detaliile contului tău:
   - **Nume de utilizator** și **Parolă** (de pe portalul EON).
   - ~~**Cod încasare**: dacă codul este format din 10 cifre, de exemplu `2100023241`, trebuie să adaugi două zerouri la început. Rezultatul final ar trebui să fie `002100023241`.~~
   - **Cod încasare**: Se găsește pe factura ta
     - Nu mai este nevoie să introduci manual 00 înaintea codului de încasare! Dacă codul tău este format din 10 cifre (de exemplu `2100023241`), funcția de corectare implementată va adăuga automat două zerouri la început. Rezultatul final va deveni `002100023241`, astfel încât autentificarea să fie corectă și fără erori.
   - **Interval de actualizare** (în secunde, implicit: 3600).

4. După configurare, senzorii vor fi disponibili în **Entități**.

---

### 🖼️ Crearea Cardurilor Lovelace

#### **Card pentru Index Curent**
Adaugă acest cod YAML pentru a afișa detaliile indexului curent:

---

#### 🚨 ATENȚIE:
  - Înlocuiește **sensor.eonromania_index_curent_XXXXXX ** cu **ID-ul exact** al senzorului din Home Assistant.
  - Adaugă acest YAML în tabloul tău Lovelace.
  - Salvează și verifică.

```yaml
type: entities
title: Index Curent
entities:
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Numărul dispozitivului
    name: Numărul dispozitivului
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Data de începere a următoarei citiri
    name: Data de începere a următoarei citiri
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Data de final a citirii
    name: Data de final a citirii
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Autorizat să citească contorul
    name: Autorizat să citească contorul
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Permite modificarea citirii
    name: Permite modificarea citirii
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Dispozitiv inteligent
    name: Dispozitiv inteligent
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Tipul citirii curente
    name: Tipul citirii curente
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Citire anterioară
    name: Citire anterioară
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Ultima citire validată
    name: Ultima citire validată
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Index propus pentru facturare
    name: Index propus pentru facturare
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Trimis la
    name: Trimis la
  - type: attribute
    entity: eonromania_index_curent_XXXXXX
    attribute: Poate fi modificat până la
    name: Poate fi modificat până la
```
