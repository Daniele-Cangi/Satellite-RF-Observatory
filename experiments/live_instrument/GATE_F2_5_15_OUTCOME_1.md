# Gate F2.5.15 — outcome live 1

Stato terminale:

```text
QUALIFICATION_INCOMPLETE
```

L'unica autorità riferita al commit
`f01a20baa684ae4aa2eadf4aa5198e94177aaaea` e all'authority envelope
`4a1d4fc9d7dff2efc970502654113bb0396b5e9e91c01e8d8870243b92bf514e`
è stata consumata il 17 agosto 2026. Non è stato effettuato alcun retry e non
è autorizzata una seconda esecuzione.

## Artifact congelato

```text
path: experiments/live_instrument/session_receipts/gate-f2-5-15-20260817T112702.764940Z.jsonl
SHA-256: ba77314fa10ea5ebc6fa3c29f9b4a9ebfdcf0b815d94fe77182a939b63e77619
prefix SHA-256: 9dd51ec1813427db243ee12bfba6a3790e90c0f61353fa0e9b643d4180d9d04a
bytes: 318154
events: 8 + 1 terminal manifest
retention: COMPLETE
description errors: 0
raw RF persistence: ZERO
physical decision affected by receipt: false
```

Il primo evento lega authority envelope, execution envelope e control-surface
hash. L'ultimo evento è il manifest terminale. Il JSON è rigoroso e contiene
soltanto metadati, stati di clausola, contatori e artifact hash.

## Risultato per candidato

| Candidato | Reference | Perturbed | Pair |
|---|---|---|---|
| `dl1bajkiwisdr.ddns.net:8074` | allocation 0, close senza SND | allocation 1, close senza SND | `QUALIFICATION_INCOMPLETE` |
| `g0ghk.uk:8050` | rifiuto `badp` | rifiuto `badp` | `EXPLICIT_PAIR_REJECTED` |
| `hill.n8ga.org:8073` | allocation 4, close senza SND | allocation 3, close senza SND | `QUALIFICATION_INCOMPLETE` |
| `kiwisdr2blair.ddns.net:8073` | rifiuto `badp` | allocation 0, close senza SND | `QUALIFICATION_INCOMPLETE` |
| `kiwisdr.kfsdr.com:8074` | allocation 0, close senza SND | rifiuto `badp` | `QUALIFICATION_INCOMPLETE` |
| `va6ok.ddns.net:8073` | allocation 1, close senza SND | allocation 0, close senza SND | `QUALIFICATION_INCOMPLETE` |

Conteggi complessivi:

```text
candidate pair attempted: 6
direct branches attempted: 12
CAPABILITY_REJECTED branches: 4
QUALIFICATION_ERROR branches: 8
channel allocation observed: 8
MOD_IQ_SENT observed locally: 8
semantic SND frames: 0
empty close without peer status: 8
dual-ready pair: 0
```

## Cosa dimostra il receipt

Per tutti i dodici rami è avvenuto un vero tentativo WebSocket SND. Quattro
rami hanno ricevuto un rifiuto server `badp` osservabile e autorizzano
`CAPABILITY_REJECTED` per quel ramo.

Gli altri otto hanno osservato sample rate, allocation, `badp` positivo,
invio locale di `mod=iq` e poi un close WebSocket con payload vuoto. Il nuovo
confine semantico dimostra che tra i frame ricevuti non esiste alcun frame con
tag SND: il conteggio è zero, non un SND stale, non-IQ o fallito al decode.

Il close vuoto è rappresentato esclusivamente come:

```text
close_payload_state = EMPTY_NO_STATUS
peer_close_status_code = null
```

Nessun `1005` locale viene promosso a status del peer.

## Cosa non dimostra

Il receipt non distingue fra possibili cause non osservate del close, ad
esempio policy dell'operatore, incompatibilità di una sequenza di controllo,
stato interno del server o altra terminazione. Non autorizza quindi nessuna di
queste attribuzioni.

Inoltre non autorizza le affermazioni:

- nessuna Kiwi pubblica supporta due canali;
- gli otto rami allocati non avrebbero mai prodotto IQ;
- il server ha accettato il comando `mod=iq` soltanto perché il client lo ha
  inviato;
- i channel ID distinti costituiscono un pair simultaneo senza due witness IQ;
- una feature RF era assente o non rilevabile;
- una topologia DDC è stata qualificata;
- una delle ipotesi upstream/downstream è supportata.

Le clausole di topologia successive restano `NOT_EVALUATED`, perché nessun
candidato ha prodotto due readiness root SND/IQ.

## Perché non è NO_MULTI_CHANNEL_CAPABILITY

Solo `g0ghk.uk:8050` ha prodotto due rifiuti espliciti. Negli altri candidati
almeno un ramo termina descrittivamente senza SND. Promuovere questi close a
rifiuti fisici trasformerebbe l'assenza di un witness in una proprietà della
capability. La priorità corretta è quindi `QUALIFICATION_INCOMPLETE`.

## SHOCK

L'integrazione semantica ha risolto l'ambiguità “nessun SND oppure SND scartato
dal predicate”: il risultato è precisamente **nessun frame SND osservato**.
Non ha però risolto la causa del close. Un receipt più dettagliato non crea una
causa remota che il protocollo non ha espresso.

La qualification ha quindi raggiunto il nuovo confine corretto: sappiamo dove
la catena osservabile termina, ma non possediamo ancora evidenza per spiegare
perché termina lì.

Gate F2.5.15 outcome 1 resta congelato. Qualunque prossimo lavoro deve essere
offline e non può riusare l'autorità consumata.
