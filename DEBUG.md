# Ghid de debugging — E·ON România

Acest ghid explică cum activezi logarea detaliată, ce mesaje să cauți, și cum interpretezi fiecare situație.

---

## 1. Activează debug logging

Editează `configuration.yaml` și adaugă:

```yaml
logger:
  default: warning
  logs:
    custom_components.eonromania: debug
```

Restartează Home Assistant (**Setări** → **Sistem** → **Restart**).

Pentru a reduce zgomotul din loguri, poți adăuga:

```yaml
logger:
  default: warning
  logs:
    custom_components.eonromania: debug
    homeassistant.const: critical
    homeassistant.loader: critical
    homeassistant.helpers.frame: critical
```

**Important**: dezactivează debug logging după ce ai rezolvat problema (setează `custom_components.eonromania: info` sau șterge blocul). Logarea debug generează mult text și poate conține date personale.

---

## 2. Unde găsești logurile

### Din UI

**Setări** → **Sistem** → **Jurnale** → filtrează după `eonromania`

### Din fișier

```bash
# Calea implicită
cat config/home-assistant.log | grep -i eonromania

# Doar erorile
grep -E "(ERROR|WARNING).*eonromania" config/home-assistant.log

# Ultimele 100 linii
grep -i eonromania config/home-assistant.log | tail -100
```

### Din terminal (Docker/HAOS)

```bash
# Docker
docker logs homeassistant 2>&1 | grep -i eonromania

# Home Assistant OS (SSH add-on)
ha core logs | grep -i eonromania
```

---

## 3. Cum citești logurile API

Fiecare cerere API este etichetată cu un **label descriptiv** care include numele endpoint-ului și codul de încasare. Formatul este:

```
[label] METODA URL
[label] Răspuns OK (200). Dimensiune: XXX caractere.
```

### Exemplu de ciclu normal de actualizare (contract individual)

```
[LOGIN] Token obținut cu succes (expires_in=3600).
[contract_details (004412345678)] GET https://api2.eon.ro/partners/v2/account-contracts/004412345678?includeMeterReading=true
[contract_details (004412345678)] Răspuns OK (200). Dimensiune: 1523 caractere.
[invoice_balance (004412345678)] GET https://api2.eon.ro/invoices/v1/invoices/invoice-balance?accountContract=004412345678
[invoice_balance (004412345678)] Răspuns OK (200). Dimensiune: 245 caractere.
[meter_index (004412345678)] GET https://api2.eon.ro/meterreadings/v1/meter-reading/004412345678/index
[meter_index (004412345678)] Răspuns OK (200). Dimensiune: 892 caractere.
[payments (004412345678)] Pagină 1: 10 elemente, are_următoare=true.
[payments (004412345678)] Pagină 2: 3 elemente, are_următoare=false.
[payments (004412345678)] Total: 13 elemente din 2 pagini.
```

### Exemplu de ciclu normal de actualizare (contract DUO)

```
Contract colectiv/DUO detectat (contract=009900123456). Se interoghează subcontractele via list?collectiveContract.
[contracts_list] Date primite: type=list, len=2
DUO sub_codes (contract=009900123456): 2 coduri → ['002100234567', '002200345678'].
[contract_details (002100234567)] Răspuns OK (200). Dimensiune: 1823 caractere.
[contract_details (002200345678)] Răspuns OK (200). Dimensiune: 1456 caractere.
[consumption_convention (002100234567)] Răspuns OK (200). Dimensiune: 534 caractere.
[consumption_convention (002200345678)] Răspuns OK (200). Dimensiune: 478 caractere.
[meter_index (002100234567)] Răspuns OK (200). Dimensiune: 892 caractere.
[meter_index (002200345678)] Răspuns OK (200). Dimensiune: 756 caractere.
DUO contract_details individuale (contract=009900123456): 2/2 reușite. Convenții: 2/2 reușite. Meter index: 2/2 reușite.
```

### Etichete disponibile

| Etichetă | Endpoint | Senzor asociat |
|----------|----------|----------------|
| `LOGIN` | mobile-login | — (autentificare) |
| `REFRESH` | mobile-refresh-token | — (reîmprospătare token) |
| `contracts_list` | account-contracts/list | — (config flow + DUO discovery) |
| `contract_details` | account-contracts/{cod} | Date contract |
| `invoices_unpaid` | invoices/list | Factură restantă |
| `invoices_prosum` | invoices/list-prosum | Factură restantă prosumator |
| `invoice_balance` | invoices/invoice-balance | Sold factură |
| `invoice_balance_prosum` | invoices/invoice-balance-prosum | Sold prosumator |
| `rescheduling_plans` | rescheduling-plans | Planuri eșalonare |
| `graphic_consumption` | invoices/graphic-consumption/{cod} | Arhivă consum |
| `meter_index` | meter-reading/{cod}/index | Index + Citire permisă |
| `meter_history` | meter-reading/{cod}/history | Arhivă index |
| `consumption_convention` | consumption-convention/{cod} | Convenție consum |
| `payments` | payments/payment-list | Arhivă plăți |
| `submit_meter` | meter-reading/index (POST) | Buton Trimite index |

