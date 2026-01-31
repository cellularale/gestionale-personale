# Cartella dati (NON versionata)

Metti qui il database Excel locale:

- `persgest_master.xlsx`

Questa cartella deve essere **gitignored** (contiene dati reali).  
L'app crea anche:

- `backups/` (backup automatici del DB)
- `db_meta.json` (metadati/versione DB)
- `persgest_master.xlsx.lock` (lock file scritture)

