# Gate F2.5.20 — verticale prospettico dalla capability qualificata

Stato: **MATERIALIZZATO OFFLINE; NESSUNA AUTORITÀ LIVE**.

Gate F2.5.19 ha stabilito un fatto nuovo: una Kiwi pubblica ha fornito due rami
SND/IQ simultanei e distinti. Gate F2.5.20 usa soltanto quel fatto per costruire
il prossimo esperimento; non interpreta i due frame di readiness come discovery
e non cerca un'altra capability.

## Domanda fisica

Una struttura osservata sui due canali è a monte oppure rimane fissa a valle
del DDC del solo ramo perturbato?

Le sole ipotesi congelabili sono:

```text
H_UPSTREAM_OF_CHANNEL_DDC
  la coordinata RF ricostruita resta invariata;
  la feature trasla in baseband soltanto nel ramo perturbato;
  target e witness restano stabili nel ramo reference.

H_DOWNSTREAM_CHANNEL_FIXED
  la feature resta nella stessa posizione baseband del ramo perturbato;
  la coordinata RF ricostruita cambia con il tuning;
  target e witness restano stabili nel ramo reference.

H_UNRESOLVED
  nessuna delle due predizioni è supportata in modo univoco.
```

“Upstream” comprende antenna, front-end, ADC, clock e relativi artefatti
condivisi. Non significa automaticamente RF esterna.

## Lineage immutabile

- outcome padre: commit
  `db7e314490122474fecaf2a8acaed74b0a55dcdc`;
- artifact padre SHA-256:
  `ab2ea016e60ca100d665310f520dbec022c206c3d42f1f92a7b55f5d0b684a47`;
- endpoint ammesso: `dl1bajkiwisdr.ddns.net:8074`;
- coordinata bootstrap: `16683606.560446203 Hz`;
- ruolo della coordinata: `QUALIFICATION_BOOTSTRAP_NOT_FEATURE`;
- retry pre-freeze: zero;
- retry post-freeze: zero;
- persistenza RF/IQ/STFT/waterfall: zero.

Il vecchio receipt seleziona l'endpoint, ma non soddisfa l'ammissione futura.
Le due connessioni corrette devono essere riqualificate nella stessa sessione
prima della nuova discovery.

## Sequenza futura esatta

```text
corrected dual-SND requalification
  -> topology continuity witness
  -> new 4 s local-IQ discovery window
  -> target + distinct witness + feasible delta
  -> witness-only A1/B/A2 retune qualification
  -> freeze target, witness, delta, sign, intervals, thresholds and controls
  -> one new post-freeze A1/B/A2 confirmation
  -> one outcome and stop
```

Topologia, discovery e retune restano fasi distinte. Il target non entra nella
qualification del retune: una feature separata deve traslare nel ramo
perturbato, rimanere fissa nel reference e tornare in A2. Solo dopo questo
witness vengono congelate le predizioni sul target.

## Detectability envelope invariato

Gate F2.5.20 non modifica i limiti già congelati nel verticale:

- discovery: 4 s;
- segmenti diagnostici: 2.5 s;
- segmenti di conferma: 3 s;
- settling: 0.8 s;
- contrasto target minimo: 5 dB;
- contrasto witness minimo: 5 dB;
- correlazione fingerprint minima: 0.65;
- contrasto minimo in entrambe le metà temporali: 3 dB;
- delta ammesso: 300–1500 Hz;
- tolleranza: 2.5 bin spettrali;
- massima latenza event-time/arrival: 5 s;
- GPS solution age massimo: 30 s.

Non vengono introdotte probabilità calibrate. Il piano usa intervalli
geometrici disgiunti e invarianti di continuità, event time, sequenza, overflow
e causalità dei comandi.

## Transizioni e controlli congelati

Transizione positiva:

```text
il witness trasla nel ramo perturbato del delta firmato previsto e ritorna in A2
```

Transizione negativa:

```text
target e witness non si muovono nel ramo reference e il suo command ledger resta vuoto
```

Controlli predefiniti:

- posizione con segno opposto;
- posizione con magnitudine errata;
- posizione off-feature;
- ritorno A2;
- assenza di comandi sul reference.

Il target deve essere rilevabile su entrambi i rami in A1 e sul reference in B.
Se il witness non valida l'intervento, il target non decide l'ipotesi.

## Outcome ammessi

Prima del freeze:

- `QUALIFICATION_INCOMPLETE` per errore software/trasporto;
- `NO_MULTI_CHANNEL_CAPABILITY` o `NO_ADMISSIBLE_CAUSAL_TOPOLOGY` soltanto
  dalle rispettive clausole osservate;
- `NO_FALSIFIABLE_INTERVENTION` se la nuova finestra non produce un envelope;
- downstream `NOT_EVALUATED` quando l'ammissione precedente fallisce.

Dopo il freeze:

- `UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`;
- `DOWNSTREAM_CHANNEL_FIXED_SUPPORTED`;
- `AMBIGUOUS`;
- `INTERVENTION_INVALID`;
- `NOT_DETECTABLE`.

Dopo il freeze non esiste alcun retry, cambio endpoint, frequenza, feature,
delta, finestra, trasformazione o soglia.

## Modifica minima

Il detector prospettico esistente non viene duplicato. Gate F2.5.20 sostituisce
soltanto il suo ingresso obsoleto con il dual-SND phase-aware dimostrato in
F2.5.19 e riduce il candidate loop all'unico endpoint realmente qualificato.
Il raccordo continua a riusare discovery, witness, freeze, controlli ed
evaluator A1/B/A2 già testati. Non nasce un adapter SDK o un runtime generale.

## Confine di autorità

Il modulo richiede connector e qualifier iniettati, non importa `websocket`,
non contiene `run()` o `main()` e non possiede una superficie live. I test
usano soltanto socket e IQ sintetici. Un post-commit seal separato dovrà legare
il commit e l'ambiente prima che possa essere richiesta una singola autorità
live.
