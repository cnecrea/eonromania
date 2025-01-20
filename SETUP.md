
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
