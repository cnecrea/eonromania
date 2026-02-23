# Debugging pentru integrarea E·ON România

Când ceva nu merge cum trebuie, logurile sunt primul loc unde cauți răspunsuri. Aici găsești cum activezi logarea detaliată, cum citești logurile și cum raportezi o problemă.

---

## 1. Activează logarea detaliată

Editează fișierul `configuration.yaml` și adaugă (sau modifică) secțiunea `logger`:

```yaml
logger:
  default: warning
  logs:
    custom_components.eonromania: debug
    homeassistant.const: critical
    homeassistant.loader: critical
    homeassistant.helpers.frame: critical
```

Salvează fișierul și **repornește Home Assistant** pentru ca modificările să aibă efect.

> **Ce face asta?** Setează nivelul de logare al integrării pe `debug`, ceea ce înseamnă că vei vedea toate mesajele — inclusiv detalii despre autentificare, apelurile API, datele primite și erorile. Restul componentelor rămân pe `warning` ca să nu te îneci în loguri irelevante.

---

## 2. Unde găsesc logurile

Logurile se scriu în fișierul `home-assistant.log`, care se află în directorul principal al Home Assistant (acolo unde e și `configuration.yaml`).

Poți accesa logurile și din interfața web: **Setări** → **Sistem** → **Jurnale**.

### Filtrare din terminal

Dacă ai acces SSH sau la terminalul containerului:

```bash
grep 'custom_components.eonromania' home-assistant.log
```

Pentru a urmări logurile în timp real:

```bash
tail -f home-assistant.log | grep 'eonromania'
```

---

## 3. Ce să cauți în loguri

### Autentificare
Dacă autentificarea reușește, vei vedea:
```
DEBUG Token obținut cu succes (autentificare reușită).
```

Dacă eșuează, cauți mesaje cu `Eroare la autentificare` sau `Cod HTTP=`:
```
ERROR Eroare la autentificare. Cod HTTP=401, Răspuns=...
```

**Notă:** Integrarea reutilizează token-ul între ciclurile de actualizare. Login-ul se face doar la pornire și când token-ul expiră (eroare 401). Dacă vezi `Token deja disponibil (obținut de alt apel concurent)`, înseamnă că un alt apel paralel a obținut deja token-ul — e un comportament normal.

### Actualizare date
La fiecare ciclu de actualizare, coordinatorul loghează:
```
DEBUG Începe actualizarea datelor E·ON (contract=00XXXXXXXXXX).
DEBUG Actualizare E·ON finalizată (contract=00XXXXXXXXXX). Endpointuri fără date: 0/9.
```

Dacă `Endpointuri fără date` arată un număr mare (ex: 7/9), înseamnă că mai multe apeluri API au eșuat. Caută mesajele de eroare anterioare pentru detalii.

**Numărul de endpointuri fără date:**
- **0/9** — totul funcționează perfect
- **1-2/9** — normal dacă nu ești prosumator (endpoint-urile `facturasold_prosum` și `facturasold_prosum_balance` returnează `None`)
- **3+/9** — posibilă problemă cu API-ul E·ON sau cu credențialele; verifică erorile precedente

### Senzori de prosumator
Dacă nu ești prosumator, e normal ca endpoint-urile `facturasold_prosum` și `facturasold_prosum_balance` să returneze `None`. Asta nu e o eroare — pur și simplu API-ul nu are date pentru acel contract.

### Trimitere index
Când apeși butonul „Trimite index gaz" (`button.eonromania_00XXXXXXXXXX_trimite_index_gaz`):
```
DEBUG Se trimite indexul: valoare=XXX (contract=00XXXXXXXXXX, ablbelnr=...).
DEBUG Index trimis cu succes pentru contractul 00XXXXXXXXXX.
```

Dacă apare o eroare, mesajul va include codul HTTP și răspunsul serverului.

**Erori frecvente la trimiterea indexului:**
- `Nu există entitatea input_number.gas_meter_reading` — trebuie să creezi manual această entitate.
- `Nu există datele de citire index (citireindex)` — nu ești în perioada de citire sau datele nu au fost încă obținute.
- `Nu a fost găsit ID-ul intern al contorului (ablbelnr/SAP)` — API-ul nu a returnat identificatorul intern al contorului.

