# Întrebări frecvente

- [Am cont DUO, pot folosi integrarea?](#am-cont-duo-pot-folosi-integrarea)
- [Ce înseamnă index curent?](#ce-înseamnă-index-curent)
- [Nu îmi apare indexul curent. De ce?](#nu-îmi-apare-indexul-curent-de-ce)
- [Nu îmi apare senzorul citire permisă. De ce?](#nu-îmi-apare-senzorul-citire-permisa-de-ce)

---

## Am cont DUO, pot folosi integrarea?

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

**Răspuns:**  
Indexul curent se referă la indexul actual înregistrat pentru consumul tău, fie că este vorba de gaze naturale sau de energie electrică. Este un termen generic utilizat pentru a desemna ultima valoare citită sau transmisă a consumului.

---

## Nu îmi apare indexul curent. De ce?

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

**Răspuns:**  
Acest lucru se întâmplă din același motiv pentru care „Index curent” nu apare. Te rugăm să consulți explicațiile de mai sus pentru mai multe detalii despre această situație.