**Notă DUO**: Pentru contracte colective, `contract_details`, `consumption_convention` și `meter_index` sunt apelate per subcontract. În loguri vei vedea codul subcontractului (ex: `002100234567`), nu codul colectiv.

---

## 4. Mesajele de la pornire

La prima pornire a integrării (sau după restart), ar trebui să vezi:

### Contract individual:
```
INFO  Se configurează integrarea eonromania (entry_id=01ABC...).
DEBUG Contracte selectate: ['004412345678'], interval=3600s.
DEBUG [LOGIN] Token obținut cu succes (expires_in=3600).
DEBUG Începe actualizarea datelor E·ON (contract=004412345678, colectiv=False).
DEBUG Actualizare E·ON finalizată (contract=004412345678, colectiv=False). Endpointuri fără date: 0/11.
INFO  1 coordinatoare active din 1 contracte selectate (entry_id=01ABC...).
```

### Contract DUO:
```
INFO  Se configurează integrarea eonromania (entry_id=01ABC...).
DEBUG Contracte selectate: ['009900123456'], interval=3600s.
DEBUG [LOGIN] Token obținut cu succes (expires_in=3600).
DEBUG Începe actualizarea datelor E·ON (contract=009900123456, colectiv=True).
DEBUG Contract colectiv/DUO detectat (contract=009900123456). Se interoghează subcontractele via list?collectiveContract.
DEBUG DUO sub_codes (contract=009900123456): 2 coduri → ['002100234567', '002200345678'].
DEBUG DUO contract_details individuale (contract=009900123456): 2/2 reușite. Convenții: 2/2 reușite. Meter index: 2/2 reușite.
DEBUG Actualizare E·ON finalizată (contract=009900123456, colectiv=True). Endpointuri fără date: 1/11.
```

---

## 5. Situații normale (nu sunt erori)

### Licență — heartbeat

```
[LICENSE] Heartbeat OK. Licența este validă (expiră: 2027-01-15).
```

**Cauza**: verificarea periodică a licenței cu serverul a reușit. Comportament normal.

### Token reînnoit automat

```
[invoice_balance (004412345678)] Eroare: GET ... → Cod HTTP=401
[invoice_balance (004412345678)] Cod HTTP=401 → se reîncearcă cu refresh token.
[REFRESH] Token reîmprospătat cu succes (expires_in=3600).
[invoice_balance (004412345678)] Răspuns OK (200). Dimensiune: 245 caractere.
```

**Cauza**: token-ul API a expirat. Integrarea re-autentifică automat și reîncearcă request-ul. Comportament normal.

### Endpoint-uri prosumator fără date

Dacă nu ești prosumator, e normal ca `invoices_prosum` și `invoice_balance_prosum` să returneze `None` sau liste goale. Asta nu e o eroare — pur și simplu API-ul nu are date pentru acel contract.

### Login concurent

```
[LOGIN] Token deja disponibil (obținut de alt apel concurent).
```

**Cauza**: mai multe apeluri paralele au încercat să se autentifice simultan. Lock-ul intern a permis doar unul — restul au reutilizat token-ul obținut. Comportament normal.

### DUO — endpoint-uri fără date pe subcontracte

```
DUO contract_details individuale (contract=009900123456): 2/2 reușite. Convenții: 1/2 reușite. Meter index: 1/2 reușite.
```

**Cauza**: un subcontract (de obicei electricitate) poate să nu aibă convenție de consum sau date de contor disponibile. Asta depinde de contractul real — nu e neapărat o eroare.

---

## 6. Situații de eroare

### Autentificare eșuată

```
[LOGIN] Eroare autentificare. Cod HTTP=401, Răspuns=...
```

**Cauza**: email sau parolă incorectă, sau cont blocat.

**Rezolvare**:
1. Verifică credențialele pe aplicația E·ON Myline
2. Dacă contul e blocat, așteaptă și reîncearcă
3. Reconfigurează integrarea cu credențiale corecte

### Eroare de rețea / timeout

```
[contract_details (004412345678)] Depășire de timp: GET https://api2.eon.ro/...
```

**Cauza**: API-ul E·ON nu răspunde sau conexiunea HA la internet e întreruptă.

**Rezolvare**:
1. Verifică conexiunea la internet din HA
2. Integrarea reîncearcă automat la următorul ciclu — de obicei se rezolvă singur
3. Dacă persistă, mărește intervalul de actualizare

### Prima actualizare eșuată