### Unitatea de măsură
Integrarea detectează automat unitatea de măsură din răspunsul API:
```
DEBUG Unitate de măsură detectată: 'm3' (contract=00XXXXXXXXXX).
```

- `m3` = gaz (metri cubi) — senzorii vor avea sufixul `_gaz`
- `kwh` = energie electrică (kilowatt-oră) — senzorii vor avea sufixul `_energie_electrica`
- Dacă câmpul lipsește, se folosește implicit `m3`.

### Modificare opțiuni
Când modifici opțiunile integrării, vei vedea:
```
INFO Opțiunile integrării eonromania s-au schimbat (entry_id=...). Se reîncarcă...
```

Integrarea se reîncarcă automat — nu este necesar un restart manual.

---

## 4. Probleme frecvente

### „Prima actualizare a datelor E·ON a eșuat"
Apare la pornirea integrării când API-ul E·ON nu răspunde sau credențialele sunt greșite. Verifică: (a) username/parolă corecte, (b) codul de încasare corect (12 cifre), (c) API-ul E·ON funcționează (testează un login pe site-ul lor).

### „Depășire de timp la conectarea cu API-ul E·ON"
API-ul E·ON nu a răspuns în 30 de secunde. Poate fi o problemă temporară a serverului lor. Integrarea va reîncerca la următorul ciclu de actualizare.

### Senzorul „Index gaz" / „Index energie electrică" arată 0
E normal dacă nu ești în perioada de citire. Consultă [FAQ — Nu îmi apare indexul curent](./FAQ.md#nu-îmi-apare-indexul-curent-de-ce).

### Senzori noi nu apar după ce a început perioada de citire
Senzorii sunt creați la pornirea integrării. Dacă integrarea s-a pornit în afara perioadei de citire, senzorii de index și citire permisă există dar pot afișa date goale. Datele se vor actualiza automat în următorul ciclu de refresh. Dacă nu se actualizează, fă un reload al integrării din **Setări** → **Dispozitive și Servicii** → **E·ON România** → cele trei puncte → **Reîncarcă**.

### „Autentificare eșuată la modificarea opțiunilor"
Apare în OptionsFlow dacă ai modificat credențialele (username, parolă sau cod de încasare) și noile date sunt incorecte. Configurația existentă rămâne neschimbată — corectează datele și încearcă din nou.

---

## 5. Cum raportezi o problemă

Dacă ai identificat un bug, deschide un [issue pe GitHub](https://github.com/cnecrea/eonromania/issues) și include:

1. **Versiunea integrării** (o găsești în `manifest.json` sau în HACS).
2. **Versiunea Home Assistant** (Setări → Despre).
3. **Logurile relevante** — filtrează pe `eonromania` și copiază doar liniile relevante.
4. **Pașii de reproducere** — ce ai făcut ca să apară problema.

### Cum postezi cod în discuții

Folosește blocuri de cod delimitate de trei backticks, urmate de limbaj:

<pre>
```yaml
2025-02-21 15:35:12 INFO     custom_components.eonromania: Se configurează integrarea eonromania.
2025-02-21 15:35:13 DEBUG    custom_components.eonromania: Parametri intrare: contract=00XXXXXXXXXX, interval=3600s.
2025-02-21 15:35:14 ERROR    custom_components.eonromania.api: Eroare la autentificare. Cod HTTP=401.
```
</pre>

Rezultatul va arăta astfel:

```yaml
2025-02-21 15:35:12 INFO     custom_components.eonromania: Se configurează integrarea eonromania.
2025-02-21 15:35:13 DEBUG    custom_components.eonromania: Parametri intrare: contract=00XXXXXXXXXX, interval=3600s.
2025-02-21 15:35:14 ERROR    custom_components.eonromania.api: Eroare la autentificare. Cod HTTP=401.
```

> **Nu posta parola, token-ul sau date personale în loguri.** Integrarea nu loghează parola, dar verifică întotdeauna înainte de a posta.
