# Gate F2.5.21 — outcome live 1

Stato terminale:

```text
NO_FALSIFIABLE_INTERVENTION
```

L'unica autorità riferita al commit
`9673f72bc3f6c75b584de1c80ce0e4881dba5e66` e all'authority envelope
`9299f8da2d66efb4d0b06a288b151110bb38c75a5254bf903af8ea03e66510d7`
è stata consumata il 18 agosto 2026. Non è stato effettuato alcun retry e non
è autorizzata una seconda finestra con questa authority.

## Artifact congelato

```text
path: experiments/live_instrument/session_receipts/gate-f2-5-21-20260818T111608.453433Z.jsonl
SHA-256: 5307caa715a1f18199a5f933e16ad0c64fb0ce2cfa7753cd254e54e01e9b49fb
prefix SHA-256: 877c3973c5ec390777a3b7ade0d5af354206fa046fefefc3ebafe2d978c0e2b0
bytes: 157705
events: 9 + 1 terminal manifest
retention: COMPLETE
description errors: 0
raw RF persistence: ZERO
physical decision affected by receipt: false
```

Il JSON Lines rigoroso contiene soltanto envelope, receipt, metadati,
contatori e hash calcolati prima della distruzione degli artifact effimeri. Non
contiene IQ, campioni, waterfall, STFT o frame RF.

## Sequenza realmente eseguita

La sessione ha contattato una sola Kiwi congelata,
`dl1bajkiwisdr.ddns.net:8074`, al bootstrap deterministico
`16683606.560446203 Hz`. Il bootstrap qualificava il trasporto e non era una
feature selezionata. Status, `ext_api` e waterfall non hanno partecipato
all'ammissione.

| Fase | Stato | Conseguenza |
|---|---|---|
| direct dual-SND qualification | `SATISFIED` | due stream IQ simultanei e validi |
| local-IQ feature discovery | `UNSATISFIED` | meno di due strutture stabili distinte |
| per-channel retune qualification | `NOT_EVALUATED` | bloccata prima dell'ingresso |
| plan freeze | `NOT_EVALUATED` | nessun piano prospettico prodotto |
| one confirmation | `NOT_EVALUATED` | nessun A1/B/A2 eseguito |

La stop condition ha chiuso la sessione al primo outcome. `plan_hash` e
`physical_result` sono entrambi null: non esiste quindi un risultato fisico da
interpretare e l'autorità non può essere usata per una seconda discovery.

## Capacità multicanale osservata

Il tentativo diretto ha allocato due connessioni e due canali server distinti:

| Ramo | Channel ID | Sequence ammessa | GPS age | Stato |
|---|---:|---:|---:|---|
| reference | `2` | `2` | `0 s` | `READY` |
| perturbed | `1` | `2` | `0 s` | `READY` |

I witness event-time hanno avuto `0.012584 s` di overlap. Le clausole di stesso
endpoint, connessioni distinte, channel ID distinti, receipt e sequence
separati e overlap event-time sono tutte `SATISFIED`. Entrambi gli stream sono
stati descritti come continui, allineati al clock condiviso e senza overflow.
Non sono stati osservati errori di qualification.

Il controllo locale ha attraversato, su entrambi i rami, la sequenza congelata
`AUTH_EMITTED_LOCAL → REQUIRED_METADATA_OBSERVED →
REQUIRED_SETUP_EMITTED_LOCAL → FIRST_SND_READY_OBSERVED`. Non è stato emesso
alcun keepalive prima o dopo il setup. Come già previsto, il protocollo non ha
fornito un acknowledgement remoto esplicito del setup e la relativa clausola
resta `NOT_EVALUATED`.

Questa parte dell'esito replica e rafforza la conclusione stretta di F2.5.19:
una singola Kiwi può fornire la topologia dual-SND richiesta. Non dice ancora
nulla sull'indipendenza del retune per canale.

## Discovery e stop epistemico

La nuova finestra effimera di quattro secondi ha prodotto dual IQ, poi la
trasformazione locale di discovery ha restituito:

```text
prospective discovery contains fewer than two distinct stable structures
```

Il suo receipt conserva soltanto l'artifact hash
`a7ed0ed8e619a33d90876404a1d469d68cd9fef2993a4c1ddea83f703d83d01e`.
Non essendo disponibile una coppia target/witness distinta, non era possibile
congelare un delta che rendesse il successivo retune falsificabile. Il runtime
ha quindi rifiutato correttamente di adattare la feature, cambiare frequenza,
allargare la finestra o eseguire comunque l'intervento.

Questo risultato non dimostra che il passband fosse privo di energia o di
segnali. Dimostra soltanto che la discovery congelata non ha materializzato la
struttura minima richiesta dal piano: due feature stabili e distinguibili, una
target e una witness, necessarie per testare movimento e stabilità sotto un
retune per-canale.

## Claim autorizzato

Nella sessione una topologia dual-SND ammessa non ha prodotto l'envelope
target/witness/delta predefinito. Pertanto nessun intervento fisico
falsificabile era disponibile con quella finestra e quelle trasformazioni.

## Claim non autorizzati

Questo outcome non autorizza ad affermare che:

- non esistessero segnali RF nel passband;
- i segnali presenti fossero irrilevanti o non fisici;
- il retune per-canale funzioni o non funzioni;
- la feature sia upstream o downstream del channel DDC;
- una delle ipotesi DDC sia supportata o falsificata;
- l'origine sia RF esterna anziché antenna/front-end/ADC/clock;
- `ext_api` provi la multicanalità;
- una waterfall sia necessaria per qualificare due stream SND;
- un trasmettitore, satellite o fenomeno sia stato identificato.

## SHOCK

La capability viva ha determinato correttamente il limite dell'esperimento:
ha offerto due rami simultanei, ma non una coppia di feature che consentisse di
intervenire senza ambiguità. Il risultato più importante non è un segnale
classificato, ma il rifiuto prospettico di trasformare una struttura
insufficiente in una domanda fisica post-hoc.

In questa esecuzione il planner centrale non ha aggiunto valore: la decisione è
emersa dalla catena locale `capability → discovery → ammissione per clausole`.
Restano necessari receipt atomici, transform ledger, event time, lineage e la
separazione fra descrizione e decisione. Target e identità del fenomeno sono
rimasti opzionali; senza una feature e un witness ammessi non sono stati
inventati.

Gate F2.5.21 outcome 1 resta congelato. Qualunque lavoro successivo deve essere
offline e partire da questo limite osservato. Non può reinterpretare la
discovery negativa come assenza fisica né riutilizzare l'autorità consumata.
