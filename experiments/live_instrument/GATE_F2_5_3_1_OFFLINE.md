# Gate F2.5.3.1 — chiusura verificabile dell'artifact, solo offline

Stato: **PREPARATO E TESTATO; NESSUNA ESECUZIONE LIVE**.

La review pre-esecuzione di F2.5.3 ha trovato un unico blocker: l'hash finale e
gli errori del receipt artifact esistevano nell'oggetto restituito da
`run_once()`, ma `main()` lo scartava. Un errore di serializzazione o un cap
raggiunto potevano quindi lasciare un JSONL incompleto senza un marcatore
persistente di incompletezza.

Il commit F2.5.3 `d067b1e66989532bba4846f29eaa509609f66edf` resta congelato.
F2.5.3.1 aggiunge esclusivamente la chiusura descrittiva necessaria prima di
una futura esecuzione.

## Invarianti ereditate

- stessi sei candidati e stesso ordine;
- stessi centri bootstrap;
- stesso budget di 420 secondi;
- due retry totali, massimo uno per endpoint;
- stessa allowlist di errori tipizzati;
- stesse soglie, feature, domanda DDC e stop condition;
- zero retry dopo plan freeze;
- nessuna W/F, nuova sorgente o persistenza RF.

## Manifest terminale in-band

Lo stesso, unico file JSONL riserva 16 KiB prima di accettare eventi ordinari.
La sua ultima riga deve essere
`gate_f2_5_3_1_receipt_artifact_terminal` e contiene:

- numero e byte delle righe precedenti;
- SHA-256 esatto di tutte le righe precedenti, newline incluse;
- stato `COMPLETE` o `DESCRIPTIVE_ERROR`;
- conteggio, ledger hash e tipi degli errori descrittivi;
- indicazione esplicita di eventuali error hash omessi dal dettaglio limitato;
- `retention_complete`;
- cap e riserva congelati;
- `raw_rf_persistence = ZERO`;
- `physical_decision_affected = false`.

Il manifest non può contenere l'hash del file che include sé stesso. Dopo la
chiusura il runtime calcola quindi anche l'hash complessivo e `main()` emette
un receipt finale `gate_f2_5_3_1_artifact_closed`. Il manifest persistente
permette di distinguere autonomamente un artifact completo da un prefisso
troncato; il receipt finale consente di legare l'intero file all'outcome.

## Failure semantics

- serializzazione o campo RF vietato: evento non scritto,
  `retention_complete = false`;
- evento oltre il cap riservato: nessuna riga parziale, manifest ancora
  scrivibile, `retention_complete = false`;
- mirror stdout fallito: manifest e artifact possono restare completi, ma lo
  stato descrittivo registra l'errore;
- path già esistente o apertura fallita: nessuna sovrascrittura, nessun hash
  rivendicato e nessun manifest fittizio;
- eccezione runtime inattesa: l'errore entra nel ledger e il manifest viene
  scritto in `finally` prima di rilanciare l'eccezione.

Questi stati non riclassificano capability, topologia o ipotesi fisica.

## Contenuto ammesso

Il boundary resta quello di F2.5.3: receipt, controllo e hash in JSON rigoroso.
Array NumPy, campioni, IQ, frame raw, waterfall, STFT e blocchi RF sono
rifiutati prima della scrittura. Numeri non finiti diventano stati numerici
espliciti, mai `NaN` o `Infinity` JSON.

## Verifica offline

I test dimostrano:

- lineage esplicita dal commit F2.5.3;
- ultima riga terminale obbligatoria;
- hash del prefisso ricostruibile byte per byte;
- hash complessivo del file dopo la chiusura;
- manifest presente dopo serialization failure e cap exhaustion;
- distinzione tra mirror failure e retention failure;
- finalizzazione dopo eccezione runtime;
- creazione esclusiva senza overwrite;
- outcome fisico identico con receipt valido o deliberatamente non
  serializzabile;
- receipt finale esposto da `main()`;
- zero rete all'import e nessuna superficie di storage RF.

Suite completa: `215 passed`. Compilazione Python e controllo diff puliti.
Tutti i test hanno usato fixture deterministiche offline; nessuna socket remota
è stata aperta.

## Claim autorizzati

- Una futura sessione può dimostrare dal file se il ledger receipt è completo.
- Gli errori descrittivi non vengono persi soltanto perché stdout fallisce.
- Il file completo ha un hash complessivo esposto dopo la chiusura.
- Failure descrittivi e decisione fisica restano separati.

## Claim non autorizzati

- Una capability live ammetterà due canali.
- Il futuro artifact sarà necessariamente `COMPLETE`.
- Una feature o un retune saranno qualificati.
- Una delle ipotesi DDC è supportata.
- Questo checkpoint autorizza rete o acquisizione.

## SHOCK

“Il file esiste” non è una prova di retention completa. La proprietà utile è
più stretta: il file deve contenere una chiusura che impegna byte per byte ciò
che la precede e dichiara ciò che non è riuscito a entrarvi. Solo allora
l'errore descrittivo può restare separato dalla fisica senza diventare
invisibile.

F2.5.3.1 si ferma qui, prima della rete.
