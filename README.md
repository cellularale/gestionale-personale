# gestionale-personale (monorepo)

Questa repo contiene:

- `frontend/` (Vite + Tailwind) — opzionale / landing / UI statica
- `backend/` (Streamlit + Excel DB) — applicativo operativo

## Avvio backend (locale)

Requisiti: Python 3.10+.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/persgest.py
```

## Database (Excel)

Il DB è un file Excel **locale**:

- percorso previsto: `backend/data/persgest_master.xlsx`

⚠️ Il file DB, i backup e i log **NON** vanno versionati (vedi `.gitignore`).

## Sicurezza scritture (≈10 utenti)

Il backend serializza le scritture sul DB Excel tramite:
- lock globale + lock su file (`*.lock`)
- backup automatico in `backend/backups/`
- salvataggio atomico su `.tmp` e sostituzione con `os.replace`

Queste modifiche **non** cambiano logiche, flussi, strutture o nomi dei fogli/tabelle.
