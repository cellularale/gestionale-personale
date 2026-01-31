from __future__ import annotations

# NOTE: alcune utility (festivi/pasqua) sono definite prima degli import principali.
# Per evitare NameError sulle annotazioni (Python 3.11+) e rendere il modulo importabile,
# importiamo qui le dipendenze minime usate da queste funzioni.
from datetime import date, timedelta
import pandas as pd


def _easter_date(year: int) -> date:
    """Ritorna la data di Pasqua (calendario gregoriano)."""
    # algoritmo di Meeus/Jones/Butcher
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

def _build_holiday_index(df_festivi: pd.DataFrame, years: list[int]):
    """Crea dict date->descrizione per anni specificati."""
    holiday = {}
    if df_festivi is not None and len(df_festivi) > 0 and 'GiornoFestivo' in df_festivi.columns:
        tmp = df_festivi.copy()
        tmp['GiornoFestivo'] = pd.to_numeric(tmp['GiornoFestivo'], errors='coerce').astype('Int64')
        tmp = tmp[tmp['GiornoFestivo'].notna()]
        # mmdd = month*100+day (es. 0101=101)
        rows = tmp[['GiornoFestivo'] + ([c for c in ['Descrizione'] if c in tmp.columns])].to_dict('records')
        mmdd_to_desc = {}
        for r in rows:
            mmdd = int(r['GiornoFestivo'])
            desc = str(r.get('Descrizione','')).strip() or f"Festivo {mmdd:04d}"
            mmdd_to_desc[mmdd] = desc
        for y in years:
            for mmdd, desc in mmdd_to_desc.items():
                m = mmdd // 100
                d = mmdd % 100
                try:
                    dt = date(y, m, d)
                    holiday[dt] = desc
                except Exception:
                    continue
    # Pasqua / Pasquetta
    for y in years:
        try:
            eas = _easter_date(y)
            holiday[eas] = 'Pasqua'
            holiday[eas + timedelta(days=1)] = 'Pasquetta'
        except Exception:
            pass
    return holiday
"""
PersGest v7 ENTERPRISE
Sistema Gestione Personale con UI Aziendale
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import textwrap
from datetime import datetime, timedelta, date
from pathlib import Path
import sys
import os
import json
import re

sys.path.append(str(Path(__file__).parent))
from database import PersGestDatabase

# Asset (immagini) per UI (es. Calendario "vista ampia")
ASSETS_DIR = Path(__file__).parent / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

def _find_asset(stem: str):
    """Cerca un asset con estensioni comuni (png/jpg/jpeg/webp)."""
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = ASSETS_DIR / f"{stem}{ext}"
        if p.exists():
            return p
    return None


# -----------------------------
# UI helpers
# -----------------------------
def _header_box(title: str, subtitle: str = "") -> str:
    """Header coerente con lo stile globale (page-header).

    Molte sezioni usano direttamente l'HTML; Festivi lo richiama tramite questa
    funzione per evitare duplicazioni e NameError.
    """
    subtitle_html = f"<div class='page-subtitle'>{subtitle}</div>" if subtitle else ""
    return (
        "<div class='page-header'>"
        f"<div class='page-title'>{title}</div>"
        f"{subtitle_html}"
        "</div>"
    )

# Config
try:
    import tkinter as _tk
    from tkinter import filedialog as _fd
except Exception:
    _tk, _fd = None, None

APPDATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "PersGestStreamlit"
APPDATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = APPDATA_DIR / "config.json"

def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except:
        return {}

def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def pick_folder_dialog(title="Seleziona cartella"):
    if not _tk or not _fd:
        return ""
    root = _tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = _fd.askdirectory(title=title)
    try:
        root.destroy()
    except:
        pass
    return path or ""

# ========== FIX MINUTI → ORE ==========
def minuti_to_ore(minuti):
    """Converte minuti in ore (2 decimali)"""
    if pd.isna(minuti):
        return 0.0
    try:
        return round(float(minuti) / 60.0, 2)
    except:
        return 0.0


def minuti_to_ore_float(minuti):
    """Converte minuti in ore (float) senza arrotondare (per calcoli)."""
    if pd.isna(minuti):
        return 0.0
    try:
        return float(minuti) / 60.0
    except:
        return 0.0

def format_minuti(minuti):
    """Formatta minuti come 'Xh Ym' (es. 8 minuti -> '0h 08m')."""
    if pd.isna(minuti):
        minuti = 0
    try:
        mins = int(round(float(minuti)))
    except:
        mins = 0
    if mins < 0:
        mins = 0
    h = mins // 60
    m = mins % 60
    return f"{h}h {m:02d}m"
def format_ore(ore):
    """Formatta ore per display"""
    return f"{ore:.2f}h"


def _to_float_clean(x):
    """Converte valori numerici anche in formato stringa tipo '8.00h' o '8,00'."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    try:
        if isinstance(x, str):
            s = x.strip().lower().replace('h','').replace('ore','').strip()
            s = s.replace(',', '.')
            if s == '':
                return None
            return float(s)
        return float(x)
    except Exception:
        return None


def series_to_numeric(series: pd.Series) -> pd.Series:
    """Serie -> float pulito (NaN dove non convertibile)."""
    if series is None:
        return pd.Series(dtype=float)
    return series.apply(_to_float_clean).astype(float)


def extract_gt_overtime(attivita: pd.DataFrame) -> pd.DataFrame:
    """Estrae straordinari importati dal GT dalla tabella Attivita.

    Regole:
      - considera righe dove (turno == STR/RPD/RPN) oppure (att == STR/RPD/RPN)
      - solo se valore/minuti > 0
      - ritorna df con colonne: matricola, data, turno, ore, _is_gt_ot=True
    """
    if attivita is None or len(attivita) == 0:
        return pd.DataFrame(columns=['matricola','data','turno','minuti','ore','_is_gt_ot'])

    df = attivita.copy()

    if 'matricola' not in df.columns or 'data' not in df.columns:
        return pd.DataFrame(columns=['matricola','data','turno','minuti','ore','_is_gt_ot'])

    df['matricola'] = df['matricola'].astype(str).str.strip()
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df = df[df['data'].notna()].copy()

    # valore/minuti
    val_col = None
    for cand in ['valore', 'minuti', 'mins', 'minute']:
        if cand in df.columns:
            val_col = cand
            break
    if val_col is None:
        return pd.DataFrame(columns=['matricola','data','turno','minuti','ore','_is_gt_ot'])

    df['_min'] = series_to_numeric(df[val_col]).fillna(0.0).astype(float)

    # Normalizzazione input GT:
    # - atteso: MINUTI (es. 480 = 8h)
    # - in alcuni export: ORE (es. 8 = 8h)
    # Regola conservativa: se il valore è un intero tra 1 e 24 lo trattiamo come ORE.
    mask_hours = (df['_min'] > 0) & (df['_min'] <= 24) & ((df['_min'] % 1) == 0)
    if mask_hours.any():
        df.loc[mask_hours, '_min'] = df.loc[mask_hours, '_min'] * 60
    df = df[df['_min'] > 0].copy()
    if len(df) == 0:
        return pd.DataFrame(columns=['matricola','data','turno','minuti','ore','_is_gt_ot'])

    OT_CODES = {'STR', 'RPD', 'RPN'}

    recs = []
    for col in ['turno', 'att']:
        if col in df.columns:
            c = df[col].astype(str).str.strip().str.upper()
            mm = c.isin(OT_CODES)
            if mm.any():
                tmp = df.loc[mm, ['matricola','data','_min']].copy()
                tmp['turno'] = c[mm].values
                recs.append(tmp)

    if not recs:
        return pd.DataFrame(columns=['matricola','data','turno','minuti','ore','_is_gt_ot'])

    out = pd.concat(recs, ignore_index=True)

    # Nel report, RPD/RPN devono essere trattati come un'unica voce "REP".
    out['turno'] = out['turno'].replace({'RPD': 'REP', 'RPN': 'REP'})

    # de-dup: somma minuti per stessa persona/data/codice
    out = out.groupby(['matricola','data','turno'], as_index=False)['_min'].sum()
    out['minuti'] = out['_min'].astype(float)
    out['ore'] = out['minuti'].apply(minuti_to_ore_float)
    out['_is_gt_ot'] = True
    return out[['matricola','data','turno','minuti','ore','_is_gt_ot']]


def parse_date_ddmmyyyy(s: str, default_dt: datetime) -> datetime:
    """Parsa una data in formato gg/mm/aaaa (day-first).
    Se non valida, ritorna default_dt."""
    try:
        s = (s or '').strip()
        return datetime.strptime(s, '%d/%m/%Y')
    except Exception:
        return default_dt

# ========== REGISTRO RELAZIONALE (Nome/Matricola/UO/Categoria) ==========
@st.cache_data(ttl=5)
def get_person_registry():
    """Costruisce un registro persone in logica relazionale.

    Priorita:
      1) Tabella Personale (se presente) -> matricola, nome, uo, catproftipo
      2) Tabella Attivita (sempre presente nel tuo flusso) -> mapping matricola->nome e UO

    Ritorna DataFrame con colonne: matricola, nome, uo, cat
    """
    try:
        pers = db.get_all('Personale')
    except Exception:
        pers = pd.DataFrame()
    try:
        att = db.get_all('Attivita')
    except Exception:
        att = pd.DataFrame()

    def _norm_col(c: str) -> str:
        c = str(c).strip().lower()
        # normalizza separatori
        for ch in ['\u00a0', ' ', '-', '/', '\\', '.', ':']:
            c = c.replace(ch, '_')
        while '__' in c:
            c = c.replace('__', '_')
        return c.strip('_')

    # --- da Personale ---
    if len(pers) > 0:
        p = pers.copy()

        # mappa colonne normalizzate -> originali (per gestire CatProfTipo, Unita Operativa, ecc.)
        colmap = {_norm_col(c): c for c in p.columns}

        # matricola (accetta varianti: Matricola, MATR, ecc.)
        matr_col = None
        for key in ['matricola', 'matr', 'matricola_id']:
            if key in colmap:
                matr_col = colmap[key]
                break
        if matr_col is not None:
            p['matricola'] = p[matr_col].astype(str).str.strip()

            # nome: prova varie combinazioni (anche con varianti maiuscole)
            # 1) Cognome + Nome (se esistono entrambi come colonne distinte)
            if ('cognome' in colmap) and ('nome' in colmap) and (colmap['cognome'] != colmap['nome']):
                p['nome'] = (
                    p[colmap['cognome']].astype(str).str.strip() + ' ' +
                    p[colmap['nome']].astype(str).str.strip()
                ).str.strip()
            else:
                nome_src = None
                for key in ['nominativo', 'cognome_e_nome', 'cognome_nome', 'nome', 'cognome']:
                    if key in colmap:
                        nome_src = colmap[key]
                        break
                if nome_src is not None:
                    p['nome'] = p[nome_src].astype(str).str.strip()
                else:
                    p['nome'] = p['matricola']
            p['nome'] = p['nome'].replace({'': None}).fillna(p['matricola'])

            # uo
            uo_col = None
            for key in ['uo', 'unita_operativa', 'unita_operativa_uo', 'unitaoperativa', 'unità_operativa']:
                if key in colmap:
                    uo_col = colmap[key]
                    break
            p['uo'] = p[uo_col].astype(str).str.strip() if uo_col else ''

            # categoria (CatProfTipo)
            cat_col = None
            for key in ['catproftipo', 'cat_prof_tipo', 'categoria', 'cat', 'cat_prof', 'catprof']:
                if key in colmap:
                    cat_col = colmap[key]
                    break
            p['cat'] = p[cat_col].astype(str).str.strip() if cat_col else ''

            reg = p[['matricola', 'nome', 'uo', 'cat']].drop_duplicates('matricola')
            # se nome vuoto, fallback
            reg['nome'] = reg['nome'].replace({'': None}).fillna(reg['matricola'])
            return reg

    # --- fallback da Attivita (tuo caso) ---
    if len(att) == 0 or 'matricola' not in att.columns:
        return pd.DataFrame(columns=['matricola', 'nome', 'uo', 'cat'])

    a = att.copy()
    a['matricola'] = a['matricola'].astype(str).str.strip()

    # nome da attivita: usa il piu frequente per matricola (supporta varianti colonna)
    name_col = None
    for c in ['nome', 'Nome', 'cognome_e_nome', 'cognome e nome', 'Cognome e Nome', 'nominativo', 'Nominativo']:
        if c in a.columns:
            name_col = c
            break
    if name_col is not None:
        a['_nome_src'] = a[name_col].astype(str).str.strip()
        name_map = (a[a['_nome_src'].notna() & (a['_nome_src'] != '')]
                    .groupby('matricola')['_nome_src']
                    .agg(lambda s: s.value_counts().index[0]))
    else:
        name_map = pd.Series(dtype=str)

    # uo: piu frequente per matricola (supporta varianti colonna)
    uo_col = None
    for c in ['uo', 'UO', 'unita_operativa', 'unità_operativa', 'unità operativa', 'Unita Operativa', 'Unità Operativa']:
        if c in a.columns:
            uo_col = c
            break
    if uo_col is not None:
        a['_uo_src'] = a[uo_col].astype(str).str.strip()
        uo_map = (a[a['_uo_src'].notna() & (a['_uo_src'] != '')]
                  .groupby('matricola')['_uo_src']
                  .agg(lambda s: s.value_counts().index[0]))
    else:
        uo_map = pd.Series(dtype=str)

    reg = pd.DataFrame({'matricola': sorted(a['matricola'].dropna().unique())})
    reg['nome'] = reg['matricola'].map(name_map).fillna(reg['matricola'])
    reg['uo'] = reg['matricola'].map(uo_map).fillna('')
    reg['cat'] = ''
    return reg


# ========== META PERSONALE (con in_forza) + FILTRI GLOBALI ==========

def _norm_in_forza_global(v):
    """Normalizza il flag "in forza/attivo" in modo robusto e consistente in tutto il progetto."""
    try:
        if pd.isna(v):
            return True
    except Exception:
        pass
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s == "":
        return True
    falsy = {
        '0', 'false', 'f', 'no', 'n', 'non', 'na', 'null',
        'off', 'cessato', 'cess', 'non attivo', 'inattivo', 'terminato', 'dimesso', 'fine', 'uscito'
    }
    truthy = {'1', 'true', 't', 'si', 'sì', 'yes', 'y', 'on', 'attivo', 'in forza', 'in_forza'}
    if s in falsy:
        return False
    if s in truthy:
        return True
    return True


@st.cache_data(ttl=5)


def _compile_wildcard_patterns(s: str) -> list[str]:
    """Converte input utente con jolly '*' in regex (per str.contains).

    Regole:
    - Se NON metti '*', il match è "contiene" (es: 'rp' => '*rp*' => '.*RP.*')
    - Se metti '*', il comportamento è quello atteso:
        'rp*'   => inizia con RP
        '*rp'   => finisce con RP
        '*fer*' => contiene FER
    - Più pattern separati da spazio, virgola, ';' o '|' (OR).
    """
    if s is None:
        return []
    s = str(s).strip()
    if not s:
        return []
    s = s.upper()

    tokens = [t for t in re.split(r"[,\s;|]+", s) if t]
    pats: list[str] = []
    for tok in tokens:
        tok = tok.strip().upper()
        if not tok:
            continue

        # default: contiene
        if "*" not in tok:
            tok = f"*{tok}*"

        # escape, poi sostituisci jolly
        rpat = re.escape(tok).replace(r"\*", ".*")

        # ancora inizio/fine solo se l'utente non mette '*' ai bordi
        if not tok.startswith("*"):
            rpat = "^" + rpat
        if not tok.endswith("*"):
            rpat = rpat + "$"
        pats.append(rpat)
    return pats


def get_person_meta() -> pd.DataFrame:
    """Registro persone + stato (in_forza) come base unica per tutto il progetto.

    Colonne garantite: matricola, nome, uo, cat, in_forza
    """
    reg = get_person_registry().copy() if isinstance(get_person_registry(), pd.DataFrame) else pd.DataFrame()
    if reg is None or reg.empty:
        reg = pd.DataFrame(columns=['matricola', 'nome', 'uo', 'cat'])

    # default columns
    for c in ['matricola', 'nome', 'uo', 'cat']:
        if c not in reg.columns:
            reg[c] = ''

    reg['matricola'] = reg['matricola'].astype(str).str.strip()
    reg['nome'] = reg['nome'].fillna('').astype(str).str.strip()
    reg['uo'] = reg['uo'].fillna('').astype(str).str.strip()
    reg['cat'] = reg['cat'].fillna('').astype(str).str.strip()

    # prova a leggere in_forza da Personale
    try:
        pers = db.get_all('Personale') if 'Personale' in getattr(db, 'TABLES', []) else pd.DataFrame()
    except Exception:
        pers = pd.DataFrame()

    inf_map = {}
    if pers is not None and len(pers) > 0:
        cols_l = {str(c).strip().lower(): c for c in pers.columns}
        # prova a colmare 'nome' dal foglio Personale se mancante nel registro
        name_col = (cols_l.get('nome') or cols_l.get('nominativo') or cols_l.get('cognome_nome') or cols_l.get('cognomenome')
                    or cols_l.get('dipendente') or cols_l.get('persona'))
        if name_col is not None:
            try:
                tmpn = pers[[cols_l.get('matricola') or cols_l.get('matr') or cols_l.get('matricola ') or list(pers.columns)[0], name_col]].copy()
                tmpn.columns = ['matricola', 'nome_pers']
                tmpn['matricola'] = tmpn['matricola'].astype(str).str.strip()
                tmpn['nome_pers'] = tmpn['nome_pers'].fillna('').astype(str).str.strip()
                nmap = (tmpn[tmpn['nome_pers'] != '']
                            .drop_duplicates(subset=['matricola'])
                            .set_index('matricola')['nome_pers']
                            .to_dict())
                reg.loc[(reg['nome'] == '') | (reg['nome'].str.lower() == 'nan'), 'nome'] = reg['matricola'].map(nmap).fillna(reg['nome'])
                reg['nome'] = reg['nome'].fillna('').astype(str).str.strip()
            except Exception:
                pass
        
        matr_col = cols_l.get('matricola') or cols_l.get('matr')
        inf_col = (cols_l.get('in_forza') or cols_l.get('inforza') or cols_l.get('in forza') or cols_l.get('in_servizio') or cols_l.get('in servizio') or cols_l.get('servizio') or cols_l.get('attivo') or cols_l.get('stato') or cols_l.get('status'))
        if matr_col in pers.columns and inf_col in pers.columns:
            tmp = pers[[matr_col, inf_col]].copy()
            tmp.columns = ['matricola', 'in_forza']
            tmp['matricola'] = tmp['matricola'].astype(str).str.strip()
            tmp['in_forza'] = tmp['in_forza'].apply(_norm_in_forza_global)
            # in caso di duplicati matricola, prendi il valore più frequente
            try:
                inf_map = (tmp.dropna(subset=['matricola'])
                             .groupby('matricola')['in_forza']
                             .agg(lambda s: bool(s.value_counts().index[0]))
                             .to_dict())
            except Exception:
                inf_map = dict(zip(tmp['matricola'], tmp['in_forza']))

    reg['in_forza'] = reg['matricola'].map(inf_map)
    reg['in_forza'] = reg['in_forza'].apply(_norm_in_forza_global)

    # drop duplicates
    reg = reg.drop_duplicates(subset=['matricola'])
    return reg[['matricola', 'nome', 'uo', 'cat', 'in_forza']]


def get_relational_selections():
    """Ritorna (uo_sel, cat_sel) dai filtri globali in sidebar."""
    return (
        st.session_state.get('filter_uo', 'Tutte'),
        st.session_state.get('filter_cat', 'Tutte'),
    )


def get_person_meta_rel_filtered(uo_sel: str | None = None, cat_sel: str | None = None) -> pd.DataFrame:
    """Meta personale filtrata dai selettori relazionali globali (sidebar)."""
    if uo_sel is None or cat_sel is None:
        uo_sel2, cat_sel2 = get_relational_selections()
        uo_sel = uo_sel if uo_sel is not None else uo_sel2
        cat_sel = cat_sel if cat_sel is not None else cat_sel2

    meta = get_person_meta().copy()
    if uo_sel and uo_sel != 'Tutte':
        meta = meta[meta['uo'].astype(str) == str(uo_sel)]
    if cat_sel and cat_sel != 'Tutte':
        meta = meta[meta['cat'].astype(str) == str(cat_sel)]
    return meta


def apply_relational_filters(df: pd.DataFrame, uo_sel: str, cat_sel: str) -> pd.DataFrame:
    """Applica filtri relazionali (UO, Categoria) ad un dataframe con almeno 'matricola'.

    Regola globale del progetto:
    - Il filtro in sidebar determina SEMPRE l'insieme persone/record da mostrare.
    - Il filtro si applica per matricola (join relazionale), NON si fida di eventuali colonne uo/cat già presenti nel df.

    Nota: evita collisioni di colonne (uo/cat) mantenendo lo schema originale.
    """
    if df is None or len(df) == 0:
        return df
    if 'matricola' not in df.columns:
        return df

    out = df.copy()
    out['matricola'] = out['matricola'].astype(str).str.strip()

    meta = get_person_meta_rel_filtered(uo_sel=uo_sel, cat_sel=cat_sel)
    keep = set(meta['matricola'].astype(str)) if len(meta) > 0 else set()

    # Se meta è vuoto e il filtro NON è 'Tutte', restituisci vuoto: coerente col filtro relazionale.
    if (uo_sel and uo_sel != 'Tutte') or (cat_sel and cat_sel != 'Tutte'):
        out = out[out['matricola'].isin(keep)].copy()
    else:
        # 'Tutte' => nessun filtro (mostra tutto)
        pass

    return out


