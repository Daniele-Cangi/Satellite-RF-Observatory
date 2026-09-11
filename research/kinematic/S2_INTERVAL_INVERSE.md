# S2 — Stima inversa con codici agli estremi e incrementi di fase

`interval_fit.py` aggiunge un estimatore separato per posizione, velocità,
accelerazione e clock del target, clock dei ricevitori e coordinate terrestri.
I vecchi estimatori e i loro report restano immutati. Il nuovo modello è
validato esclusivamente su dati inventati, con `real_rf_qualified=false`.

## Informazione fisica cercata

La fase precisa permette di confrontare il cambiamento del cammino nel tempo.
Non misura automaticamente una velocità istantanea. Il nuovo fit confronta
la fase osservata con la differenza di due previsioni agli stessi estremi:

```text
rate_medio[i,j] = (baseline(t[i+1],j) − baseline(t[i],j)) / (t[i+1] − t[i])
```

La baseline riusa il modello S2a con tempo di ricezione, emissione implicita,
rotazione terrestre durante il tempo di volo e clock affini. Il cammino IF
di fase condivide questa baseline solo sotto le ipotesi dichiarate: vuoto,
rimozione ionosferica al primo ordine, ambiguità costanti e nessun bias
hardware/antenna variabile. Non si equiparano codice e fase reali.

Undici epoche producono 77 codici e 70 incrementi per sette ricevitori.
Gli array hanno dunque dimensioni temporali diverse. Il fit non interpola,
non ripara slip e non aggiusta finestre o ricevitori per ottenere accettazione.

## Dati, parametri e confronto

L'ordine dei dati è codici, rate medi, clock di riferimento (due coefficienti
per ricevitore), coordinate terrestri (tre per ricevitore). Il modello ha
46 parametri: 11 del target, 14 di clock ricevitore e 21 correzioni terrestri.
Non esistono prior di traiettoria target. L'inizializzazione usa snapshot dei
codici e differenze dei codici, identici nei due bracci del confronto.

Con `include_phase=False`, i valori di fase non vengono neppure decodificati
e la covarianza è la sottomatrice marginale dei dati rimasti. Il confronto
usa gli stessi codici, clock, coordinate e perturbazioni casuali.

La covarianza grezza descrive codici e cammini IF agli estremi in metri,
clock e coordinate. La matrice di differenza trasforma il blocco di fase
e tutti i suoi blocchi incrociati in un solo passaggio. Lo studio assume
sigma codice 20 m, sigma fase 0,01 m e correlazione code/fase 0,1, oltre a
modi condivisi fra RF, calibrazione e coordinate. Sono ipotesi sintetiche,
non precisioni accertate su ricevitori. L'anticorrelazione degli estremi
condivisi resta presente, ma una deriva comune può dominare il segno totale.

Ottimizzazione, covarianza locale e test dei residui usano la stessa matrice
fissata prima delle estrazioni. Non si ristimano sigma dai residui e non si
aggiunge jitter. SVD e rango sono controllati in coordinate scalate. I gradi
di libertà sono 136 con fase e 66 senza; p < 0,01 respinge il modello.
La distribuzione chi-quadro è esatta nel problema lineare gaussiano locale,
approssimata nel modello non lineare, senza copertura totale dichiarata.

## Ricerca delle soluzioni e diagnostica

Il solver usa gli inizi finiti della soluzione snapshot; non dimostra di
avere trovato ogni ramo. Conserva costo, stato e distanza di ogni candidato
nella metrica della covarianza locale. Candidati a costo compatibile distanti
più di 0,1 sigma locale rendono il risultato ambiguo; terminazioni più vicine
appartengono alla stessa regione numerica locale per questa diagnostica.
La soglia è una regola numerica esplicita, non una prova di unicità globale.

Durante lo sviluppo, la soglia assoluta del vecchio solver classificava come
rami distinti terminazioni distanti circa 0,002 sigma. La nuova diagnostica
conserva tali candidati e la loro distanza. Il mancato accordo del modello
con i dati ha priorità nell'esito `MODEL_REJECTED`; eventuale ambiguità e
fallimenti di convergenza restano registrati. Le soglie fisiche e i casi di
stress non sono stati cambiati per farli passare.

## Previsione esclusa

`forecast_interval` prevede posizione e velocità all'estremo finale, codice
finale e rate medio su due estremi esclusi. Richiede fit e calibrazione
accettati, non legge valori target esclusi e verifica l'hash del blocco di
covarianza usato nel fit. Propaga anche i blocchi incrociati con clock,
coordinate e rumore del ricevitore escluso, se dichiarati dal chiamante.

Lo studio usa un ottavo ricevitore e gli estremi futuri 30 e 60 secondi,
con un blocco escluso esplicitamente indipendente dal fit. La previsione
viene serializzata e hashata prima di calcolare i valori di valutazione
con il generatore inerziale indipendente. È una disciplina sintetica di
previsione/valutazione, non un congelamento di nuove osservazioni reali.

## Confine con il ponte RINEX

Il fit riconosce `REFERENCE_PHASE_MODEL_ACCEPTED` e il precedente stato di
calibrazione sintetica compressa. Un riferimento respinto ferma il fit
prima della decodifica target. Riconoscere uno stato non qualifica una fonte:
il chiamante deve fornire clock, epoca, stazioni e covarianza coerenti.

Lo studio usa calibrazioni gaussiane compresse inventate, non concatena
automaticamente i file RINEX del ponte a misure target reali. Restano aperti
la qualifica del ricevitore, continuità della fase target, derivazione delle
correlazioni riferimento/target, ritardi neutri e dispersivi residui, bias
variabili, errore delle effemeridi dei riferimenti e inviluppo totale.

I risultati e le istruzioni di riproduzione sono nel
[report](results/S2_INTERVAL_REPORT.md). S3 e sito restano sospesi.
