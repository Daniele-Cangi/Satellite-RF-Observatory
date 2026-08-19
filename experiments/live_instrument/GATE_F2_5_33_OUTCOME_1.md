# Gate F2.5.33 — outcome live 1

Stato terminale:

```text
NO_FALSIFIABLE_INTERVENTION
```

L'unica autorità riferita al commit
`77a5f733725e83e758560eb1af7db4ee1a4d3d25` e all'authority envelope
`3f052af8686b37be6e04b85543a5fca30ad05e8536a8d57d796034cc98c6ab52`
è stata consumata il 19 agosto 2026. Non è stato effettuato alcun retry e non
è autorizzata una seconda finestra con questa authority.

## Artifact congelato

```text
path: experiments/live_instrument/session_receipts/gate-f2-5-33-20260819T001930.319362Z.jsonl
SHA-256: 1d0b9c2ff97702f533f7944f2c23c7f782da4bb2427ec3d02a3d3e6279aad62c
prefix SHA-256: 08180d45a0cac8a0fd57b2f6934a3f8347114b416ca25368d8c40c576868ec44
bytes: 26961
events: 2 + 1 terminal manifest
retention: COMPLETE
description errors: 0
raw RF persistence: ZERO
physical decision affected by receipt: false
```

Il JSON Lines rigoroso conserva l'authority envelope, receipt scalari,
artifact hash pre-analisi, stati delle clausole e il manifest terminale. Non
contiene frame body, IQ, campioni, waterfall, STFT o profili spettrali.

## Sequenza realmente eseguita

La sessione ha usato esclusivamente la capability e la coordinata congelate.

| Fase | Stato | Conseguenza |
|---|---|---|
| open dual SND handles | `SATISFIED` | due connessioni e due channel ID distinti |
| relative temporal admission | `SATISFIED` | stesso sample clock, continuità e overlap ammessi |
| local one-feature discovery | `UNSATISFIED` | nessuna feature comune ha superato l'envelope congelato |
| A1→B boundary | `NOT_EVALUATED` | nessun comando di retune emesso |
| B→A2 boundary | `NOT_EVALUATED` | intervento mai iniziato |
| plan freeze | `NOT_EVALUATED` | nessuna prediction fisica congelata |
| one confirmation | `NOT_EVALUATED` | nessuna ipotesi fisica valutata |

La stop condition ha terminato la sessione immediatamente dopo la discovery
negativa. I receipt contengono zero comandi, zero command-boundary witness,
zero distributed witness e zero target match.

## Capability realmente ammessa

Il server ha assegnato:

| Ramo | Channel ID | Sample rate | Frame A1 | Frame temporali utilizzabili |
|---|---:|---:|---:|---:|
| reference | `0` | `11998.995708 Hz` | `8` | `7` |
| perturbed | `1` | `11998.995708 Hz` | `8` | `7` |

Entrambi i rami hanno registrato:

- zero sequence gap;
- zero arrival-order violation;
- zero timestamp-step violation;
- zero server clock error code;
- un solo timestamp iniziale nullo, contato ed escluso;
- identico sample rate;
- overlap comune di `253937919 ns`, pari ad almeno `3047` campioni.

La topologia same-Kiwi, due DDC distinti e il ponte temporale relativo erano
quindi operativi per la domanda sperimentale. Questo è un risultato di
capability, non supporto per una delle ipotesi sulla feature.

## Discovery negativa

La discovery ha analizzato in RAM otto frame per ramo, cioè `4096` campioni
per canale, con la geometria STFT congelata `1024/512`. Le soglie sono rimaste:

```text
minimum joint contrast:             5.0 dB
minimum contrast in both halves:    3.0 dB
minimum cross-branch correlation:   0.65
```

Il receipt terminale è:

```text
state: NO_FEATURE_ADMITTED
selected_baseband_hz: null
joint_contrast_db: null
first_half_contrast_db: null
second_half_contrast_db: null
cross_branch_correlation: null
threshold_source: UNCHANGED_MOTHER_PLAN
```

Questo significa soltanto che nessuna struttura ha soddisfatto congiuntamente
l'envelope nella finestra A1. Non significa che non fossero presenti energia,
segnali, portanti o informazione fisica nel passband.

Il receipt non conserva il numero di picchi grezzi, le rejection stage o i
margini rispetto alle tre soglie. Non è quindi possibile attribuire il
fallimento a contrasto, stabilità temporale, similarità fra canali oppure a una
combinazione di questi fattori. Una causa più specifica sarebbe post-hoc e non
supportata dall'artifact.

## Cleanup

Il terminale registra:

```text
transport frame leases: 53 acquired / 53 released
decoded IQ frames: 16
decoded IQ samples: 8192
sockets: 2 opened / 2 closed
all IQ zeroized: true
transient raw references after return: 0
```

L'artifact persistente contiene soltanto metadata, stati e hash.

## Claim autorizzati

- La capability ha offerto due canali SND/IQ distinti e simultanei sullo stesso
  sample clock.
- La finestra A1 ha soddisfatto il contratto temporale relativo.
- Con soglie e trasformazioni congelate, nessuna feature comune è stata
  ammessa in quella finestra.
- Il runtime ha rifiutato di emettere il retune senza una feature falsificabile.
- Nessuna ipotesi upstream/downstream è stata valutata.

## Claim non autorizzati

Questo outcome non autorizza ad affermare che:

- il passband non contenesse segnali importanti;
- non esistesse alcun fenomeno RF osservabile;
- il receiver o uno dei due DDC non funzionasse;
- il retune per-canale fosse valido oppure invalido;
- la feature fosse upstream o downstream del channel DDC;
- una soglia dovesse essere abbassata dopo il risultato;
- un'altra finestra avrebbe necessariamente prodotto lo stesso esito;
- un trasmettitore, un satellite o un'origine RF esterna fosse identificato.

## SHOCK

Il percorso tecnico che aveva bloccato i Gate precedenti questa volta ha
funzionato: due canali, sample clock comune, overlap e cleanup sono stati
realmente ottenuti. Il blocco è passato dal trasporto all'enunciato fisico.

La capability era capace di misurare, ma la sessione non ha fornito una feature
che rendesse falsificabile l'intervento. Quindi `MEASUREMENT_AVAILABLE` non
implica `FALSIFIABLE_FEATURE_AVAILABLE`. Il comportamento corretto non era
retunare comunque, né cercare una frequenza migliore dopo aver visto i dati:
era fermarsi.

Gate F2.5.33 outcome 1 resta congelato. Qualunque lavoro successivo deve essere
offline, non può riutilizzare l'autorità consumata e non può reinterpretare
retroattivamente `NO_FEATURE_ADMITTED` come assenza di segnali.