def get_shift_hours_map(att_df: pd.DataFrame) -> dict:
    """Ritorna una mappa TURNO->ORE attese.

    Priorita:
      1) Tabella Turni_tipo (colonna Minuti)
      2) Stima da Attivita: mediana delle ore per turno
    """
    # 1) Turni_tipo
    try:
        tt = db.get_all('Turni_tipo')
    except Exception:
        tt = pd.DataFrame()

    out = {}
    if tt is not None and len(tt) > 0:
        # normalizza colonne
        cols = {c: str(c).strip() for c in tt.columns}
        tt = tt.rename(columns=cols)
        turno_col = None
        for c in ['Turno', 'turno', 'SIGLA', 'sigla']:
            if c in tt.columns:
                turno_col = c
                break
        min_col = None
        for c in ['Minuti', 'minuti', 'Durata', 'durata']:
            if c in tt.columns:
                min_col = c
                break
        if turno_col and min_col:
            t = tt[[turno_col, min_col]].copy()
            t[turno_col] = t[turno_col].astype(str).str.strip().str.upper()
            mins = pd.to_numeric(t[min_col], errors='coerce').fillna(0.0)
            hrs = (mins / 60.0).round(2)
            out.update({k: float(v) for k, v in zip(t[turno_col], hrs) if k and float(v) > 0})

    # 2) fallback da attivita (mediana per turno)
    if (not out) and (att_df is not None) and len(att_df) > 0 and ('turno' in att_df.columns) and ('ore' in att_df.columns):
        tmp = att_df.copy()
        tmp['turno'] = tmp['turno'].astype(str).str.strip().str.upper()
        tmp['ore'] = pd.to_numeric(tmp['ore'], errors='coerce')
        grp = tmp.dropna(subset=['turno']).groupby('turno')['ore'].median()
        for k, v in grp.items():
            if k and v and v > 0:
                out[str(k).upper()] = float(round(v, 2))

    return out

