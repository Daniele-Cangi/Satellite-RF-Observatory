# Gate F2.5.36 — outcome live 1

Stato terminale emesso:

```text
INTERVENTION_INVALID
physical hypothesis: NOT_EVALUATED
```

L'unica autorità riferita al commit
`5fd579ae7564158a8952391cf4533f25ca5fd99b` e all'authority envelope
`37f9a442274f45e165549d8e5910179d84d3f63b46342b8133cfdaf2e39c32dc`
è stata consumata il 19 agosto 2026. Non è stato effettuato alcun retry e
questa authority non autorizza una seconda finestra.

## Artifact congelato

```text
path: experiments/live_instrument/session_receipts/gate-f2-5-36-20260819T082846.463772Z.jsonl
SHA-256: 9c976fabf725eb509f71308d19125b31e1360c1ea0994c2c4d6b679b46628246
prefix SHA-256: 2229c39dcec6fa342f8ab3350ae65a422f7a800af5c75b89875eb89aa05202e6
bytes: 41897
events: 2 + 1 terminal manifest
retention: COMPLETE
description errors: 0
raw RF persistence: ZERO
physical decision affected by receipt: false
```

Il file passa parsing JSON rigoroso. Conserva soltanto receipt scalari, stati,
command receipt e hash pre-analisi; non conserva IQ, campioni, waterfall,
STFT, spettri o patch di candidati.

## Sequenza realmente eseguita

| Fase | Stato emesso | Evidenza |
|---|---|---|
| open dual SND handles | `SATISFIED` | channel ID distinti `1` e `0`, stesso sample rate |
| relative temporal admission | `SATISFIED` | sequenze, sample clock e overlap iniziale ammessi |
| local one-feature discovery | `SATISFIED` | una feature comune supera l'envelope congelato |
| A1→B boundary | `SATISFIED` | comando privato e boundary dual-stream testimoniati |
| B→A2 boundary | `UNSATISFIED` | i boundary locali passano, il controllo finale di continuità no |
| plan freeze | `NOT_EVALUATED` | bloccato dal controllo di continuità |
| one confirmation | `NOT_EVALUATED` | nessuna ipotesi fisica valutata |

Entrambi i comandi sono stati emessi soltanto sul ramo perturbato. I receipt
dei due boundary sono `BOUNDARY_WITNESSED`; il ramo reference non registra
alcun comando di retune.

## Capability e feature realmente osservate

I due handle simultanei hanno negoziato `11998.995409 Hz`. L'ammissione
temporale iniziale ha utilizzato sette frame validi per ramo dopo aver contato
ed escluso un timestamp iniziale nullo. Ha registrato:

- zero sequence gap;
- zero arrival-order violation;
- zero timestamp-step violation;
- zero server clock error code;
- `266855673 ns` di overlap comune;
- almeno `3201` campioni comuni.

La discovery in RAM ha poi ammesso una feature a circa
`-3597.3550689091794 Hz` in baseband:

```text
joint contrast:                 5.282878875732422 dB
first-half contrast:            3.2903785705566406 dB
second-half contrast:           6.388923645019531 dB
cross-branch correlation:       0.8341251707826356
```

Le soglie congelate erano rispettivamente `5.0 dB`, `3.0 dB` in entrambe le
metà e correlazione `0.65`. Il sibling audit, incapace di cambiare la
decisione, registra tre picchi grezzi, tre patch complete, un candidato che
supera correlazione e stabilità e una feature ammessa. I margini migliori
sono `+0.5613250732421875 dB` sul contrasto, `+0.18412517078263557` sulla
correlazione e `+0.2903785705566406 dB` sulla stabilità minima.

Questo autorizza `ONE_FEATURE_ADMITTED` nella finestra A1. Non identifica il
fenomeno e non prova un'origine RF esterna.

## Failure attribution offline

Il receipt finale descrive, per entrambi i rami, sequenze continue ma un solo
`timestamp_step_violation`:

| Ramo | Frame | Sequence gap | Violazioni timestamp | Residuo massimo (campioni) |
|---|---:|---:|---:|---:|
| reference | 64 | 0 | 1 | `3476653914.302939` |
| perturbed | 63 | 0 | 1 | `3476654296.302945` |

