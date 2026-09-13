# Sensibilità ai riferimenti nel flusso locale

La diagnostica esplorativa può ora accompagnare il risultato di una richiesta.
Mostra quante esclusioni sono state provate, quante sono confrontabili, minimo,
mediana e massimo degli spostamenti, i cinque riferimenti con maggior effetto,
tutte le varianti fallite e il tempo di calcolo. La baseline non entra nelle
statistiche delle esclusioni. Nessuna soglia arbitraria classifica la richiesta
come accurata o verificata in base a questa dispersione.

## Uso

Leggere il risultato scientifico con un rapporto già disponibile:

```text
python -m service result RUN --diagnostic REPORT.json
python -m service request-status UUID --owner OWNER --queue QUEUE --runs RUNS --diagnostic REPORT.json
```

`diagnostics.reference_sensitivity` accompagna il risultato senza modificarne
verdetto, posizione, raggio prospettico o controlli. Non si riscrive il risultato
sigillato nella coda: l'aggiunta avviene soltanto nella risposta di lettura.
L'associazione richiede gli stessi byte di osservazioni ammesse e navigazione,
satellite, giorno, finestra e stazioni del rapporto. Nessuna associazione
automatica basata soltanto sul nome del satellite.

Per leggere anche i rapporti degli eventi legacy senza dossier del worker:

```text
python -m service diagnostic research/exploratory/results/g12_reference_sensitivity_v1.json --inputs research/exploratory/inputs/g12_doy248
```

Per calcolare una nuova diagnostica dopo la chiusura di una richiesta:

```text
python -m service diagnose RUN NUOVO_REPORT.json
```

Questo comando richiede un risultato terminale sigillato e avvia in un processo
separato il runner esplorativo esistente, con limite di dieci minuti. Usa gli
input già ammessi, senza download, orbita o soluzione storica come input del
fit. Il file di uscita deve essere nuovo e fuori dalla cartella della richiesta.
Nessun calcolo automatico alla lettura, nessuna modifica al worker scientifico.
Il comando `diagnostic` legge; `diagnose` calcola.

## Risposte e limiti

- `NOT_COMPUTED`: nessun rapporto richiesto; non significa zero sensibilità.
- `NOT_READY`: la richiesta in coda non ha ancora un risultato terminale.
- `UNAVAILABLE`: rapporto o input non disponibili.
- `INVALID`: rapporto contraddittorio o non corrispondente agli input.
- `AVAILABLE`: baseline e tutte le esclusioni sono confrontabili.
- `PARTIAL`: solo alcune esclusioni sono confrontabili; fallimenti conservati.
- `BASELINE_UNAVAILABLE`: mancano confronti con una baseline valida; metriche `null`.

`AVAILABLE` non significa verifica scientifica superata. Il rapporto misura la
sensibilità di una baseline di sviluppo a pesi fissi; non è l'accuratezza della
soluzione originale, un raggio al 95% o una nuova conferma. Anche l'istante di
emissione stimato può variare. Gli hash identificano file locali; non autenticano
l'autore del rapporto o certificano il modello fisico.

G14 e G12 sono già consultabili con questi comandi. HTTP, interfaccia web e
diagnostica automatica per tutte le richieste restano da realizzare.
