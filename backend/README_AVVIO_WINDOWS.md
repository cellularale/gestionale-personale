# Avvio su Windows (senza finestre e senza avvisi inutili)

## 1) Avvio **senza finestra PowerShell/CMD** (consigliato)
Doppio click su:
- **AVVIA_SILENZIOSO.vbs**

Avvia Streamlit con **PowerShell nascosto**.

## 2) Avvio rapido (si chiude subito)
Doppio click su:
- **START_RAPIDO.bat**

## 3) Evitare il popup "Impossibile verificare l'autore"
Quel popup appare perché Windows applica il *Mark of the Web* ai file scaricati.

**Soluzione consigliata (una volta sola):**
1. Tasto destro sul file **.zip** scaricato
2. **Proprietà**
3. Spunta **Sblocca** (in basso)
4. Applica, poi estrai lo zip

In alternativa (PowerShell):
```powershell
Unblock-File -Path .\AVVIA_SILENZIOSO.vbs
Unblock-File -Path .\START_RAPIDO.bat
```

> Nota: senza firma digitale, Windows potrebbe comunque mostrare un avviso su alcuni PC aziendali (policy). In quel caso l'unica soluzione definitiva e' firmare i file con un certificato.
