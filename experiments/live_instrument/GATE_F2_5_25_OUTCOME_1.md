# Gate F2.5.25 — outcome live 1

Stato terminale:

```text
QUALIFICATION_INCOMPLETE
```

L'unica autorità riferita al commit
`d95ff53c416f5e207a58890e726312f7d88f1832` e all'authority envelope
`fa21168df4487508b63cba9aec1324c57a91c60e9e144d7d646a972a09a4953d`
è stata consumata il 18 agosto 2026. Non è stato effettuato alcun retry e non
è autorizzata una seconda finestra con questa authority.

## Artifact congelato

```text
path: experiments/live_instrument/session_receipts/gate-f2-5-25-20260818T194244.943090Z.jsonl
SHA-256: 921deca68780b6546d19d4f8be2cb3cbb0ed5c9710d333f5dd24bf5d799b7380
prefix SHA-256: 22dede9a078858af115eb2ba042d4bfd0e2893f931c061e51428fae7790c5890
bytes: 857267
events: 8 + 1 terminal manifest
retention: COMPLETE
description errors: 0
raw RF persistence: ZERO
physical decision affected by receipt: false
```

Il JSON Lines rigoroso conserva envelope, receipt atomici, metadati di frame,
stati di clausola e hash calcolati prima della distruzione degli artifact
effimeri. Non contiene body di frame, IQ, campioni, waterfall o STFT.

## Sequenza realmente eseguita

La sessione ha contattato una sola volta la capability congelata
`dl1bajkiwisdr.ddns.net:8074` al bootstrap qualificativo
`16683606.560446203 Hz`.

| Fase | Stato | Conseguenza |
|---|---|---|
| direct dual-SND qualification | `QUALIFICATION_ERROR` | due canali hanno prodotto SND/IQ, ma nessun event-time witness ha soddisfatto il contratto |
| one-target discovery | `NOT_EVALUATED` | bloccata prima dell'ingresso |
| distributed retune qualification | `NOT_EVALUATED` | nessun intervento eseguito |
| plan freeze | `NOT_EVALUATED` | nessuna prediction congelata |
| one confirmation | `NOT_EVALUATED` | nessun A1/B/A2 prospettico eseguito |

La stop condition ha chiuso l'esecuzione al primo outcome. Non esiste un
`plan_hash`, nessuna delle cinque ipotesi di confirmation è stata valutata e
l'autorità non può essere riutilizzata.

## Che cosa è stato realmente osservato

Entrambe le connessioni hanno superato apertura, auth locale, metadata, channel
allocation, `badp=0`, audio rate e `mod=iq`. Il server ha assegnato channel ID
distinti, `0` e `1`.

| Ramo | Frame ricevuti | Frame SND | Header/decode/IQ mode | SND ammessi come readiness |
|---|---:|---:|---|---:|
| reference | `295` | `275` | tutti `SATISFIED` | `0` |
| perturbed | `293` | `274` | tutti `SATISFIED` | `0` |

Per ciascun ramo il primo SND riportava `gps_solution_age_s = 0`, ma non
conteneva i secondi GPS; non poteva quindi fornire event time. Tutti i SND
successivi contenevano i secondi GPS, ma l'età della soluzione cresceva da
`92 s` a `103 s`, oltre il massimo congelato di `30 s`. Nessun frame ha
soddisfatto simultaneamente le clausole temporali. Entrambi i rami hanno infine
terminato il budget di attesa con `TimeoutError`.

Questa è disponibilità di campioni senza disponibilità di una misura
temporalmente ammissibile. Il runtime non ha promosso il mero flusso IQ a
evidenza e non ha usato i channel ID distinti per aggirare la clausola mancante.

## Perché non è `NO_MULTI_CHANNEL_CAPABILITY`

Due connessioni, due channel ID e centinaia di frame SND sono stati realmente
osservati. Il fallimento non dimostra l'assenza di multicanalità. Tuttavia i
witness di readiness richiesti non erano validi, quindi le clausole su
connessioni distinte, sequence separate e overlap event-time non potevano
essere completate. La classificazione corretta resta
`QUALIFICATION_INCOMPLETE`, non `CAPABILITY_REJECTED` e non
`NO_MULTI_CHANNEL_CAPABILITY`.

## Claim autorizzato

In questa sessione la capability ha consegnato due flussi SND/IQ distinti, ma
non ha prodotto due measurement root con event time entro il limite congelato.
La topologia same-session non ha quindi ammesso la discovery prospettica.

## Claim non autorizzati

Questo outcome non autorizza ad affermare che:

- non esistessero segnali o strutture nel passband;
- i campioni ricevuti fossero privi di informazione fisica;
- il receiver non fosse multicanale;
- il limite di `30 s` dovesse essere cambiato dopo l'esito;
- la feature fosse upstream o downstream del channel DDC;
- il retune per-canale fosse valido o invalido;
- una delle ipotesi F2.5.24 fosse supportata o falsificata;
- un'origine RF esterna, un trasmettitore o un satellite fosse identificato.

## SHOCK

L'accesso ai dati non coincide con l'osservabilità. Qui Internet ha fornito
due canali e centinaia di blocchi IQ, ma il percorso causale richiesto includeva
anche un clock event-time qualificato. Senza quel ponte, una feature spettrale
avrebbe potuto essere calcolata, ma un risultato negativo non sarebbe stato
temporalmente interpretabile.

La clausola ha quindi eliminato l'esperimento prima che il volume dei dati
potesse creare una falsa impressione di evidenza. Il componente essenziale non
era un planner né un target: era la distinzione fra `DATA_AVAILABLE` e
`MEASUREMENT_ADMISSIBLE`.

Gate F2.5.25 outcome 1 resta congelato. Qualunque lavoro successivo deve essere
offline, non può abbassare retroattivamente il limite temporale e non può
riutilizzare l'autorità consumata.
