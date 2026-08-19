# Gate F2.5.13 — integrazione offline nel direct-SND ordered opener

Stato:

```text
SEMANTIC_ORDERED_OPENER_INTEGRATED_OFFLINE
```

F2.5.13 collega il receipt semantico F2.5.12 al causal path reale di
`_open_channel_ordered()`. Tutte le verifiche usano socket sintetici. Non sono
state aperte connessioni, non è stato eseguito un candidate loop e non esiste
un entry point live in questo Gate.

## Successore senza modificare le causal sources congelate

Il primo tentativo additivo di inserire hook opzionali in F2.5.8 è stato
rifiutato dai guard F2.5.10: quel file appartiene alle causal sources
congelate. Gli hash attesi non sono stati aggiornati e i guard non sono stati
indeboliti.

La modifica finale lascia quindi F2.5.8 byte-identico e implementa un opener
successore in F2.5.13. Riusa soltanto i tipi e gli helper allowlisted del path
congelato, preservandone l'ordine di auth, campi server, allocation e comandi.
Ogni nuovo frame viene hashato prima del parsing, attraversa F2.5.12 e deve
produrre lo stesso SHA-256 nel wire layer e nel semantic layer. Una divergenza
termina descrittivamente.

Il nuovo entry point:

```text
open_channel_semantic_injected(
    ...,
    connector=<obbligatorio>,
    websocket_module=<obbligatorio>
)
```

non possiede un connector o WebSocket module di default. Non importa
`websocket`, non seleziona endpoint e non può aprire autonomamente la rete. Il
caller di test deve fornire esplicitamente factory e costanti di framing
sintetiche.

## Nuovo confine del receipt

Il risultato legacy F2.5.8 rimane interno e viene ridotto a:

- hash del receipt ordinato;
- allowlist dei soli control-event kind;
- channel ID osservato;
- command hash;
- stato, event time e typed error;
- pair disposition.

Il nuovo receipt espone direttamente la sequenza completa dei frame receipt
F2.5.12. Non serializza il transcript legacy con i suoi dettagli ormai
ambigui.

Le invarianti richiedono:

- un frame receipt semantico per ogni frame hashato dal wire layer;
- identico ordine e identici SHA-256 nei due layer;
- una sola transizione `READINESS = SATISFIED` per un ramo `READY`;
- identici frame hash, sequence, GPS age ed event time fra readiness ordinata e
  semantica;
- nessuna readiness su un ramo fallito;
- rifiuto di capability soltanto in presenza di `badp` o `too_busy` esplicito;
- stato e peer status del close derivati esclusivamente dal frame receipt
  semantico.

## Close a payload vuoto

Il successore costruisce internamente un receipt nel formato F2.5.8 per
riutilizzarne le invarianti; quel formato conserva il sentinel legacy. Il nuovo
confine non serializza il campo né il transcript interno. Per un close vuoto
espone soltanto:

```text
close_payload_state = EMPTY_NO_STATUS
peer_close_status_code = null
```

Il test strict JSON verifica esplicitamente che la stringa `1005` non compaia
nel receipt integrato. Se due byte di status sono realmente presenti, il codice
peer viene invece conservato.

## Distinzioni dimostrate nel causal path

I socket sintetici attraversano auth, allowlisted server fields, allocation,
send locale di `mod_iq`, SND e close. Il receipt integrato distingue:

- control path seguito da close senza alcun SND;
- SND con GPS age 31 secondi;
- SND con GPS seconds uguale a zero;
- SND non-IQ;
- SND con errore di sample decode;
- SND ready con frame hash, sequence ed event time corrispondenti;
- rifiuto `badp` esplicito;
- close vuoto e close con vero peer status.

Un SND non-IQ conserva `IQ_MODE = UNSATISFIED`, anche se il decoder legacy
termina poi il ramo con un typed `QUALIFICATION_ERROR`. La decisione fisica e
la descrizione del termine restano quindi separate.

## Zero persistenza e strict JSON

Il nuovo receipt contiene soltanto metadati, enum, tempi, contatori e SHA-256.
Non contiene body, payload, IQ, sample, array, STFT o waterfall. Un campo MSG
non allowlisted viene distrutto: soltanto il suo artifact hash sopravvive.

Non è stato scritto alcun JSONL perché non è avvenuta una sessione.

## Cosa non è ancora implementato

F2.5.13 integra un singolo branch. Non implementa ancora:

- composizione simultanea reference/perturbed con il nuovo receipt;
- candidate loop;
- retry selector;
- terminal JSONL;
- envelope con commit, candidati, timing e authority surface;
- plan freeze o A1/B/A2;
- live runner.

Queste superfici devono essere materializzate e revisionate offline prima di
qualsiasi nuova autorità di rete.

## Semantica dell'autorizzazione

Una generica autorizzazione espressa prima dell'esistenza dell'envelope non
viene consumata come live authority. L'autorità deve riferirsi al runner e
all'envelope esatti dopo il loro freeze; altrimenti candidati, timing, retry e
stop condition non sarebbero ancora l'oggetto autorizzato.

Questo Gate autorizza e completa soltanto l'integrazione sintetica.

## SHOCK

Non serviva modificare le causal sources congelate né sostituire l'intero
client ordinato. Era sufficiente costruire un successore e sdoppiare il confine:

```text
wire receipt = integrità e ordine del trasporto
semantic receipt = motivo clause-by-clause dell'ammissione
```

I due layer si sorvegliano tramite la stessa sequenza di artifact hash. Nessuno
dei due, isolatamente, era sufficiente a interpretare un negativo.

Gate F2.5.13 si ferma prima di dual composition e pre-live review.
