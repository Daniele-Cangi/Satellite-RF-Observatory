# Gate F2.5.37 — full-session continuity normalization

Gate F2.5.37 è esclusivamente offline. Non modifica i sorgenti congelati
F2.5.31–36, non riapre il receiver e non cambia endpoint, frequenza, feature,
soglie, finestre o retry. Il receipt e l'outcome F2.5.36 restano immutati.

La domanda è una sola:

> Il controllo di continuità full-session può applicare la stessa regola sui
> timestamp già usata dall'ammissione temporale iniziale?

## Lineage congelata

```text
outcome commit:
  91df4965efee9b1b8935fe03b2b5be99b285320e

outcome receipt:
  session_receipts/gate-f2-5-36-20260819T082846.463772Z.jsonl

receipt SHA-256:
  9c976fabf725eb509f71308d19125b31e1360c1ea0994c2c4d6b679b46628246

prefix SHA-256:
  2229c39dcec6fa342f8ab3350ae65a422f7a800af5c75b89875eb89aa05202e6

frozen F2.5.31 source:
  dd447450510bd17d5b7ad1502fab84f86f5b129194d3b97550842ab5f8257672

frozen F2.5.35 source:
  b13523f10edaab9b7eda9615f05ecfd6ab611bd40a499a28005dcaf087e46c86
```

L'assessment rifiuta il successore se uno di questi artifact cambia. Verifica
anche che l'outcome storico rimanga `INTERVENTION_INVALID`, l'ipotesi fisica
rimanga `NOT_EVALUATED` e i due residui anomali siano ancora ricostruibili
esattamente dai timestamp iniziali nulli.

## Correzione minima

Non viene introdotta una seconda regola temporale. Il nuovo evaluator richiama
direttamente `_unwrap_start_times()` di F2.5.27, già usata dalla qualification
iniziale, poi applica gli stessi controlli esistenti:

```text
all scalar frame receipts
  → count and exclude only leading zero timestamps
  → unwrap only a forward GPS-week rollover
  → check sequence continuity on usable frames
  → compare timestamp steps with decoded sample duration
  → retain the existing SessionContinuityReceipt shape
```

Restano invariati:

- tolleranza massima di un campione;
- sample-rate e sample-duration semantics;
- sequenza modulo `uint32`;
- artifact hash di tutti i frame, inclusi gli zeri iniziali esclusi;
- discovery e sibling scalar audit;
- witness, prediction e physical evaluator;
- zero retry e zero RF persistence.

Uno zero dopo l'inizio dello stream non viene scartato. Se non rappresenta un
rollover in avanti oltre metà settimana GPS, produce ancora una violazione.
Un'intera sessione composta soltanto da timestamp nulli rimane non ammessa.

## Integrazione senza riscrivere il vertical

I moduli congelati non vengono editati. Una seam privata installa il nuovo
evaluator soltanto durante un singolo vertical sintetico F2.5.35, sotto lock,
e ripristina quello congelato in un `finally`, anche se il downstream solleva
un errore.

Questa è deliberatamente una soluzione locale al Gate. Non è una registry di
evaluator, una DSL temporale o un framework di plugin. Non esiste un connector
né una funzione `run_reviewed_once`.

## Regressioni

I test offline coprono:

1. binding del receipt e attribuzione matematica F2.5.36;
2. riproduzione esatta del falso gap `zero → primo timestamp valido`;
3. uno e più timestamp nulli iniziali;
4. rifiuto di uno zero interno non giustificato;
5. rollover in avanti della settimana GPS;
6. vertical sintetico identico con e senza la correzione;
7. invarianti di discovery, audit, cleanup e zero persistenza RF;
8. ripristino dell'evaluator congelato anche dopo errore;
9. assenza di rete, authority e nuovi controlli sperimentali.

Nel vertical sintetico con uno zero iniziale per ramo, il runtime congelato si
ferma `INTERVENTION_INVALID`; il successore mantiene la stessa decisione di
discovery e porta il fixture preesistente all'outcome sintetico
`UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`. Questo prova che il falso blocco è stato
rimosso. Non converte l'outcome live e non costituisce evidenza fisica.

## Claim autorizzati

- L'attribuzione del blocco F2.5.36 ai timestamp iniziali nulli è riproducibile.
- La qualification iniziale e quella full-session ora condividono una sola
  regola di normalizzazione nel successore offline.
- La correzione non scarta zeri interni e non indebolisce la tolleranza.
- Il vertical corretto può raggiungere il physical evaluator su fixture
  sintetici già esistenti.
- I moduli, il receipt e l'outcome live congelati non sono stati modificati.

## Claim non autorizzati

Gate F2.5.37 non autorizza ad affermare che:

- l'outcome live F2.5.36 fosse upstream o downstream del DDC;
- il target-excluded witness live avrebbe superato l'ammissione;
- un nuovo run produrrebbe lo stesso segnale o outcome;
- la feature fosse RF esterna o avesse un'identità nota;
- una nuova esecuzione live sia autorizzata.

## SHOCK

Il difetto non richiedeva un nuovo modello temporale. La regola corretta era
già presente e aveva già ammesso la stessa sessione; il problema era che il
runtime possedeva due implementazioni della medesima clausola.

Il minimo hardening non è rendere il contratto più ricco: è impedire che una
clausola abbia più semantiche operative lungo lo stesso causal path.

Gate F2.5.37 si ferma qui. Il prossimo lavoro ammissibile è un post-commit seal
offline del solo vertical corretto. Nessuna nuova authority o acquisizione è
inclusa.
