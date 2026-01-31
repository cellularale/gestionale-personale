# PersGest v7 ENTERPRISE 🏢

## 🎉 NOVITÀ VERSIONE ENTERPRISE

### ✅ UI AZIENDALE PROFESSIONALE
- Design corporate blu (#1E40AF)
- Gradient headers moderni
- Card con hover effects
- Sidebar branded
- Tabelle eleganti
- Animazioni fluide

### ⚠️ FIX CRITICO: MINUTI → ORE
**PROBLEMA RISOLTO:** Valori database in minuti ora convertiti correttamente in ore!

**Prima:**
- Database: 120 minuti
- Display: "120h" ❌ SBAGLIATO

**Adesso:**
- Database: 120 minuti (mantenuto)
- Conversione: 120 / 60 = 2.00
- Display: "2.00h" ✅ CORRETTO

### 📊 DOVE APPLICATO
- ✅ Report Straordinari (tutti i calcoli)
- ✅ Verifica Match GT-STR (confronti)
- ✅ Export CSV (valori corretti)
- ✅ Tabelle aggregate (somme/medie)

---

## 🚀 QUICK START

### 1. Setup

```bash
# Installa Python 3.9+
python --version

# Installa dipendenze
pip install -r requirements.txt
```

### 2. Avvio

**Opzione A - Script (facile):**
```
Doppio click: AVVIA.bat
```

**Opzione B - Manuale:**
```bash
cd app
python -m streamlit run persgest.py
```

### 3. Primo Uso

1. Menu → Configurazione
2. Imposta percorso database Excel
3. Menu → Import/Export
4. Importa i tuoi file Excel
5. Dashboard → Verifica dati

---

## 📊 FUNZIONALITÀ

### Dashboard
- Statistiche generali
- 4 metriche principali
- Dettaglio 18 tabelle
- Categorie organizzate

### Report Straordinari ⭐
- **FIX: Conversione minuti→ore automatica**
- Filtri persona + periodo
- Riepilogo 4 metriche (in ORE)
- Aggregato per persona
- Dettaglio giornaliero
- Export CSV

### Verifica Match GT-STR
- **FIX: Ore corrette in confronto**
- % match con color coding
- Match perfetti
- Discrepanze identificate
- Target: >95% match

### Editor Dati
- ⚠️ Warning: "valori in MINUTI"
- Modifica inline 18 tabelle
- Ricerca globale
- Salvataggio immediato
- Aggiungi/Elimina record

### Import/Export
- Import Excel multiplo
- ⚠️ File devono avere valori in MINUTI
- Export selettivo tabelle
- Mapping flessibile
- Valori mantenuti in minuti

### Configurazione
- Percorso database flessibile
- Selettore cartelle
- Info sistema
- Persistenza impostazioni

---

## ⚠️ IMPORTANTE: MINUTI vs ORE

### Database Excel
**Formato:** MINUTI
- Campo `valore` è in MINUTI
- Esempio: 120 = 2 ore
- Import/Export mantiene minuti

### App Streamlit
**Display:** ORE
- Conversione automatica per visualizzazione
- Formattato come "2.00h"
- Calcoli corretti (medie, totali)

### Editor Dati
**⚠️ Attenzione quando modifichi:**
- Valori in MINUTI nel database
- Per 1 ora → inserisci 60
- Per 2.5 ore → inserisci 150
- Per 8 ore → inserisci 480

---

## 🎨 UI ENTERPRISE

### Tema Colori
```
Primary:   #1E40AF (blu scuro)
Secondary: #3B82F6 (blu medio)
Accent:    #60A5FA (blu chiaro)
Success:   #10B981 (verde)
Warning:   #F59E0B (arancione)
Danger:    #EF4444 (rosso)
```

### Componenti
- Gradient headers
- Card professionali con shadow
- Metric cards con hover
- Tabelle con header colorato
- Sidebar branded
- Button animations

---

## 📋 VERIFICA CORRETTEZZA

### Test Conversione

**Singolo Record:**
```
Database: 120 minuti
Conversione: 120 / 60 = 2.00
Display: "2.00h" ✅
```

**Aggregazione:**
```
3 record: 60, 90, 150 minuti
Totale: 300 minuti
Conversione: 300 / 60 = 5.00
Display: "5.00h" ✅
```

**Media:**
```
Totale: 450 min = 7.50 ore
Giorni: 3
Media: 7.50 / 3 = 2.50 ore/gg
Display: "2.50h/gg" ✅
```

---

## 🔧 TROUBLESHOOTING

### App non parte

**Errore: streamlit not found**
```bash
pip install streamlit pandas openpyxl
```

**Errore: python not found**
```
Reinstalla Python con "Add to PATH" ✓
```

### Ore sembrano sbagliate

**Sintomo:** Vedi 7,650h invece di 127h

**Soluzione:** Usa questa versione Enterprise con fix!

### Editor mostra valori strani

**Ricorda:** Valori sono in MINUTI nel database
- 60 = 1 ora
- 120 = 2 ore
- 480 = 8 ore

---

## 💡 BEST PRACTICES

### Report
- Usa filtri per periodo specifico
- Controlla unità: sempre ORE in display
- Export CSV per elaborazioni

### Editor
- ⚠️ Valori in MINUTI!
- Calcola: ore × 60 = minuti
- Verifica dopo modifica

### Import
- File Excel con valori in MINUTI
- Mapping corretto fogli→tabelle
- Verifica conteggi dopo import

### Backup
- Export settimanale database
- Versioning SharePoint attivo
- File sincronizzato OneDrive

---

## 📞 SUPPORTO

### Documentazione
- `README.md` (questo file)
- `docs/GUIDA_ENTERPRISE.md`
- `docs/CHANGELOG.md`

### Problemi Comuni
1. Streamlit non trovato → pip install
2. Python non trovato → Reinstalla
3. File non trovato → Verifica sync OneDrive
4. Ore sbagliate → Usa versione Enterprise

---

## 🚀 VERSIONI

**v7.0 Enterprise (Attuale)**
- ✅ UI aziendale completa
- ✅ Fix minuti→ore
- ✅ Flussi verificati
- ✅ Production ready

**Prossime (Roadmap):**
- v7.1: Calendari + Grafici
- v7.2: AI/ML previsioni
- v7.3: Integrazione ERP

---

## 📄 LICENZA

Uso interno aziendale.

---

## 🎊 CREDITS

- **Sviluppo:** Claude AI
- **Design:** Corporate Blue Theme
- **Testing:** Team IT

---

**PersGest v7 Enterprise - Il Futuro della Gestione HR** 🏢

**Setup in 5 minuti | SharePoint Ready | Production Grade**

🚀 **READY TO GO!** 🚀

---
## Avvio senza finestra (niente PowerShell/CMD visibile)

### Opzione consigliata: **AVVIA_SILENZIOSO.vbs**
- Doppio click su `AVVIA_SILENZIOSO.vbs`.
- Avvia Streamlit in background (PowerShell nascosto) e poi puoi aprire il browser su:
  - `http://localhost:8501`

### Se Windows mostra l’avviso “Impossibile verificare l’autore...” (file scaricato)
Questo succede perché Windows applica la “Mark of the Web” ai file scaricati.

**Soluzione 1 (consigliata): sblocca lo ZIP prima di estrarre**
1. tasto destro sul file `.zip` → **Proprietà**
2. spunta **Sblocca** → Applica
3. estrai di nuovo la cartella

**Soluzione 2: sblocca singolo file**
- tasto destro su `AVVIA_SILENZIOSO.vbs` (o `.bat`) → Proprietà → **Sblocca**

### Comando diretto (senza file .bat)
Da PowerShell/CMD, dentro la cartella progetto:
```bat
cd app
python -m streamlit run persgest.py
```
