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
    python3 genera_dashboard.py       # rigenera index.html + CSV + widget/
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


# ---------------------------------------------------------------- widget --
# Widget da incorporare in siti terzi (3 iframe: testo + 2 caroselli di
# grafici). A differenza della dashboard, qui le statistiche sono calcolate
# in Python e incorporate gia' aggregate, cosi' le pagine restano leggere
# (pochi KB invece dell'intero dataset). La logica rispecchia computeStats()
# in dashboard_template.html: se cambia li', va aggiornata anche qui.

WIDGET_DIR = BASE / "widget"
DASHBOARD_URL = "https://gnucoop.github.io/dashboard-dati-piano-mattei/"
WIDGET_BASE_URL = DASHBOARD_URL + "widget/"

DIRETTRICE_ORDER = ["Acqua", "Agricoltura/Pesca", "Energia", "Infrastrutture fisiche e digitali",
                    "Istruzione/Formazione/Cultura", "Salute"]
DIRETTRICE_SLOT = {d: i + 1 for i, d in enumerate(DIRETTRICE_ORDER)}
# etichette brevi per lo spazio ridotto dei grafici del widget (il nome completo resta nel tooltip)
DIRETTRICE_SHORT = {"Agricoltura/Pesca": "Agricoltura e pesca", "Infrastrutture fisiche e digitali": "Infrastrutture",
                    "Istruzione/Formazione/Cultura": "Istruzione e cultura"}
STATO_ORDER = ["Identificato", "Formulato", "Approvato", "In corso", "Concluso"]
STATO_SLOT = {s: i + 1 for i, s in enumerate(STATO_ORDER)}


def split_list(s, sep):
    return [x.strip() for x in (s or "").split(sep) if x.strip()]


def truncate(s, n):
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def short_ente(e):
    """Nome breve di un ente esecutore, per le etichette del widget."""
    m = re.search(r"\(([A-Z][A-Z0-9-]{1,9})\)\s*$", e)
    if m:  # sigla tra parentesi, es. "Programma delle Nazioni Unite per lo Sviluppo (UNDP)"
        return m.group(1)
    return re.sub(r"^Universit[àa] degli Studi di ", "Università di ", e)


def top(counter, n):
    return sorted(counter.items(), key=lambda kv: -kv[1])[:n]


def widget_stats(rows):
    eur_rows = [r for r in rows if r["_importo"] is not None and r["_valuta"] == "EUR"]

    def primary(r):
        dirs = split_list(r["Direttrice"], ";")
        return dirs[0] if dirs else "Non specificata"

    direttrice_count, direttrice_budget, stato, paesi, paese_budget, enti = {}, {}, {}, {}, {}, {}
    for r in rows:
        for d in split_list(r["Direttrice"], ";"):
            direttrice_count[d] = direttrice_count.get(d, 0) + 1
        if r["Stato"]:
            stato[r["Stato"]] = stato.get(r["Stato"], 0) + 1
        for p in split_list(r["Nazione/i"], ","):
            if p != "Africa":
                paesi[p] = paesi.get(p, 0) + 1
        for e in re.split(r"[,;]", r["Ente Esecutore / Capofila"] or ""):
            e = e.strip()
            if len(e) > 3:
                enti[e] = enti.get(e, 0) + 1
    for r in eur_rows:
        direttrice_budget[primary(r)] = direttrice_budget.get(primary(r), 0) + r["_importo"]
        ps = split_list(r["Nazione/i"], ",")
        if ps and ps != ["Africa"]:
            reali = [p for p in ps if p != "Africa"] or ps
            for p in reali:
                paese_budget[p] = paese_budget.get(p, 0) + r["_importo"] / len(reali)

    buckets = [(0, 1, "<1M"), (1, 10, "1-10M"), (10, 50, "10-50M"), (50, 100, "50-100M"), (100, float("inf"), ">100M")]
    bucket_counts = {label: 0 for _, _, label in buckets}
    for r in eur_rows:
        for lo, hi, label in buckets:
            if lo <= r["_importo"] < hi:
                bucket_counts[label] += 1
                break

    top_progetti = sorted(eur_rows, key=lambda r: -r["_importo"])[:8]
    dir_labels = [d for d in DIRETTRICE_ORDER if d in direttrice_count]
    dir_budget_labels = [d for d in DIRETTRICE_ORDER if d in direttrice_budget]
    stato_labels = [s for s in STATO_ORDER if s in stato]
    top_paesi = top(paesi, 10)
    top_paesi_budget = top(paese_budget, 10)
    top_enti = top(enti, 8)

    charts = {
        "direttrice_count": {
            "title": "Progetti per direttrice",
            "note": "Un progetto può coprire più direttrici",
            "type": "bar", "horizontal": True, "unit": "progetti",
            "labels": [DIRETTRICE_SHORT.get(d, d) for d in dir_labels], "full_labels": dir_labels,
            "values": [direttrice_count[d] for d in dir_labels],
            "slots": [DIRETTRICE_SLOT[d] for d in dir_labels],
        },
        "stato": {
            "title": "Progetti per stato di avanzamento",
            "type": "bar", "horizontal": False, "unit": "progetti",
            "labels": stato_labels, "values": [stato[s] for s in stato_labels],
            "slots": [STATO_SLOT[s] for s in stato_labels],
        },
        "top_paesi": {
            "title": "Top 10 paesi per numero di progetti",
            "type": "bar", "horizontal": True, "unit": "progetti",
            "labels": [p for p, _ in top_paesi], "values": [n for _, n in top_paesi],
            "slots": [1] * len(top_paesi),
        },
        "top_paesi_budget": {
            "title": "Top 10 paesi per finanziamento stimato",
            "note": "Milioni di euro; progetti multi-paese ripartiti in quote uguali",
            "type": "bar", "horizontal": True, "unit": "eur",
            "labels": [p for p, _ in top_paesi_budget], "values": [round(v, 1) for _, v in top_paesi_budget],
            "slots": [3] * len(top_paesi_budget),
        },
        "direttrice_budget": {
            "title": "Finanziamento per direttrice",
            "note": "Milioni di euro, per direttrice principale",
            "type": "bar", "horizontal": True, "unit": "eur",
            "labels": [DIRETTRICE_SHORT.get(d, d) for d in dir_budget_labels], "full_labels": dir_budget_labels,
            "values": [round(direttrice_budget[d], 1) for d in dir_budget_labels],
            "slots": [DIRETTRICE_SLOT[d] for d in dir_budget_labels],
        },
        "top_progetti": {
            "title": "I progetti più grandi per importo",
            "note": "Milioni di euro",
            "type": "bar", "horizontal": True, "unit": "eur",
            "labels": [truncate(r["Nome Progetto"], 48) for r in top_progetti],
            "full_labels": [r["Nome Progetto"] for r in top_progetti],
            "values": [round(r["_importo"], 1) for r in top_progetti],
            "slots": [DIRETTRICE_SLOT.get(primary(r), 1) for r in top_progetti],
        },
        "bucket_importo": {
            "title": "Progetti per fascia di importo",
            "note": "Milioni di euro",
            "type": "bar", "horizontal": False, "unit": "progetti",
            "labels": list(bucket_counts), "values": list(bucket_counts.values()),
            "slots": [2] * len(bucket_counts),
        },
        "enti": {
            "title": "Enti esecutori più ricorrenti",
            "type": "bar", "horizontal": True, "unit": "progetti",
            "labels": [truncate(short_ente(e), 48) for e, _ in top_enti],
            "full_labels": [e for e, _ in top_enti],
            "values": [n for _, n in top_enti],
            "slots": [7] * len(top_enti),
        },
    }
    summary = {
        "n_progetti": len(rows),
        "tot_eur": round(sum(r["_importo"] for r in eur_rows)),
        "n_paesi": len(paesi),
    }
    return charts, summary


