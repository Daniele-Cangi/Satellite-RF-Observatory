# Gate F2.5.38 — outcome live 1

Stato terminale emesso:

```text
NO_FALSIFIABLE_INTERVENTION
physical hypothesis: NOT_EVALUATED
```

L'unica autorità riferita al commit
`65ca096d450e21a37585d33593f3631ca115a1d1` e all'authority envelope
`e2a1ee4e835f32960a00986fbfbe514feb838af6026419d8e958cface127f91d`
è stata consumata il 19 agosto 2026. Non è stato effettuato alcun retry e
questa authority non autorizza una seconda finestra.

## Artifact congelato

```text
path: experiments/live_instrument/session_receipts/gate-f2-5-38-20260819T091054.766396Z.jsonl
SHA-256: f3c8079261918ac186ba4cd70dc8714b29a8f9b7932989c9a8180875592ee25e
prefix SHA-256: ba36c6fc31869ebca6ef450b9f49c5943af51651514a3ba774c13be7b258f49f
bytes: 31933
events: 2 + 1 terminal manifest
retention: COMPLETE
description errors: 0
raw RF persistence: ZERO
physical decision affected by receipt: false
```

Il file passa parsing JSON rigoroso. Conserva receipt scalari, stati e hash
pre-analisi; non conserva IQ, campioni, waterfall, STFT, spettri o patch dei
candidati.

## Sequenza realmente eseguita

| Fase | Stato emesso | Evidenza |
|---|---|---|
| open dual SND handles | `SATISFIED` | channel ID distinti `1` e `0`, stesso sample rate |
| relative temporal admission | `SATISFIED` | sequenze, sample clock e overlap iniziale ammessi |
| local one-feature discovery | `UNSATISFIED` | nessuna feature supera l'intero envelope congelato |
| A1→B boundary | `NOT_EVALUATED` | nessuna feature ammessa autorizza il retune |
| B→A2 boundary | `NOT_EVALUATED` | nessun primo boundary eseguito |
| plan freeze | `NOT_EVALUATED` | nessun target falsificabile da congelare |
| one confirmation | `NOT_EVALUATED` | nessuna ipotesi fisica valutata |

Non è stato emesso alcun comando di retune. Non esistono boundary receipt,
receipt di continuità full-session o target match da reinterpretare.

## Capability e tempo realmente qualificati

Una singola Kiwi ha aperto due handle SND/IQ simultanei:

| Ramo | Channel ID | Sample rate | Frame iniziali | Frame utilizzabili |
|---|---:|---:|---:|---:|
| reference | 1 | `11998.995409 Hz` | 8 | 7 |
| perturbed | 0 | `11998.995409 Hz` | 8 | 7 |

Per ogni ramo è stato contato ed escluso un solo timestamp iniziale nullo.
Entrambi registrano zero gap di sequenza, zero violazioni dell'ordine di
arrivo, zero violazioni dei passi temporali e zero codici di errore del clock.
L'overlap comune è `217851571 ns`, con almeno `2614` campioni comuni.

Questo dimostra che la correzione F2.5.37 ha rimosso il precedente falso
blocco software e che sensore, doppio stream, decoder, hash-before-analysis,
normalizzazione temporale e trasformazione STFT erano operativi nella finestra
A1. Non dimostra l'esistenza di una feature ammissibile.

## Audit della discovery

Il selector autoritativo ha applicato le soglie ereditate e immutate:

```text
minimum joint contrast:          5.0 dB
minimum half-window contrast:    3.0 dB in entrambe le metà
minimum cross-branch correlation: 0.65
STFT:                            nperseg 1024, noverlap 512
```

Il sibling scalar audit non poteva cambiare la decisione e ha registrato:

| Taglio | Candidati |
|---|---:|
| picchi grezzi | 5 |
| patch incomplete | 0 |
| patch valide | 5 |
| correlazione sotto soglia | 1 |
| correlazione superata | 4 |
| stabilità nelle due metà sotto soglia | 4 |
| stabilità nelle due metà superata | 0 |
| feature ammesse | 0 |

