# FIX MINUTI → ORE - Guida Tecnica

## 🎯 PROBLEMA

Il database Excel ha valori nel campo `valore` espressi in **MINUTI**, ma venivano visualizzati come se fossero **ORE**.

### Esempio del Problema

**Database:**
```
Straordinario
| matricola | data       | turno | valore |
|-----------|------------|-------|--------|
| M001      | 2026-01-15 | A     | 120    |  ← 120 MINUTI
| M002      | 2026-01-15 | B     | 180    |  ← 180 MINUTI
```

**Visualizzato PRIMA (SBAGLIATO):**
```
Report Straordinari
Totale Ore: 300h  ← SBAGLIATO! (120+180)
```

**Visualizzato ADESSO (CORRETTO):**
```
Report Straordinari
Totale Ore: 5.00h  ← CORRETTO! (300min / 60 = 5h)
```

---

## ✅ SOLUZIONE IMPLEMENTATA

### Funzioni Helper

```python
def minuti_to_ore(minuti):
    """Converte minuti in ore con 2 decimali"""
    if pd.isna(minuti):
        return 0.0
    try:
        return round(float(minuti) / 60.0, 2)
    except:
        return 0.0

def format_ore(ore):
    """Formatta ore per display"""
    return f"{ore:.2f}h"
```

### Dove Applicato

#### 1. Report Straordinari

**PRIMA:**
```python
tot_ore = filtered['valore'].astype(float).sum()  # ❌ Somma minuti!
```

**ADESSO:**
```python
# ⭐ Converti minuti → ore
filtered['ore'] = filtered['valore'].apply(minuti_to_ore)

# Usa colonna 'ore' per calcoli
tot_ore = filtered['ore'].sum()  # ✅ Somma ore!
```

#### 2. Aggregazione per Persona

**PRIMA:**
```python
agg = filtered.groupby('matricola').agg({
    'valore': 'sum'  # ❌ Somma minuti!
})
```

**ADESSO:**
```python
agg = filtered.groupby('matricola').agg({
    'ore': 'sum'  # ✅ Somma ore!
})
```

#### 3. Dettaglio Giornaliero

**PRIMA:**
```python
detail['Ore'] = detail['valore'].astype(float)  # ❌ Minuti!
```

**ADESSO:**
```python
detail['Ore'] = detail['ore'].apply(format_ore)  # ✅ Ore formattate!
```

#### 4. Verifica Match

**PRIMA:**
```python
'ore_str': s['valore'],  # ❌ Minuti!
'ore_gt': match.iloc[0]['valore']  # ❌ Minuti!
```

**ADESSO:**
```python
# Prima converti
straordinari['ore'] = straordinari['valore'].apply(minuti_to_ore)
attivita['ore'] = attivita['valore'].apply(minuti_to_ore)

# Poi usa 'ore'
'ore_str': s['ore'],  # ✅ Ore!
'ore_gt': match.iloc[0]['ore']  # ✅ Ore!
```

---

## 📊 ESEMPI PRATICI

### Esempio 1: Record Singolo

**Database:**
```
valore: 150 minuti
```

**Conversione:**
```python
ore = minuti_to_ore(150)
# 150 / 60 = 2.50

formatted = format_ore(2.50)
# "2.50h"
```

**Display:** `2.50h` ✅

### Esempio 2: Totale Giornata

**Database:**
```
Record 1: 120 minuti (2h)
Record 2: 90 minuti (1.5h)
Record 3: 180 minuti (3h)
Totale: 390 minuti
```

**Conversione:**
```python
tot_minuti = 390
tot_ore = tot_minuti / 60
# 390 / 60 = 6.50

formatted = format_ore(6.50)
# "6.50h"
```

**Display:** `6.50h` ✅

### Esempio 3: Media

**Database:**
```
Totale: 450 minuti = 7.50 ore
Giorni: 3
```

**Calcolo:**
```python
tot_ore = 450 / 60  # 7.50
giorni = 3
media = tot_ore / giorni
# 7.50 / 3 = 2.50 ore/giorno

formatted = format_ore(2.50)
# "2.50h"
```

**Display:** `2.50h/gg` ✅

---

## ⚠️ IMPORTANTE

### Database NON Modificato

Il database Excel **mantiene valori in MINUTI**:

```
✅ Database Excel: 120 minuti (invariato)
✅ App Streamlit: conversione → 2.00h (solo display)
```

**Perché?**
1. Compatibilità con sistemi esistenti
2. Import/Export preserva formato originale
3. Conversione solo in visualizzazione

