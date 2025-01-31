<!-- Adaugă o ancoră la începutul paginii -->
<a name="top"></a>
# Întrebări frecvente

- [Cum să adaug integrarea în Home Assistant?](#cum-să-adaug-integrarea-în-home-assistant)
- [Am cont DUO, pot folosi integrarea?](#am-cont-duo-pot-folosi-integrarea)
- [Ce înseamnă index curent?](#ce-înseamnă-index-curent)
- [Nu îmi apare indexul curent. De ce?](#nu-îmi-apare-indexul-curent-de-ce)
- [Nu îmi apare senzorul citire permisă. De ce?](#nu-îmi-apare-senzorul-citire-permisă-de-ce)
- [Vreau să trimit indexul de la gaz de forma automată. De ce am nevoie?](#vreau-să-trimit-indexul-de-la-gaz-de-forma-automată-de-ce-am-nevoie)
- [Am instalat un cititor de contor gaz. Cum fac automatizarea?](#am-instalat-un-cititor-de-contor-gaz-cum-fac-automatizarea)
- [Îmi place acest proiect. Cum pot să-l susțin?](#îmi-place-acest-proiect-cum-pot-să-l-susțin)
---

## Cum să adaug integrarea în Home Assistant?

Pentru a reveni la începutul paginii, [apăsați aici](#top).


**Răspuns:**  
HACS (Home Assistant Community Store) permite instalarea și gestionarea integrărilor, temelor și modulelor personalizate create de comunitate. Urmează pașii de mai jos pentru a adăuga un repository extern în HACS și pentru a instala o integrare:

  - **1.	Asigură-te că HACS este instalat**
      - Verifică dacă HACS este deja instalat în Home Assistant.
      - Navighează la **Setări** > **Dispozitive și servicii** > **Integrări** și caută "HACS".
      - Dacă nu este instalat, urmează ghidul oficial de instalare pentru HACS: [HACS Installation Guide](https://hacs.xyz/docs/use).
   
  - **2. Găsește repository-ul extern**
      - Accesează pagina GitHub a integrării pe care vrei să o adaugi. De exemplu, repository-ul ar putea arăta astfel:  
  `https://github.com/autorul-integarii/nume-integrare`.

  - **3. Adaugă repository-ul în HACS**
      - În Home Assistant, mergi la **HACS** din bara laterală.
      - Apasă pe butonul cu **cele trei puncte** din colțul din dreapta sus și selectează **Repositories**.
      - În secțiunea "Custom repositories", introdu URL-ul repository-ului extern (de exemplu, `https://github.com/autorul-integarii/nume-integrare`).
      - Selectează tipul de repository:
        - **Integration** pentru integrări.
        - **Plugin** pentru module front-end.
        - **Theme** pentru teme.
      - Apasă pe **Add** pentru a adăuga repository-ul.

  - **4. Instalează integrarea**
      - După ce repository-ul a fost adăugat, mergi la **HACS** > **Integrations**.
      - Caută numele integrării pe care tocmai ai adăugat-o.
      - Apasă pe integrare și selectează **Download** sau **Install**.
      - După instalare, Home Assistant îți poate solicita să repornești sistemul. Urmează instrucțiunile pentru a finaliza configurarea.

  - **5. Configurează integrarea**
      - După repornire, mergi la **Setări** > **Dispozitive și servicii** > **Adaugă integrare**.
      - Caută numele integrării instalate și urmează pașii de configurare specifici.

> **Notă:** 
> Asigură-te că Home Assistant și HACS sunt actualizate la cea mai recentă versiune pentru a evita erorile de compatibilitate.

---

## Am cont DUO, pot folosi integrarea?

Pentru a reveni la începutul paginii, [apăsați aici](#top).


**Răspuns:**  
Da, integrarea poate fi utilizată cu un cont DUO, însă trebuie să reții că **codul de încasare** este diferit față de cel afișat pe factură. Pentru a obține codurile de încasare corecte pentru fiecare serviciu (de exemplu, ENERGIE ELECTRICĂ, GAZ), urmează pașii de mai jos:

1. **Autentifică-te** în contul tău EON.
2. Accesează secțiunea **Contul meu**.
3. Navighează la opțiunea **Transmitere index**.
4. Selectează contul tău DUO (clic pe numele contului) pentru a deschide opțiunile asociate.
5. În această secțiune, vei observa **serviciile asociate contului DUO** (de exemplu, ENERGIE ELECTRICĂ, GAZ). Fiecare serviciu are:
   - Un **cod de încasare** unic, care începe cu `2XXXX`.  
   - Acest cod este cel corect pentru integrare.

> **Notă:** Nu folosi codul DUO care începe cu `9XXXX`, deoarece acesta nu este valid pentru integrarea serviciilor.

---

## Ce înseamnă index curent?

Pentru a reveni la începutul paginii, [apăsați aici](#top).


**Răspuns:**  
Indexul curent se referă la indexul actual înregistrat pentru consumul tău, fie că este vorba de gaze naturale sau de energie electrică. Este un termen generic utilizat pentru a desemna ultima valoare citită sau transmisă a consumului.

---

## Nu îmi apare indexul curent. De ce?

Pentru a reveni la începutul paginii, [apăsați aici](#top).


**Răspuns:**  
Indexul curent apare doar atunci când se apropie perioada de citire programată. Dacă perioada de citire nu este încă activă, datele asociate indexului curent nu sunt propagate de EON, iar acestea nu vor apărea în formatul JSON.

### Exemple:
- **Date în JSON când perioada de citire NU s-a apropiat:**

```json
{
    "readingPeriod": {
        "startDate": "2025-01-20",
        "endDate": "2025-01-28",
        "startDateDistributor": null,
        "endDateDistributor": null,
        "allowedReading": true,
        "allowChange": true,
        "hasReadingCommand": false,
        "smartDevice": false,
        "distributorType": null,
        "invoiceRequested": null,
        "accountContract": "00XXXXXXXXXX",
        "annualConvention": null,
        "currentReadingType": "02",
        "hasDifferentDeviceInstalled": null,
        "billingPortion": null,
        "disconnectionStatus": null,
        "inPeriod": false
    },
    "indexDetails": {
        "devices": []
    }
}
```
- **Date în JSON când perioada de citire s-a apropiat:**
```json
{
    "readingPeriod": {
        "startDate": "2025-01-08",
        "endDate": "2025-01-14",
        "startDateDistributor": "2025-01-08",
        "endDateDistributor": "2025-01-14",
        "allowedReading": true,
        "allowChange": false,
        "hasReadingCommand": true,
        "smartDevice": false,
        "distributorType": "I",
        "invoiceRequested": null,
        "accountContract": "00XXXXXXXXXX",
        "annualConvention": null,
        "currentReadingType": "01",
        "hasDifferentDeviceInstalled": false,
        "billingPortion": "MMS12",
        "disconnectionStatus": null,
        "inPeriod": true
    },
    "indexDetails": {
        "devices": [
            {
                "deviceNumber": "00XXXXXXXXXXXXXXX",
                "deviceType": null,
                "invalidDevice": false,
                "indexes": [
                    {
                        "oldValue": 828,
                        "oldDate": "2024-12-09",
                        "oldReadingType": "02",
                        "minValue": 828,
                        "maxValue": 1783,
                        "ablbelnr": "0000000000XXXXXXXXXXX",
                        "currentValue": 949,
                        "type": "TG",
                        "code": "ME",
                        "digits": 6,
                        "decimals": 0,
                        "channel": "WEBSITE",
                        "sentAt": "2025-01-10 23:08:46",
                        "canBeChangedTill": "2025-01-10 23:59:59",
                        "readingType": "03",
                        "readingDate": null,
                        "oldSelfIndexValue": 949,
                        "oldSelfIndexDate": "2025-01-10 23:08:46"
                    }
                ],
                "newDevice": null
            }
        ]
    }
}
```

Înțelegând aceste aspecte, putem concluziona că integrarea nu prezintă o problemă, ci pur și simplu nu are de unde să extragă date pentru acest senzor. Prin urmare, atât timp cât EON nu publică aceste date în format JSON, este logic ca senzorul să nu poată prelua informații pentru a le afișa.

---

## Nu îmi apare senzorul citire permisă. De ce?

Pentru a reveni la începutul paginii, [apăsați aici](#top).


**Răspuns:**  
Acest lucru se întâmplă din același motiv pentru care „[Index curent](#nu-îmi-apare-indexul-curent-de-ce)” nu apare. Te rugăm să consulți explicațiile de mai sus pentru mai multe detalii despre această situație.


---

## Vreau să trimit indexul de la gaz de forma automată. De ce am nevoie?

Pentru a reveni la începutul paginii, [apăsați aici](#top).


**Răspuns:**  
Pentru a trimite indexul de la gaz automat, este important să înțelegem situația și cerințele. Sunt necesare două lucruri principale:

  - **1.	Partea hardware pregătită și instalată pe contor, pentru preluarea datelor.**
      - Este necesar un cititor de contor inteligent (smart meter) sau un senzor capabil să citească impulsurile generate de contor. Acest senzor trebuie să îndeplinească două condiții esențiale:
        - **Capacitatea de a citi corect impulsurile**: Senzorul trebuie să fie compatibil cu contorul și să interpreteze semnalele corect, fie că este vorba de un contact reed (magnetic), fie de alte metode.
        - **Integrarea non-invazivă cu contorul**: Soluția hardware trebuie să fie instalată fără să afecteze funcționarea contorului sau să necesite modificări permanente ale acestuia.

După ce partea hardware este pregătită, putem trece la următorul pas.

  - **2. Dacă analizăm integrarea, observăm că în fișierul button.py există următorul cod:**

```python
    async def async_press(self):
        """Execută trimiterea indexului."""
        cod_incasare = self.config_entry.data.get("cod_incasare", "necunoscut")
        try:
            # Obține indexValue din input_number
            gas_meter_state = self.coordinator.hass.states.get("input_number.gas_meter_reading")
            if not gas_meter_state:
                _LOGGER.error("Entitatea input_number.gas_meter_reading nu este definită.")
                return

```
Acest cod indică faptul că butonul „Trimite index” din integrare utilizează un input_number pentru a transmite indexul.

**Interpretare**:
  - Partea hardware instalată pe contorul de gaz “**transferă**” impulsurile către entitatea **input_number.gas_meter_reading**.
  - De fiecare dată când există consum, impulsurile sunt convertite într-o valoare numerică și adunate în entitatea input_number.

Astfel, hardware-ul contorului de gaz este responsabil pentru detectarea consumului și actualizarea valorii input_number, iar codul din integrare permite trimiterea automată a acestor date.

---
# Am instalat un cititor de contor gaz. Cum fac automatizarea?

Pentru a reveni la începutul paginii, [apăsați aici](#top).


**Răspuns:**  
Dacă ai un cititor de gaz care incrementează consumul în entitatea **input_number.gas_meter_reading**, poți folosi următorul exemplu de automatizare.

**Principii utilizate în exemplul de automatizare:**

1. **Declanșatorul automatizării:**
   - Automatizarea rulează în **ziua 9 a fiecărei luni.**
  
2. **Acțiuni definite:**
   - **Ora 9:00 dimineața**: Trimiterea unui mesaj SMS pe telefon (sau o notificare utilizând serviciul notify.notify).
   - **Ora 12:00**: Activarea butonului “**Trimite index**” prin intermediul integrării existente.

**Exemplu de automatizare în YAML:**
```yaml
alias: "AUTOMATIZARE --- GAZ: Transmitere index"
description: >-
  Trimite notificări la ora 09:00 și apasă butonul pentru trimiterea indexului
  la ora 12:00.
triggers:
  - at: "09:00:00"
    trigger: time
  - at: "12:00:00"
    trigger: time
conditions:
  - condition: template
    value_template: "{{ now().day == 9 }}"
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ trigger.now.hour == 9 }}"
        sequence:
          - metadata: {}
            data:
              target: 4XXXXXXXXXX
              message: >-
                E·ON GAZ (mesaj automat): Pentru luna {{
                states('sensor.current_month_translated') }}, noul index este de
                {{ (states('input_number.gas_meter_reading') | float | round(0))
                }} {{ state_attr('sensor.index_curent', 'unit_of_measurement')
                }}
            alias: SMS pe telefon
            action: notify.smsto
        alias: "Optiunea 1: Trimite SMS la ora 09:00"
      - conditions:
          - condition: template
            value_template: "{{ trigger.now.hour == 12 }}"
        sequence:
          - metadata: {}
            data: {}
            target:
              entity_id: button.eonromania_trimite_index_XXXXXXXXXXXX
            action: button.press
        alias: "Optiunea 2: Trimite index la EON la ora 12:00"
```
**Detalii explicative:**
1. **Declanșatoare:**
   - Automatizarea este declanșată la ora **09:00** și **12:00**.
2. **Condiția:**
   - Automatizarea se rulează doar dacă este **ziua 9 a lunii curente**.
3. **Acțiuni:**
   - **Ora 9:00**: Se trimite o notificare prin serviciul notify.notify, afișând indexul curent din **input_number.gas_meter_reading**.
   - **Ora 12:00**: Se apasă butonul **eonromania_trimite_index_XXXXXXXXXXXX** pentru a trimite indexul.
> **Notă:**
> 
> Înlocuiește **eonromania_trimite_index_XXXXXXXXXXXX** cu ID-ul exact al butonului utilizat în integrarea ta.
>
> Dacă dorești să schimbi serviciul de notificare, ajustează notify.notify pentru a corespunde setărilor tale.


---

# Îmi place acest proiect. Cum pot să-l susțin?

Pentru a reveni la începutul paginii, [apăsați aici](#top).

**Răspuns:**  
  - **Oferă un star pe GitHub** – Apasă butonul **“Star”** de pe pagina repository-ului pentru a arăta aprecierea ta.
  - **Contribuie cu cod** – Dacă ai idei sau îmbunătățiri, poți crea un pull request cu modificările propuse.
  - **Raportează probleme** – Dacă întâmpini bug-uri sau ai sugestii, deschide un issue pe GitHub.
  - **Donează** – Dacă dorești să sprijini proiectul financiar, poți face o donație prin intermediul [Buy Me a Coffee](https://buymeacoffee.com/cnecrea). Orice contribuție este apreciată și ajută la dezvoltarea proiectului!
  - **Distribuie proiectul** – Recomandă-l prietenilor sau comunității tale pentru a crește vizibilitatea.


