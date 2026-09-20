# Piano Mattei — Dashboard progetti

Dashboard interattiva e dataset strutturato dei progetti di cooperazione allo sviluppo finanziati dal governo italiano in Africa nell'ambito del [Piano Mattei](https://www.governo.it/it/piano-mattei/progetti/).

I dati **non** sono un file statico curato a mano: vengono estratti direttamente dal sito ufficiale ad ogni esecuzione degli script (vedi [Come funziona](#come-funziona-la-pipeline-dati)), quindi possono essere aggiornati in qualunque momento senza dover ricostruire nulla a mano.

## Contenuto del repo

| File | Descrizione |
|---|---|
| [`dashboard_piano_mattei.html`](dashboard_piano_mattei.html) | La dashboard, pronta all'uso — basta aprirla in un browser. Nessun server richiesto. |
| [`estrai_dati_mattei.py`](estrai_dati_mattei.py) | Script che scarica i dati aggiornati direttamente da governo.it e li normalizza in `dati_progetti_mattei.json`. |
| [`genera_dashboard.py`](genera_dashboard.py) | Rigenera `index.html` (e il CSV) a partire da `dati_progetti_mattei.json`. |
| [`dashboard_template.html`](dashboard_template.html) | Template HTML/CSS/JS della dashboard, usato da `genera_dashboard.py`. |

I file generati dalla pipeline — `dati_progetti_mattei.json`, `progetti_piano_mattei_aggiornato.csv` e `index.html` — non sono versionati: vengono ricreati da zero ad ogni esecuzione degli script e ad ogni deploy.

## Dashboard

Apri `dashboard_piano_mattei.html` in un browser. Include:

- **Quadro generale**: progetti per direttrice, stato di avanzamento, tipologia (bilaterale/transnazionale/panafricano).
- **Distribuzione geografica**: top 15 paesi per numero di progetti e per finanziamento stimato.
- **Analisi finanziaria**: top 10 progetti per importo, concentrazione del finanziamento, distribuzione per fascia di importo e per durata.
- **Analisi più approfondita**: stato di avanzamento per direttrice, importo medio per direttrice/tipologia, principali strumenti di finanziamento ed enti esecutori, struttura a programmi-ombrello.
- **Filtri interattivi** per Direttrice, Paese e Stato (in alto): tutti i grafici e le statistiche si ricalcolano al volo nel browser, senza bisogno di rigenerare la pagina.
- **Esportazione CSV**: il pulsante "Scarica dataset (CSV)" scarica l'intero dataset così com'è caricato in pagina.
- Tema chiaro/scuro (automatico in base al sistema, con toggle manuale).

Le note metodologiche complete (unità di misura, criteri di attribuzione multi-direttrice/multi-paese, casi esclusi) sono in fondo alla pagina stessa.

## Come funziona la pipeline dati

Il sito governo.it non espone una vera API: i dati dei progetti sono incorporati come JSON in uno dei bundle JavaScript caricati dalla pagina, il cui nome cambia ad ogni deploy del sito. Per questo `estrai_dati_mattei.py` non punta a un URL fisso, ma:

1. scarica la pagina `https://www.governo.it/it/piano-mattei/progetti/`;
2. individua dinamicamente, tra tutti i bundle referenziati, quello che contiene i dati dei progetti;
3. lo estrae e normalizza in `dati_progetti_mattei.json`.

`genera_dashboard.py` legge solo questo JSON (mai il CSV) e incorpora il dataset nella pagina HTML; tutte le statistiche aggregate sono calcolate lato client in JavaScript, così i filtri possono ricalcolarle istantaneamente.

**Nota:** una pagina HTML statica non può richiamare direttamente governo.it dal browser (il sito non invia gli header CORS necessari), quindi l'aggiornamento dei dati richiede di rieseguire gli script — non avviene automaticamente ad ogni apertura della dashboard.

### Aggiornare i dati

```bash
python3 estrai_dati_mattei.py     # scarica i dati aggiornati dal sito
python3 genera_dashboard.py       # rigenera index.html + CSV
```

Richiede solo Python 3 (nessuna dipendenza esterna, solo libreria standard).

## Pubblicazione

La dashboard è pubblicata su GitHub Pages all'indirizzo
[gnucoop.github.io/dashboard-dati-piano-mattei](https://gnucoop.github.io/dashboard-dati-piano-mattei/).

Il workflow [`deploy.yml`](.github/workflows/deploy.yml) riesegue l'intera pipeline
(estrazione + generazione) ogni giorno alle 04:00 UTC e pubblica `index.html`,
quindi il sito riflette sempre i dati più recenti disponibili su governo.it.
Si può lanciare anche a mano dalla tab *Actions*.

## Fonte

[governo.it/piano-mattei/progetti](https://www.governo.it/it/piano-mattei/progetti/) — Presidenza del Consiglio dei Ministri.