### Editor Dati

Quando modifichi nel Editor Dati:

```
⚠️ ATTENZIONE: Inserisci valore in MINUTI!

Per inserire 2 ore:
❌ NON scrivere: 2
✅ Scrivi: 120

Per inserire 2.5 ore:
❌ NON scrivere: 2.5
✅ Scrivi: 150

Per inserire 8 ore:
❌ NON scrivere: 8
✅ Scrivi: 480
```

---

## 🧪 TEST VALIDAZIONE

### Test 1: Conversione Base
```python
assert minuti_to_ore(60) == 1.00    # 1 ora
assert minuti_to_ore(120) == 2.00   # 2 ore
assert minuti_to_ore(150) == 2.50   # 2.5 ore
assert minuti_to_ore(0) == 0.00     # zero
```

### Test 2: Formatting
```python
assert format_ore(1.00) == "1.00h"
assert format_ore(2.50) == "2.50h"
assert format_ore(127.50) == "127.50h"
```

### Test 3: Aggregazione
```python
df = pd.DataFrame({'valore': [60, 90, 150]})
df['ore'] = df['valore'].apply(minuti_to_ore)
assert df['ore'].sum() == 5.00  # (60+90+150)/60 = 5
```

### Test 4: Media
```python
tot_ore = 7.50
giorni = 3
media = tot_ore / giorni
assert media == 2.50  # 7.50 / 3 = 2.50
```

---

## 📈 BEFORE / AFTER

### Report Straordinari

**BEFORE:**
```
Record: 503
Giorni: 23
Totale Ore: 30,180h  ← ❌ IMPOSSIBILE!
Media/Gg: 1,312.17h  ← ❌ ASSURDO!
```

**AFTER:**
```
Record: 503
Giorni: 23
Totale Ore: 503.00h  ← ✅ REALISTICO!
Media/Gg: 21.87h     ← ✅ SENSATO!
```

### Dettaglio Persona

**BEFORE:**
```
Nome         | Ore
-------------|--------
ROSSI M.     | 2,730h  ← ❌ 113 giorni!
BIANCHI L.   | 2,280h  ← ❌ 95 giorni!
```

**AFTER:**
```
Nome         | Ore
-------------|--------
ROSSI M.     | 45.50h  ← ✅ Normale
BIANCHI L.   | 38.00h  ← ✅ Normale
```

---

## 🔍 DEBUG

### Come Verificare

**1. Check Valore Database:**
```python
straordinari = db.get_all('Straordinario')
print(straordinari['valore'].head())
# Output: 120, 180, 90, ... (MINUTI)
```

**2. Check Valore Convertito:**
```python
straordinari['ore'] = straordinari['valore'].apply(minuti_to_ore)
print(straordinari['ore'].head())
# Output: 2.00, 3.00, 1.50, ... (ORE)
```

**3. Check Display:**
```python
straordinari['ore_formatted'] = straordinari['ore'].apply(format_ore)
print(straordinari['ore_formatted'].head())
# Output: "2.00h", "3.00h", "1.50h", ...
```

### Log di Debug

Se serve debug, aggiungi:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

def minuti_to_ore(minuti):
    ore = round(float(minuti) / 60.0, 2)
    logging.debug(f"Convertito {minuti} min → {ore} ore")
    return ore
```

---

## 💡 TIPS

### 1. Verifica Conversione

Dopo import dati, verifica:
```python
straordinari = db.get_all('Straordinario')
ore_totali = straordinari['valore'].apply(minuti_to_ore).sum()
print(f"Totale ore straordinari: {ore_totali:.2f}h")
```

### 2. Export con Ore

Se vuoi export in ore (non minuti):
```python
df['ore'] = df['valore'].apply(minuti_to_ore)
df[['data', 'matricola', 'ore']].to_csv('export_ore.csv')
```

### 3. Import da Ore

Se ricevi file in ore, converti in minuti:
```python
df['valore'] = df['ore'] * 60
db.save_table('Straordinario', df)
```

---

## 🎯 CONCLUSIONE

**Fix implementato con successo!**

✅ **Conversione automatica** minuti→ore
✅ **Tutti i calcoli corretti** (somme, medie)
✅ **Database invariato** (compatibilità)
✅ **Display chiaro** (formato "X.XXh")
✅ **Warning espliciti** (Editor Dati)

**Valori ora realistici e corretti!** 🎉

---

**Versione:** v7.0 Enterprise
**Data:** Gennaio 2026
**Status:** ✅ Production Ready