I migliori scalari disponibili sono:

```text
best valid joint contrast:                    6.842048645019531 dB
joint-contrast margin:                       +1.8420486450195312 dB
best patch correlation:                       0.8287524310347112
correlation margin:                          +0.17875243103471117
best correlation-passing minimum-half value:  2.0756149291992188 dB
half-stability margin:                       -0.9243850708007812 dB
```

La decisione `NO_FEATURE_ADMITTED` è quindi attribuibile esattamente al taglio
di stabilità: quattro candidati superano la correlazione, ma nessuno raggiunge
`3.0 dB` in entrambe le metà. Non sono state cambiate soglie, feature,
normalizzazione o finestra dopo aver visto il risultato.

## Interpretazione epistemica

Il risultato è falsificante soltanto per la proposizione stretta:

> questa specifica finestra A1 contiene almeno una feature comune ai due rami
> che soddisfa contemporaneamente contrasto, correlazione e stabilità temporale
> del piano congelato.

La proposizione è falsa per questa finestra. Il receipt non distingue, e non
autorizza a scegliere, fra possibili spiegazioni quali variabilità temporale
della struttura, cambiamenti del fenomeno, mismatch della trasformazione o
instabilità reale della feature. Il fallimento del taglio non è una misura
della causa del fallimento.

Per la domanda DDC, invece, l'outcome è pre-intervento: senza feature ammessa,
retune, piano congelato e conferma, né `H_UPSTREAM_OF_CHANNEL_DDC` né
`H_DOWNSTREAM_CHANNEL_FIXED` è falsificabile con questo receipt.

```text
measurement availability:       AVAILABLE
dual-channel temporal topology:  ADMISSIBLE
composite discovery proposition: FALSIFIED_IN_THIS_A1_WINDOW
falsifiable DDC intervention:    UNAVAILABLE
H_UPSTREAM_OF_CHANNEL_DDC:        NOT_EVALUATED
H_DOWNSTREAM_CHANNEL_FIXED:       NOT_EVALUATED
```

## Cleanup

```text
transport frame leases: 54 acquired / 54 released
decoded IQ frames: 16
decoded IQ samples: 8192
sockets: 2 opened / 2 closed
all IQ zeroized: true
transient raw references after return: 0
```

## Claim autorizzati

- La capability ha fornito due SND/IQ simultanei su channel DDC distinti e
  sample clock comune.
- La qualification temporale corretta ha superato tutte le proprie clausole.
- Sensore e trasformazioni fino alla feature extraction erano operativi.
- Cinque patch erano complete; quattro superavano la correlazione congelata.
- Nessuna superava la stabilità minima congelata in entrambe le metà.
- L'esecuzione si è fermata prima del retune, senza retry e senza persistenza
  RF.

## Claim non autorizzati

Questo outcome non autorizza ad affermare che:

- nella finestra non esistessero segnali o informazione RF;
- non esistesse alcun fenomeno fisico importante;
- una soglia inferiore avrebbe prodotto un esperimento valido;
- la causa del fallimento fosse il trasmettitore, la propagazione, il
  ricevitore o la trasformazione;
- una feature fosse upstream o downstream del channel DDC;
- la feature provenisse da RF esterna o da un trasmettitore identificabile;
- una seconda acquisizione sia autorizzata.

## SHOCK

Il successore corretto ha superato proprio il confine che aveva bloccato
F2.5.36. La capability non era il limite: due canali, tempo relativo e
trasformazioni erano utilizzabili. Il limite osservato è più sottile: una
finestra può contenere strutture forti e correlate senza contenere una
struttura abbastanza persistente da sostenere l'intervento prospettico già
congelato.

Quindi “ci sono segnali interessanti” e “c'è una feature falsificabile per
questa domanda” non sono equivalenti. Il receipt scalare consente finalmente
di dirlo senza adattare il detector e senza inventare una causa.

Gate F2.5.38 outcome 1 resta congelato. Nessun retry o nuova osservazione è
autorizzato da questo artifact.
