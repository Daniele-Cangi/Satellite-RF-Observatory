# S2 — File RINEX, clock dai codici e controllo degli incrementi di fase

Il nuovo ponte collega la lettura dei riferimenti ai rate medi di fase e
alla loro previsione. Non richiede D1C/D2W e non li sostituisce nel vecchio
fit istantaneo. La verifica avviene sui soli riferimenti non-target.
Report: [results/S2_PHASE_BRIDGE_REPORT.md](results/S2_PHASE_BRIDGE_REPORT.md).

## Ordine delle operazioni

1. Fissare riferimenti, estremi degli intervalli, base GPST, covarianza grezza,
   modello di propagazione, età massima delle effemeridi e soglie.
2. Leggere i codici C1C/C2W e le fasi L1C/L2W dei soli riferimenti sulla
   griglia completa. Rifiutare dati mancanti, eventi/reset e flag di slip.
3. Ammettere come testo solo le effemeridi broadcast GPS dei riferimenti.
4. Stimare offset e drift del clock **dai soli codici**. Se fallisce il
   controllo dei codici, non eseguire quello di fase.
5. Prevedere la differenza del cammino IF fra gli stessi estremi delle fasi.
6. Confrontare gli incrementi di fase inutilizzati nella stima del clock,
   propagando clock stimato, rumore di fase e correlazioni code/fase.

`REFERENCE_PHASE_MODEL_ACCEPTED` significa coerenza col modello e con la
covarianza dichiarati. Rimane `real_rf_qualified=false`; questo esito non
è ancora ammesso automaticamente dai fit inversi precedenti.

## Importer specifico, senza modificare quello congelato

`rinex_phase_observations.py` supporta il sottoinsieme GPS di RINEX 3.04/3.05,
anche in file misti con sistemi dichiarati. I controlli dell'header sono
specializzati dall'importer S2b immutato; cambia il gruppo di segnali richiesti,
non vengono falsificate dichiarazioni Doppler. Restano richiesti header
geodetico, identità completa del ricevitore, coordinate/offset antenna finiti,
GPST, intervallo conforme al piano e clock non già corretto.

La finestra comprende tutti gli estremi: dodici epoche producono undici
intervalli. Non serve un ulteriore predecessore, né si interpola su un buco.
I valori target e quelli dopo l'ultimo estremo non vengono decodificati;
un test li sostituisce con testo non numerico. Eventi nel prefisso letto,
epoche duplicate/fuori griglia, segnali incompleti, scaling non qualificato,
fasi non valide o LLI non nullo respingono l'importazione o l'intero arco.