# ========== CONFIG PAGE ==========
st.set_page_config(
    page_title="PersGest Enterprise",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== CSS AZIENDALE ==========
st.markdown("""
<style>
    /* TEMA CORPORATE BLU */
    :root {
        --primary: #1E40AF;
        --secondary: #3B82F6;
        --accent: #60A5FA;
        --success: #10B981;
        --warning: #F59E0B;
        --danger: #EF4444;
        --text-primary: #1E293B;
        --text-secondary: #64748B;
        --bg-light: #F8FAFC;
        --border: #E2E8F0;
    }
    
    /* GLOBAL */
    .main {
        background: var(--bg-light);
    }
    
    /* PAGE HEADER */
    .page-header {
        background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
    }
    
    .page-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: white;
        margin: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .page-subtitle {
        font-size: 1.1rem;
        color: rgba(255,255,255,0.9);
        margin-top: 0.5rem;
    }
    
    /* METRIC CARDS */
    .metric-card {
        background: white;
        padding: 2rem;
        border-radius: 16px;
        border-left: 5px solid var(--secondary);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    }
    
    .metric-value {
        font-size: 3rem;
        font-weight: 800;
        color: var(--primary);
        line-height: 1;
        margin-bottom: 0.5rem;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    
    /* SIDEBAR */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--primary) 0%, #1E3A8A 100%);
    }
    
    section[data-testid="stSidebar"] .element-container {
        color: white;
    }
    
    .company-logo {
        text-align: center;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        background: rgba(255,255,255,0.1);
        border-radius: 12px;
        backdrop-filter: blur(10px);
    }
    
    .company-name {
        font-size: 2rem;
        font-weight: 800;
        color: white;
        margin: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    .company-tagline {
        font-size: 0.75rem;
        color: rgba(255,255,255,0.8);
        margin-top: 0.5rem;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    
    .section-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        margin: 1.5rem 0;
    }
    
    /* BUTTONS */
    .stButton button {
        background: white;
        color: var(--primary);
        border: 2px solid rgba(255,255,255,0.2);
        border-radius: 12px;
        padding: 0.875rem 1.5rem;
        font-weight: 700;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.875rem;
    }
    
    .stButton button:hover {
        background: var(--accent);
        color: white;
        border-color: var(--accent);
        transform: translateX(4px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    
    /* TABLES */
    .dataframe {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .dataframe thead tr th {
        background: var(--primary) !important;
        color: white !important;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 1px;
        padding: 1.25rem !important;
    }
    
    .dataframe tbody tr:hover {
        background-color: var(--bg-light) !important;
    }
    
    /* INFO BOXES */
    .stAlert {
        border-radius: 12px;
        border-left: 5px solid var(--secondary);
    }
    
    /* TABS */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 12px 12px 0 0;
        padding: 1rem 2rem;
        font-weight: 600;
    }


    /* SIDEBAR - CONTROLS */
    section[data-testid="stSidebar"] .stSelectbox > div > div,
    section[data-testid="stSidebar"] .stTextInput > div > div {
        background: rgba(255,255,255,0.12) !important;
        border: 1px solid rgba(255,255,255,0.18) !important;
        border-radius: 12px !important;
        color: white !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stTextInput label {
        color: rgba(255,255,255,0.9) !important;
        font-weight: 700;
    }

    /* SIDEBAR - RADIO MENU (nav style) */
    /* Nota: Streamlit wrappa il testo del radio in tag diversi (p/span).
       Forziamo il bianco per il menu laterale come richiesto. */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: rgba(255,255,255,0.92) !important;
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 0;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        width: 100%;
        display: flex;
        align-items: center;
        background: transparent;
        border: none;
        margin: 0;
        padding: 0.65rem 0.75rem;
        border-radius: 0;
        border-left: 3px solid transparent;
        border-bottom: 1px solid rgba(255,255,255,0.18);
        transition: background 0.18s ease, border-left-color 0.18s ease;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:last-child {
        border-bottom: none;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background: rgba(255,255,255,0.08);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background: rgba(255,255,255,0.14);
        border-left-color: rgba(255,255,255,0.85);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label span,
    section[data-testid="stSidebar"] div[role="radiogroup"] > label p {
        color: rgba(255,255,255,0.92) !important;
        font-weight: 650;
        margin: 0;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) span,
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
        color: #ffffff !important;
        font-weight: 800;
    }

    /* RESPONSIVE */
    @media (max-width: 992px) {
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        .page-header { padding: 1.25rem; border-radius: 14px; }
        .page-title { font-size: 1.9rem; }
        .page-subtitle { font-size: 1rem; }
        .metric-card { padding: 1.25rem; border-radius: 14px; margin-bottom: 0.75rem; }
        .metric-value { font-size: 2.2rem; }
        .stTabs [data-baseweb="tab"] { padding: 0.75rem 1rem; }
    }
    @media (max-width: 768px) {
        .page-title { font-size: 1.6rem; }
        .metric-value { font-size: 2rem; }
        section[data-testid="stSidebar"] { width: 88vw !important; }
    }
</style>
""", unsafe_allow_html=True)

# ========== DB INIT ==========
@st.cache_resource
def get_database():
    cfg = load_config()
    base_dir = (cfg.get("base_dir") or "").strip()
    
    candidates = []
    if base_dir:
        bd = Path(base_dir)
        candidates += [
            bd / "persgest_master.xlsx",
            bd / "data" / "persgest_master.xlsx",
        ]
    
    candidates += [
        Path('data/persgest_master.xlsx'),
        Path('../data/persgest_master.xlsx'),
        Path('persgest_master.xlsx')
    ]
    
    for p in candidates:
        try:
            if p.exists():
                return PersGestDatabase(str(p))
        except:
            continue
    
    return PersGestDatabase('data/persgest_master.xlsx')

db = get_database()

# ========== SEED FESTIVI (se tabella vuota) ==========
try:
    fest = db.get_all('Festivi')
    if fest is None or len(fest) == 0:
        fest_path = Path(__file__).parent / 'data' / 'FestiviItalia.xlsx'
        if fest_path.exists():
            df_f = pd.read_excel(fest_path)
            # normalizza come in import
            df_f = df_f.rename(columns={c: str(c).strip() for c in df_f.columns})
            col_map = {}
            for c in df_f.columns:
                lc = str(c).strip().lower()
                if lc in ('giornofestivo','giorno_festivo','mmdd','data','giorno'):
                    col_map[c] = 'GiornoFestivo'
                elif lc in ('descrizione','desc','festa','festivo'):
                    col_map[c] = 'Descrizione'
                elif lc in ('localita','località','luogo'):
                    col_map[c] = 'Localita'
            df_f = df_f.rename(columns=col_map)
            keep = [c for c in ['GiornoFestivo','Descrizione','Localita'] if c in df_f.columns]
            df_f = df_f[keep].copy()
            if 'GiornoFestivo' in df_f.columns:
                df_f['GiornoFestivo'] = pd.to_numeric(df_f['GiornoFestivo'], errors='coerce').astype('Int64')
            if 'Descrizione' in df_f.columns:
                df_f['Descrizione'] = df_f['Descrizione'].fillna('').astype(str).str.strip()
            if 'Localita' in df_f.columns:
                df_f['Localita'] = df_f['Localita'].fillna('').astype(str).str.strip()
            df_f = df_f.dropna(how='all')
            df_f = df_f[df_f.get('GiornoFestivo').notna()] if 'GiornoFestivo' in df_f.columns else df_f
            db.save_table('Festivi', df_f)
except Exception:
    pass


# ========== SESSION STATE ==========
if 'page' not in st.session_state:
    st.session_state.page = 'Dashboard'

# ========== SIDEBAR ==========

def _set_page_from_nav():
    sel = st.session_state.get('nav_page')
    if sel:
        st.session_state.page = sel

# Sidebar: logo + filtri + navigazione compatta (miglior UX)
with st.sidebar:
    st.markdown(
        """
        <div class="company-logo">
            <div class="company-name">🏢 PersGest</div>
            <div class="company-tagline">Enterprise HRM</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Filtri relazionali (collassabili per migliore UX su schermi piccoli) ---
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    with st.expander('🔗 Filtri relazionali', expanded=True):
        reg = get_person_registry()
        uo_opts = ['Tutte']
        if len(reg) > 0 and 'uo' in reg.columns:
            uo_vals = sorted([x for x in reg['uo'].dropna().astype(str).unique().tolist() if x.strip()])
            uo_opts += uo_vals
        st.session_state.filter_uo = st.selectbox('🏭 Unità Operativa (UO)', uo_opts, key='flt_uo')

        cat_opts = ['Tutte']
        if len(reg) > 0 and 'cat' in reg.columns:
            cat_vals = sorted([x for x in reg['cat'].dropna().astype(str).unique().tolist() if x.strip()])
            cat_opts += cat_vals
        st.session_state.filter_cat = st.selectbox('🏷️ Categoria (CatProfTipo)', cat_opts, key='flt_cat')

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # --- Navigazione: radio stile “menu” con evidenza pagina attiva ---
    pages = [
        'Dashboard',
        'Calendario Crosstab',
        'Conteggi Turni Crosstab',
        'Specializzazioni Personale',
        'Controllo WE liberi',
        'Report Straordinari',
        'Festivi',
        'Verifica Match',
        'Editor Dati',
        'Import Export',
        'Configurazione',
    ]
    labels = {
        'Dashboard': '📈 Dashboard',
        'Calendario Crosstab': '🗓️ Calendario Crosstab',
        'Conteggi Turni Crosstab': '🧮 Conteggi Turni',
        'Specializzazioni Personale': '🎯 Specializzazioni',
        'Controllo WE liberi': '🧭 Controllo WE liberi',
        'Report Straordinari': '⏰ Report Straordinari',
        'Verifica Match': '🔍 Verifica Match',
        'Editor Dati': '✏️ Editor Dati',
        'Import Export': '📥 Import/Export',
        'Configurazione': '⚙️ Configurazione',
        'Festivi': '🎉 Festivi',

    }

    if 'page' not in st.session_state:
        st.session_state.page = 'Dashboard'

    # sincronizza selezione iniziale
    if 'nav_page' not in st.session_state:
        st.session_state.nav_page = st.session_state.page

    st.markdown('### 📌 Menu')
    st.radio(
        label='Menu',
        options=pages,
        key='nav_page',
        label_visibility='collapsed',
        on_change=_set_page_from_nav,
        format_func=lambda p: labels.get(p, p),
    )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div style="text-align:center; padding:0.75rem 0.25rem; color:rgba(255,255,255,0.65); font-size:0.75rem;">
            <div>📍 {db.excel_path.name}</div>
            <div style="margin-top:0.35rem;">v7.0 Enterprise</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# mantieni page coerente quando si usa st.session_state.page altrove
if st.session_state.get('nav_page') != st.session_state.get('page'):
    st.session_state.nav_page = st.session_state.get('page', 'Dashboard')
# ========== PAGES ==========

# ===== DASHBOARD =====
if st.session_state.page == 'Dashboard':
    st.markdown("""
    <div class="page-header">
        <div class="page-title">📊 Dashboard Generale</div>
        <div class="page-subtitle">Panoramica sistema di gestione risorse umane</div>
    </div>
    """, unsafe_allow_html=True)
    
    stats = db.get_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{stats.get('Attivita', 0):,}</div>
            <div class="metric-label">Attività</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{stats.get('Personale', 0):,}</div>
            <div class="metric-label">Dipendenti</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{stats.get('Straordinario', 0):,}</div>
            <div class="metric-label">Straordinari</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        total = sum(stats.values())
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total:,}</div>
            <div class="metric-label">Record Totali</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("### 💾 Database - Dettaglio Tabelle")
    
    categorie = {
        "📋 Principali": ['Attivita', 'Personale', 'Straordinario', 'Ripo'],
        "🏖️ Assenze": ['Ferie_AP', 'Ferie_Godute', 'Malattia', 'Infortunio', 'Maternita'],
        "📝 Altre": ['Permesso', 'Aspettativa', 'Congedo', 'Sciopero', 'Altro_Assenza'],
        "🎓 Attività": ['Formazione', 'Missione', 'Smart_Working', 'Note']
    }
    
    for cat, tables in categorie.items():
        with st.expander(f"{cat} ({len(tables)} tabelle)", expanded=(cat == "📋 Principali")):
            cols = st.columns(4)
            for idx, table in enumerate(tables):
                with cols[idx % 4]:
                    count = stats.get(table, 0)
                    st.metric(table, f"{count:,}")

# ===== REPORT STRAORDINARI =====
elif st.session_state.page == 'Report Straordinari':
    st.markdown("""
    <div class="page-header">
        <div class="page-title">⏰ Report Straordinari</div>
        <div class="page-subtitle">Analisi ore straordinarie (valori convertiti da MINUTI a ORE)</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🔍 Filtri")
    col1, col2, col3, col4 = st.columns([2,2,2,1])
    
    straordinari = db.get_all('Straordinario')
    personale = db.get_all('Personale')
    # Attivita: serve per estrarre straordinari importati da GT (STR/RPD/RPN con minuti>0)
    attivita = db.get_all('Attivita')
    
    # Normalizza matricole per merge
    if len(personale) > 0 and 'matricola' in personale.columns:
        personale_clean = personale.copy()
        personale_clean['matricola'] = personale_clean['matricola'].astype(str).str.strip()
    else:
        personale_clean = personale.copy()
    
    if len(straordinari) > 0 and 'matricola' in straordinari.columns:
        straordinari['matricola'] = straordinari['matricola'].astype(str).str.strip()
    
    with col1:
        # Lista persone in logica relazionale (Nome ↔ Matricola), filtrata per UO/Categoria
        reg = get_person_registry()
        uo_sel = st.session_state.get('filter_uo', 'Tutte')
        cat_sel = st.session_state.get('filter_cat', 'Tutte')
        if len(reg) > 0:
            if uo_sel != 'Tutte':
                reg = reg[reg['uo'].fillna('') == uo_sel]
            if cat_sel != 'Tutte':
                reg = reg[reg['cat'].fillna('') == cat_sel]
            persone_list = ['Tutti'] + sorted(reg['nome'].dropna().astype(str).unique().tolist())
        else:
            persone_list = ['Tutti']
        # mapping Nome -> Matricola (serve per filtro persona)
        persona_mappa = {}
        if len(reg) > 0 and ('nome' in reg.columns) and ('matricola' in reg.columns):
            persona_mappa = dict(
                zip(
                    reg['nome'].fillna('').astype(str).str.strip().tolist(),
                    reg['matricola'].fillna('').astype(str).str.strip().tolist(),
                )
            )
        persona_sel = st.selectbox("👤 Persona", persone_list, key="str_pers")
    
    with col2:
        oggi = datetime.now()
        primo = datetime(oggi.year, oggi.month, 1)
        # Date picker (calendario popup) + formato dd/mm/yyyy
        di_date = st.date_input('📅 Inizio', value=primo.date(), format="DD/MM/YYYY", key='str_di_date')
        data_inizio = datetime.combine(di_date, datetime.min.time())
    
    with col3:
        if oggi.month == 12:
            ultimo = datetime(oggi.year, 12, 31)
        else:
            ultimo = datetime(oggi.year, oggi.month + 1, 1) - timedelta(days=1)
        df_date = st.date_input('📅 Fine', value=ultimo.date(), format="DD/MM/YYYY", key='str_df_date')
        data_fine = datetime.combine(df_date, datetime.min.time())

    # Range datetime usato sia per Straordinari (tabella) che per OT da Attivita (GT)
    d0 = pd.to_datetime(data_inizio)
    d1 = pd.to_datetime(data_fine)
    
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        genera = st.button("🔍 GENERA", type="primary", width="stretch")
    
    if genera:
        if (straordinari is None or len(straordinari) == 0) and (attivita is None or len(attivita) == 0):
            st.warning("Nessun dato in tabelle Straordinario / Attivita.")
        else:
            # --- Manuale (tabella Straordinario) ---
            manual = straordinari.copy() if straordinari is not None else pd.DataFrame()
            if len(manual) > 0:
                manual['matricola'] = manual['matricola'].astype(str).str.strip()
                manual['data'] = pd.to_datetime(manual['data'], errors='coerce', dayfirst=True)
                manual = manual[manual['data'].notna()].copy()

                # Filtri relazionali globali (UO/CAT) via Personale
                manual = apply_relational_filters(manual, uo_sel, cat_sel)

                # Filtro persona specifica
                if persona_sel != "Tutti":
                    mat = persona_mappa.get(persona_sel, None)
                    if mat:
                        manual = manual[manual['matricola'] == str(mat)].copy()

            # Date range (d0/d1 già calcolati sopra)
            if len(manual) > 0:
                manual = manual[(manual['data'] >= d0) & (manual['data'] <= d1)].copy()

            # Ore manuali (valore in minuti -> minuti + ore float)
            if len(manual) > 0 and 'valore' in manual.columns:
                manual['minuti'] = series_to_numeric(manual['valore']).fillna(0).astype(float)
                manual['ore'] = manual['minuti'].map(minuti_to_ore_float)
            else:
                manual['minuti'] = 0.0
                manual['ore'] = 0.0
            manual['_is_gt_ot'] = False

            # --- GT (tabella Attivita: STR / RPD / RPN con minuti>0) ---
            gt = pd.DataFrame(columns=['matricola','data','turno','minuti','ore','_is_gt_ot'])
            if attivita is not None and len(attivita) > 0:
                att = attivita.copy()

                # Filtri relazionali globali (UO/CAT)
                att = apply_relational_filters(att, uo_sel, cat_sel)

                # Filtro persona specifica
                if persona_sel != "Tutti":
                    mat = persona_mappa.get(persona_sel, None)
                    if mat and 'matricola' in att.columns:
                        att = att[att['matricola'].astype(str).str.strip() == str(mat)].copy()

                # Date range (prima dell'estrazione)
                if 'data' in att.columns:
                    att['data'] = pd.to_datetime(att['data'], errors='coerce', dayfirst=True)
                    att = att[att['data'].notna()].copy()
                    att = att[(att['data'] >= d0) & (att['data'] <= d1)].copy()

                gt = extract_gt_overtime(att)

            # --- Combina (Manuale + GT) ---
            combined = pd.concat([
                manual[['matricola','data','turno','minuti','ore','_is_gt_ot']].copy() if len(manual) > 0 else pd.DataFrame(columns=['matricola','data','turno','minuti','ore','_is_gt_ot']),
                gt[['matricola','data','turno','minuti','ore','_is_gt_ot']].copy() if len(gt) > 0 else pd.DataFrame(columns=['matricola','data','turno','minuti','ore','_is_gt_ot'])
            ], ignore_index=True)

            if len(combined) == 0:
                st.info("Nessuno straordinario trovato nel periodo selezionato (Manuale + GT).")
            else:
                # join nome
                pers = personale.copy() if personale is not None else pd.DataFrame()
                if len(pers) > 0:
                    pers['matricola'] = pers['matricola'].astype(str).str.strip()
                    pers['nome'] = pers['nome'].astype(str).str.strip()
                    combined = combined.merge(pers[['matricola','nome']], on='matricola', how='left')
                else:
                    combined['nome'] = combined.get('matricola', '').astype(str)

                # ===== RIEPILOGO =====
                tot_rec = len(combined)
                tot_gg = combined['data'].dt.date.nunique()
                tot_minuti = combined['minuti'].sum()
                media_minuti = (tot_minuti / tot_gg) if tot_gg else 0

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("RECORD", tot_rec)
                with c2:
                    st.metric("GIORNI", tot_gg)
                with c3:
                    st.metric("TOTALE ORE", format_minuti(tot_minuti))
                with c4:
                    st.metric("MEDIA/GG", format_minuti(media_minuti))

                st.markdown("---")

                # ===== PER PERSONA =====
                st.subheader("👥 Per Persona")
                agg = combined.groupby(['nome','matricola'], as_index=False).agg(
                    giorni=('data', lambda s: pd.Series(s.dt.date).nunique()),
                    minuti=('minuti','sum')
                )
                agg['media_minuti'] = agg.apply(lambda r: (r['minuti']/r['giorni']) if r['giorni'] else 0, axis=1)
                agg = agg.sort_values(['minuti','nome'], ascending=[False, True])

                agg_view = agg.copy()
                agg_view['Ore'] = agg_view['minuti'].map(format_minuti)
                agg_view['Media'] = agg_view['media_minuti'].map(format_minuti)
                st.dataframe(agg_view[['nome','matricola','giorni','Ore','Media']].rename(columns={'nome':'Nome','matricola':'Matricola','giorni':'Giorni'}), use_container_width=True, hide_index=True)

                st.markdown("---")

                # ===== DETTAGLIO GIORNALIERO =====
                st.subheader("📅 Dettaglio Giornaliero")
                det = combined.sort_values(['data','nome'], ascending=[False, True]).copy()
                det['Data'] = det['data'].dt.strftime("%d/%m/%Y")
                det.loc[det['_is_gt_ot'] == True, 'Data'] = det.loc[det['_is_gt_ot'] == True, 'Data'] + " OT"
                det['Ore'] = det['minuti'].map(format_minuti)

                det_view = det[['Data','nome','matricola','turno','Ore']].rename(columns={
                    'nome':'Nome',
                    'matricola':'Matricola',
                    'turno':'Turno'
                })
                st.dataframe(det_view, use_container_width=True, hide_index=True)

                csv = det_view.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Scarica CSV", data=csv, file_name="report_straordinari_plus_gt.csv", mime="text/csv")

# ===== VERIFICA MATCH =====
elif st.session_state.page == 'Verifica Match':
    st.markdown("""
    <div class="page-header">
        <div class="page-title">🔍 Verifica Match GT-Straordinari</div>
        <div class="page-subtitle">Controllo corrispondenza dati</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,1,2])
    with col1:
        oggi = datetime.now()
        mese = st.selectbox("📅 Mese", 
                           ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
                            'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'],
                           index=oggi.month - 1, key="match_mese")
    with col2:
        anno = st.number_input("Anno", min_value=2020, max_value=2030, value=oggi.year, key="match_anno")
    
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        verifica = st.button("🔍 VERIFICA", type="primary", width="stretch")
    
    if verifica:
        straordinari = db.get_all('Straordinario')
        attivita = db.get_all('Attivita')
        personale = db.get_all('Personale')
        
        # Check se tabelle hanno dati
        if len(straordinari) == 0 or len(attivita) == 0:
            st.warning("⚠️ Tabelle Straordinario o Attivita vuote. Importa prima i dati.")
        else:
            # Straordinario: 'valore' puo' essere minuti o gia' ore (o stringa tipo '8.00h')
            if 'valore' in straordinari.columns:
                v = series_to_numeric(straordinari['valore'])
                med = float(v.dropna().median()) if v.notna().any() else 0.0
                # se mediana > 24 presumiamo minuti, altrimenti ore
                if med > 24:
                    straordinari['ore'] = v.fillna(0.0).apply(minuti_to_ore)
                else:
                    straordinari['ore'] = v.fillna(0.0)
            else:
                st.error("❌ Colonna 'valore' non trovata in Straordinario")
                st.stop()
            
            # Attivita: calcolo ore robusto ("minuti" potrebbe esistere ma essere vuoto)
            def _find_col(df: pd.DataFrame, candidates):
                cols = list(df.columns)
                low = [str(c).strip().lower() for c in cols]
                for cand in candidates:
                    # match esatto
                    if cand in low:
                        return cols[low.index(cand)]
                # match per sottostringa
                for i, c in enumerate(low):
                    for cand in candidates:
                        if cand in c:
                            return cols[i]
                return None

            def _calc_attivita_ore(df: pd.DataFrame) -> pd.Series:
                # 1) prova minuti se contiene dati sensati (accetta varianti di nome colonna)
                col_min = _find_col(df, ['minuti', 'minuto', 'minutes', 'mins', 'valore_minuti', 'valore (minuti)'])
                if col_min is not None:
                    m = series_to_numeric(df[col_min])
                    m_valid = m.dropna()
                    # consideriamo valido se almeno un valore > 0
                    if len(m_valid) > 0 and float(m_valid.fillna(0.0).sum()) > 0:
                        return (m.fillna(0.0) / 60.0).round(2)
                # 2) fallback su valore (puo' essere minuti, ore, o stringa "8.00h")
                col_val = _find_col(df, ['valore', 'value', 'ore', 'hours'])
                if col_val is not None:
                    v = series_to_numeric(df[col_val])
                    v_valid = v.dropna()
                    med = float(v_valid.median()) if len(v_valid) else 0.0
                    # se valori grandi => minuti
                    if med > 24:
                        return v.fillna(0.0).apply(minuti_to_ore)
                    # se sembra ore (0-24)
                    return v.fillna(0.0)

                # 3) ultima spiaggia: auto-detect della colonna minuti (utile se import headerless ha mappato male)
                exclude = set([c for c in df.columns if str(c).strip().lower() in (
                    'matricola','nome','cognome','cognome e nome','cognome_e_nome','uo','unità operativa','unita operativa',
                    'turno','att','attivita','attività','pox','data','_data_key'
                )])
                best_col = None
                best_score = -1.0
                for c in df.columns:
                    if c in exclude:
                        continue
                    s = series_to_numeric(df[c])
                    s = s.replace([np.inf, -np.inf], np.nan)
                    s_valid = s.dropna()
                    # la colonna minuti potrebbe essere "sparsa" (solo alcune attivita): accetta anche poche righe
                    if len(s_valid) < max(3, int(len(df)*0.01)):
                        continue
                    med = float(s_valid.median())
                    mx = float(s_valid.max())
                    # minuti tipici: 15..900 (max comunque <= 2000)
                    if mx <= 0 or mx > 2000:
                        continue
                    frac = len(s_valid) / max(1, len(df))
                    band = 1.0 if (med >= 30 and med <= 900) else 0.2
                    # premia valori tipici minuti anche se sparsi
                    score = (0.2 + frac) * band
                    if score > best_score:
                        best_score = score
                        best_col = c
                if best_col is not None:
                    m = series_to_numeric(df[best_col]).fillna(0.0)
                    return (m / 60.0).round(2)
                raise KeyError("minuti/valore")

            try:
                attivita['ore'] = _calc_attivita_ore(attivita)
            except KeyError:
                st.error("❌ Colonne 'minuti'/'valore' non trovate in Attivita")
                st.stop()

            # Converti mese nome in numero
            mesi_dict = {'Gennaio': 1, 'Febbraio': 2, 'Marzo': 3, 'Aprile': 4, 'Maggio': 5, 'Giugno': 6,
                        'Luglio': 7, 'Agosto': 8, 'Settembre': 9, 'Ottobre': 10, 'Novembre': 11, 'Dicembre': 12}
            mese_num = mesi_dict[mese]
            
            # Filtra per periodo (anno-mese) - date dd/mm/yyyy
            straordinari['data'] = pd.to_datetime(straordinari['data'], errors='coerce', dayfirst=True)
            attivita['data'] = pd.to_datetime(attivita['data'], errors='coerce', dayfirst=True)
            # normalizza chiavi per match
            if 'matricola' in straordinari.columns:
                straordinari['matricola'] = straordinari['matricola'].astype(str).str.strip()
            if 'matricola' in attivita.columns:
                attivita['matricola'] = attivita['matricola'].astype(str).str.strip()
            # usa solo la data (senza orario) per evitare mismatch Timestamp
            straordinari['_data_key'] = straordinari['data'].dt.date
            attivita['_data_key'] = attivita['data'].dt.date
            str_filt = straordinari[(straordinari['data'].dt.year == int(anno)) & (straordinari['data'].dt.month == int(mese_num))]
            att_filt = attivita[(attivita['data'].dt.year == int(anno)) & (attivita['data'].dt.month == int(mese_num))]

            # Applica filtri relazionali (UO/Categoria) anche in match
            uo_sel = st.session_state.get('filter_uo', 'Tutte')
            cat_sel = st.session_state.get('filter_cat', 'Tutte')
            str_filt = apply_relational_filters(str_filt, uo_sel, cat_sel)
            att_filt = apply_relational_filters(att_filt, uo_sel, cat_sel)
            perfetti = []
            discrepanze = []

            # Registro persone (Nome↔Matricola) anche se non importi Personale
            reg = get_person_registry()
            reg_map = {}
            if len(reg) > 0 and 'matricola' in reg.columns and 'nome' in reg.columns:
                reg_map = dict(zip(reg['matricola'].astype(str).str.strip(), reg['nome'].astype(str).str.strip()))

            # Mappa ore attese per TURNO (da Turni_tipo o stima)
            shift_hours = get_shift_hours_map(att_filt)
            TOL = 0.05  # ~3 minuti

            for _, s in str_filt.iterrows():
                matr = str(s.get('matricola', '')).strip()
                turno = str(s.get('turno', '')).strip().upper()
                data_s = s.get('data')

                # confronto data su solo giorno (evita mismatch per eventuali timestamp)
                ds = pd.to_datetime(data_s, errors='coerce')
                d_day = ds.date() if pd.notna(ds) else None
                att_tmp = att_filt.copy()
                att_tmp['_day'] = pd.to_datetime(att_tmp['data'], errors='coerce', dayfirst=True).dt.date
                match = att_tmp[(att_tmp['matricola'] == matr) & (att_tmp['_day'] == d_day) & (att_tmp['turno'].astype(str).str.strip().str.upper() == turno)]

                if len(match) > 0:
                    ore_gt_tot = float(pd.to_numeric(match['ore'], errors='coerce').fillna(0.0).sum())
                    ore_str = float(s.get('ore', 0.0) or 0.0)
                    ore_attese = shift_hours.get(turno)

                    ok_turno_gt = True
                    if ore_attese is not None and ore_attese > 0:
                        ok_turno_gt = abs(ore_gt_tot - ore_attese) <= TOL

                    ok_str_gt = abs(ore_str - ore_gt_tot) <= TOL

                    if ok_turno_gt and ok_str_gt:
                        perfetti.append({
                            'data': data_s,
                            'nome': reg_map.get(matr, matr),
                            'matricola': matr,
                            'turno': turno,
                            'ore_str': ore_str,
                            'ore_gt': ore_gt_tot,
                            'ore_attese': ore_attese,
                            'coerente': True
                        })
                    else:
                        if (ore_attese is not None and ore_attese > 0) and (not ok_turno_gt):
                            problema = f"Ore turno GT non coerenti (attese {ore_attese:.2f}h)"
                        elif not ok_str_gt:
                            problema = "Ore STR diverse da Ore GT"
                        else:
                            problema = "Match non coerente"
                        discrepanze.append({
                            'data': data_s,
                            'nome': reg_map.get(matr, matr),
                            'matricola': matr,
                            'turno': turno,
                            'ore_str': ore_str,
                            'ore_gt': ore_gt_tot,
                            'ore_attese': ore_attese,
                            'problema': problema
                        })
                else:
                    any_match = att_filt[(att_filt['matricola'] == matr) & (att_filt['data'] == data_s)]
                    prob = "Turno diverso" if len(any_match) > 0 else "Nessuna attività GT"
                    discrepanze.append({
                        'data': data_s,
                        'nome': reg_map.get(matr, matr),
                        'matricola': matr,
                        'turno': turno,
                        'ore_str': float(s.get('ore', 0.0) or 0.0),
                        'ore_gt': 0.0,
                        'ore_attese': shift_hours.get(turno),
                        'problema': prob
                    })

            # Riepilogo
            st.markdown("---")
            st.markdown("### 📊 Riepilogo")
            
            col1, col2, col3, col4 = st.columns(4)
            
            tot_str = len(str_filt)
            tot_match = len(perfetti)
            tot_disc = len(discrepanze)
            perc = (tot_match / tot_str * 100) if tot_str > 0 else 0
            
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{tot_str}</div>
                    <div class="metric-label">Tot STR</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="metric-card" style="border-left-color: var(--success);">
                    <div class="metric-value" style="color: var(--success);">{tot_match}</div>
                    <div class="metric-label">Match</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="metric-card" style="border-left-color: var(--danger);">
                    <div class="metric-value" style="color: var(--danger);">{tot_disc}</div>
                    <div class="metric-label">Discrepanze</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                color = "var(--success)" if perc >= 95 else "var(--warning)" if perc >= 80 else "var(--danger)"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value" style="color: {color};">{perc:.1f}%</div>
                    <div class="metric-label">% Match</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Normalizza matricole per merge (rimuovi spazi, converti a str)
            if len(personale) > 0 and 'matricola' in personale.columns:
                personale_clean = personale.copy()
                personale_clean['matricola'] = personale_clean['matricola'].astype(str).str.strip()
            # Match (coerenti)
            st.markdown("---")
            st.markdown("### ✅ Match Coerenti")
            if perfetti:
                df_p = pd.DataFrame(perfetti)
                # formato data
                df_p['Data'] = pd.to_datetime(df_p['data'], errors='coerce', dayfirst=True).dt.strftime('%d/%m/%Y')
                df_p['Nome'] = df_p.get('nome', df_p.get('matricola', '')).astype(str)
                df_p['Matr'] = df_p.get('matricola', '').astype(str)
                df_p['Turno'] = df_p.get('turno', '').astype(str)
                df_p['Ore Attese'] = df_p.get('ore_attese').apply(lambda x: format_ore(x) if pd.notna(x) else "")
                df_p['Ore STR'] = df_p.get('ore_str', 0.0).apply(format_ore)
                df_p['Ore GT'] = df_p.get('ore_gt', 0.0).apply(format_ore)
                df_p['Esito'] = "OK"

                df_p = df_p[['Data', 'Nome', 'Matr', 'Turno', 'Ore Attese', 'Ore STR', 'Ore GT', 'Esito']]
                st.dataframe(df_p.head(500), width="stretch", hide_index=True)
            else:
                st.info("Nessun match coerente")

            # Discrepanze
# Discrepanze
            st.markdown("---")
            st.markdown("### ⚠️ Discrepanze")
            if discrepanze:
                df_d = pd.DataFrame(discrepanze)
                df_d['Data'] = pd.to_datetime(df_d['data'], errors='coerce', dayfirst=True).dt.strftime('%d/%m/%Y')
                df_d['Nome'] = df_d.get('nome', df_d.get('matricola', '')).astype(str)
                df_d['Matr'] = df_d.get('matricola', '').astype(str)
                df_d['Turno'] = df_d.get('turno', '').astype(str)
                df_d['Ore Attese'] = df_d.get('ore_attese').apply(lambda x: format_ore(x) if pd.notna(x) else "")
                df_d['Ore STR'] = df_d.get('ore_str', 0.0).apply(format_ore)
                df_d['Ore GT'] = df_d.get('ore_gt', 0.0).apply(format_ore)
                df_d['Problema'] = df_d.get('problema', '').astype(str)

                df_d = df_d[['Data', 'Nome', 'Matr', 'Turno', 'Ore Attese', 'Ore STR', 'Ore GT', 'Problema']]
                st.dataframe(df_d.head(1000), width="stretch", hide_index=True)
            else:
                st.success("🎉 100% match!")


# ===== EDITOR =====
elif st.session_state.page == 'Editor Dati':
    st.markdown("""
    <div class="page-header">
        <div class="page-title">✏️ Editor Dati</div>
        <div class="page-subtitle">Modifica record (⚠️ campo 'valore' in MINUTI)</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1,2])
    
    with col1:
        # ✅ Mostra TUTTE le tabelle presenti nel DB (incluse quelle "parametriche" generate).
        tabs = list(db.TABLES)

        # Filtri utili per liste lunghe
        only_nonempty = st.checkbox("Solo tabelle con record", value=False, key="edit_only_nonempty")
        if only_nonempty:
            stats = db.get_stats()
            tabs = [t for t in tabs if stats.get(t, 0) > 0]

        tab_search = st.text_input("🔎 Cerca tabella", value="", placeholder="Es. CatProfTipo, Turni...", key="edit_tab_search")
        if tab_search:
            q = tab_search.strip().lower()
            tabs = [t for t in tabs if q in t.lower()]

        # Default: Attivita se presente
        options = ['-- Seleziona --'] + tabs
        default_idx = 0
        if 'Attivita' in tabs:
            default_idx = options.index('Attivita')
        tab_sel = st.selectbox("📋 Tabella", options, index=default_idx, key="edit_tab")
    
    if tab_sel != '-- Seleziona --':
        df = db.get_all(tab_sel)
        st.info(f"📊 **{tab_sel}** - {len(df):,} record | ⚠️ 'valore' in MINUTI (60=1h)")
        
        with col2:
            search = st.text_input("🔍 Ricerca", placeholder="Cerca...", key="edit_srch")
        
        if search:
            mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
            df = df[mask]

        # Filtro date range (solo per Straordinario)
        if tab_sel == 'Straordinario' and 'data' in df.columns:
            with col2:
                d1, d2 = st.columns(2)
                # Calendario popup (evita anche l'autofill del browser)
                use_da = d1.checkbox('Da', value=False, key='edit_str_da_on')
                da_date = d1.date_input('📅 Da', value=date.today(), format="DD/MM/YYYY", key='edit_str_da_date', disabled=not use_da)
                use_a = d2.checkbox('A', value=False, key='edit_str_a_on')
                a_date = d2.date_input('📅 A', value=date.today(), format="DD/MM/YYYY", key='edit_str_a_date', disabled=not use_a)
            if use_da or use_a:
                sdt = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
                mask = pd.Series(True, index=df.index)
                if use_da:
                    da = datetime.combine(da_date, datetime.min.time())
                    mask &= (sdt >= pd.to_datetime(da))
                if use_a:
                    a = datetime.combine(a_date, datetime.min.time())
                    mask &= (sdt <= pd.to_datetime(a))
                df = df.loc[mask]

        st.caption(f"Visualizzati: {len(df):,} (max 100)")

        # --- Display-only formatting ---
        # Mostra sempre la data in formato gg/mm/aaaa (senza orario)
        df_head = df.head(100).copy()

        # Colonna selezione record direttamente dalla tabella (per Modifica/Elimina)
        sel_state_key = f"crud_sel_idx_{tab_sel}"

        def _norm_idx(x):
            """Normalizza un indice (gestisce numpy/pandas scalari) per confronti coerenti."""
            if x is None:
                return None
            try:
                if hasattr(x, 'item') and callable(getattr(x, 'item')):
                    x = x.item()
            except Exception:
                pass
            try:
                return int(x)
            except Exception:
                return str(x)

        # Reset index per evitare warning Streamlit (hide_index + num_rows='dynamic')
        # Manteniamo un mapping alle chiavi originali per la selezione CRUD.
        orig_idx = list(df_head.index)
        df_show = df_head.reset_index(drop=True)

        df_show.insert(0, '__sel__', False)
        prev_sel = _norm_idx(st.session_state.get(sel_state_key))
        if prev_sel is not None and prev_sel in orig_idx:
            try:
                row_pos = orig_idx.index(prev_sel)
                df_show.loc[row_pos, '__sel__'] = True
            except Exception:
                pass

        if 'data' in df_show.columns:
            df_show['data'] = pd.to_datetime(df_show['data'], errors='coerce', dayfirst=True).dt.strftime('%d/%m/%Y')

        edited = st.data_editor(
            df_show,
            width="stretch",
            num_rows="dynamic",
            hide_index=True,
            height=500,
            key=f"editor_{tab_sel}",
            column_config={
                '__sel__': st.column_config.CheckboxColumn('')
            }
        )

        # Se l'utente seleziona una riga tramite checkbox, sincronizza la selezione CRUD
        try:
            _prev_sel_for_sync = _norm_idx(st.session_state.get(sel_state_key))
            chosen = edited[edited['__sel__'] == True]
            if len(chosen) > 0:
                # Se più di una selezionata, prende l'ultima (più recente)
                sel_row_pos = int(list(chosen.index)[-1])
                sel_idx_table = _norm_idx(orig_idx[sel_row_pos]) if 0 <= sel_row_pos < len(orig_idx) else None
                st.session_state[sel_state_key] = sel_idx_table
                # Flag per sincronizzare anche la selectbox sottostante (fascia grigia)
                if _prev_sel_for_sync != sel_idx_table:
                    st.session_state[f"_crud_sel_changed_{tab_sel}"] = True
                if len(chosen) > 1:
                    st.info("ℹ️ Selezionate più righe: uso l'ultima selezionata per Modifica/Elimina.")
        except Exception:
            pass

        # ==========================
        # CRUD via popup (Nuovo / Modifica / Elimina)
        # ==========================

        # Selezione record (basata sugli indici reali del DataFrame nel DB)
        # Nota: per tabelle molto grandi usiamo solo un sottoinsieme per la selezione.
        cand = df.copy()
        if len(cand) > 5000:
            cand = cand.head(5000)

        label_cols = [c for c in [
            'matricola', 'nome', 'Nome', 'UO', 'uo', 'turno', 'att', 'data'
        ] if c in cand.columns]

        def _fmt_val(v):
            if pd.isna(v):
                return ""
            # date -> dd/mm/yyyy
            try:
                if isinstance(v, (pd.Timestamp, datetime, date)):
                    return pd.to_datetime(v, errors='coerce', dayfirst=True).strftime('%d/%m/%Y')
            except Exception:
                pass
            s = str(v)
            return s[:40] + ("…" if len(s) > 40 else "")

        record_options = []
        desired_idx = _norm_idx(st.session_state.get(sel_state_key))
        if len(cand) > 0:
            sample = cand.head(300)

            # Se l'utente ha selezionato una riga dalla tabella (checkbox),
            # assicura che compaia nelle opzioni anche se non e' nei primi 300.
            if desired_idx is not None and desired_idx in cand.index and desired_idx not in sample.index:
                try:
                    row = cand.loc[desired_idx]
                    parts = [f"#{desired_idx}"]
                    for c in label_cols:
                        parts.append(f"{c}:{_fmt_val(row.get(c))}")
                    record_options.append((" | ".join(parts), desired_idx))
                except Exception:
                    pass

            for idx, row in sample.iterrows():
                idx_n = _norm_idx(idx)
                parts = [f"#{idx_n}"]
                for c in label_cols:
                    parts.append(f"{c}:{_fmt_val(row.get(c))}")
                record_options.append((" | ".join(parts), idx_n))

        sel_label = None
        sel_idx = None
        if record_options:
            labels = [x[0] for x in record_options]
            label_to_idx = {lbl: idx for (lbl, idx) in record_options}
            idx_to_label = {idx: lbl for (lbl, idx) in record_options}

            crud_key = f"crud_sel_{tab_sel}"
            prev_desired = _norm_idx(st.session_state.get(f"_crud_sel_prev_idx_{tab_sel}"))
            desired_idx = _norm_idx(st.session_state.get(sel_state_key))

            # Se e' cambiata la selezione dalla tabella, forza l'aggancio della selectbox (fascia grigia)
            if desired_idx is not None and (st.session_state.get(f"_crud_sel_changed_{tab_sel}") or desired_idx != prev_desired):
                if desired_idx in idx_to_label:
                    st.session_state[crud_key] = idx_to_label[desired_idx]
                st.session_state[f"_crud_sel_prev_idx_{tab_sel}"] = desired_idx
                st.session_state.pop(f"_crud_sel_changed_{tab_sel}", None)

            # Index coerente con il valore in session_state
            if st.session_state.get(crud_key) in labels:
                pre_idx = labels.index(st.session_state.get(crud_key))
            else:
                # fallback: prova a pre-selezionare il record spuntato
                pre_idx = 0
                if desired_idx is not None and desired_idx in idx_to_label:
                    pre_idx = labels.index(idx_to_label[desired_idx])

            sel_label = st.selectbox(
                "Seleziona record (per Modifica/Elimina)",
                labels,
                index=pre_idx,
                key=crud_key
            )
            sel_idx = label_to_idx.get(sel_label)
            if sel_idx is not None:
                st.session_state[sel_state_key] = _norm_idx(sel_idx)

        def _infer_widget(col: str, series: pd.Series, value):
            """Ritorna (widget_value, widget_type) per un singolo campo."""
            cl = str(col).strip().lower()
            # Streamlit: se una chiave e' gia' presente in session_state NON passare anche
            # value/index/default al widget, altrimenti compare l'avviso:
            # "...created with a default value but also had its value set via Session State API."
            wkey = f"fld_{tab_sel}_{st.session_state.get('crud_mode','')}_{col}"
            has_state = wkey in st.session_state

            # ----------
            # Reference-driven dropdowns (UO / Turno / Categoria)
            # ----------
            # Usa le tabelle consolidate se presenti, invece di far digitare a mano.
            # (Il popolamento "a cascata" avviene nei dialog NEW/EDIT, vedi sotto.)
            try:
                if cl in ('uo', 'unità operativa', 'unita operativa', 'unita_operativa'):
                    uo_df = db.get_all('tbl_UO') if 'tbl_UO' in getattr(db, 'TABLES', []) else pd.DataFrame()
                    uo_col = None
                    if not uo_df.empty:
                        for c in uo_df.columns:
                            if str(c).strip().lower() in ('uo', 'unità operativa', 'unita operativa', 'codice', 'cod'):
                                uo_col = c
                                break
                        if uo_col is None:
                            uo_col = uo_df.columns[0]
                        opts = [str(x).strip() for x in uo_df[uo_col].dropna().astype(str).unique().tolist() if str(x).strip()]
                        opts = sorted(list(dict.fromkeys(opts)))
                        cur = '' if pd.isna(value) else str(value)
                        if cur and cur not in opts:
                            opts = [cur] + opts
                        if has_state:
                            cur_s = '' if pd.isna(st.session_state.get(wkey)) else str(st.session_state.get(wkey))
                            if cur_s and cur_s not in opts:
                                opts = [cur_s] + opts
                            return st.selectbox(col, opts if opts else [cur_s or cur], key=wkey), 'select'
                        idx = opts.index(cur) if cur in opts else 0
                        return st.selectbox(col, opts if opts else [cur], index=idx, key=wkey), 'select'
            except Exception:
                pass

            try:
                if cl in ('cat', 'categoria', 'catproftipo', 'cat_prof_tipo'):
                    cat_df = db.get_all('CatProfTipo') if 'CatProfTipo' in getattr(db, 'TABLES', []) else pd.DataFrame()
                    cat_col = None
                    if not cat_df.empty:
                        for c in cat_df.columns:
                            if str(c).strip().lower() in ('cat', 'categoria', 'catproftipo', 'codice', 'cod'):
                                cat_col = c
                                break
                        if cat_col is None:
                            cat_col = cat_df.columns[0]
                        opts = [str(x).strip() for x in cat_df[cat_col].dropna().astype(str).unique().tolist() if str(x).strip()]
                        opts = sorted(list(dict.fromkeys(opts)))
                        cur = '' if pd.isna(value) else str(value)
                        if cur and cur not in opts:
                            opts = [cur] + opts
                        if has_state:
                            cur_s = '' if pd.isna(st.session_state.get(wkey)) else str(st.session_state.get(wkey))
                            if cur_s and cur_s not in opts:
                                opts = [cur_s] + opts
                            return st.selectbox(col, opts if opts else [cur_s or cur], key=wkey), 'select'
                        idx = opts.index(cur) if cur in opts else 0
                        return st.selectbox(col, opts if opts else [cur], index=idx, key=wkey), 'select'
            except Exception:
                pass

            try:
                if cl == 'turno':
                    tdf = db.get_all('Turni_tipo') if 'Turni_tipo' in getattr(db, 'TABLES', []) else pd.DataFrame()
                    if not tdf.empty:
                        # Colonna codice turno
                        code_col = None
                        for c in tdf.columns:
                            if str(c).strip().lower() in ('turno', 'codice', 'cod'):
                                code_col = c
                                break
                        if code_col is None:
                            code_col = tdf.columns[0]
                        opts = [str(x).strip() for x in tdf[code_col].dropna().astype(str).unique().tolist() if str(x).strip()]
                        opts = sorted(list(dict.fromkeys(opts)))
                        cur = '' if pd.isna(value) else str(value)

                        # NEW UX: in creazione (value vuoto) non pre-selezionare il primo turno.
                        # Aggiungiamo opzione vuota per forzare la scelta esplicita.
                        if '' not in opts:
                            opts = [''] + opts

                        if cur and cur not in opts:
                            opts = [cur] + opts
                        if has_state:
                            cur_s = '' if pd.isna(st.session_state.get(wkey)) else str(st.session_state.get(wkey))
                            if cur_s and cur_s not in opts:
                                opts = [cur_s] + opts
                            return st.selectbox(col, opts if opts else [cur_s or cur], key=wkey), 'select'
                        idx = opts.index(cur) if cur in opts else 0
                        return st.selectbox(col, opts if opts else [cur], index=idx, key=wkey), 'select'
            except Exception:
                pass

            # Date
            if 'data' in cl or cl.endswith('_dt') or cl.endswith('_date'):
                dv = None
                try:
                    dv = pd.to_datetime(value, errors='coerce', dayfirst=True)
                    dv = dv.date() if pd.notna(dv) else None
                except Exception:
                    dv = None
                if has_state:
                    sv = st.session_state.get(wkey)
                    try:
                        if isinstance(sv, str) and sv.strip():
                            dt = pd.to_datetime(sv, errors='coerce', dayfirst=True)
                            if pd.notna(dt):
                                st.session_state[wkey] = dt.date()
                        elif isinstance(sv, datetime):
                            st.session_state[wkey] = sv.date()
                    except Exception:
                        pass
                    return st.date_input(col, format="DD/MM/YYYY", key=wkey), 'date'
                return st.date_input(col, value=dv, format="DD/MM/YYYY", key=wkey), 'date'

            # Numerico
            try:
                if pd.api.types.is_numeric_dtype(series):
                    nv = pd.to_numeric(value, errors='coerce')
                    nv = 0.0 if pd.isna(nv) else float(nv)
                    if has_state:
                        return st.number_input(col, step=1.0, key=wkey), 'number'
                    return st.number_input(col, value=nv, step=1.0, key=wkey), 'number'
            except Exception:
                pass

            # Se poche scelte -> selectbox
            try:
                uniq = series.dropna().astype(str).unique().tolist()
                if 0 < len(uniq) <= 25:
                    sv = "" if pd.isna(value) else str(value)
                    if sv not in uniq:
                        uniq = [sv] + uniq
                    if has_state:
                        cur_s = '' if pd.isna(st.session_state.get(wkey)) else str(st.session_state.get(wkey))
                        if cur_s and cur_s not in uniq:
                            uniq = [cur_s] + uniq
                        return st.selectbox(col, uniq, key=wkey), 'select'
                    return st.selectbox(col, uniq, index=max(0, uniq.index(sv)), key=wkey), 'select'
            except Exception:
                pass

            sv = "" if pd.isna(value) else str(value)
            if has_state:
                return st.text_input(col, key=wkey), 'text'
            return st.text_input(col, value=sv, key=wkey), 'text'

        # ----------
        # Helpers: lookups for cascata (Dipendente -> Matricola/UO/Cat..., Turno -> Minuti/Ore)
        # ----------
        def _get_people_registry() -> pd.DataFrame:
            """Registro persone coerente con i filtri relazionali globali (sidebar).

            Regola: se in sidebar e' selezionata una UO/Categoria specifica,
            qui devono comparire SOLO quei nominativi (e viceversa).
            """
            return get_person_meta_rel_filtered().copy()

        def _get_turni_minutes_map() -> dict:
            """Mappa turno -> minuti (se trovati in Turni_tipo)."""
            try:
                tdf = db.get_all('Turni_tipo') if 'Turni_tipo' in getattr(db, 'TABLES', []) else pd.DataFrame()
            except Exception:
                tdf = pd.DataFrame()
            if tdf.empty:
                return {}
            cols_l = {str(c).strip().lower(): c for c in tdf.columns}
            code_col = cols_l.get('turno') or cols_l.get('codice') or cols_l.get('cod') or (tdf.columns[0] if len(tdf.columns) else None)
            # minuti: preferisci colonna che contiene 'min'
            min_col = None
            for k, c in cols_l.items():
                if 'min' in k and pd.api.types.is_numeric_dtype(tdf[c]):
                    min_col = c
                    break
            if min_col is None:
                # prima colonna numerica
                for c in tdf.columns:
                    if pd.api.types.is_numeric_dtype(tdf[c]):
                        min_col = c
                        break
            if code_col is None or min_col is None:
                return {}
            m = {}
            for _, r in tdf.iterrows():
                k = str(r.get(code_col)).strip()
                if not k or k.lower() == 'nan':
                    continue
                v = pd.to_numeric(r.get(min_col), errors='coerce')
                if pd.isna(v):
                    continue
                m[k] = int(v)
            return m

        # Record selezionato: usa sempre lo stato persistente (checkbox/selectbox) per evitare
        # che alla pressione del bottone si perda la selezione e venga aperto il record #0.
        selected_idx = st.session_state.get(sel_state_key)
        if selected_idx is None:
            selected_idx = sel_idx

        crud_c1, crud_c2, crud_c3 = st.columns(3)

        with crud_c1:
            new_clicked = st.button("➕ Nuovo", width="stretch", key=f"crud_new_{tab_sel}")

        with crud_c2:
            edit_clicked = st.button("✏️ Modifica", width="stretch", disabled=(selected_idx is None), key=f"crud_edit_{tab_sel}")

        with crud_c3:
            del_clicked = st.button("🗑️ Elimina", width="stretch", disabled=(selected_idx is None), key=f"crud_del_{tab_sel}")

        if new_clicked:
            st.session_state['crud_mode'] = 'new'

            # UX: apertura "Nuovo" deve partire SEMPRE pulita (senza dati residui da edit/new precedenti)
            _mode = 'new'
            _mode_id = f"{tab_sel}_{_mode}"
            for _k in list(st.session_state.keys()):
                if str(_k).startswith(f"fld_{tab_sel}_{_mode}_"):
                    st.session_state.pop(_k, None)
            for _k in [
                f"emp_sel_{_mode_id}",
                f"_emp_prev_{_mode_id}",
                f"_turno_prev_{_mode_id}",
            ]:
                st.session_state.pop(_k, None)

            @st.dialog(f"Nuovo record - {tab_sel}")
            def _dlg_new():
                cols = list(df.columns)

                # ---- Cascata: Dipendente / Turno (usa dati consolidati) ----
                mode = 'new'
                mode_id = f"{tab_sel}_{mode}"

                # Individua i nomi colonna reali (case-insensitive)
                cols_l = {str(c).strip().lower(): c for c in cols}
                nome_col = cols_l.get('nome') or cols_l.get('nominativo')
                matr_col = cols_l.get('matricola') or cols_l.get('matr')
                uo_col = cols_l.get('uo') or cols_l.get('unità operativa') or cols_l.get('unita operativa') or cols_l.get('unita_operativa')
                cat_col = cols_l.get('catproftipo') or cols_l.get('categoria') or cols_l.get('cat')
                minuti_col = cols_l.get('minuti')
                valore_col = cols_l.get('valore')
                turno_col = cols_l.get('turno')

                people = _get_people_registry()
                turni_map = _get_turni_minutes_map()

                # Se la tabella ha matricola/nome, abilita selezione dipendente che precompila i campi correlati
                if matr_col is not None:
                    if not people.empty:
                        # Placeholder (nessuna selezione) per evitare precompilazione involontaria
                        options = [(f"{r['nome']} ({r['matricola']})", str(r['matricola'])) for _, r in people.iterrows()]
                        options = sorted(options, key=lambda x: x[0])
                        options = [("— Seleziona dipendente —", None)] + options
                        labels = [o[0] for o in options]
                        label_to_m = {lbl: m for (lbl, m) in options}
                        sel_label = st.selectbox("Dipendente", labels, index=0, key=f"emp_sel_{mode_id}") if labels else None
                        sel_m = label_to_m.get(sel_label) if sel_label else None
                        prev_m = st.session_state.get(f"_emp_prev_{mode_id}")
                        if sel_m is not None and sel_m != prev_m:
                            st.session_state[f"_emp_prev_{mode_id}"] = sel_m
                            r = people.loc[people['matricola'].astype(str) == str(sel_m)].head(1)
                            if len(r):
                                r = r.iloc[0]
                                if nome_col is not None:
                                    st.session_state[f"fld_{tab_sel}_{mode}_{nome_col}"] = str(r.get('nome', ''))
                                st.session_state[f"fld_{tab_sel}_{mode}_{matr_col}"] = str(r.get('matricola', ''))
                                if uo_col is not None:
                                    st.session_state[f"fld_{tab_sel}_{mode}_{uo_col}"] = '' if pd.isna(r.get('uo')) else str(r.get('uo'))
                                if cat_col is not None:
                                    st.session_state[f"fld_{tab_sel}_{mode}_{cat_col}"] = '' if pd.isna(r.get('cat')) else str(r.get('cat'))

                # Pre-cascata Turno -> minuti/valore (prima del rendering dei widget, evita StreamlitAPIException)
                if turno_col is not None and turni_map:
                    turno_key = f"fld_{tab_sel}_{mode}_{turno_col}"
                    cur_t = st.session_state.get(turno_key)
                    prev_t = st.session_state.get(f"_turno_prev_{mode_id}")
                    if cur_t and cur_t != prev_t:
                        st.session_state[f"_turno_prev_{mode_id}"] = cur_t
                        mins = int(turni_map.get(str(cur_t).strip(), 0))
                        if minuti_col is not None:
                            st.session_state[f"fld_{tab_sel}_{mode}_{minuti_col}"] = float(mins)
                        if valore_col is not None:
                            # se esiste il campo minuti, valore = ore (min/60), altrimenti manteniamo minuti
                            v = float(round(mins / 60.0, 2)) if minuti_col is not None else float(mins)
                            st.session_state[f"fld_{tab_sel}_{mode}_{valore_col}"] = v


                # --- Form layout (meno verticale): tabs + griglia 2 colonne ---
                def _group_cols(_cols):
                    person_keys = {
                        'nome','nominativo','cognome e nome','cognome_nome','matricola','matr',
                        'uo','unità operativa','unita operativa','unita_operativa',
                        'cat','categoria','catproftipo','in_forza','inforza','stato'
                    }
                    work_keys = {'turno','att','data','minuti','valore','ore','stp'}
                    extra_keys = {'note','contattato_il','contattato il','pox','posizione operativa','posizione_operativa'}
                    g1,g2,g3 = [],[],[]
                    for c in _cols:
                        cl = str(c).strip().lower()
                        if cl in person_keys:
                            g1.append(c)
                        elif cl in extra_keys and cl not in work_keys:
                            g3.append(c)
                        else:
                            g2.append(c)
                    return g1, g2, g3

                g_person, g_work, g_extra = _group_cols(cols)
                has_extra = len(g_extra) > 0

                # CSS: dialog piu largo e controlli compatti
                st.markdown(
                    "<style>"
                    "div[data-testid='stDialog'] div[role='dialog']{max-width:980px;}"
                    "div[data-testid='stDialog'] .stTextInput input,"
                    "div[data-testid='stDialog'] .stNumberInput input{padding:.35rem .5rem;}"
                    "div[data-testid='stDialog'] label{font-size:.85rem;}"
                    "</style>",
                    unsafe_allow_html=True,
                )

                def _render_group(title, group_cols, row_values):
                    if not group_cols:
                        return {}
                    st.markdown(f"#### {title}")
                    out = {}
                    cL, cR = st.columns(2, gap='large')
                    for i, c in enumerate(group_cols):
                        with (cL if i % 2 == 0 else cR):
                            out[c], _ = _infer_widget(c, df[c] if c in df.columns else pd.Series(dtype=object), row_values.get(c, ''))
                    return out

                data = {}
                if has_extra:
                    t1, t2, t3 = st.tabs(['Anagrafica', 'Dati', 'Extra'])
                    with t1:
                        data.update(_render_group('Dati persona', g_person, {}))
                    with t2:
                        data.update(_render_group('Dettaglio', g_work, {}))
                    with t3:
                        data.update(_render_group('Note / Extra', g_extra, {}))
                else:
                    data.update(_render_group('Dati persona', g_person, {}))
                    st.divider()
                    data.update(_render_group('Dettaglio', g_work, {}))

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Crea", type="primary", width="stretch"):
                        with st.spinner("Salvataggio..."):
                            # normalizza date (solo giorno)
                            for k, v in list(data.items()):
                                if isinstance(v, datetime):
                                    data[k] = v.date()
                                elif isinstance(v, date):
                                    data[k] = v
                            db.add_record(tab_sel, data)
                        st.success("Record creato")
                        st.rerun()
                with c2:
                    st.button("Annulla", width="stretch")

            _dlg_new()

        if edit_clicked and selected_idx is not None:
            st.session_state['crud_mode'] = 'edit'

            @st.dialog(f"Modifica record #{selected_idx} - {tab_sel}")
            def _dlg_edit():
                row = db.get_all(tab_sel).loc[selected_idx]
                cols = list(db.get_all(tab_sel).columns)

                # ---- Cascata: Dipendente / Turno (usa dati consolidati) ----
                mode = 'edit'
                mode_id = f"{tab_sel}_{mode}"
                cols_l = {str(c).strip().lower(): c for c in cols}
                nome_col = cols_l.get('nome') or cols_l.get('nominativo')
                matr_col = cols_l.get('matricola') or cols_l.get('matr')
                uo_col = cols_l.get('uo') or cols_l.get('unità operativa') or cols_l.get('unita operativa') or cols_l.get('unita_operativa')
                cat_col = cols_l.get('catproftipo') or cols_l.get('categoria') or cols_l.get('cat')
                minuti_col = cols_l.get('minuti')
                valore_col = cols_l.get('valore')
                turno_col = cols_l.get('turno')

                people = _get_people_registry()
                turni_map = _get_turni_minutes_map()

                # Selezione dipendente (preseleziona record corrente)
                if matr_col is not None and not people.empty:
                    cur_m = '' if pd.isna(row.get(matr_col)) else str(row.get(matr_col))
                    options = [(f"{r['nome']} ({r['matricola']})", str(r['matricola'])) for _, r in people.iterrows()]
                    options = sorted(options, key=lambda x: x[0])
                    labels = [o[0] for o in options]
                    label_to_m = dict(options)
                    # index preselect
                    pre_idx = 0
                    for i, (_, m) in enumerate(options):
                        if m == cur_m:
                            pre_idx = i
                            break
                    sel_label = st.selectbox("Dipendente", labels, index=pre_idx, key=f"emp_sel_{mode_id}") if labels else None
                    sel_m = label_to_m.get(sel_label) if sel_label else None
                    prev_m = st.session_state.get(f"_emp_prev_{mode_id}")
                    if sel_m and sel_m != prev_m:
                        st.session_state[f"_emp_prev_{mode_id}"] = sel_m
                        r = people.loc[people['matricola'].astype(str) == str(sel_m)].head(1)
                        if len(r):
                            r = r.iloc[0]
                            if nome_col is not None:
                                st.session_state[f"fld_{tab_sel}_{mode}_{nome_col}"] = str(r.get('nome', ''))
                            st.session_state[f"fld_{tab_sel}_{mode}_{matr_col}"] = str(r.get('matricola', ''))
                            if uo_col is not None:
                                st.session_state[f"fld_{tab_sel}_{mode}_{uo_col}"] = '' if pd.isna(r.get('uo')) else str(r.get('uo'))
                            if cat_col is not None:
                                st.session_state[f"fld_{tab_sel}_{mode}_{cat_col}"] = '' if pd.isna(r.get('cat')) else str(r.get('cat'))

                # Pre-cascata Turno -> minuti/valore (prima del rendering dei widget, evita StreamlitAPIException)
                if turno_col is not None and turni_map:
                    turno_key = f"fld_{tab_sel}_{mode}_{turno_col}"
                    cur_t = st.session_state.get(turno_key)
                    prev_t = st.session_state.get(f"_turno_prev_{mode_id}")
                    if cur_t and cur_t != prev_t:
                        st.session_state[f"_turno_prev_{mode_id}"] = cur_t
                        mins = int(turni_map.get(str(cur_t).strip(), 0))
                        if minuti_col is not None:
                            st.session_state[f"fld_{tab_sel}_{mode}_{minuti_col}"] = float(mins)
                        if valore_col is not None:
                            v = float(round(mins / 60.0, 2)) if minuti_col is not None else float(mins)
                            st.session_state[f"fld_{tab_sel}_{mode}_{valore_col}"] = v


                # --- Form layout (meno verticale): tabs + griglia 2 colonne ---
                def _group_cols(_cols):
                    person_keys = {
                        'nome','nominativo','cognome e nome','cognome_nome','matricola','matr',
                        'uo','unità operativa','unita operativa','unita_operativa',
                        'cat','categoria','catproftipo','in_forza','inforza','stato'
                    }
                    work_keys = {'turno','att','data','minuti','valore','ore','stp'}
                    extra_keys = {'note','contattato_il','contattato il','pox','posizione operativa','posizione_operativa'}
                    g1,g2,g3 = [],[],[]
                    for c in _cols:
                        cl = str(c).strip().lower()
                        if cl in person_keys:
                            g1.append(c)
                        elif cl in extra_keys and cl not in work_keys:
                            g3.append(c)
                        else:
                            g2.append(c)
                    return g1, g2, g3

                cols_all = list(db.get_all(tab_sel).columns)
                g_person, g_work, g_extra = _group_cols(cols_all)
                has_extra = len(g_extra) > 0

                st.markdown(
                    "<style>"
                    "div[data-testid='stDialog'] div[role='dialog']{max-width:980px;}"
                    "div[data-testid='stDialog'] .stTextInput input,"
                    "div[data-testid='stDialog'] .stNumberInput input{padding:.35rem .5rem;}"
                    "div[data-testid='stDialog'] label{font-size:.85rem;}"
                    "</style>",
                    unsafe_allow_html=True,
                )

                def _render_group(title, group_cols):
                    if not group_cols:
                        return {}
                    st.markdown(f"#### {title}")
                    out = {}
                    cL, cR = st.columns(2, gap='large')
                    for i, c in enumerate(group_cols):
                        with (cL if i % 2 == 0 else cR):
                            out[c], _ = _infer_widget(c, db.get_all(tab_sel)[c], row.get(c))
                    return out

                data = {}
                if has_extra:
                    t1, t2, t3 = st.tabs(['Anagrafica', 'Dati', 'Extra'])
                    with t1:
                        data.update(_render_group('Dati persona', g_person))
                    with t2:
                        data.update(_render_group('Dettaglio', g_work))
                    with t3:
                        data.update(_render_group('Note / Extra', g_extra))
                else:
                    data.update(_render_group('Dati persona', g_person))
                    st.divider()
                    data.update(_render_group('Dettaglio', g_work))

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("💾 Salva modifiche", type="primary", width="stretch"):
                        with st.spinner("Salvataggio..."):
                            db.update_record(tab_sel, selected_idx, data)
                        st.success("Record aggiornato")
                        st.rerun()
                with c2:
                    st.button("Annulla", width="stretch")

            _dlg_edit()

        if del_clicked and selected_idx is not None:
            st.session_state['crud_mode'] = 'delete'

            @st.dialog(f"Elimina record #{selected_idx} - {tab_sel}")
            def _dlg_del():
                st.warning("⚠️ Operazione irreversibile")
                st.write("Confermi eliminazione del record selezionato?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🗑️ Elimina", type="primary", width="stretch"):
                        with st.spinner("Eliminazione..."):
                            db.delete_record(tab_sel, selected_idx)
                        st.success("Record eliminato")
                        st.rerun()
                with c2:
                    st.button("Annulla", width="stretch")

            _dlg_del()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("💾 SALVA", type="primary", width="stretch"):
                try:
                    edited_save = edited.copy()
                    if '__sel__' in edited_save.columns:
                        edited_save = edited_save.drop(columns=['__sel__'])

                    if len(df) > 100:
                        final = pd.concat([edited_save, df.iloc[100:]], ignore_index=True)
                    else:
                        final = edited_save

                    # Re-parse data (gg/mm/aaaa) -> datetime/date coerente
                    if 'data' in final.columns:
                        dtp = pd.to_datetime(final['data'], errors='coerce', dayfirst=True)
                        # salva senza orario (solo data)
                        final['data'] = dtp.dt.date
                    db.save_table(tab_sel, final)
                    st.success("✅ Salvato!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")
        
        with col2:
            if st.button("🔄 ANNULLA", width="stretch"):
                st.rerun()
        
        with col3:
            # Svuota tabella con doppia conferma
            if f'confirm_clear_{tab_sel}' not in st.session_state:
                st.session_state[f'confirm_clear_{tab_sel}'] = False
            
            if not st.session_state[f'confirm_clear_{tab_sel}']:
                if st.button("🗑️ SVUOTA TABELLA", width="stretch"):
                    st.session_state[f'confirm_clear_{tab_sel}'] = True
                    st.rerun()
            else:
                if st.button("⚠️ CONFERMA SVUOTAMENTO", type="primary", width="stretch"):
                    try:
                        db.clear_table(tab_sel)
                        st.session_state[f'confirm_clear_{tab_sel}'] = False
                        st.success(f"✅ Tabella {tab_sel} svuotata!")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")
                        st.session_state[f'confirm_clear_{tab_sel}'] = False
        
        # Mostra warning se in modalità conferma
        if st.session_state.get(f'confirm_clear_{tab_sel}', False):
            st.warning(f"⚠️ **ATTENZIONE!** Stai per svuotare la tabella **{tab_sel}** con {len(df):,} record. Questa azione è **IRREVERSIBILE**! Clicca di nuovo 'CONFERMA SVUOTAMENTO' per procedere o 'ANNULLA' per tornare indietro.")

# ===== IMPORT/EXPORT =====

elif st.session_state.page == 'Festivi':
    # _header_box restituisce HTML: va renderizzato (coerente con le altre pagine)
    st.markdown(
        _header_box('🎉 Festivi', 'Conteggio festivi (tabella Festivi + Pasqua/Pasquetta).'),
        unsafe_allow_html=True,
    )

    # Il filtro relazionale (UO/Categoria) è globale nel progetto:
    # la funzione get_person_meta_rel_filtered usa già il DB/cache interna.
    rel_uo = st.session_state.get('rel_uo', 'Tutte')
    rel_cat = st.session_state.get('rel_cat', 'Tutte')
    meta = get_person_meta_rel_filtered(rel_uo, rel_cat)
    if meta is None:
        meta = pd.DataFrame()

    # Normalizza i nomi colonna: in altre maschere le colonne arrivano spesso in lowercase
    # (matricola/nome/cat/uo/in_forza). Qui usiamo le versioni "canonical".
    if not meta.empty:
        rename_map = {}
        if 'matricola' in meta.columns and 'Matricola' not in meta.columns:
            rename_map['matricola'] = 'Matricola'
        if 'nome' in meta.columns and 'Nome' not in meta.columns:
            rename_map['nome'] = 'Nome'
        if 'cat' in meta.columns and 'CatProfTipo' not in meta.columns:
            rename_map['cat'] = 'CatProfTipo'
        if 'uo' in meta.columns and 'UO' not in meta.columns:
            rename_map['uo'] = 'UO'
        if 'in_forza' in meta.columns and 'In_Forza' not in meta.columns:
            rename_map['in_forza'] = 'In_Forza'
        if 'inforza' in meta.columns and 'In_Forza' not in meta.columns:
            rename_map['inforza'] = 'In_Forza'
        if rename_map:
            meta = meta.rename(columns=rename_map)

    if 'Matricola' in meta.columns:
        meta['Matricola'] = meta['Matricola'].fillna('').astype(str).str.strip()
    if 'Nome' in meta.columns:
        meta['Nome'] = meta['Nome'].fillna('').astype(str).str.strip()

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        d1 = st.date_input('Da', value=date.today().replace(day=1), key='fest_da', format='DD/MM/YYYY')
    with c2:
        d2 = st.date_input('A', value=date.today(), key='fest_a', format='DD/MM/YYYY')
    with c3:
        only_inforza = st.checkbox('Solo in forza', value=True, key='fest_inforza')

    f1, f2 = st.columns([1, 1])
    cats = sorted([c for c in meta.get('CatProfTipo', pd.Series(dtype=str)).dropna().astype(str).unique().tolist() if c != '']) if len(meta) > 0 else []
    noms = sorted([f"{r.get('Nome','')} | {r.get('Matricola','')}" for _, r in meta[['Nome', 'Matricola']].dropna(how='all').iterrows()]) if len(meta) > 0 and 'Nome' in meta.columns and 'Matricola' in meta.columns else []
    with f1:
        cat_sel = st.multiselect('Categorie', cats, default=[], key='fest_cat')
    with f2:
        nom_sel = st.multiselect('Nominativi', noms, default=[], key='fest_nom')

    meta_f = meta.copy()
    if only_inforza and 'In_Forza' in meta_f.columns:
        meta_f['In_Forza'] = meta_f['In_Forza'].astype(str).str.strip().str.lower().isin(['1', 'true', 'yes', 'si', 'sì', 'y'])
        meta_f = meta_f[meta_f['In_Forza']]
    if cat_sel and 'CatProfTipo' in meta_f.columns:
        meta_f = meta_f[meta_f['CatProfTipo'].astype(str).isin(cat_sel)]
    if nom_sel and 'Nome' in meta_f.columns and 'Matricola' in meta_f.columns:
        key = meta_f.apply(lambda r: f"{r.get('Nome','')} | {r.get('Matricola','')}", axis=1)
        meta_f = meta_f[key.isin(nom_sel)]

    if st.button('🔎 Genera', key='fest_gen'):
        df_att = db.get_all('Attivita')
        df_fest = db.get_all('Festivi')

        if df_att is None or len(df_att) == 0 or len(meta_f) == 0:
            st.info('Nessun dato da mostrare (verifica Personale/Attivita e filtri).')
        else:
            df = df_att.copy()
            if 'matricola' in df.columns:
                df['matricola'] = df['matricola'].fillna('').astype(str).str.strip()
            if 'data' in df.columns:
                df['data'] = pd.to_datetime(df['data'], errors='coerce').dt.date

            mats = set(meta_f['Matricola'].astype(str)) if 'Matricola' in meta_f.columns else set()
            df = df[df['matricola'].isin(mats)] if mats else df.iloc[0:0]
            df = df[(df['data'] >= d1) & (df['data'] <= d2)]

            if 'minuti' in df.columns:
                df['minuti'] = pd.to_numeric(df['minuti'], errors='coerce').fillna(0)
            elif 'valore' in df.columns:
                df['minuti'] = pd.to_numeric(df['valore'], errors='coerce').fillna(0)
            else:
                df['minuti'] = 0

            years = list(range(d1.year, d2.year + 1))
            hol = _build_holiday_index(df_fest, years)
            hol_dates = set([dt for dt in hol.keys() if dt >= d1 and dt <= d2])

            df = df[df['data'].isin(hol_dates)]

            # Escludi dal conteggio i giorni dove il turno primario o una attività
            # secondaria contiene una delle stringhe presenti nella tabella
            # Turni_Assenze (tabella editabile).
            try:
                df_ass = db.get_all('Turni_Assenze')
            except Exception:
                df_ass = None
            # Codici assenza/non-presenza usati per escludere il conteggio dei festivi.
            # IMPORTANTISSIMO: la logica NON deve essere hardcoded.
            # I codici devono arrivare ESCLUSIVAMENTE dalla tabella editabile Turni_Assenze,
            # in modo che l'utente possa aggiungere/rimuovere sigle liberamente.
            assenze_codes: set[str] = set()
            if df_ass is not None and len(df_ass) > 0:
                # prova a trovare la colonna che contiene le sigle (case-insensitive)
                col_turno = None
                for c in df_ass.columns:
                    if str(c).strip().lower() in ('turno', 'sigla', 'codice', 'code'):
                        col_turno = c
                        break
                if col_turno is None and len(df_ass.columns) > 0:
                    col_turno = df_ass.columns[0]
                if col_turno is not None:
                    assenze_codes = {
                        str(x).strip().upper()
                        for x in df_ass[col_turno].dropna().tolist()
                        if str(x).strip() != ''
                    }

            if len(assenze_codes) > 0 and len(df) > 0:
                def _has_assenza(row) -> bool:
                    vals = []
                    if 'turno' in row and pd.notna(row['turno']):
                        vals.append(str(row['turno']))
                    if 'att' in row and pd.notna(row['att']):
                        vals.append(str(row['att']))
                    blob = ' '.join(vals).upper()
                    # tokenizza per evitare match parziali (es. P38 vs 38)
                    toks = re.findall(r"[A-Z0-9]+", blob)
                    return any(t in assenze_codes for t in toks)

                df['_has_assenza'] = df.apply(_has_assenza, axis=1)
                any_abs = df.groupby(['matricola', 'data'])['_has_assenza'].transform('any')
                df = df[~any_abs].drop(columns=['_has_assenza'])

            if len(df) == 0:
                st.info('Nessun record in giorni festivi nel periodo selezionato.')
            else:
                df['festivo'] = df['data'].map(lambda x: hol.get(x, ''))
                meta_map = meta_f.set_index('Matricola')['Nome'].to_dict() if 'Matricola' in meta_f.columns and 'Nome' in meta_f.columns else {}
                df['Nome'] = df['matricola'].map(lambda m: meta_map.get(m, ''))

                g = df.groupby(['Nome', 'matricola'], dropna=False).agg(Giorni=('data', 'nunique'), Minuti=('minuti', 'sum')).reset_index()
                g['Ore'] = g['Minuti'].map(lambda x: f"{int(x)//60:02d}h {int(x)%60:02d}m")
                g = g.sort_values(['Nome', 'matricola'])

                st.subheader('Per Persona')
                st.dataframe(g[['Nome', 'matricola', 'Giorni', 'Ore']], use_container_width=True)

                st.subheader('Dettaglio Giornaliero')
                det = df.copy()
                det['Data'] = det['data'].map(lambda x: x.strftime('%d/%m/%Y'))
                det['Ore'] = det['minuti'].map(lambda x: f"{int(x)//60:02d}h {int(x)%60:02d}m")
                det = det.sort_values(['data', 'Nome', 'matricola'])
                cols = ['Data', 'Nome', 'matricola', 'turno', 'att', 'festivo', 'Ore']
                cols = [c for c in cols if c in det.columns]
                st.dataframe(det[cols], use_container_width=True)

elif st.session_state.page == 'Import Export':
    st.markdown("""
    <div class="page-header">
        <div class="page-title">📥 Import / Export</div>
        <div class="page-subtitle">Gestione file Excel</div>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📥 IMPORT", "📤 EXPORT"])
    
    with tab1:
        st.markdown("### Importa Excel")
        st.info("⚠️ File Excel deve avere valori in MINUTI")

        imp_mode_lbl = st.radio(
            "Modalità import",
            ["Sostituisci (svuota tabella prima di import)", "Aggiungi (mantieni record esistenti)"] ,
            index=0,
            horizontal=True,
            key="imp_mode"
        )
        imp_mode = 'replace' if imp_mode_lbl.startswith('Sostituisci') else 'append'
        
        file = st.file_uploader("File", type=['xlsx', 'xlsm'], key="imp_file")
        
        if file:
            excel = pd.ExcelFile(file)
            fogli = excel.sheet_names
            
            st.success(f"✅ {file.name}")
            st.info(f"📄 Fogli: {', '.join(fogli)}")
            
            st.markdown("### Mapping")
            
            mapping = {}
            for foglio in fogli:
                col1, col2, col3 = st.columns([2,1,2])
                with col1:
                    st.text(f"📄 {foglio}")
                with col2:
                    st.text("→")
                with col3:
                    dest = st.selectbox(
                        "Dest",
                        ['-- Ignora --'] + db.TABLES,
                        key=f"map_{foglio}",
                        label_visibility="collapsed"
                    )
                    if dest != '-- Ignora --':
                        mapping[foglio] = dest
            
            if st.button("📥 IMPORTA", type="primary", width="stretch"):
                success, msg = db.import_excel(file, mapping, mode=imp_mode)
                if success:
                    st.success(f"✅ {msg}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
    
    with tab2:
        st.markdown("### Esporta Excel")
        
        tabs_exp = st.multiselect(
            "Tabelle",
            db.TABLES,
            default=db.TABLES,
            key="exp_tabs"
        )
        
        if st.button("📤 GENERA", type="primary", width="stretch"):
            try:
                path = db.export_excel(tabs_exp)
                
                with open(path, 'rb') as f:
                    st.download_button(
                        "📥 SCARICA",
                        f,
                        file_name=f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch",
                        type="primary"
                    )
                
                st.success(f"✅ {path.name}")
            except Exception as e:
                st.error(f"❌ {e}")

# ===== CONFIG =====
elif st.session_state.page == 'Configurazione':
    st.markdown("""
    <div class="page-header">
        <div class="page-title">⚙️ Configurazione</div>
        <div class="page-subtitle">Impostazioni sistema</div>
    </div>
    """, unsafe_allow_html=True)
    
    cfg = load_config()
    
    st.markdown("### 📂 Percorso Database")
    
    col1, col2 = st.columns([3,1])
    
    with col1:
        current = cfg.get("base_dir", str(db.excel_path.parent))
        new_path = st.text_input("Percorso", current, key="cfg_path")
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📁 SFOGLIA", width="stretch"):
            folder = pick_folder_dialog()
            if folder:
                st.session_state.selected_folder = folder
                st.info(f"✅ {folder}")
    
    if st.button("💾 SALVA", type="primary"):
        cfg["base_dir"] = new_path
        save_config(cfg)
        st.success("✅ Salvato! Riavvia app.")
    
    st.markdown("---")
    st.markdown("### ℹ️ Info Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"""
        **📍 Database:** `{db.excel_path.name}`  
        **📊 Tabelle:** {len(db.TABLES)}  
        **💾 Record:** {sum(db.get_stats().values()):,}
        """)
    
    with col2:
        st.info(f"""
        **🔧 Versione:** v7.0 Enterprise  
        **📅 Data:** {datetime.now().strftime('%d/%m/%Y %H:%M')}  
        """)

# ===== CALENDARIO CROSSTAB =====
elif st.session_state.page == 'Calendario Crosstab':
    st.markdown("""
    <div class="page-header">
        <div class="page-title">📊 Calendario Crosstab</div>
        <div class="page-subtitle">Visualizzazione turni per persona (righe=persone, colonne=giorni)</div>
    </div>
    """, unsafe_allow_html=True)
    

    # Mantieni il calendario visibile dopo il primo 'GENERA' (evita reset quando cambi filtri)
    if 'crosstab_show' not in st.session_state:
        st.session_state.crosstab_show = False

    # --- Selettori periodo + azioni ---
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        oggi = datetime.now()
        mese = st.selectbox(
            "📅 Mese",
            ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
             'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'],
            index=oggi.month - 1,
            key="crosstab_mese",
        )

    with col2:
        anno = st.number_input("Anno", min_value=2020, max_value=2030, value=oggi.year, key="crosstab_anno")

    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        genera_crosstab = st.button("📊 GENERA CALENDARIO", type="primary", width="stretch")

    if genera_crosstab:
        st.session_state.crosstab_show = True

    # --- Dati anagrafica per filtri calendario (sempre visibili) ---
    # Regola globale: i filtri relazionali in sidebar (UO/Categoria) determinano SEMPRE
    # l'insieme del personale visibile in tutta l'app.
    meta_rel = get_person_meta_rel_filtered()
    uo_sel, cat_sel = get_relational_selections()

    # Filtri calendario (sempre visibili)
    with st.expander("🔎 Filtri Calendario", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns([1.2, 1.1, 2.2, 1.5])
        with fc1:
            cats = sorted([c for c in meta_rel['cat'].dropna().astype(str).unique().tolist() if str(c).strip() != ''])
            cal_cat = st.selectbox("Categoria personale", ['Tutte'] + cats, index=0, key='cal_filter_cat')
        with fc2:
            only_in_forza = st.checkbox("Solo In forza", value=True, key='cal_filter_in_forza')
        with fc3:
            person_opts = ['Tutti'] + [f"{r['nome']} ({r['matricola']})" for _, r in meta_rel.iterrows()]
            sel_person = st.selectbox("Dipendente", person_opts, index=0, key='cal_filter_person')
        with fc4:
            st.caption("Ordinamento: Cat ↑, Nome A→Z")

    # Helper: calcola la vista persone in base ai filtri calendario
    def _meta_view_from_filters(meta_df: pd.DataFrame):
        mv = meta_df.copy()
        if cal_cat != 'Tutte':
            mv = mv[mv['cat'].astype(str) == str(cal_cat)]
        if only_in_forza:
            mv = mv[mv['in_forza'] == True]
        if sel_person != 'Tutti':
            m = sel_person.split('(')[-1].replace(')', '').strip()
            mv = mv[mv['matricola'].astype(str) == m]
        # ordinamento
        mv['_cat_sort'] = mv['cat'].fillna('').replace('', 'ZZZ').astype(str).str.upper()
        mv['_name_sort'] = mv['nome'].fillna('').astype(str).str.upper()
        mv = mv.sort_values(['_cat_sort', '_name_sort', 'matricola'], ascending=[True, True, True])
        mv = mv.drop(columns=['_cat_sort', '_name_sort'])
        return mv

    meta_view = _meta_view_from_filters(meta_rel)

    def _render_crosstab_calendar(_mese, _anno, _meta_view, _genera=False, _height=720, _in_popup: bool = False):
        """Render calendario crosstab (riusabile anche nel popup)."""
        # alias parametri → variabili usate nel corpo (per riuso senza riscrivere tutto)
        mese = _mese
        anno = _anno
        meta_view = _meta_view
        genera_crosstab = _genera

        import contextlib
        with (st.spinner('⏳ Aggiornamento in corso...') if _genera else contextlib.nullcontext()):

            import contextlib

            with (st.spinner('⏳ Aggiornamento in corso...') if genera_crosstab else contextlib.nullcontext()):

                    # Carica dati

                    attivita = db.get_all('Attivita')

                    # Straordinari (per evidenziare il turno primario in Crosstab)
                    straordinari = db.get_all('Straordinario')

                    personale = db.get_all('Personale')
    

                    # Normalizza matricole

                    if len(attivita) > 0 and 'matricola' in attivita.columns:

                        attivita['matricola'] = attivita['matricola'].astype(str).str.strip()
    

                    if len(personale) > 0 and 'matricola' in personale.columns:

                        personale_clean = personale.copy()

                        personale_clean['matricola'] = personale_clean['matricola'].astype(str).str.strip()

                    else:

                        personale_clean = personale.copy()
    

                    if len(attivita) == 0:

                        st.warning("⚠️ Nessuna attività trovata nel database. Importa prima i dati.")

                    else:

                        # Check colonne necessarie esistono

                        if 'data' not in attivita.columns:

                            st.error("❌ Colonna 'data' non trovata in Attivita")

                        elif 'turno' not in attivita.columns:

                            st.error("❌ Colonna 'turno' non trovata in Attivita")

                        elif 'matricola' not in attivita.columns:

                            st.error("❌ Colonna 'matricola' non trovata in Attivita")

                        else:

                            # Converti mese nome → numero

                            mesi_dict = {'Gennaio': 1, 'Febbraio': 2, 'Marzo': 3, 'Aprile': 4, 'Maggio': 5, 'Giugno': 6,

                                        'Luglio': 7, 'Agosto': 8, 'Settembre': 9, 'Ottobre': 10, 'Novembre': 11, 'Dicembre': 12}

                            mese_num = mesi_dict[mese]
            

                            # Filtra attività per periodo (date sempre dayfirst)

                            attivita['data'] = pd.to_datetime(attivita['data'], errors='coerce', dayfirst=True)

                            att_filt = attivita[(attivita['data'].dt.year == int(anno)) & (attivita['data'].dt.month == int(mese_num))].copy()


                            # Applica logica relazionale (UO/Categoria)

                            uo_sel = st.session_state.get('filter_uo', 'Tutte')

                            cat_sel = st.session_state.get('filter_cat', 'Tutte')

                            att_filt = apply_relational_filters(att_filt, uo_sel, cat_sel)

                            # --- Straordinari (match su matricola + data + turno) ---
                            overtime_keys = set()
                            try:
                                if len(straordinari) > 0 and {'matricola', 'data', 'turno'}.issubset(set(straordinari.columns)):
                                    stx = straordinari.copy()
                                    stx['matricola'] = stx['matricola'].astype(str).str.strip()
                                    stx['turno'] = stx['turno'].astype(str).str.strip().str.upper()
                                    stx['data'] = pd.to_datetime(stx['data'], errors='coerce', dayfirst=True)
                                    stx = stx[(stx['data'].dt.year == int(anno)) & (stx['data'].dt.month == int(mese_num))].copy()
                                    stx = apply_relational_filters(stx, uo_sel, cat_sel)
                                    stx = stx.dropna(subset=['matricola', 'data', 'turno'])
                                    if len(stx) > 0:
                                        stx['d'] = stx['data'].dt.date
                                        overtime_keys = set(zip(stx['matricola'], stx['d'], stx['turno']))
                            except Exception:
                                overtime_keys = set()
            

                            if len(att_filt) == 0:

                                st.info(f"ℹ️ Nessuna attività trovata per {mese} {anno}")

                            else:

                                # Giorno nel mese

                                att_filt['giorno'] = att_filt['data'].dt.day


                                # --- UI Calendario avanzata (come screenshot) ---


                                import html as _html

                                import re


                                def _esc(x):

                                    return _html.escape('' if x is None else str(x))


                                # Calcola numero giorni nel mese

                                if mese_num in [1, 3, 5, 7, 8, 10, 12]:

                                    giorni_mese = 31

                                elif mese_num in [4, 6, 9, 11]:

                                    giorni_mese = 30

                                else:  # Febbraio

                                    if (int(anno) % 4 == 0 and int(anno) % 100 != 0) or (int(anno) % 400 == 0):

                                        giorni_mese = 29

                                    else:

                                        giorni_mese = 28


                                # --- Registro persone (relazionale) ---

                                reg = get_person_registry()

                                reg_idx = None

                                if len(reg) > 0 and 'matricola' in reg.columns:

                                    tmp = reg.copy()

                                    tmp['matricola'] = tmp['matricola'].astype(str).str.strip()

                                    tmp = tmp.drop_duplicates(subset=['matricola'])

                                    reg_idx = tmp.set_index('matricola')


                                # Normalizza campi utili

                                # Best-effort: mappa colonne alternative verso gli alias usati dall'app
                                _col_map = {str(c).strip().lower(): c for c in att_filt.columns}

                                # attivita' secondaria: crea alias 'att' se non presente
                                if 'att' not in att_filt.columns:
                                    for cand in [
                                        'attivita', 'attività', 'att1', 'att_prim', 'attivita1', 'attività1',
                                        'secondaria', 'att_sec', 'att_secondaria', 'attivita_sec', 'attività_sec'
                                    ]:
                                        oc = _col_map.get(cand)
                                        if oc is not None:
                                            att_filt['att'] = att_filt[oc]
                                            break

                                # minuti/valore: crea alias 'valore' se esiste un campo minuti/durata
                                if 'valore' not in att_filt.columns:
                                    for cand in ['minuti', 'min', 'durata', 'durata_min', 'valore_min']:
                                        oc = _col_map.get(cand)
                                        if oc is not None:
                                            att_filt['valore'] = att_filt[oc]
                                            break

                                att_filt['matricola'] = att_filt['matricola'].astype(str).str.strip()

                                for col in ['nome', 'uo', 'cat', 'turno', 'att', 'pox']:

                                    if col not in att_filt.columns:

                                        att_filt[col] = ''

                                    att_filt[col] = att_filt[col].fillna('').astype(str).str.strip()

                                if 'valore' in att_filt.columns:

                                    att_filt['valore'] = pd.to_numeric(att_filt['valore'], errors='coerce').fillna(0.0)

                                else:

                                    att_filt['valore'] = 0.0


                                # --- Meta persone (per filtri/sorting) ---

                                # Costruisce un elenco persone del mese con campi relazionali (cat, uo, in_forza)

                                matr_list = sorted(att_filt['matricola'].unique().tolist())

                                meta_rows = []

                                for matr in matr_list:

                                    subm = att_filt[att_filt['matricola'] == matr]


                                    nome_m = ''

                                    uo_m = ''

                                    cat_m = ''

                                    in_forza_m = True

                                    if reg_idx is not None and matr in reg_idx.index:

                                        rr = reg_idx.loc[matr]

                                        nome_m = str(rr.get('nome', '') or '').strip()

                                        uo_m = str(rr.get('uo', '') or '').strip()

                                        cat_m = str(rr.get('cat', '') or '').strip()

                                        # best-effort: campi possibili per stato in forza

                                        for cand in ['in_forza', 'stato', 'attivo', 'status']:

                                            if cand in rr.index:

                                                v = str(rr.get(cand, '')).strip().lower()

                                                if v in {'0', 'false', 'no', 'n', 'off', 'cessato', 'non attivo'}:

                                                    in_forza_m = False

                                                break


                                    if not nome_m:

                                        nn = subm['nome'].astype(str).str.strip().replace({'nan': '', 'None': '', 'NONE': ''})

                                        nome_m = nn[nn != ''].mode().iloc[0] if (nn != '').any() else matr


                                    if not uo_m:

                                        uu = subm['uo'].astype(str).str.strip().replace({'nan': '', 'None': '', 'NONE': ''})

                                        uo_m = uu[uu != ''].mode().iloc[0] if (uu != '').any() else ''


                                    meta_rows.append({'matricola': matr, 'nome': nome_m, 'uo': uo_m, 'cat': cat_m, 'in_forza': in_forza_m})


                                meta_df = pd.DataFrame(meta_rows)

                                if len(meta_df) == 0:

                                    meta_df = pd.DataFrame(columns=['matricola', 'nome', 'uo', 'cat', 'in_forza'])


                                # Ordina per categoria (crescente) e poi alfabetico

                                meta_df['_cat_sort'] = meta_df['cat'].fillna('').replace('', 'ZZZ').astype(str).str.upper()

                                meta_df['_name_sort'] = meta_df['nome'].fillna('').astype(str).str.upper()

                                meta_df = meta_df.sort_values(['_cat_sort', '_name_sort', 'matricola'], ascending=[True, True, True])

                                meta_df = meta_df.drop(columns=['_cat_sort', '_name_sort'])

                                # --- Filtri calendario: UI resa sopra (sempre visibile) ---

                                # meta_view calcolata sopra in base ai filtri
                                meta_view = meta_view

                                # Lookup ore attese per turno (Turni_tipo -> minuti)

                                try:

                                    tt = db.get_all('Turni_tipo')

                                except Exception:

                                    tt = pd.DataFrame()


                                turni_lookup = {}

                                if len(tt) > 0:

                                    tt2 = tt.copy()

                                    tt2.columns = [str(c).strip().lower() for c in tt2.columns]

                                    code_col = None

                                    for cand in ['turno', 'codice', 'sigla', 'nome', 'id']:

                                        if cand in tt2.columns:

                                            code_col = cand

                                            break

                                    min_col = None

                                    for cand in ['minuti', 'min', 'durata', 'valore']:

                                        if cand in tt2.columns:

                                            min_col = cand

                                            break

                                    if code_col and min_col:

                                        tt2[code_col] = tt2[code_col].astype(str).str.strip().str.upper()

                                        tt2[min_col] = pd.to_numeric(tt2[min_col], errors='coerce')

                                        for _, r in tt2.dropna(subset=[code_col, min_col]).iterrows():

                                            turni_lookup[str(r[code_col]).upper()] = float(r[min_col]) / 60.0


                                def _hours_for_shift(code: str) -> float:

                                    c = (code or '').strip().upper()

                                    if c in {'', 'NAN', 'NONE'}:

                                        return 0.0

                                    if c in turni_lookup:

                                        return float(turni_lookup[c])

                                    if re.match(r'^[MPN]\d{1,3}$', c):

                                        return 8.0

                                    if re.match(r'^\d{1,4}$', c):  # codici numerici (es. 104)

                                        return 8.0

                                    # assenze/altro

                                    return 0.0


                                # Giorni e intestazioni (numero + dow)

                                dow_it = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom']

                                day_dates = [datetime(int(anno), int(mese_num), g) for g in range(1, giorni_mese + 1)]

                                headers = [f"{d.day}<br><span class='dow'>{dow_it[d.weekday()]}</span>" for d in day_dates]


                                def _badge(code: str, hours: float, kind: str, sub: str = '', extra_cls: str = '') -> str:

                                    c = (code or '').strip().upper()

                                    if c in {'', 'NAN', 'NONE'}:

                                        return ''

                                    sub_html = f"<div class='sub'>{_esc(sub)}</div>" if (sub or '').strip() else ''

                                    extra = f" {extra_cls}" if (extra_cls or '').strip() else ''
                                    return (
                                        f"<div class='badge {kind}{extra}'>"

                                        f"<div class='left'>"

                                        f"<div class='code'>{_esc(c)}</div>"

                                        f"{sub_html}"

                                        f"</div>"

                                        f"<div class='hrs'>{hours:.1f}h</div>"

                                        f"</div>"

                                    )


                                def _cell(primary_code: str, primary_h: float, sec_items: list, extra: int, force_free: bool = False, weekendfree: bool = False, is_overtime: bool = False, is_gt_overtime: bool = False) -> str:
                                    if (primary_code or '').strip() == '' and not sec_items:
                                        return "<div class='cell empty'></div>"

                                    parts = []

                                    if (primary_code or '').strip() != '':
                                        pc_up = str(primary_code).strip().upper()
                                        kind = 'free' if (pc_up == 'FREE' or (force_free and pc_up in {'FER','RFS',''})) else 'primary'
                                        extra_cls_parts = []
                                        if weekendfree and kind == 'free':
                                            extra_cls_parts.append('weekendfree')
                                        # Evidenziazione straordinari:
                                        # - overtime: match in tabella Straordinario (manuale)
                                        # - nomatch: straordinario GT (STR/RPD/RPN in Attivita con minuti>0) ma non presente in Straordinario
                                        if kind == 'primary':
                                            if is_overtime:
                                                extra_cls_parts.append('overtime')
                                        extra_cls = ' '.join(extra_cls_parts)
                                        parts.append(_badge(primary_code, primary_h, kind, extra_cls=extra_cls))

                                    for item in sec_items:
                                        # item = (code, hours, sub[, extra_cls])
                                        if isinstance(item, (list, tuple)) and len(item) >= 4:
                                            sc, sh, ss, _extra = item[0], item[1], item[2], item[3]
                                        else:
                                            sc, sh, ss = item[0], item[1], (item[2] if len(item) > 2 else '')
                                            _extra = ''

                                        sc_up = str(sc).strip().upper()
                                        sec_kind = 'free' if (sc_up in {'FER', 'RFS', 'FREE'} or force_free) else 'secondary'
                                        extra_cls = 'weekendfree' if (weekendfree and sec_kind == 'free') else ''
                                        # evidenzia STR "GT" (straordinario importato da Attivita)
                                        if (str(_extra).strip() != ''):
                                            extra_cls = (extra_cls + ' ' + str(_extra)).strip()
                                        parts.append(_badge(sc, sh, sec_kind, ss, extra_cls=extra_cls))

                                    if extra > 0:
                                        parts.append(f"<div class='more'>+{extra}</div>")
                                    return "<div class='cell'>" + "".join(parts) + "</div>"

                                def _person_box(nome: str, matr: str, uo: str, cat: str, ore: float, in_forza: bool) -> str:

                                    stato_html = "<span class='ok'>In forza</span>" if in_forza else "<span class='ko'>Non in forza</span>"

                                    return (

                                        "<div class='pbox'>"

                                        f"<div class='pname'>{_esc(nome)}</div>"

                                        f"<div class='psub'>{_esc(matr)} <span class='muted'>{_esc(uo)}</span></div>"

                                        f"<div class='psub'>{stato_html} &nbsp; Ore: {ore:.1f} &nbsp; <span class='muted'>Cat: {_esc(cat) if cat else '-'} </span></div>"

                                        "</div>"

                                    )


                                # Costruisci righe (applica filtri calendario + ordinamento per categoria e alfabetico)

                                if len(meta_view) == 0:

                                    st.info("ℹ️ Nessuna persona soddisfa i filtri selezionati.")

                                    st.stop()


                                people = meta_view['matricola'].astype(str).tolist()

                                rows = []

                                presenze = 0


                                # Anche per export: turno primario per giorno

                                export_rows = []


                                # lookup rapido metadati persona

                                _meta_idx = meta_view.set_index('matricola', drop=False)


                                for matr in people:

                                    sub = att_filt[att_filt['matricola'] == matr].copy()


                                    # meta

                                    nome = ''

                                    uo_p = ''

                                    cat_p = ''

                                    in_forza_p = True


                                    if matr in _meta_idx.index:

                                        mr = _meta_idx.loc[matr]

                                        nome = str(mr.get('nome', '') or '').strip()

                                        uo_p = str(mr.get('uo', '') or '').strip()

                                        cat_p = str(mr.get('cat', '') or '').strip()

                                        in_forza_p = bool(mr.get('in_forza', True))

                                    if reg_idx is not None and matr in reg_idx.index:

                                        rr = reg_idx.loc[matr]

                                        nome = str(rr.get('nome', '') or '').strip()

                                        uo_p = str(rr.get('uo', '') or '').strip()

                                        cat_p = str(rr.get('cat', '') or '').strip()


                                    if not nome:

                                        if sub['nome'].replace({'nan':'', 'None':'', 'NONE':''}).astype(str).str.strip().ne('').any():

                                            nome = sub['nome'].astype(str).str.strip().replace({'nan':''}).mode().iloc[0]

                                        else:

                                            nome = matr


                                    if not uo_p:

                                        if sub['uo'].replace({'nan':'', 'None':'', 'NONE':''}).astype(str).str.strip().ne('').any():

                                            uo_p = sub['uo'].astype(str).str.strip().replace({'nan':''}).mode().iloc[0]



                                    # celle

                                    total_h = 0.0

                                    cell_htmls = []

                                    td_classes = []

                                    weekend_engaged = {}  # g -> bool (solo sab/dom)

                                    exp = {'Nominativo': nome, 'Matricola': matr, 'UO': uo_p, 'Cat': cat_p}


                                    # stato per giorno (serve per FREE weekend)

                                    day_state = []


                                    for g, dt in enumerate(day_dates, start=1):

                                        day_rows = sub[sub['giorno'] == g]

                                        # --- Turno primario + eventuali righe "seconda riga" (stessa data/matricola) ---
                                        _day_turno = day_rows.copy()

                                        # normalizza minuti per usare i valori reali della tabella Attivita (minuti o valore)
                                        if 'minuti' in _day_turno.columns:
                                            _day_turno['_mins'] = pd.to_numeric(_day_turno['minuti'], errors='coerce').fillna(0.0)
                                        elif 'valore' in _day_turno.columns:
                                            _v = pd.to_numeric(_day_turno['valore'], errors='coerce').fillna(0.0)
                                            # euristica: se sembra ore (< 24) -> converto in minuti
                                            _day_turno['_mins'] = (_v * 60.0) if float(_v.max() if len(_v) else 0.0) <= 24.0 else _v
                                        else:
                                            _day_turno['_mins'] = 0.0

                                        _day_turno['_t'] = _day_turno['turno'].astype(str).str.strip().replace({'nan': '', 'None': '', 'NONE': ''})
                                        _day_turno = _day_turno[_day_turno['_t'] != '']
                                        _day_turno['_t_up'] = _day_turno['_t'].astype(str).str.upper().str.strip()

                                        # non mostrare POX nel calendario
                                        _day_turno = _day_turno[_day_turno['_t_up'] != 'POX']

                                        primary_code = ''
                                        primary_mins = 0.0
                                        sec_turno_groups = []

                                        if len(_day_turno) > 0:
                                            _grp = (
                                                _day_turno.groupby('_t_up', as_index=False)
                                                          .agg(minuti=('_mins', 'sum'))
                                                          .sort_values('minuti', ascending=False)
                                            )

                                            # scelta primario: quello con più minuti; se tutti 0 -> primo in ordine originale
                                            if float(_grp['minuti'].max()) > 0:
                                                primary_code = str(_grp.iloc[0]['_t_up']).strip()
                                                primary_mins = float(_grp.iloc[0]['minuti'])
                                            else:
                                                primary_code = str(_day_turno.iloc[0]['_t_up']).strip()
                                                primary_mins = float(_day_turno.iloc[0]['_mins'])

                                            # secondarie = tutti gli altri codici presenti come "seconda riga" nello stesso giorno
                                            _sec_grp = _grp[_grp['_t_up'] != primary_code].copy()
                                            sec_turno_groups = [(str(r['_t_up']).strip().upper(), float(r['minuti'])) for _, r in _sec_grp.iterrows()]

                                        sec_turno_present = len(sec_turno_groups) > 0

                                        # ore del primario: usa minuti reali se presenti, altrimenti lookup
                                        ph = (primary_mins / 60.0) if (primary_code != '' and primary_mins > 0) else _hours_for_shift(primary_code)

                                        # ph gia' calcolato sopra (minuti reali o lookup)

                                        if primary_code != '':

                                            presenze += 1

                                        total_h += ph


                                        # Secondarie (ATT) - mostra SEMPRE anche FER/RFS (richiesta: es. turno + ferie)

                                        # NB: nel calendario NON mostrare POX

                                        sec_df = day_rows.copy()

                                        # normalizza minuti (alcuni DB possono avere solo 'valore' in ore)
                                        if 'minuti' not in sec_df.columns:
                                            if 'valore' in sec_df.columns:
                                                _v = pd.to_numeric(sec_df['valore'], errors='coerce').fillna(0.0)
                                                sec_df['minuti'] = (_v * 60.0) if float(_v.max() if len(_v) else 0.0) <= 24.0 else _v
                                            else:
                                                sec_df['minuti'] = 0.0

                                        sec_df['att'] = sec_df['att'].astype(str).str.strip().replace({'nan': '', 'None': '', 'NONE': ''})

                                        sec_df = sec_df[sec_df['att'] != '']


                                        # Per il calcolo "impegnato" nel weekend:

                                        # - FER/RFS NON contano come impegno

                                        # - Se c'e' un turno (es. M78) ma in ATT secondaria compare FER/RFS

                                        #   (e non ci sono altre ATT reali), consideriamo il giorno NON impegnato

                                        #   (tipico: turno pianificato ma ferie/riposo segnato).

                                        has_fer_rfs = False

                                        if len(sec_df) > 0:

                                            sec_df['_att_up'] = sec_df['att'].astype(str).str.upper().str.strip()

                                            has_fer_rfs = sec_df['_att_up'].isin({'FER', 'RFS'}).any()

                                            real_sec = sec_df[~sec_df['_att_up'].isin({'FER', 'RFS'})].copy()

                                            only_fer_rfs = (len(real_sec) == 0) and (not sec_turno_present)

                                        else:

                                            real_sec = sec_df

                                            only_fer_rfs = True


                                        # default: se c'e' un turno "reale" (non FER/RFS) o una ATT reale allora impegnato

                                        prim_up = (primary_code or '').strip().upper()

                                        engaged = ((prim_up != '') and (prim_up not in {'FER', 'RFS'})) or (len(real_sec) > 0)

                                        # override: solo FER/RFS come secondaria -> non impegnato (anche se turno presente)

                                        if has_fer_rfs and only_fer_rfs:

                                            engaged = False

                                        if dt.weekday() >= 5:

                                            weekend_engaged[g] = bool(engaged)


                                        # display: tutte le secondarie (incluse FER/RFS)
                                        sec_items = []

                                        # Accumulo secondarie per codice (somma ore) per evitare duplicati tra TURNO "seconda riga" e campo ATT
                                        _sec_acc: dict[str, list] = {}

                                        # Secondarie anche da righe multiple con TURNO (stesso giorno/matricola)
                                        # (oltre al campo ATT). Es: due righe stesso giorno: TURNO=M78 e TURNO=ESAU.
                                        if sec_turno_present:
                                            for _code, _mins_sum in sec_turno_groups:
                                                _code = str(_code).strip().upper()
                                                if not _code or _code in {'NAN', 'NONE'}:
                                                    continue
                                                if _code in {'POX'}:
                                                    continue  # non mostrare POX nel calendario
                                                if _code == str(primary_code).strip().upper():
                                                    continue

                                                # per le secondarie: usa SOLO i minuti reali del DB.
                                                # evitare fallback su ore standard perche' genera pillole "fantasma"
                                                # quando nel DB il valore e' 0.
                                                _hrs = float(_mins_sum) / 60.0 if float(_mins_sum) > 0 else 0.0
                                                if _hrs <= 0 and _code not in {'FREE'}:
                                                    continue

                                                _extra_cls = 'gtstr' if (_code in {'STR', 'RPD', 'RPN'} and float(_mins_sum) > 0) else ''
                                                if _code not in _sec_acc:
                                                    _sec_acc[_code] = [0.0, '']
                                                _sec_acc[_code][0] += float(_hrs)
                                                if _extra_cls:
                                                    _sec_acc[_code][1] = _extra_cls

                                        # Secondarie da campo ATT (attivita' secondarie "esplicite")
                                        if len(sec_df) > 0:
                                            grp = (
                                                sec_df.groupby('att', as_index=False)
                                                      .agg(minuti=('minuti', 'sum'))
                                                      .sort_values('minuti', ascending=False)
                                            )

                                            # Mostra TUTTE le attivita' secondarie (richiesta)
                                            for _, r in grp.iterrows():
                                                _att_code = str(r['att']).strip().upper()
                                                if not _att_code or _att_code in {'NAN', 'NONE'}:
                                                    continue
                                                _mins_sum = float(r['minuti']) if pd.notna(r['minuti']) else 0.0
                                                _hrs = (_mins_sum / 60.0) if _mins_sum > 0 else 0.0
                                                _extra_cls = 'gtstr' if (_att_code in {'STR', 'RPD', 'RPN'} and _mins_sum > 0) else ''
                                                if _att_code not in _sec_acc:
                                                    _sec_acc[_att_code] = [0.0, '']
                                                _sec_acc[_att_code][0] += float(_hrs)
                                                if _extra_cls:
                                                    _sec_acc[_att_code][1] = _extra_cls

                                        # materializza lista ordinata per ore decrescenti
                                        # razionalizza: 1 pillola per codice (somma ore) e niente duplicati
                                        # (evita doppio passaggio su sec_df che generava ripetizioni)
                                        _keep_zero = {'FREE'}
                                        sec_items = [
                                            (_c, round(v[0], 2), '', v[1])
                                            for _c, v in sorted(_sec_acc.items(), key=lambda kv: kv[1][0], reverse=True)
                                            if (float(v[0]) > 0.0) or (_c in _keep_zero)
                                        ]

                                        # placeholder compatibilita' (usato dalla renderer)
                                        extra = 0


                                        td_cls = 'day-cell weekend' if dt.weekday() >= 5 else 'day-cell'

                                        td_classes.append(td_cls)

                                        force_free = bool(has_fer_rfs and only_fer_rfs)

                                        # evidenzia turno primario:
                                        # - rosso se match in tabella Straordinario (manuale)
                                        # - giallo se straordinario GT presente (STR/RPD/RPN in Attivita con minuti>0) ma NON in Straordinario
                                        is_ot = False
                                        if (primary_code or '').strip() != '':
                                            _t = str(primary_code).strip().upper()
                                            _d = pd.to_datetime(dt).date()
                                            is_ot = (str(matr).strip(), _d, _t) in overtime_keys

                                        # Straordinario "GT" da Attivita: righe secondarie (ATT o TURNO) con STR/RPD/RPN e minuti>0
                                        gt_codes = {'STR', 'RPD', 'RPN'}
                                        gt_mins = 0.0
                                        try:
                                            if len(sec_df) > 0:
                                                _tmp = sec_df.copy()
                                                _tmp['_att_up'] = _tmp['att'].astype(str).str.strip().str.upper()
                                                if 'minuti' in _tmp.columns:
                                                    _tmp['_mins'] = pd.to_numeric(_tmp['minuti'], errors='coerce').fillna(0.0)
                                                elif 'valore' in _tmp.columns:
                                                    _v = pd.to_numeric(_tmp['valore'], errors='coerce').fillna(0.0)
                                                    _tmp['_mins'] = (_v * 60.0) if float(_v.max() if len(_v) else 0.0) <= 24.0 else _v
                                                else:
                                                    _tmp['_mins'] = 0.0
                                                gt_mins += float(_tmp.loc[_tmp['_att_up'].isin(gt_codes) & (_tmp['_mins'] > 0), '_mins'].sum())
                                            if sec_turno_present:
                                                for _c, _m in sec_turno_groups:
                                                    _c = str(_c).strip().upper()
                                                    if _c in gt_codes and float(_m) > 0:
                                                        gt_mins += float(_m)


                                        except:
                                            pass

                                        is_gt = (gt_mins > 0) and (not is_ot)

                                        cell_htmls.append(_cell(primary_code, ph, sec_items, extra, force_free=force_free, weekendfree=False, is_overtime=is_ot, is_gt_overtime=is_gt))

                                        day_state.append({'primary': primary_code, 'ph': ph, 'sec_items': sec_items, 'extra': extra, 'only_fer_rfs': only_fer_rfs, 'has_any_sec': (len(sec_df) > 0) or sec_turno_present, 'is_ot': is_ot, 'is_gt': is_gt, 'gt_mins': gt_mins})

                                        exp[f"{g:02d}"] = (primary_code or '').strip()


                                    # NEW FEATURE: evidenzia WEEKEND FREE (sfondo verde chiaro)

                                    # Se SAB+DOM entrambi "non impegnati" (nessun turno e nessuna secondaria reale),

                                    # marca le celle come freeweek. Se nelle celle ci sono solo FER/RFS, resta freeweek ma si mostrano anche.

                                    for idx, d0 in enumerate(day_dates[:-1]):

                                        if d0.weekday() == 5:  # sabato

                                            g0 = idx + 1

                                            g1 = g0 + 1

                                            if weekend_engaged.get(g0, True) is False and weekend_engaged.get(g1, True) is False:

                                                # aggiungi badge FREE se non c'e' turno (e/o solo FER/RFS)

                                                st0 = day_state[g0 - 1]

                                                st1 = day_state[g1 - 1]

                                                # ricostruisci celle con stile "weekendfree" applicato alle pillole FREE/FER/RFS
                                                st0_force = bool(st0.get('only_fer_rfs', False) and st0.get('has_any_sec', False))
                                                st1_force = bool(st1.get('only_fer_rfs', False) and st1.get('has_any_sec', False))

                                                if (st0['primary'] or '').strip() == '':
                                                    cell_htmls[g0 - 1] = _cell('FREE', 0.0, st0['sec_items'], st0['extra'], force_free=True, weekendfree=True, is_overtime=False, is_gt_overtime=False)
                                                else:
                                                    _t0 = str(st0['primary']).strip().upper()
                                                    _d0 = pd.to_datetime(day_dates[g0 - 1]).date()
                                                    is_ot0 = (str(matr).strip(), _d0, _t0) in overtime_keys
                                                    cell_htmls[g0 - 1] = _cell(st0['primary'], st0['ph'], st0['sec_items'], st0['extra'], force_free=st0_force, weekendfree=True, is_overtime=is_ot0, is_gt_overtime=bool(st0.get('is_gt', False)))

                                                if (st1['primary'] or '').strip() == '':
                                                    cell_htmls[g1 - 1] = _cell('FREE', 0.0, st1['sec_items'], st1['extra'], force_free=True, weekendfree=True, is_overtime=False, is_gt_overtime=False)
                                                else:
                                                    _t1 = str(st1['primary']).strip().upper()
                                                    _d1 = pd.to_datetime(day_dates[g1 - 1]).date()
                                                    is_ot1 = (str(matr).strip(), _d1, _t1) in overtime_keys
                                                    cell_htmls[g1 - 1] = _cell(st1['primary'], st1['ph'], st1['sec_items'], st1['extra'], force_free=st1_force, weekendfree=True, is_overtime=is_ot1, is_gt_overtime=bool(st1.get('is_gt', False)))

                                                td_classes[g0 - 1] = td_classes[g0 - 1] + ' freeweek'
                                                td_classes[g1 - 1] = td_classes[g1 - 1] + ' freeweek'


                                    # Costruisci i <td> finali (dopo eventuale FREE weekend)

                                    tds = [f"<td class='{cls}'>{html}</td>" for cls, html in zip(td_classes, cell_htmls)]


                                    # mostra stato in forza (se noto)

                                    if not in_forza_p:

                                        stato_lbl = "Non in forza"

                                    else:

                                        stato_lbl = "In forza"


                                    left = _person_box(nome, matr, uo_p, cat_p, total_h, in_forza_p)

                                    rows.append("<tr><td class='sticky-col'>" + left + "</td>" + "".join(tds) + "</tr>")

                                    export_rows.append(exp)


                                tot_persone = len(people)

                                tot_giorni_con_dati = presenze

                                tot_celle = tot_persone * giorni_mese

                                perc_copertura = (tot_giorni_con_dati / tot_celle * 100) if tot_celle else 0.0


                                # --- Statistiche ---
                                if not _in_popup:
                                    st.markdown("---")
                                    st.markdown("### 📊 Riepilogo")
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.markdown(textwrap.dedent(f"""
                                        <div class="metric-card">
                                          <div class="metric-value">{tot_persone}</div>
                                          <div class="metric-label">Persone</div>
                                        </div>
                                        """), unsafe_allow_html=True)
                                    with col2:
                                        st.markdown(textwrap.dedent(f"""
                                        <div class="metric-card">
                                          <div class="metric-value">{giorni_mese}</div>
                                          <div class="metric-label">Giorni Mese</div>
                                        </div>
                                        """), unsafe_allow_html=True)
                                    with col3:
                                        st.markdown(textwrap.dedent(f"""
                                        <div class="metric-card">
                                          <div class="metric-value">{tot_giorni_con_dati:,}</div>
                                          <div class="metric-label">Presenze</div>
                                        </div>
                                        """), unsafe_allow_html=True)
                                    with col4:
                                        color = "var(--success)" if perc_copertura >= 80 else "var(--warning)" if perc_copertura >= 50 else "var(--danger)"
                                        st.markdown(textwrap.dedent(f"""
                                        <div class="metric-card">
                                          <div class="metric-value" style="color: {color};">{perc_copertura:.1f}%</div>
                                          <div class="metric-label">Copertura</div>
                                        </div>
                                        """), unsafe_allow_html=True)

                                # --- Tabella calendario ---
                                if not _in_popup:
                                    st.markdown('---')
                                    st.markdown(f"### 📅 Calendario {mese} {anno}")                                # Adatta l'altezza dello scroll interno al contenitore (utile in popup full-screen)
                                cal_max_h = max(360, int(_height * (0.92 if _in_popup else 0.82)))
                                # In popup vogliamo una griglia che riempia lo spazio dell'iframe.
                                calwrap_dim = f"height:{cal_max_h}px; max-height:none;" if _in_popup else f"max-height:{cal_max_h}px;"

                                css = f"""

                                <style>

                                 /* --- Calendario: look piu' "gestionale" e compatto --- */

                                /* Scroll interno: header sticky + corpo scrollabile */

                                .calwrap{{{calwrap_dim} overflow:auto; scrollbar-gutter: stable both-edges; border:1px solid #E2E8F0; border-radius:10px; background:white;}}

                                table.cal{{border-collapse:separate; border-spacing:0; min-width:1200px; width:max-content;

                                          font-family: Calibri, "Segoe UI", Arial, sans-serif; font-size:11px;}}

                                table.cal th, table.cal td{{border-bottom:1px solid #EEF2F7; border-right:1px solid #EEF2F7; padding:3px; vertical-align:top;}}

                                table.cal th{{position:sticky; top:0; background:#F8FAFC; z-index:3; text-align:center; font-weight:700; color:#0F172A;}}

                                table.cal th .dow{{display:block; font-weight:600; font-size:11px; color:#64748B; text-transform:lowercase;}}

                                .sticky-col{{position:sticky; left:0; z-index:4; background:white; min-width:210px; max-width:210px;}}

                                th.sticky-h{{left:0; z-index:5; text-align:left;}}

                                .pbox{{line-height:1.1;}}

                                .pname{{font-weight:800; color:#0F172A; font-size:12px;}}

                                .psub{{font-size:10.5px; color:#475569; margin-top:2px;}}

                                .muted{{color:#94A3B8; margin-left:6px;}}

                                .ok{{color:#16A34A; font-weight:700;}}

                                .ko{{color:#DC2626; font-weight:700;}}

                                .day-cell{{min-width:70px; max-width:70px; background:#FFFFFF;}}

                                table.cal th.weekend{{background:#E6F7FF;}}

                                td.day-cell.weekend{{background:#E6F7FF;}}

                                td.day-cell.weekend .cell.empty{{background:#DFF3FF;}}

                                /* FREE weekend: evidenzia SOLO la pillola (non la cella) */

                                .cell{{display:flex; flex-direction:column; gap:2px; min-height:28px;}}

                                .cell.empty{{background:#F8FAFC; border-radius:6px;}}

                                /* Badge compatto: avvicina codice turno e ore */

                                .badge{{display:flex; justify-content:flex-start; align-items:center; gap:2px; border-radius:6px; padding:1px 4px; border:1px solid #E2E8F0;}}

                                .badge .left{{display:flex; flex-direction:column; gap:2px;}}

                                .badge .code{{font-weight:800; letter-spacing:0.2px; line-height:1.05;}}

                                .badge .sub{{font-size:9px; color:#64748B; line-height:1.05;}}

                                .badge .hrs{{font-size:10px; color:#475569; white-space:nowrap; margin-left:1px;}}

                                .badge.primary{{background:#EFF6FF; border-color:#BFDBFE;}}
                                /* Straordinario (solo turno primario): evidenzia in rosso se match in tabella Straordinario */
                                .badge.overtime{{background:#FEE2E2; border-color:#FCA5A5;}}
                                .badge.gtstr{{background:#FEF9C3; border-color:#FDE047;}}
                                .badge.gtstr .code{{color:#B91C1C; font-weight:800;}}
                                .badge.gtstr .hrs{{color:#B91C1C; font-weight:800;}}
                                .badge.overtime .code{{color:#991B1B;}}
                                .badge.overtime .hrs{{color:#991B1B; font-weight:800;}}

                                /* Nessun match straordinario (solo turno primario): sfondo giallo, testo rosso */
                                .badge.free{{background:#DCFCE7; border-color:#86EFAC;}}

                                /* Weekend free: bordo amaranto sulla pillola (stesso colore delle FREE) */

                                .badge.free.weekendfree{{border:2px solid #7A1230;}}

                                /* Se il weekend e' libero, contorna TUTTE le pillole del sab/dom (anche turno primario) */
                                td.freeweek .badge{{border-color:#7A1230 !important; border-width:2px !important;}}

                                .badge.secondary{{background:#F8FAFC;}}

                                .more{{font-size:11px; color:#64748B; text-align:right;}}

                                </style>

                                """


                                header_cells = []

                                for d, h in zip(day_dates, headers):

                                    cls = "weekend" if d.weekday() >= 5 else ""

                                    header_cells.append(f"<th class='{cls}'>{h}</th>")

                                header_html = "<tr><th class='sticky-h'>Nominativo</th>" + "".join(header_cells) + "</tr>"

                                table_html = "<div class='calwrap'><table class='cal'>" + header_html + "".join(rows) + "</table></div>"

                                # NOTE: usare components.html evita che Streamlit/Markdown trasformi l'HTML in testo (code block)

                                # in presenza di indentazioni/tab nei <style>.

                                # scrolling=False: lo scroll avviene dentro .calwrap (header sticky sempre visibile)

                                components.html(css + table_html, height=_height, scrolling=False)


                                if not _in_popup:
                                    # Export (CSV) con turno primario per giorno
                                    export_df = pd.DataFrame(export_rows)
                                    csv = export_df.to_csv(index=False).encode('utf-8')
                                    st.download_button(
                                        '📥 Scarica Calendario CSV',
                                        csv,
                                        f'calendario_{mese}_{anno}.csv',
                                        'text/csv',
                                        width='stretch'
                                    )

    if st.session_state.crosstab_show:
        _render_crosstab_calendar(mese, anno, meta_view, genera_crosstab, 720)




# ===== CONTEGGI TURNI CROSSTAB =====
elif st.session_state.page == 'Conteggi Turni Crosstab':
    st.markdown("""
    <div class="page-header">
        <div class="page-title">🧮 Conteggi Turni (Crosstab)</div>
        <div class="page-subtitle">Conteggio turni per persona con mesi in colonna (dinamico su intervallo date)</div>
    </div>
    """, unsafe_allow_html=True)

    uo_sel, cat_sel = get_relational_selections()
    meta = get_person_meta_rel_filtered(uo_sel=uo_sel, cat_sel=cat_sel)

    # filtri maschera
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.4, 1.4])
    today = date.today()
    default_start = date(today.year, today.month, 1)
    default_end = (date(today.year + (today.month // 12), ((today.month % 12) + 1), 1) - timedelta(days=1))

    with c1:
        dt_from = st.date_input('📅 Da', value=st.session_state.get('turnicnt_from', default_start), format='DD/MM/YYYY', key='turnicnt_from')
    with c2:
        dt_to = st.date_input('📅 A', value=st.session_state.get('turnicnt_to', default_end), format='DD/MM/YYYY', key='turnicnt_to')
    with c3:
        exclude_abs = st.checkbox('Escludi assenze (FER/RPD/MAL/ASS/...)', value=True, key='turnicnt_excl_abs')
    with c4:
        mode = st.selectbox('Modalità', ['Totale per mese', 'Dettaglio per turno (mese × turno)'], key='turnicnt_mode')

    turno_filter = st.text_input('🔎 Filtro turno (wildcard)', value=st.session_state.get('turnicnt_turno_filter', ''), placeholder='es. rp*  |  p3*  |  *fer*', key='turnicnt_turno_filter')

    # nominativi (coerenti con filtro relazionale)
    meta2 = meta.copy()
    only_active = st.checkbox('Solo personale in servizio', value=True, key='turnicnt_only_active')
    if only_active and 'in_forza' in meta2.columns:
        meta2 = meta2[meta2['in_forza'] == True]

    name_map = {
        str(r['matricola']): str(r['nome']).strip() for _, r in meta2.iterrows()
    } if len(meta2) else {}
    nominativi_opts = [
        (f"{(name_map.get(m) or '').strip()} | {m}" if (name_map.get(m) or '').strip() else f"{m}")
        for m in sorted(name_map.keys(), key=lambda x: (name_map.get(x) or x))
    ]

    sel_all = st.checkbox('Tutti i nominativi (filtrati)', value=True, key='turnicnt_all_names')
    selected_mats = list(name_map.keys())
    if not sel_all:
        chosen = st.multiselect('👤 Nominativi', nominativi_opts, default=nominativi_opts[:min(10, len(nominativi_opts))], key='turnicnt_names')
        selected_mats = [x.split('|')[-1].strip() for x in chosen]

    # carica Attivita
    try:
        att = db.get_all('Attivita')
    except Exception as e:
        att = pd.DataFrame()
        st.error(f"Errore lettura Attivita: {e}")

    if att is None or att.empty:
        st.info('Nessun dato Attivita disponibile.')
    else:
        # filtri globali relazionali sempre applicati
        att = apply_relational_filters(att, uo_sel=uo_sel, cat_sel=cat_sel)
        att['matricola'] = att['matricola'].astype(str).str.strip()
        if selected_mats:
            att = att[att['matricola'].isin(set(selected_mats))]

        # date
        att['data'] = pd.to_datetime(att['data'], errors='coerce', dayfirst=True)
        att = att.dropna(subset=['data'])
        att = att[(att['data'].dt.date >= dt_from) & (att['data'].dt.date <= dt_to)]

        # turno
        if 'turno' not in att.columns:
            st.warning("Colonna 'turno' non presente in Attivita.")
        else:
            t = att.copy()

            # normalizza colonne testo (turno + attività) per filtro wildcard
            # turno è la colonna principale; se turno è vuoto ma l'attività è valorizzata,
            # useremo un "codice effettivo" per conteggiare.
            t['turno'] = t['turno'].fillna('').astype(str).str.strip()
            t['_turno_norm'] = t['turno'].astype(str).str.strip().str.upper()

            # trova colonne attività presenti in Attivita
            cols_l = {str(c).strip().lower(): c for c in t.columns}
            act_candidates = [
                'att', 'att1', 'att2', 'attivita', 'attività', 'attivita1', 'attivita2',
                'att_prim', 'att_sec', 'att_secondaria', 'att_second', 'attivita_secondaria', 'attività_secondaria'
            ]
            act_cols = []
            for k in act_candidates:
                if k in cols_l and cols_l[k] not in act_cols:
                    act_cols.append(cols_l[k])

            match_cols = ['_turno_norm']
            for c in act_cols:
                norm_c = f"_{str(c).strip().lower()}_norm"
                t[norm_c] = t[c].fillna('').astype(str).str.strip().str.upper()
                match_cols.append(norm_c)

            # filtro testo con wildcard (* = jolly). Default: "contiene" (rp => *rp*)
            pats = _compile_wildcard_patterns(turno_filter)
            if pats:
                union = "(?:" + ")|(?:".join(pats) + ")"
                mask = pd.Series(False, index=t.index)
                for c in match_cols:
                    mask = mask | t[c].str.contains(union, regex=True, na=False)
                t = t[mask]

            # se non matcha nulla, spiegalo chiaramente
            if t is None or len(t) == 0:
                st.warning("Nessun record in Attivita corrisponde al filtro testo indicato nel periodo selezionato.")
                st.stop()

            # codifica effettiva per conteggio: turno se presente, altrimenti prima attività non vuota
            t['_cod_eff'] = t['_turno_norm']
            for c in match_cols[1:]:
                miss = t['_cod_eff'].eq('')
                if miss.any():
                    t.loc[miss, '_cod_eff'] = t.loc[miss, c]
            t['turno'] = t['_cod_eff']

            # gestione "Escludi assenze": se stai cercando esplicitamente un codice assenza (RPD/FER/...)
            # non ha senso escluderlo: lo disattiviamo automaticamente per evitare tabella vuota.
            abs_codes = {'FER', 'RFS', 'RPD', 'MAL', 'ASS', 'RIP', 'RIPO', 'PER', 'ASP', 'CONG', 'SCI', 'ALTRO'}
            exclude_abs_effective = exclude_abs
            if exclude_abs and turno_filter and str(turno_filter).strip():
                toks = [x.strip().upper().replace('*','') for x in re.split(r"[,\s;|]+", str(turno_filter)) if x.strip()]
                if any(x in abs_codes for x in toks):
                    exclude_abs_effective = False
                    st.info("Filtro testo contiene un codice assenza (es. FER/RPD/...): disattivo 'Escludi assenze' per mostrare i risultati.")

            if exclude_abs_effective:
                t = t[~t['turno'].isin(abs_codes)]

            # rimuovi codici vuoti
            t = t[t['turno'].astype(str).str.strip() != '']

            # mese label
            t['mese'] = t['data'].dt.to_period('M').astype(str)

            # label persona (Nome | Matricola) con fallback robusto
            meta_lbl = meta2[['matricola', 'nome']].copy() if len(meta2) else pd.DataFrame(columns=['matricola','nome'])
            meta_lbl['matricola'] = meta_lbl['matricola'].astype(str).str.strip()
            meta_lbl['nome'] = meta_lbl.get('nome', '').fillna('').astype(str).str.strip() if 'nome' in meta_lbl.columns else ''
            t = t.merge(meta_lbl, on='matricola', how='left')

            # normalizza colonna nome dopo merge (gestisce suffix _x/_y)
            if 'nome' not in t.columns:
                for cand in ['nome_y', 'nome_x', 'nominativo', 'dipendente', 'persona']:
                    if cand in t.columns:
                        t = t.rename(columns={cand: 'nome'})
                        break
            if 'nome' not in t.columns:
                t['nome'] = ''


            # fallback: se nome mancante, prova a recuperarlo dai dati Attivita (se presente)
            try:
                # cerca colonne candidate che contengono il nominativo
                cand_cols = [c for c in t.columns if str(c).strip().lower() in {
                    'nominativo','dipendente','persona','nome_persona','cognome_nome','cognomenome','nome_dipendente','nome e cognome','cognome e nome'
                }]
                if cand_cols:
                    src = cand_cols[0]
                    if 'nome' not in t.columns:
                        t['nome'] = ''
                    miss = t['nome'].fillna('').astype(str).str.strip() == ''
                    t.loc[miss, 'nome'] = t.loc[miss, src].fillna('').astype(str).str.strip()
            except Exception:
                pass
            if 'nome' not in t.columns:
                t['nome'] = ''
            t['nome'] = t['nome'].fillna('').astype(str).str.strip()
            t['persona'] = t.apply(lambda r: (f"{str(r.get('nome','')).strip()} | {r.get('matricola','')}" if str(r.get('nome','')).strip() else f"{r.get('matricola','')}"), axis=1)
            # ore (somma minuti/60) - usa colonna 'valore' se presente (minuti)
            if 'valore' in t.columns:
                t['_minuti'] = pd.to_numeric(t['valore'], errors='coerce').fillna(0.0)
            elif 'minuti' in t.columns:
                t['_minuti'] = pd.to_numeric(t['minuti'], errors='coerce').fillna(0.0)
            else:
                t['_minuti'] = 0.0
            t['_ore'] = (t['_minuti'] / 60.0).astype(float)

            if mode == 'Totale per mese':
                pv = pd.pivot_table(t, index='persona', columns='mese', values='turno', aggfunc='count', fill_value=0)
            else:
                pv = pd.pivot_table(t, index='persona', columns=['mese', 'turno'], values='matricola', aggfunc='count', fill_value=0)

            # pivot ore (somma ore) coerente coi filtri applicati
            try:
                if mode == 'Totale per mese':
                    pv_ore = pd.pivot_table(t, index='persona', columns='mese', values='_ore', aggfunc='sum', fill_value=0.0)
                    pv_ore = pv_ore.reindex(columns=pv.columns, fill_value=0.0)
                else:
                    pv_ore = pd.pivot_table(t, index='persona', columns=['mese','turno'], values='_ore', aggfunc='sum', fill_value=0.0)
                    pv_ore = pv_ore.reindex(columns=pv.columns, fill_value=0.0)
            except Exception:
                pv_ore = None


            # ordina per totale desc
            try:
                pv['Totale'] = pv.sum(axis=1)
                if pv_ore is not None:
                    pv['Ore'] = pv_ore.sum(axis=1).round(2)
                pv = pv.sort_values('Totale', ascending=False)
            except Exception:
                pass

            st.markdown('---')
            st.caption('Suggerimento: puoi scrollare orizzontalmente per vedere tutti i mesi (e i turni, in modalità dettaglio).')
            st.dataframe(pv, use_container_width=True, height=620)

            # download
            try:
                csv = pv.reset_index().to_csv(index=False).encode('utf-8')
                st.download_button('📥 Scarica CSV', csv, 'conteggi_turni_crosstab.csv', 'text/csv', width='content')
            except Exception:
                pass


# ===== SPECIALIZZAZIONI PERSONALE =====
elif st.session_state.page == 'Specializzazioni Personale':
    st.markdown("""
    <div class="page-header">
        <div class="page-title">🎯 Specializzazioni Personale</div>
        <div class="page-subtitle">Vista completa delle specializzazioni (SpecUO/Comp) per dipendente</div>
    </div>
    """, unsafe_allow_html=True)

    uo_sel, cat_sel = get_relational_selections()
    meta = get_person_meta_rel_filtered(uo_sel=uo_sel, cat_sel=cat_sel)

    c1, c2, c3 = st.columns([1.2, 2.2, 1.2])
    with c1:
        only_active = st.checkbox('Solo personale in servizio', value=True, key='spec_only_active')
    with c2:
        view_mode = st.selectbox('Vista', ['Per persona', 'Per specializzazione'], key='spec_view_mode')
    with c3:
        show_details = st.checkbox('Mostra dettaglio righe', value=False, key='spec_show_details')

    meta2 = meta.copy()
    if only_active and 'in_forza' in meta2.columns:
        meta2 = meta2[meta2['in_forza'] == True]

    try:
        spec_pers = db.get_all('SpecUOPers')
    except Exception as e:
        spec_pers = pd.DataFrame()
        st.error(f"Errore lettura SpecUOPers: {e}")

    if spec_pers is None or spec_pers.empty:
        st.info('Nessun record in SpecUOPers.')
    else:
        # normalizza nomi colonna (strip) senza cambiare lo schema
        spec_pers = spec_pers.copy()
        spec_pers.columns = [str(c).strip() for c in spec_pers.columns]
        if 'matricola' not in spec_pers.columns:
            # prova colonne alternative
            cols_l = {str(c).strip().lower(): c for c in spec_pers.columns}
            mcol = cols_l.get('matricola') or cols_l.get('matr')
            if mcol and mcol in spec_pers.columns:
                spec_pers = spec_pers.rename(columns={mcol: 'matricola'})
        if 'matricola' not in spec_pers.columns:
            spec_pers['matricola'] = ''
        spec_pers['matricola'] = spec_pers['matricola'].astype(str).str.strip()

        # applica filtro relazionale globale (regola di progetto)
        spec_pers = apply_relational_filters(spec_pers, uo_sel=uo_sel, cat_sel=cat_sel)
        if only_active and len(meta2):
            keep = set(meta2['matricola'].astype(str).str.strip())
            spec_pers = spec_pers[spec_pers['matricola'].isin(keep)]

        # colonne specializzazione
        spec_col = None
        for c in ['SpecUO/Comp', 'specuo/comp', 'specializzazione', 'spec']:
            if c in spec_pers.columns:
                spec_col = c
                break
        if spec_col is None:
            # fallback: trova colonna che contiene 'spec'
            for c in spec_pers.columns:
                if 'spec' in str(c).lower():
                    spec_col = c
                    break

        if spec_col is None:
            st.warning("Non trovo la colonna specializzazione in SpecUOPers (attesa: 'SpecUO/Comp').")
        else:
            spec_pers[spec_col] = spec_pers[spec_col].astype(str).str.strip()
            spec_pers = spec_pers[spec_pers[spec_col] != '']

            # merge nome
            meta_lbl = meta2[['matricola', 'nome', 'uo', 'cat']].copy() if len(meta2) else pd.DataFrame(columns=['matricola','nome','uo','cat'])
            meta_lbl['matricola'] = meta_lbl['matricola'].astype(str).str.strip()
            df = spec_pers.merge(meta_lbl, on='matricola', how='left')
            df['persona'] = df.apply(lambda r: f"{(r.get('nome') or '').strip()} | {r['matricola']}", axis=1)

            # filtri pagina
            all_specs = sorted(df[spec_col].dropna().unique().tolist())
            sel_specs = st.multiselect('🎯 Filtra specializzazioni', all_specs, default=[], key='spec_sel_specs')
            if sel_specs:
                df = df[df[spec_col].isin(sel_specs)]

            all_people = sorted(df['persona'].dropna().unique().tolist())
            sel_people = st.multiselect('👤 Filtra nominativi', all_people, default=[], key='spec_sel_people')
            if sel_people:
                df = df[df['persona'].isin(sel_people)]

            st.markdown('---')

            if view_mode == 'Per persona':
                grp = (df.groupby(['persona'], dropna=False)[spec_col]
                         .apply(lambda s: sorted(set([x for x in s.astype(str) if x.strip()])))
                         .reset_index())
                grp['# specializzazioni'] = grp[spec_col].apply(len)
                grp['specializzazioni'] = grp[spec_col].apply(lambda lst: ", ".join(lst))
                out = grp[['persona', '# specializzazioni', 'specializzazioni']].sort_values(['# specializzazioni','persona'], ascending=[False, True])
                st.dataframe(out, use_container_width=True, height=620)
            else:
                grp = (df.groupby([spec_col], dropna=False)['persona']
                         .apply(lambda s: sorted(set([x for x in s.astype(str) if x.strip()])))
                         .reset_index())
                grp['# persone'] = grp['persona'].apply(len)
                grp['persone'] = grp['persona'].apply(lambda lst: ", ".join(lst))
                out = grp[[spec_col, '# persone', 'persone']].sort_values(['# persone', spec_col], ascending=[False, True])
                st.dataframe(out, use_container_width=True, height=620)

            if show_details:
                with st.expander('📄 Dettaglio record (SpecUOPers filtrato)', expanded=False):
                    # --- Ottimizzazione vista dettaglio ---
                    det = df.copy()

                    # 1) Formatta le date senza orario (DD/MM/YYYY)
                    for col in det.columns:
                        cl = str(col).strip().lower()

                        # evita colonne documento/testo
                        if cl.startswith('doc') or 'pdf' in cl or 'file' in cl:
                            continue

                        ser = det[col]

                        # se già datetime, formatta diretto
                        try:
                            if pd.api.types.is_datetime64_any_dtype(ser):
                                det[col] = pd.to_datetime(ser, errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
                                continue
                        except Exception:
                            pass

                        # prova parsing su colonne "date-like" o che contengono timestamp con ore
                        try:
                            looks_time = ser.astype(str).str.contains(r"\d{2}:\d{2}:\d{2}", regex=True, na=False).any()
                        except Exception:
                            looks_time = False

                        if ('data' in cl) or ('rinnovo' in cl) or ('scad' in cl) or ('scaden' in cl) or (cl in {'r_comp', 'r-comp', 'rcomp'}) or looks_time:
                            try:
                                dtc = pd.to_datetime(ser, errors='coerce', dayfirst=True)
                                if dtc.notna().any():
                                    det[col] = dtc.dt.strftime('%d/%m/%Y').fillna('')
                            except Exception:
                                pass

                    # 2) Elimina colonne replicate (nome/matricola se già in 'persona')
                    if 'persona' in det.columns:
                        for c in ['nome', 'matricola']:
                            if c in det.columns:
                                det = det.drop(columns=[c])

                    # 3) Drop colonne duplicate (stesso contenuto)
                    try:
                        seen = set()
                        keep_cols = []
                        for c in det.columns:
                            key = tuple(det[c].fillna('').astype(str).tolist())
                            if key in seen:
                                continue
                            seen.add(key)
                            keep_cols.append(c)
                        det = det[keep_cols]
                    except Exception:
                        pass

                    # 4) Ordine colonne (persona, uo, cat, spec, ...)
                    front = []
                    for c in ['persona', 'uo', 'cat', spec_col]:
                        if c in det.columns and c not in front:
                            front.append(c)
                    rest = [c for c in det.columns if c not in front]
                    det = det[front + rest]

                    st.dataframe(det, use_container_width=True, height=420)

            # download
            try:
                csv = out.to_csv(index=False).encode('utf-8')
                st.download_button('📥 Scarica CSV', csv, 'specializzazioni_personale.csv', 'text/csv', width='content')
            except Exception:
                pass


# ===== CONTROLLO WE LIBERI =====
elif st.session_state.page == 'Controllo WE liberi':
    st.markdown("""
    <div class="page-header">
        <div class="page-title">🧭 Controllo WE liberi</div>
        <div class="page-subtitle">Verifica weekend liberi (logica coerente con Calendario Crosstab)</div>
    </div>
    """, unsafe_allow_html=True)

    # --- Anagrafica ---
    # Base unica coerente con Calendario Crosstab + filtri relazionali globali (sidebar)
    meta_rel = get_person_meta_rel_filtered()

    uo_sel, cat_sel = get_relational_selections()

    # --- Filtri pagina (indipendenti) ---
    from datetime import date
    today = date.today()
    first_day = date(today.year, today.month, 1)

    c1, c2, c3, c4 = st.columns([1.6, 1.2, 2.2, 2.4])
    with c1:
        # DD/MM/YYYY come richiesto (range date)
        dr = st.date_input('📅 Periodo (da/a)', value=(first_day, today), key='we_dr', format='DD/MM/YYYY')
        if isinstance(dr, tuple) and len(dr) == 2:
            d_start, d_end = dr
        else:
            d_start, d_end = first_day, today
        if d_start > d_end:
            d_start, d_end = d_end, d_start

    with c2:
        only_active = st.checkbox('Solo in forza', value=True, key='we_only_active')

    with c3:
        cats = sorted([c for c in meta_rel['cat'].dropna().astype(str).unique().tolist() if str(c).strip()])
        sel_cats = st.multiselect('Categorie', cats, default=[], key='we_cats')

    # Lista nominativi coerente con gli altri filtri (active + cat)
    meta_pool = meta_rel.copy()
    if only_active and 'in_forza' in meta_pool.columns:
        meta_pool = meta_pool[meta_pool['in_forza'] == True]
    if sel_cats:
        meta_pool = meta_pool[meta_pool['cat'].astype(str).isin([str(x) for x in sel_cats])]

    with c4:
        people_opts = [f"{r['nome']} ({r['matricola']})" for _, r in meta_pool.sort_values(['nome','matricola']).iterrows()]
        sel_people = st.multiselect('Nominativi', people_opts, default=[], key='we_people')

    # Applica filtri finali su meta
    meta_f = meta_pool.copy()
    if sel_people:
        sel_matr = [s.split('(')[-1].replace(')', '').strip() for s in sel_people]
        meta_f = meta_f[meta_f['matricola'].astype(str).isin(sel_matr)]

    if len(meta_f) == 0:
        st.warning('Nessuna persona corrisponde ai filtri selezionati.')
        st.stop()

    # --- Dati Attivita (stessa logica del Crosstab per weekend "impegnato") ---
    att = db.get_all('Attivita')
    if att is None or len(att) == 0:
        st.info('Nessun dato in tabella Attivita.')
        st.stop()

    att = att.copy()

    # colonne essenziali
    if 'data' not in att.columns:
        st.error("❌ Colonna 'data' non trovata in Attivita")
        st.stop()
    if 'matricola' not in att.columns:
        st.error("❌ Colonna 'matricola' non trovata in Attivita")
        st.stop()

    # normalizza
    att['data'] = pd.to_datetime(att['data'], errors='coerce', dayfirst=True)
    att = att[att['data'].notna()].copy()
    att['matricola'] = att['matricola'].astype(str).str.strip()

    # filtra periodo
    start_ts = pd.to_datetime(d_start)
    end_ts = pd.to_datetime(d_end)
    att = att[(att['data'] >= start_ts) & (att['data'] <= end_ts)].copy()

    # filtri relazionali (sidebar) anche sui dati
    att = apply_relational_filters(att, uo_sel, cat_sel)

    # filtra persone
    att = att[att['matricola'].isin(meta_f['matricola'].astype(str))].copy()

    # normalizza colonne turno/att come nel Crosstab
    if 'turno' not in att.columns:
        att['turno'] = ''
    if 'att' not in att.columns:
        att['att'] = ''

    att['turno'] = att['turno'].fillna('').astype(str).str.strip().replace({'nan': '', 'None': '', 'NONE': ''})
    att['att'] = att['att'].fillna('').astype(str).str.strip().replace({'nan': '', 'None': '', 'NONE': ''})

    # chiave giorno
    att['day'] = att['data'].dt.normalize()

    # Costruisci lista weekend (sabato+dom) nel range
    all_days = pd.date_range(start=start_ts, end=end_ts, freq='D')
    sats = [d.normalize() for d in all_days if d.weekday() == 5]
    weekend_keys = []
    for sat in sats:
        sun = (sat + pd.Timedelta(days=1)).normalize()
        if sun <= end_ts:
            weekend_keys.append((sat, sun))

    if not weekend_keys:
        st.info('Nel periodo selezionato non ci sono weekend completi (sab+dom) da analizzare.')
        st.stop()

    # Precalcola stato "engaged" per (matricola, day) con la stessa logica del Crosstab
    # engaged = (turno reale) OR (att secondaria reale)
    # override: se ci sono solo FER/RFS in secondaria -> non engaged (anche se turno presente)

    engaged_map = {}  # (matr, day) -> bool
    info_map = {}     # (matr, day) -> dict(primary, sec_all, sec_real, only_fer_rfs)

    # raggruppa per giorno/persona mantenendo l'ordine dei record
    att_sorted = att.sort_index()
    for (matr, day), gdf in att_sorted.groupby(['matricola', 'day'], sort=False):
        # TURNO: primario = codice con piu' minuti (se disponibili); le altre occorrenze in TURNO
        # (stesso giorno/persona) sono considerate "secondarie" come nel Calendario Crosstab.
        _g = gdf.copy()
        if 'minuti' in _g.columns:
            _g['_mins'] = pd.to_numeric(_g['minuti'], errors='coerce').fillna(0.0)
        elif 'valore' in _g.columns:
            _v = pd.to_numeric(_g['valore'], errors='coerce').fillna(0.0)
            _g['_mins'] = (_v * 60.0) if float(_v.max() if len(_v) else 0.0) <= 24.0 else _v
        else:
            _g['_mins'] = 0.0
        
        _g['_t'] = _g['turno'].astype(str).str.strip().replace({'nan': '', 'None': '', 'NONE': ''})
        _g = _g[_g['_t'] != '']
        _g['_t_up'] = _g['_t'].astype(str).str.upper().str.strip()
        
        # ignora POX anche qui
        _g = _g[_g['_t_up'] != 'POX']
        
        primary = ''
        sec_turno_up = pd.Series([], dtype=str)
        
        if len(_g) > 0:
            _grp = (_g.groupby('_t_up', as_index=False)
                      .agg(minuti=('_mins', 'sum'))
                      .sort_values('minuti', ascending=False))
            if float(_grp['minuti'].max()) > 0:
                primary = str(_grp.iloc[0]['_t_up']).strip()
            else:
                primary = str(_g.iloc[0]['_t_up']).strip()
        
            _sec = _grp[_grp['_t_up'] != primary].copy()
            sec_turno_up = _sec['_t_up'].astype(str).str.upper().str.strip()
        
        sec_turno_real_present = sec_turno_up[~sec_turno_up.isin({'', 'FER', 'RFS'})].shape[0] > 0

        sec_df = gdf.copy()
        sec_df['_att_up'] = sec_df['att'].astype(str).str.upper().str.strip()
        sec_df = sec_df[sec_df['_att_up'] != '']

        has_fer_rfs = False
        if len(sec_df) > 0:
            has_fer_rfs = sec_df['_att_up'].isin({'FER', 'RFS'}).any()
            real_sec = sec_df[~sec_df['_att_up'].isin({'FER', 'RFS'})]
            # "solo FER/RFS" significa: non ci sono ATT reali e non ci sono TURNO secondari reali
            only_fer_rfs = (len(real_sec) == 0) and (not sec_turno_real_present)
        else:
            real_sec = sec_df
            only_fer_rfs = True

        prim_up = (primary or '').strip().upper()
        engaged = ((prim_up != '') and (prim_up not in {'FER', 'RFS'})) or (len(real_sec) > 0) or sec_turno_real_present
        if has_fer_rfs and only_fer_rfs:
            engaged = False

        engaged_map[(str(matr), day)] = bool(engaged)
        info_map[(str(matr), day)] = {
            'primary': (primary or '').strip(),
            # secondarie: ATT (incluse FER/RFS) + eventuali TURNO extra (normalizzati)
            'sec_all': sec_df['_att_up'].tolist() + [x for x in sec_turno_up.tolist() if x],
            'sec_real': real_sec['_att_up'].tolist() if len(sec_df) > 0 else [],
            'only_fer_rfs': bool(has_fer_rfs and only_fer_rfs),
        }

    # Funzioni helper per descrizione giorno
    def _day_descr(matr: str, day: pd.Timestamp) -> str:
        info = info_map.get((matr, day))
        if not info:
            return ''
        p = info.get('primary', '')
        sec = info.get('sec_all', [])
        parts = []
        if p:
            parts.append(p)
        if sec:
            # mostra secondarie (incluse FER/RFS)
            parts.append(' + '.join(sec))
        return ' | '.join(parts)

    # Calcolo per persona
    rows = []
    details = []
    for _, r in meta_f.iterrows():
        matr = str(r['matricola'])
        nome = str(r['nome'])
        cat = str(r.get('cat', ''))

        total_we = 0
        free_we = 0
        worked_we = 0

        for sat, sun in weekend_keys:
            total_we += 1
            eng_sat = engaged_map.get((matr, sat), False)
            eng_sun = engaged_map.get((matr, sun), False)

            if (not eng_sat) and (not eng_sun):
                free_we += 1
            else:
                worked_we += 1
                details.append({
                    'matricola': matr,
                    'nome': nome,
                    'cat': cat,
                    'weekend': sat.strftime('%d/%m/%Y') + ' - ' + sun.strftime('%d/%m/%Y'),
                    'sabato': _day_descr(matr, sat),
                    'domenica': _day_descr(matr, sun),
                })

        perc_free = (free_we / total_we * 100.0) if total_we else 0.0
        rows.append({
            'matricola': matr,
            'nome': nome,
            'cat': cat,
            'weekend_tot': total_we,
            'weekend_liberi': free_we,
            'weekend_lavorati': worked_we,
            '%_liberi': round(perc_free, 1),
        })

    out = pd.DataFrame(rows).sort_values(['%_liberi', 'nome'], ascending=[False, True])

    st.markdown('### ✅ Risultato')
    st.dataframe(out, width='stretch', hide_index=True)

    csv = out.to_csv(index=False).encode('utf-8')
    st.download_button('📥 Scarica riepilogo CSV', csv, 'controllo_we_liberi.csv', 'text/csv', width='stretch')

    with st.expander('🔍 Dettaglio weekend NON liberi', expanded=False):
        if details:
            det = pd.DataFrame(details).sort_values(['nome', 'weekend'])
            st.dataframe(det, width='stretch', hide_index=True)
            csv2 = det.to_csv(index=False).encode('utf-8')
            st.download_button('📥 Scarica dettaglio CSV', csv2, 'controllo_we_non_liberi_dettaglio.csv', 'text/csv', width='stretch')
        else:
            st.success('Ottimo: nessun weekend impegnato nel periodo per i filtri selezionati.')

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#64748B; font-size:0.875rem; padding:1rem;">
    <strong>PersGest v7 Enterprise</strong> | Sistema Gestione Risorse Umane<br>
    🔄 SharePoint Sync | 💾 Database Condiviso
</div>
""", unsafe_allow_html=True)