```
ERROR Prima actualizare eșuată (entry_id=..., contract=004412345678): Nu s-a putut autentifica la API-ul E·ON.
```

**Cauza**: credențiale greșite sau API indisponibil la momentul pornirii.

**Rezolvare**: verifică logurile anterioare (mesaje `[LOGIN]`) pentru cauza exactă. Restartează HA după rezolvare.

### Endpointuri fără date

```
DEBUG Actualizare E·ON finalizată (contract=004412345678, colectiv=False). Endpointuri fără date: 3/11.
```

**Interpretare**:
- **0/11** — totul funcționează perfect
- **1-2/11** — normal dacă nu ești prosumator sau nu ai planuri de eșalonare
- **3+/11** — posibilă problemă cu API-ul E·ON sau cu credențialele; verifică erorile precedente

### DUO — subcontracte nedescoperite

```
DUO list (collective) a returnat None sau structură invalidă (contract=009900123456): NoneType.
```

**Cauza**: endpoint-ul `account-contracts/list?collectiveContract=...` nu a returnat date.

**Rezolvare**: verifică dacă codul colectiv este corect, dacă contul are efectiv subcontracte, sau dacă API-ul E·ON este disponibil.

### Licență invalidă

```
[LICENSE] Licența nu este validă. Motiv: expired / invalid_key / server_unreachable.
[LICENSE] Se creează doar senzorul LicentaNecesaraSensor.
```

**Cauza**: licența a expirat, cheia este greșită, sau serverul de licențe nu este accesibil.

**Rezolvare**:
1. Verifică cheia de licență în OptionsFlow (Setări → Dispozitive și Servicii → E·ON România → Configurare → Licență)
2. Dacă a expirat, reînnoiește de la [hubinteligent.org/donate?ref=eonromania](https://hubinteligent.org/donate?ref=eonromania)
3. Dacă serverul nu e accesibil, există un grace period — licența rămâne validă temporar
4. Verifică că cheia este copiată corect, fără spații suplimentare

### Eroare la trimitere index

```
[submit_meter (004412345678)] Token invalid. Trimiterea nu poate fi efectuată.
```

sau

```
ERROR Nu există entitatea input_number.gas_meter_reading. Nu se poate trimite indexul (contract=004412345678, tip=Trimite index gaz).
```

sau (pentru electricitate):

```
ERROR Nu există entitatea input_number.energy_meter_reading. Nu se poate trimite indexul (contract=002200345678, tip=Trimite index energie electrică).
```

**Cauze posibile**:
1. `input_number.gas_meter_reading` sau `input_number.energy_meter_reading` nu există — trebuie create manual (vezi [SETUP.md](SETUP.md))
2. `input_number` are valoare invalidă
3. Nu ești în perioada de citire (datele de contor lipsesc)
4. Token-ul e invalid și re-autentificarea a eșuat

---

## 7. Logare date API

La nivel debug, integrarea loghează dimensiunea răspunsurilor (nu conținutul complet):

```
[contract_details (004412345678)] Răspuns OK (200). Dimensiune: 1523 caractere.
```

Pentru login și refresh, răspunsul complet este logat (include token-ul):

```
[LOGIN] Răspuns: Status=200, Body={"access_token":"...","expires_in":3600,...}
```

**Atenție**: aceste loguri conțin date personale (token-uri, coduri de contract). **Nu le posta public fără a le anonimiza.**

---

## 8. Cum raportezi un bug

1. Activează debug logging (secțiunea 1)
2. Reproduce problema
3. Deschide un [issue pe GitHub](https://github.com/cnecrea/eonromania/issues) cu:
   - **Descrierea problemei** — ce ai așteptat vs. ce s-a întâmplat
   - **Logurile relevante** — filtrează după `eonromania` și include 20–50 linii relevante
   - **Versiunea HA** — din **Setări** → **Despre**
   - **Versiunea integrării** — din `manifest.json` sau HACS
   - **Tipul contractului** — individual sau DUO/colectiv

### Cum postezi loguri pe GitHub

Folosește blocuri de cod delimitate de 3 backticks:

````
```
2026-03-04 10:15:12 DEBUG custom_components.eonromania [contract_details (004412345678)] GET https://api2.eon.ro/...
2026-03-04 10:15:13 DEBUG custom_components.eonromania [contract_details (004412345678)] Răspuns OK (200). Dimensiune: 1523 caractere.
2026-03-04 10:15:14 ERROR custom_components.eonromania [LOGIN] Eroare autentificare. Cod HTTP=401
```
````

Dacă logul e foarte lung (peste 50 linii), folosește secțiunea colapsabilă:

````
<details>
<summary>Log complet (click pentru a expanda)</summary>

```
... logul aici ...
```

</details>
````

> **Nu posta parola, token-ul sau date personale în loguri.** Integrarea loghează token-urile în mesajele de login/refresh — anonimizează-le înainte de a le posta.