Le convenzioni dei campi derivano da
[RINEX 3.05](https://files.igs.org/pub/data/format/rinex305.pdf), §§4.2–4.4,
5.2, 5.3 e 6.7. Questo sottoinsieme non costituisce supporto universale a
ricevitori, file RINEX o prodotti con correzioni pregresse.

## Stessa grandezza osservata e prevista

Si riusa la geometria di emissione/ricezione e il clock broadcast dei
**riferimenti** dal ponte S2b. Una sola effemeride per riferimento viene
scelta all'inizio dell'arco e mantenuta su tutti gli estremi e differenze
numeriche; salute ed età vengono controllate senza wrapping di settimane
che renda nuovamente valida un'effemeride obsoleta.

Nel modello dichiarato, codice IF e cammino di fase IF condividono il
termine geometrico, i clock e il ritardo neutro. Le ambiguità di fase sono
costanti e si cancellano nella differenza. Questa equivalenza presuppone
rimozione ionosferica al primo ordine e assenza di termini hardware/antenna
variabili non modellati: **non** afferma che codice e fase reali siano
intercambiabili. Wind-up, multipath, residui dispersivi e bias variabili
rimangono da qualificare. La validazione eseguita qui è in vuoto.

```text
codice_predetto(t) = baseline(t, clock)
rate_fase_predetto[i] = (baseline(t[i+1], clock) − baseline(t[i], clock)) / Δt[i]
```

Non si usa la derivata istantanea alla fine o al centro dell'intervallo.
Le ambiguità costanti aggiunte alle fasi non cambiano il clock stimato.
Uno slip cambia i residui della fase e non induce un aggiustamento del clock
per assorbirlo. Non sono implementate riparazioni di slip o nuovi tentativi
con finestre/riferimenti diversi.

## Covarianza con blocchi rettangolari

La covarianza grezza ha ordine estremo/riferimento/[C1C, C2W, L1C, L2W],
con codici in metri e fasi in cicli. È trasformata una sola volta in
covarianza di N codici IF e M incrementi medi di fase, con N diverso da M.
La trasformazione mantiene correlazioni temporali e cross code/fase,
compresa l'anticorrelazione dovuta agli estremi condivisi.

Con Jc derivata dei codici rispetto ai due coefficienti del clock, Jr
derivata dei rate medi e K guadagno GLS del fit dei codici:

```text
K = (Jcᵀ Σcc⁻¹ Jc)⁻¹ Jcᵀ Σcc⁻¹
δresiduo_fase = δrate − Jr K δcodici
Σresiduo_fase = [−Jr K, I] Σcodice,rate [−Jr K, I]ᵀ
```

Il calcolo effettivo di K usa SVD, senza equazioni normali. La matrice
del residuo comprende anche i termini incrociati negativi; sommare soltanto
Var(rate) e Var(predizione) non dà lo stesso risultato.
Un controllo Monte Carlo del problema lineare con 60.000 estrazioni e
dimensioni rettangolari verifica questa propagazione, non la copertura RF.

Il codice ha N−2 gradi di libertà; la fase ne ha M, poiché i suoi valori
non hanno stimato parametri. Nel caso sintetico sono 46 e 44. Entrambi i
test hanno soglia marginale p < 0,01; non dichiarano un tasso globale di
falso rifiuto dell'1% per la procedura sequenziale. Non linearità,
selezione e covarianze reali richiedono ulteriori verifiche.

## Disegno e limiti del risultato

La fixture `tests/fixtures/s2_phase_observations.rnx` deriva dal generatore
inerziale indipendente S2b: mantiene i codici e le fasi inventati, elimina
tutti i Doppler e conserva una continuazione dell'header. Riusa la navigazione
sintetica S2b; il target G08 rimane testo volutamente non numerico.

La covarianza fissata assume sigma 1 m per ciascun codice e 0,01 cicli
per ciascuna fase, con correlazione C1C/L1C +0,3 e C2W/L2W −0,1. I blocchi
grezzi dei diversi estremi/riferimenti sono indipendenti in questo studio;
non lo sono gli incrementi trasformati. Non è una specifica di ricevitore.

Si conservano nove casi: nominale, ambiguità costanti, slip di un ciclo
non segnalato, slip segnalato, fase mancante, reset, salto sui codici,
effemeride obsoleta e piccola deriva comune della fase. Il controllo rileva
lo slip non segnalato in questo caso; la deriva comune di 0,001 m/s resta
compatibile con l'incertezza del clock ricavato dai codici. Non si deduce
quindi rilevabilità universale delle discontinuità o dei bias.

```text
python -m pytest research/kinematic/tests/test_phase_reference_bridge.py -q
python -m research.kinematic.phase_bridge_study NUOVO_REPORT.json
```

Il writer rifiuta sovrascritture e conserva tutti gli esiti, hash di sorgenti
e fixture, ipotesi e ambiente. Tutte le evidenze precedenti restano immutate.
Il prossimo passo è integrare questo osservabile **per intervalli** in un
estimatore dedicato, conservando la covarianza con codici e calibrazione.
Qualifica delle fonti reali, controllo degli errori fisici e inviluppo totale
restano necessari prima di una nuova conferma target; sito e S3 restano sospesi.