Questi numeri non richiedono una causa remota. Il codice finale
`_continuity()` confronta tutti i receipt adiacenti, incluso il timestamp
iniziale nullo. Diversamente, l'ammissione temporale iniziale applica la
regola congelata che conta ed esclude gli zeri iniziali.

Con `512` campioni per frame, sample rate `11998.995409 Hz` e durata scalare
`42670239 ns`, i due residui si ricostruiscono esattamente:

```text
reference:
  abs(289745458498570 - 42670239) / (1e9 / 11998.995409)
  = 3476653914.302939 samples

perturbed:
  abs(289745490334569 - 42670239) / (1e9 / 11998.995409)
  = 3476654296.302945 samples
```

Poiché ciascun ramo contiene una sola violazione e il valore registrato è
esattamente quello prodotto dalla coppia `zero iniziale → primo timestamp
valido`, il blocco è attribuito al validatore software. Il receipt live resta
immutabile e il suo outcome storico resta `INTERVENTION_INVALID`; la corretta
classificazione causale post-run è `QUALIFICATION_ERROR`, non receiver
failure, perdita di stream o clock discontinuity dimostrata.

## Decisione fisica

La feature era disponibile e i due boundary locali erano testimoniati, ma il
runtime ha bloccato plan freeze e confirmation. Pertanto:

```text
measurement availability:       AVAILABLE
falsifiable feature:             AVAILABLE
emitted intervention lifecycle:  INTERVENTION_INVALID
failure attribution:             QUALIFICATION_ERROR (software)
H_UPSTREAM_OF_CHANNEL_DDC:        NOT_EVALUATED
H_DOWNSTREAM_CHANNEL_FIXED:       NOT_EVALUATED
```

La sessione non può essere reinterpretata simulando offline ciò che il ramo
fisico non ha valutato dopo il blocco.

## Cleanup

```text
transport frame leases: 165 acquired / 165 released
decoded IQ frames: 127
decoded IQ samples: 65024
sockets: 2 opened / 2 closed
all IQ zeroized: true
transient raw references after return: 0
```

## Claim autorizzati

- Una singola Kiwi ha fornito due SND/IQ simultanei su DDC distinti e sample
  clock comune.
- La qualification temporale iniziale e la discovery hanno funzionato.
- Una feature comune ha superato le soglie preesistenti senza adattamento.
- Entrambi i comandi e i rispettivi boundary locali sono stati registrati.
- Il blocco finale deriva dall'inclusione software dei timestamp iniziali nulli
  nel secondo controllo di continuità.
- Nessuna ipotesi fisica è stata valutata e nessun dato RF è persistito.

## Claim non autorizzati

Questo outcome non autorizza ad affermare che:

- la feature fosse upstream o downstream del channel DDC;
- la feature provenisse da RF esterna o da un trasmettitore identificabile;
- il clock del server abbia realmente compiuto il salto riportato;
- i DDC abbiano risposto fisicamente come previsto ai comandi;
- eliminando il difetto software la stessa finestra avrebbe prodotto un
  outcome fisico;
- una seconda acquisizione sia autorizzata.

## Minimo successore ammissibile

Il solo cambiamento concettualmente necessario è fare applicare al controllo
di continuità full-session la stessa normalizzazione dei timestamp già
congelata e usata dalla qualification iniziale, verificandola offline con
frame iniziali nulli su entrambi i rami. Questo outcome non apporta la
correzione e non concede una nuova authority.

## SHOCK

Per la prima volta il percorso live ha prodotto contemporaneamente due canali
ammessi, una feature falsificabile e due interventi testimoniati. Il blocco non
è più nella capability né nella feature: è nella duplicazione incoerente di
una regola temporale all'interno del runtime.

Una clausola corretta non basta se due evaluator implementano diversamente lo
stesso dominio. In questo caso il receipt atomico ha fatto esattamente il suo
lavoro: ha impedito di trasformare un errore di qualification in un claim
fisico.

Gate F2.5.36 outcome 1 resta congelato. Nessun retry o nuova osservazione è
autorizzato da questo artifact.
