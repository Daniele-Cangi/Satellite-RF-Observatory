# Gate F2.5.2 — receipt atomici dei rami SND, esclusivamente offline

Stato: **PREPARATO E TESTATO; NESSUNA NUOVA ESECUZIONE LIVE**.

Questo gate corregge soltanto il confine descrittivo emerso da
`GATE_F2_5_1_OUTCOME_1.md`. Il runtime e l'outcome F2.5.1 restano immutati: non
è possibile ricostruire retroattivamente quale singolo ramo avesse raggiunto
readiness nella sessione conclusa.

## Lineage congelato

- runtime F2.5.1 padre:
  `892aa26dd7018e8d86c1eaedad0d0ae64b9a7273`;
- outcome F2.5.1 padre:
  `706f581767fd543d4faf36b83adce8387245cb8e`;
- transform F2.5.2:
  `gate-f2.5.2-atomic-snd-branch-receipts-v1`;
- candidate set, ordine, centri bootstrap, retry, soglie e domanda DDC:
  invariati;
- W/F: assente;
- `ext_api`: hint descrittivo;
- persistenza RF: zero.

## Correzione causale minima

F2.5.1 produceva un solo errore da `_open_dual()` quando uno dei due future
falliva. L'eventuale connessione già pronta veniva chiusa e la sua storia non
raggiungeva il receipt.

F2.5.2 rende atomica l'apertura, non l'intero strumento:

```text
reference SND attempt -> BranchOpenReceipt(reference)
                                                   \
                                                    -> pair composition
                                                   /
perturbed SND attempt -> BranchOpenReceipt(perturbed)
```

Ogni ramo termina separatamente come:

- `READY`;
- `CAPABILITY_REJECTED`;
- `QUALIFICATION_ERROR`.

Solo dopo entrambi i receipt il composer può:

- ammettere due rami `READY` con channel ID distinti alla capture di topologia;
- chiudere un ramo pronto dopo il failure del peer, preservandone però il
  receipt;
- rifiutare due channel ID uguali senza cancellare la readiness raggiunta;
- lasciare la multicanalità indeterminata se almeno un ramo ha un errore di
  qualification.

`BranchOpenReceipt` è locale a questo esperimento. Non è una nuova classe
generica per sorgenti Internet e non cambia l'identità del fenomeno o la
domanda fisica.

## Evidenza conservata per ramo

Il receipt contiene soltanto descrizione e hash:

- ruolo reference/perturbed;
- tempi di inizio e completamento;
- tentativo e apertura WebSocket;
- numero e hash del handshake descrittivo;
- invio della configurazione e sample rate negoziato;
- channel ID e sua base;
- numero e byte totali dei frame SND osservati;
- hash incrementale del flusso effimero;
- hash del frame che soddisfa la readiness;
- event start/end, sequence e GPS solution age del readiness witness;
- errore descrittivo separato;
- disposizione finale del ramo nella composizione.

Non contiene campioni, array NumPy, frame raw o waterfall.

## Hashing prima dell'uso

Ogni messaggio `SND` attraversa questa sequenza:

```text
frame raw in RAM
  -> SHA-256 del frame
  -> SHA-256 incrementale length-delimited del ramo
  -> decode IQ
  -> predicate GNSS readiness
  -> metadata/hash nel receipt
  -> distruzione del blocco effimero
```

Il frame viene hashato anche se arriva prima della negoziazione del sample rate
o se il decode fallisce. Il digest incrementale include una lunghezza a 8 byte
prima di ogni frame, così concatenazioni diverse non condividono per
costruzione la stessa rappresentazione serializzata. Il frame che rende il
ramo `READY` conserva inoltre un hash individuale.

Il decode può allocare temporaneamente i campioni in RAM, ma nessun campione
attraversa il JSON boundary o una scrittura filesystem. Un hash dimostra
l'identità dell'artifact effimero; non dimostra il suo contenuto fisico né
l'identità di un segnale.

## Composizione e outcome

