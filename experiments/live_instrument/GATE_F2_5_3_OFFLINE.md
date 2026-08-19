# Gate F2.5.3 — controllo strutturale e retention dei receipt, solo offline

Stato: **PREPARATO E TESTATO; NESSUNA NUOVA ESECUZIONE LIVE**.

Questo gate corregge soltanto due failure descrittivi osservati in
`GATE_F2_5_2_OUTCOME_1.md`. Non ricostruisce i receipt mancanti, non
reinterpreta l'outcome e non modifica candidate, ordine, centri, soglie,
domanda DDC o stop condition.

## Lineage congelato

- runtime F2.5.2 padre:
  `64a717b8dcd13ec0c09cd7b87388986bdb2ffbb3`;
- outcome F2.5.2 padre:
  `fffb1068e987bdcb135d053abf18195211fe7458`;
- transform:
  `gate-f2.5.3-structured-control-receipt-sink-v1`;
- retry budget: due totali, massimo uno per endpoint, invariato;
- artifact receipt: massimo 4 MiB, creazione esclusiva, JSON Lines rigoroso;
- W/F e storage RF: assenti.

## Failure corretto 1: il testo non controlla più il retry

F2.5.2 aveva correttamente prodotto receipt atomici, ma il runner storico
cercava parole come `connection`, `closed` o `timeout` nello statement
aggregato. La nuova descrizione atomica non conteneva quelle parole e il
budget congelato non fu materializzato.

F2.5.3 separa definitivamente descrizione e controllo:

```text
BranchOpenState == QUALIFICATION_ERROR
  + error_type atomico nella allowlist congelata
  -> retry pre-freeze eleggibile

statement/prosa
  -> nessun effetto sul controllo
```

La allowlist contiene esclusivamente classi di trasporto osservabili dal
software: `ConnectionError`, `ConnectionResetError`, `OSError`, `TimeoutError`,
`URLError`, `WebSocketConnectionClosedException` e
`WebSocketTimeoutException`. `CAPABILITY_REJECTED`, `UNSATISFIED`, error type
sconosciuti o semplice testo non autorizzano retry.

I test materializzano esattamente il budget sull'ordine congelato: i primi due
endpoint ricevono due tentativi ciascuno, gli altri uno; sono quindi due retry
totali e mai più di uno per endpoint. Nessuna soglia o feature entra nella
decisione.

## Failure corretto 2: artifact JSONL limitato ai receipt

Il runner futuro crea un singolo file con apertura esclusiva. Ogni evento
descrittivo attraversa:

```text
receipt/control record
  -> normalizzazione JSON rigorosa
  -> rifiuto di array e campi RF
  -> limite byte pre-write
  -> JSONL
  -> SHA-256 incrementale dell'artifact
```

Sono vietati esplicitamente campi raw o derivati come `samples`, `iq_samples`,
`raw_frame`, `raw_body`, `frames`, `blocks`, `waterfall` e `stft`. I valori
numerici non finiti continuano a usare gli stati numerici espliciti introdotti
in Gate E.1; non compaiono token JSON non standard. Il receipt finale del file
riporta path, righe, byte, hash, cap ed eventuali errori descrittivi.

Il sink non conserva il contenuto fisico degli hash. Un digest testimonia
l'identità dell'artifact effimero, non ricostruisce IQ né prova una feature.

## Non interferenza epistemica

Serializzazione, apertura, scrittura, limite byte o mirror stdout possono
fallire. `SafeReceiptEmitter` registra in RAM tipo e hash della descrizione
dell'errore e non rilancia l'eccezione nel causal path. Il risultato fisico
continua a dipendere dai receipt di qualification, non dalla riuscita della
sua rappresentazione.

Il test di non interferenza esegue lo stesso runner offline due volte:

- con emissione valida;
- con payload deliberatamente non serializzabile e mirror in errore.

Outcome, sequenza di fasi e claim autorizzati/non autorizzati restano identici.
L'artifact descrittivo termina `DESCRIPTIVE_ERROR` e dichiara
`physical_decision_affected = false`.

Un path già esistente non viene sovrascritto né hashato come se appartenesse
alla nuova sessione. Il superamento del cap non scrive una riga parziale.

## Modifica minima al runner padre

`kiwi_gate_f2_5.py` riceve due hook locali e opzionali:

- `retry_selector`;
- `event_emitter`.

Senza hook, tutti i gate e outcome precedenti mantengono il comportamento
storico. F2.5.3 li usa per sostituire soltanto controllo testuale e stdout-only.
`PhaseReceipt` espone inoltre `qualification_error_types`; F2.5.2 lo popola dai
receipt atomici senza cambiare i loro stati.

Non nasce un event bus, un logger generico, un database o un framework di
esperimenti. Il writer è privato del modulo verticale e il vocabolario resta
quello necessario a questa singola esecuzione futura.

## Verifica offline

I test coprono:

- lineage e bootstrap immutabili;
- indipendenza completa dalla prosa aggregata;
- allowlist tipizzata e stati atomici;
- due retry totali, massimo uno per endpoint;
- JSON Lines rigoroso e stati numerici espliciti;
- cap pre-write e creazione esclusiva;
- rifiuto di campioni, frame, STFT, waterfall e array NumPy;
- hash incrementale del solo artifact descrittivo;
- non interferenza di errori JSON e mirror sulla decisione fisica;
- assenza di rete all'import e di superfici di persistenza RF;
- compatibilità con i gate F2.5, F2.5.1 e F2.5.2.

Suite completa: `204 passed`. Compilazione Python e controllo diff puliti.
Tutto è stato eseguito offline con fixture deterministiche; nessuna socket
remota è stata aperta.

## Claim autorizzati

- Un futuro retry F2.5.3 può essere autorizzato soltanto da stato ed error type
  strutturati.
- Il budget congelato è materializzato esattamente dal runner offline.
- I receipt di una futura sessione possono essere conservati in un artifact
  JSONL limitato, rigoroso e hashato senza conservare RF.
- Un failure descrittivo non cambia la decisione fisica.

## Claim non autorizzati

- Il receipt Hill mancante dalla sessione F2.5.2 è stato recuperato.
- Una capability futura ammetterà due canali.
- Una feature sarà rilevabile o il retune sarà testimoniabile.
- Una delle ipotesi DDC è supportata.
- Questo gate autorizza una nuova connessione o esecuzione live.

## SHOCK

Un budget congelato non esiste operativamente finché il predicato che lo
attiva dipende dalla stessa prosa che dovrebbe soltanto descriverlo. E un
receipt stdout-only non è evidenza trattenuta: è un effetto collaterale del
terminale. La correzione non richiede più osservazione né un nuovo runtime
generale; richiede che controllo strutturale e descrizione falliscano in modo
indipendente.

F2.5.3 si ferma qui, prima della rete.
