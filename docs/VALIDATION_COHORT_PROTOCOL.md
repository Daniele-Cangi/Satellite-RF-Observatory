# G3: campione candidato e rapporto completo

Stato al 2026-09-12: **disegno candidato, non ammesso all'acquisizione**.
Il rapporto software è utilizzabile offline; nessuna osservazione o orbita è
stata acquisita per questo campione. Questo documento non completa G3 o S2.

## Informazione fisica cercata

Misurare quanto spesso il profilo storico `gps-code-network-v1` ammette una
richiesta dichiarata prima dei dati, quali cause lo arrestano e quali errori,
raggi prospettici e controlli GOLD produce. Il campione può descrivere la
ripetibilità condizionale di v1; non introduce un'osservabile, non qualifica
la cinematica e non dimostra copertura al 95% sulla popolazione GPS.

## Disegno concreto da ammettere

[Il candidato](../research/validation/g3_v1_candidate.json) contiene 24 piani
completi, con prodotti, regole di selezione, rete, GOLD esclusa, modello,
incertezza, soglie e arresti del profilo esistente. La versione di esecuzione
proposta è `edf76138dfa82fcc7d15cbbdcdfe0932c817b277`.

- Giorni GPST dal 1 al 24 ottobre 2026, un evento per giorno.
- G01, G09, G17, G25 in rotazione, sei eventi ciascuno. Scelta aritmetica delle
  etichette, senza consultare orbite, visibilità o qualità delle misure.
- Dieci candidati terrestri del profilo generale, sette radici di fit;
  prima finestra strutturalmente ammissibile, senza ricerca del miglior fit.
- Nessuna sostituzione di caso, giorno, prodotto, ricevitore escluso o soglia
  dopo accesso. Ogni arresto resta nel campione, anche se è un errore software.

Questo modifica esplicitamente il precedente schema proposto quattro PRN per
sei giorni: i 24 giorni distinti evitano che le effemeridi di riferimento di
un caso comprendano il bersaglio di un altro sullo stesso prodotto giornaliero.
Non dimostra indipendenza statistica: ricevitori, modelli, giorni adiacenti e
orbite di confronto possono condividere errori o dati. Non confrontare le
prestazioni dei PRN come se i giorni fossero controllati o randomizzati.

## Prima dell'esecuzione

Restano applicabili i prerequisiti S2/S3 di AGENTS.md. I residui aggregati DOY240
non risolvono trasferimento riferimento-bersaglio, atmosfera, effetti
direzionali, multipath, continuità di fase e correlazioni. Il candidato v1
non aggira questa decisione scientifica e non ammette un profilo v2.

Prima di qualunque acquisizione serve una revisione scientifica esplicita
del dominio e delle assunzioni condizionali, con accessi pregressi aggiornati,
manifest finale, versione e dipendenze congelati e ricevuta di preregistrazione.
Fissare anche istante unico di avvio dopo maturazione dei prodotti giornalieri,
limiti di tempo e risorse, registrazione dei tempi di ogni fase e gestione degli
arresti. Non verificare disponibilità con download anticipati del campione.
Se non si conclude prima del primo giorno, conservare questo candidato come
non eseguito e dichiarare un nuovo disegno prima dei nuovi dati: nessuno
spostamento silenzioso delle date. Il file candidato non è una preregistrazione
eseguibile, e il solo hash Git non certifica l'assenza di accessi.

Eseguire eventualmente in un checkout pulito della versione congelata, con
un'unica coda autorevole privata e un caso alla volta. Non aprire una seconda
coda per aggirare una quarantena. Un'interruzione richiede ispezione; nessun
riavvio automatico o nuova chiave per ripetere il caso.

## Rapporto operativo disponibile

```text
python -m service validation-report MANIFEST --bindings BINDINGS --queue QUEUE --runs RUNS --owner OWNER
```

Il comando produce JSON senza inviare richieste né avviare worker. I percorsi
di coda e runtime devono essere esterni al checkout. `BINDINGS` è un oggetto
JSON da ID del caso a UUID della richiesta; inizialmente è `{}`. Il comando
usa la normale lettura della coda, che può mettere in quarantena una lease
scaduta. Il rapporto identifica i byte del manifest con SHA-256 e verifica
le prove sigillate attraverso il lettore del worker.

Conserva tutti i casi: senza associazione, in coda, in corso, annullati,
in quarantena, con prove illeggibili e terminali. `UNBOUND` significa soltanto
che manca l'associazione alla coda; non certifica che nessuno abbia eseguito
quel caso altrove. Piano, accessi dichiarati, versione e scopo devono coincidere.

Il denominatore principale è sempre 24. La frazione osservata di verifiche
condizionali è provvisoria finché mancano terminali; la frazione finale resta
nulla. Errori e raggi riportano valori per caso e conteggi di valori mancanti,
senza imputare zeri. Disponibilità, motivo di arresto e GOLD rimangono nel
risultato di ciascun caso; un errore di esecuzione non diventa rifiuto fisico.
Il tempo di calcolo è ancora non misurato (`null`), non dedotto dall'età della
coda. Le prove sintetiche verificano questo comportamento, non la fisica.

Prima di dichiarare G3 completato servono l'ammissione scientifica, esecuzioni
reali chiuse, misure dei tempi e l'analisi dei termini d'errore ancora aperti.