La decisione aggregata deriva ora dai due stati, non da una singola eccezione:

| Reference | Perturbed | Semantica massima |
|---|---|---|
| `READY` | `READY`, ID distinti | la coppia può entrare nella qualification temporale/topologica |
| `READY` | `CAPABILITY_REJECTED` | coppia non ammessa in quel tentativo; readiness reference preservata |
| `CAPABILITY_REJECTED` | `CAPABILITY_REJECTED` | rifiuto candidato osservato, non incapacità universale |
| qualunque | `QUALIFICATION_ERROR` | disponibilità multicanale indeterminata |
| `READY` | `READY`, stesso ID | `NO_ADMISSIBLE_CAUSAL_TOPOLOGY`, non `NO_MULTI_CHANNEL_CAPABILITY` |

Un errore descrittivo di un ramo non può diventare un rifiuto fisico
aggregato. I flag `direct_reference_opened` e `direct_perturbed_opened`
riflettono ora i receipt atomici. I due receipt completi sono inclusi nel
`PhaseReceipt` diretto e i loro receipt/artifact hash entrano nel ledger.
Il runner emette inoltre ciascun receipt atomico come JSON Line distinta prima
del receipt aggregato, così il confine descrittivo non ricrea la coppia come
unità indivisibile.

La coppia `READY/READY` non è ancora l'esperimento: event-time overlap,
sequence, continuità, clock, overflow, feature, retune e A1/B/A2 restano fasi
successive e possono ancora rifiutare la topologia o la falsificabilità.

## Verifica offline

I test coprono:

- bootstrap e lineage F2.5.1 immutabili;
- hashing length-delimited senza conservazione dei frame;
- hash eseguito prima del decode;
- readiness GNSS con channel ID e hash individuale;
- frame non-ready e frame prematuro comunque hashati;
- rifiuto esplicito distinto dall'errore di trasporto;
- impossibilità che testo descrittivo come “busy” riclassifichi un errore di
  trasporto come rifiuto della capability;
- `READY + CAPABILITY_REJECTED` con chiusura ma non cancellazione del sibling;
- due rami pronti con ID distinti;
- due rami pronti con ID duplicato;
- conservazione dei receipt pronti se la successiva capture di topologia
  fallisce;
- impossibilità che un mixed result diventi `NO_MULTI_CHANNEL_CAPABILITY`;
- status senza `bandwidth` ed `ext_api=0` ancora non-gating;
- serializzazione JSON rigorosa e assenza di raw samples;
- emissione dei due JSON Lines atomici prima del receipt di coppia;
- nessuna chiamata W/F o scrittura filesystem nel modulo;
- compatibilità completa con i gate precedenti.

Suite completa: `191 passed`. Compilazione Python pulita. Tutto è stato
eseguito offline con socket e IQ sintetici.

## Claim autorizzati

- Il futuro runtime può distinguere l'esito di ciascuna apertura SND.
- Ogni frame SND osservato dal nuovo opener viene hashato prima del decode.
- Un readiness witness non viene più cancellato descrittivamente dal failure
  del peer.
- La decisione di coppia non può trasformare un errore di qualification in
  assenza fisica di capability.
- La persistenza RF del gate offline è zero.

## Claim non autorizzati

- Uno dei candidati live F2.5.1 aveva realmente un ramo pronto.
- Un candidato futuro offrirà due slot.
- Due rami `READY` saranno temporalmente continui o ammissibili.
- La feature discovery o il retune produrranno un piano.
- Una feature è upstream/downstream del DDC o proviene da RF esterna.

## SHOCK

“Capability duale” non è una proprietà primitiva del server. È una
composizione temporale di due offerte di ramo, ciascuna con un proprio
handshake, artifact witness e failure mode. L'oggetto duale era prematuro nel
causal path: diventava reale soltanto dopo aver distrutto l'evidenza necessaria
a spiegare perché non era nato.

F2.5.2 si ferma qui. Nessuna rete è autorizzata da questo checkpoint.
