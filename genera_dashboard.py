#!/usr/bin/env python3
"""
Genera la dashboard HTML del Piano Mattei a partire dai dati estratti
direttamente dal sito del governo (dati_progetti_mattei.json, prodotto da
estrai_dati_mattei.py) -- il CSV NON e' usato come fonte, e' solo un
export generato in aggiunta per comodita'.

Le statistiche aggregate (conteggi, budget, ecc.) NON sono calcolate qui:
vengono ricalcolate interamente in JavaScript nella pagina, a partire dal
dataset completo (ROWS) incorporato nell'HTML. Questo e' cio' che permette
alla dashboard di essere filtrabile (per direttrice/paese/stato) senza
dover rigenerare la pagina: Python si limita a normalizzare i dati grezzi
e a incorporarli.

Uso:
    python3 estrai_dati_mattei.py     # aggiorna dati_progetti_mattei.json dal sito
    python3 genera_dashboard.py       # rigenera dashboard_piano_mattei.html + CSV
"""
import csv
import json
import re
from pathlib import Path

BASE = Path(__file__).parent
DATA_JSON_PATH = BASE / "dati_progetti_mattei.json"
CSV_OUT_PATH = BASE / "progetti_piano_mattei_aggiornato.csv"
HTML_OUT_PATH = BASE / "index.html"


# ---------------------------------------------------------------- helpers --

def clean(s):
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).replace("**", "")).strip()


def norm_stato(s):
    s = clean(s)
    return "In corso" if s.lower() == "in corso" else s


def parse_importo(raw):
    """Ritorna (importo_in_milioni, valuta, nota) a partire dal testo libero del sito."""
    if not raw or not raw.strip() or raw.strip().lower() in ("da definire",):
        return None, "", raw.strip() if raw else ""
    text = raw.strip()
    text_stripped = re.sub(r"\([^)]*\)", "", text)
    pattern = re.compile(r"(€|\$)?\s*([\d]{1,3}(?:[.,]\d{1,3})*)\s*(miliardi|miliardo|milioni|milione|mila)?", re.IGNORECASE)
    amounts = []
    for m in pattern.finditer(text_stripped):
        sym, num, unit = m.groups()
        if not num or (not sym and not unit):
            continue
        n = num
        if "," in n and "." in n:
            n = n.replace(".", "").replace(",", ".")
        elif "," in n:
            n = n.replace(",", ".")
        elif "." in n and unit is None and sym:
            n = n.replace(".", "")
        val = float(n)
        u = (unit or "").lower()
        if u.startswith("miliard"):
            val_millions = val * 1000
        elif u.startswith("mil") and u != "mila":
            val_millions = val
        elif u == "mila":
            val_millions = val / 1000
        else:
            val_millions = val / 1_000_000
        cur = "USD" if sym == "$" else "EUR"
        amounts.append((val_millions, cur))
    if not amounts:
        return None, "", text
    eur_total = sum(v for v, c in amounts if c == "EUR")
    usd_total = sum(v for v, c in amounts if c == "USD")
    if eur_total and not usd_total:
        return round(eur_total, 3), "EUR", ""
    if usd_total and not eur_total:
        return round(usd_total, 3), "USD", ""
    if eur_total and usd_total:
        return round(eur_total, 3), "EUR", f"+ {round(usd_total,3)} milioni USD"
    return None, "", text


def tipo_progetto(paesi):
    n = len(paesi)
    if n == 0:
        return "Regionale / non specificato"
    if n == 1 and paesi[0] == "Africa":
        return "Panafricano"
    if n == 1:
        return "Bilaterale"
    return "Transnazionale"


# ------------------------------------------------------------- pipeline ---

def build_rows(projects):
    """Riga per riga, nello schema 'leggibile' usato per l'export CSV e per i grafici."""
    rows = []
    for p in projects:
        importo_milioni, valuta, importo_nota = parse_importo(p["importo_testo"])
        paesi = p["paesi"]
        direttrici = p["direttrici"]
        rows.append({
            "ID Progetto": p["id"],
            "ID Progetto Padre": p["id_padre"],
            "Direttrice": "; ".join(direttrici),
            "Nazione/i": ", ".join(paesi),
            "Numero Nazioni": len(paesi),
            "Tipo Progetto": tipo_progetto(paesi),
            "Nome Progetto": clean(p["titolo"]),
            "Obiettivo": clean(p["obiettivo"]),
            "Descrizione": clean(p["descrizione"]),
            "Ente Esecutore / Capofila": clean(p["ente_esecutore"]),
            "Partner": clean(p["partner"]),
            "Strumento / Risorse": "; ".join(p["risorse"]),
            "Importo (milioni)": importo_milioni if importo_milioni is not None else "",
            "Valuta": valuta,
            "Importo Nota": importo_nota,
            "Importo Testo Originale": clean(p["importo_testo"]),
            "Durata": clean(p["durata"]),
            "Stato": norm_stato(p["stato"]),
            "Collegamento Iniziative Europee": "; ".join(p["collegamento_ue"]),
            # campi ausiliari per l'analisi (non stampati nel CSV "umano" con lo stesso nome ma riusati sotto)
            "_direttrici": direttrici,
            "_paesi": paesi,
            "_importo": importo_milioni,
            "_valuta": valuta,
            "_primary_direttrice": direttrici[0] if direttrici else "Non specificata",
        })
    return rows


CSV_COLUMNS = [
    "ID Progetto", "ID Progetto Padre", "Direttrice", "Nazione/i", "Numero Nazioni",
    "Tipo Progetto", "Nome Progetto", "Obiettivo", "Descrizione",
    "Ente Esecutore / Capofila", "Partner", "Strumento / Risorse",
    "Importo (milioni)", "Valuta", "Importo Nota", "Importo Testo Originale",
    "Durata", "Stato", "Collegamento Iniziative Europee",
]


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main():
    payload = json.loads(DATA_JSON_PATH.read_text(encoding="utf-8"))
    projects = payload["progetti"]
    fonte = payload["fonte"]
    estratto_il = payload["estratto_il"]

    rows = build_rows(projects)
    write_csv(rows, CSV_OUT_PATH)
    print(f"CSV scritto: {CSV_OUT_PATH} ({len(rows)} righe)")

    # dataset "piatto" incorporato nella pagina: la dashboard calcola TUTTE le
    # statistiche in JavaScript a partire da questo, cosi' da poterle
    # ricalcolare al volo quando l'utente applica i filtri.
    export_rows = [{col: r[col] for col in CSV_COLUMNS} for r in rows]

    template_path = BASE / "dashboard_template.html"
    template = template_path.read_text(encoding="utf-8")
    html = template.replace("__ROWS_JSON__", json.dumps(export_rows, ensure_ascii=False))
    html = html.replace("__CSV_COLUMNS_JSON__", json.dumps(CSV_COLUMNS, ensure_ascii=False))
    html = html.replace("__FONTE__", fonte)
    html = html.replace("__ESTRATTO_IL__", estratto_il)
    HTML_OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard scritta: {HTML_OUT_PATH}")


if __name__ == "__main__":
    main()
