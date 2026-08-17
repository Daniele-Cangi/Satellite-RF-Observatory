# Gate F2.5.14 — composizione dual-SND ed envelope offline

Stato:

```text
DUAL_ONE_SHOT_ENVELOPE_MATERIALIZED_OFFLINE
```

F2.5.14 compone il branch opener semantico di F2.5.13 in una coppia
reference/perturbed, esegue il candidate loop congelato e chiude un receipt
terminale. Tutte le prove usano socket sintetici. Non è stata aperta alcuna
connessione di rete e non è stato acquisito RF live.

## Topologia verificata

I due opener vengono inviati a un `ThreadPoolExecutor` con esattamente due
worker sullo stesso endpoint. Non sono due hardware root: sono i due rami
downstream richiesti dall'intervento NCO/DDC della stessa Kiwi.

`DUAL_READY` richiede congiuntamente:

- tentativo diretto di reference e perturbed;
- due receipt semantici ordinati e distinti;
- due oggetti di connessione distinti;
- due channel ID server osservati e distinti;
- una sequence SND osservata separatamente per ogni ramo;
- sovrapposizione positiva degli intervalli di event time dei frame IQ ready;
- identico endpoint e zero persistenza RF.

Il valore numerico delle due sequence non deve essere diverso: la proprietà
necessaria è che ciascun ramo possieda il proprio witness e receipt. Confondere
"stream separati" con "contatori numericamente disuguali" aggiungerebbe un
vincolo non derivato dal protocollo.

Se un ramo fallisce, l'eventuale peer già aperto viene chiuso. Se entrambi sono
ready ma la topologia non è ammissibile, entrambi vengono chiusi con
`CLOSED_AFTER_TOPOLOGY_REJECTION`. Anche la coppia ammessa viene chiusa dal
candidate loop prima dell'outcome: F2.5.14 non procede a discovery o retune.

## Esiti del candidate loop

Il loop conserva l'ordine dei sei candidati già congelati, tenta entrambi i
rami una sola volta per candidato, non usa retry e si ferma al primo
`DUAL_READY`. Gli outcome sono:

```text
DUAL_SEMANTIC_PAIR_READY
NO_MULTI_CHANNEL_CAPABILITY
NO_ADMISSIBLE_CAUSAL_TOPOLOGY
QUALIFICATION_INCOMPLETE
```

`NO_MULTI_CHANNEL_CAPABILITY` è lecito soltanto se tutti i candidati sono stati
attraversati e ogni candidato ha ricevuto due veri tentativi diretti terminati
da un rifiuto esplicito. Un close senza SND, un SND stale o un errore di
trasformazione resta `QUALIFICATION_INCOMPLETE`; non viene promosso a rifiuto
fisico.

## Envelope immutabile

L'envelope congela:

- parent commit F2.5.13;
- candidate set, ordine e center policy data-independent;
- ruoli R/P e due branch concorrenti su un solo endpoint alla volta;
- un solo tentativo per candidato, zero retry pre-freeze e post-freeze;
- GPS solution age massimo di 30 secondi;
- nessun requisito status prima del direct-SND;
- `ext_api` non consultato e non usato come gate;
- waterfall assente dal causal path;
- connector e modulo di framing obbligatoriamente iniettati;
- stop al primo pair ready o a candidati esauriti;
- terminal receipt e zero persistenza RF.

L'envelope porta esplicitamente
`post_commit_review_state = REQUIRED_BEFORE_LIVE_AUTHORITY`. Questo Gate crea
l'oggetto da revisionare ma non può ancora vincolare l'hash del proprio source
al commit che lo conterrà. Il prossimo passaggio deve controllare il commit e
gli hash causali dopo il freeze; soltanto allora può esistere una authority
surface esatta.

## Receipt terminale e indipendenza della decisione

Il JSON Lines contiene soltanto envelope, receipt semantici, clause state,
event time, contatori e hash. Viene chiuso con il manifest terminale di
F2.5.3.1. Un errore di apertura, serializzazione o retention del receipt resta
`DESCRIPTIVE_ERROR`: il test dimostra che non modifica il risultato fisico già
calcolato.

Nessun payload, sample, IQ, array, STFT o waterfall raggiunge il receipt. Gli
artifact effimeri restano rappresentati soltanto dai SHA-256 creati prima
dell'analisi nel layer F2.5.12/F2.5.13.

## Cosa non è ancora autorizzato

F2.5.14 non autorizza:

- una connessione Kiwi live;
- status probe o discovery di endpoint nuovi;
- una finestra RF;
- local feature discovery;
- retune qualification;
- plan freeze A1/B/A2;
- retry o una seconda finestra;
- interpretazioni upstream/downstream del DDC.

Il modulo non importa WebSocket, non possiede un connector di default e non ha
un entry point `run` o `main`. Una generica autorizzazione precedente alla
revisione post-commit non viene consumata.

## SHOCK

La multicanalità non è una proprietà del testo `/status`, di `ext_api` o del
numero di thread. È un evento composto che necessita di due transcript
semantici atomici e di un witness topologico nello stesso intervallo di event
time. Il candidate loop può essere molto piccolo perché la semantica decisiva
vive nei receipt dei due rami, non in un planner centrale.

Gate F2.5.14 si ferma prima della rete e prima del post-commit causal review.
