#!/usr/bin/env python3
"""
Estrae i dati dei progetti del Piano Mattei direttamente dal sito
https://www.governo.it/it/piano-mattei/progetti/ (nessuna dipendenza dal
CSV curato in precedenza: i dati vengono presi ad ogni esecuzione dai
bundle JavaScript pubblicati dal sito, che è come il sito stesso alimenta
la propria pagina).

Il sito e' una Next.js app: i dati dei progetti non arrivano da una vera
API, ma sono incorporati come JSON dentro uno dei chunk JS caricati dalla
pagina. L'hash del chunk cambia ad ogni deploy del sito, quindi lo script
non lo hard-codifica: legge la pagina, trova tutti i chunk referenziati e
individua quello che contiene i dati cercando un marcatore testuale
("TITOLO PROGETTO").

Uso:
    python3 estrai_dati_mattei.py
Produce:
    dati_progetti_mattei.json   (dati grezzi normalizzati, fonte per la dashboard)
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://www.governo.it"
PAGE_URL = f"{BASE_URL}/it/piano-mattei/progetti/"
OUT_PATH = Path(__file__).parent / "dati_progetti_mattei.json"

MARKER = '"slug":"progetto-'


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def find_data_chunk_url(page_html: str) -> str:
    chunk_paths = sorted(set(re.findall(r'/[A-Za-z0-9/_-]*/_next/static/chunks/[A-Za-z0-9]+\.js', page_html)))
    if not chunk_paths:
        raise RuntimeError("Nessun chunk JS trovato nella pagina: la struttura del sito potrebbe essere cambiata.")
    for path in chunk_paths:
        url = BASE_URL + path
        try:
            content = fetch(url)
        except Exception:
            continue
        if MARKER in content:
            return url, content
    raise RuntimeError(
        "Nessun chunk contiene i dati dei progetti (pattern "
        f"{MARKER!r} non trovato in nessuno dei {len(chunk_paths)} chunk). "
        "Il sito potrebbe aver cambiato struttura."
    )


def extract_json_array(js_source: str) -> list:
    marker = "JSON.parse('"
    start = js_source.find(marker)
    if start == -1:
        raise RuntimeError("Pattern JSON.parse('...') non trovato nel chunk.")
    start += len(marker)
    i = start
    while True:
        ch = js_source[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "'":
            break
        i += 1
    raw = js_source[start:i]
    unescaped = re.sub(r"\\(.)", r"\1", raw)
    return json.loads(unescaped)


def normalize(projects: list) -> list:
    """Riduce le varianti di nome-campo viste nei dati sorgente a uno schema stabile."""
    out = []
    for p in projects:
        ente = (p.get("ENTE ESECUTORE") or "").strip() or (p.get("ENTE ESECUTORE E PARTENARIATI") or "").strip()
        durata = (
            (p.get("DURATA") or "").strip()
            or (p.get("DURATA E CRONOPROGRAMMA") or "").strip()
            or (p.get("DURATA E CRONOGRAMMA") or "").strip()
        )
        out.append({
            "id": (p.get("ID") or "").strip(),
            "id_padre": (p.get("PARENT") or "").strip(),
            "slug": (p.get("slug") or "").strip(),
            "direttrici": [s.strip() for s in (p.get("SETTORE") or []) if s.strip()],
            # il sito ha almeno un refuso di battitura ("Tunisia.") che altrimenti
            # verrebbe trattato come un paese diverso da "Tunisia"
            "paesi": [c.strip().rstrip(".") for c in (p.get("PAESE") or []) if c.strip()],
            "titolo": (p.get("TITOLO PROGETTO") or "").strip(),
            "obiettivo": (p.get("OBIETTIVO") or "").strip(),
            "descrizione": (p.get("DESCRIZIONE (OBIETTIVI, ATTIVITA', RISULTATI ATTESI)") or "").strip(),
            "ente_esecutore": ente,
            "partner": (p.get("PARTENARIATI") or "").strip(),
            "risorse": [r.strip() for r in (p.get("RISORSE") or []) if r.strip()],
            "importo_testo": (p.get("IMPORTO") or "").strip(),
            "durata": durata,
            "stato": (p.get("STATO DI AVANZAMENTO (IDENTIFICAZIONE, FORMULAZIONE, APPROVAZIONE, IN CORSO, CONCLUSO)") or "").strip(),
            "collegamento_ue": [e.strip() for e in (p.get("EVENTUALE COLLEGAMENTO CON INIZIATIVE EUROPEE") or []) if e.strip()],
        })
    return out


def main():
    print(f"Scarico {PAGE_URL} ...")
    page_html = fetch(PAGE_URL)
    print("Cerco il chunk con i dati dei progetti...")
    chunk_url, chunk_content = find_data_chunk_url(page_html)
    print(f"Trovato: {chunk_url}")
    raw_projects = extract_json_array(chunk_content)
    print(f"Estratti {len(raw_projects)} record grezzi.")
    projects = normalize(raw_projects)

    payload = {
        "fonte": PAGE_URL,
        "estratto_il": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_progetti": len(projects),
        "progetti": projects,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Scritto {OUT_PATH} ({len(projects)} progetti).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)