WIDGET_CAROSELLI = {
    "carosello-1.html": ["direttrice_count", "stato", "top_paesi", "top_paesi_budget"],
    "carosello-2.html": ["direttrice_budget", "top_progetti", "bucket_importo", "enti"],
}


def write_widget(rows, dashboard_template, estratto_il):
    WIDGET_DIR.mkdir(exist_ok=True)
    charts, summary = widget_stats(rows)
    logo = re.search(r"data:image/png;base64,[A-Za-z0-9+/=]+", dashboard_template).group(0)
    data_it = "/".join(reversed(estratto_il.split(" ")[0].split("-")))
    fmt_int = lambda n: f"{n:,}".replace(",", ".")

    intro = (BASE / "widget_intro_template.html").read_text(encoding="utf-8")
    intro = (intro.replace("__LOGO__", logo)
                  .replace("__DASHBOARD_URL__", DASHBOARD_URL)
                  .replace("__N_PROGETTI__", fmt_int(summary["n_progetti"]))
                  .replace("__TOT_EUR__", fmt_int(summary["tot_eur"]))
                  .replace("__N_PAESI__", fmt_int(summary["n_paesi"]))
                  .replace("__AGGIORNATO_IL__", data_it))
    (WIDGET_DIR / "intro.html").write_text(intro, encoding="utf-8")

    carosello = (BASE / "widget_carosello_template.html").read_text(encoding="utf-8")
    for i, (name, keys) in enumerate(WIDGET_CAROSELLI.items()):
        html = (carosello.replace("__CHARTS_JSON__", json.dumps([charts[k] for k in keys], ensure_ascii=False))
                         .replace("__DASHBOARD_URL__", DASHBOARD_URL)
                         .replace("__AGGIORNATO_IL__", data_it)
                         .replace("__START_OFFSET__", str(i)))
        (WIDGET_DIR / name).write_text(html, encoding="utf-8")

    # anteprima locale: lo snippet da incollare in WordPress, dentro una pagina finta
    snippet = (BASE / "widget_snippet_wordpress.html").read_text(encoding="utf-8")
    preview = ("<!DOCTYPE html>\n<html lang=\"it\"><head><meta charset=\"UTF-8\">"
               "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
               "<title>Anteprima widget Piano Mattei</title>"
               "<style>body{margin:0;background:#f4f4f4;font-family:'Noto Sans',Verdana,sans-serif}"
               ".page{max-width:1140px;margin:0 auto;padding:40px 15px}"
               ".fake{background:#ddd;height:160px;border-radius:4px;margin:24px 0;display:flex;"
               "align-items:center;justify-content:center;color:#777}</style></head><body><div class=\"page\">"
               "<div class=\"fake\">contenuto del sito</div>\n"
               + snippet.replace(WIDGET_BASE_URL, "")
               + "\n<div class=\"fake\">riquadro LinkedIn + newsletter</div></div></body></html>\n")
    (WIDGET_DIR / "anteprima.html").write_text(preview, encoding="utf-8")
    print(f"Widget scritto: {WIDGET_DIR}/ (intro.html, {', '.join(WIDGET_CAROSELLI)}, anteprima.html)")


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

    write_widget(rows, template, estratto_il)


if __name__ == "__main__":
    main()
