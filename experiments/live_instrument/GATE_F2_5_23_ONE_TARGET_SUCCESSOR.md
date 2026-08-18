# Gate F2.5.23 — successor prospettico a un target

Stato:

```text
PREFREEZE_SUCCESSOR_MATERIALIZED_OFFLINE
```

Gate F2.5.23 integra esclusivamente offline il risultato di F2.5.22. Non
contiene connector, non ha funzioni di capture predefinite e non concede
autorità live. Ogni artifact entra soltanto attraverso callback obbligatorie
iniettate dai test.

Il successor non cambia l'outcome F2.5.21 né le soglie precedenti. Cambia una
sola rappresentazione: il target resta una feature stretta, mentre il witness
del retune diventa un fingerprint distribuito fuori dai bin del target.

## Ordine prospettico

```text
DIRECT_DUAL_SND_QUALIFICATION
        ↓
ONE_TARGET_DISCOVERY
        ↓
DISTRIBUTED_RETUNE_QUALIFICATION
        ↓
PLAN_FREEZE
        ↓
ONE_CONFIRMATION  [non eseguita in Gate F2.5.23]
```

Le due capture pre-freeze sono callback obbligatorie. Non esiste un default che
possa aprire una Kiwi. Entrambi i retry budget valgono zero.

## Topologia con socket sintetici

Il test verticale attraversa il vero opener phase-aware mediante due socket
sintetici. I rami ricevono metadata, setup e SND/IQ distinti, producono channel
ID `rx:7` e `rx:8`, conservano sequence separate e superano il witness di
simultaneità/event-time. Soltanto una `_TopologyContext` ammessa può entrare
nella nuova discovery.

Questo test non simula una risposta attraverso scorciatoie di stato: esercita
lo stesso confine di controllo che il futuro successor dovrebbe ricevere. Non
effettua rete.

## Discovery a una feature

La discovery riusa le soglie congelate:

```text
minimum_contrast_db = 5.0
minimum_half_contrast_db = 3.0
minimum_fingerprint_correlation = 0.65
minimum_delta_hz = 300.0
maximum_delta_hz = 1500.0
prediction_tolerance_bins = 2.5
```

Il receipt descrittivo di F2.5.22 lega prima della trasformazione entrambi gli
artifact hash e conserva i conteggi `peak → patch → correlation → stability →
admission`, i margini numerici e la base non mascherata usata per la bandwidth.

È sufficiente almeno una feature ammessa. Se ne esistono più di una, il target
viene scelto deterministically per:

1. correlazione cross-branch;
2. stabilità fra le due metà;
3. distanza dai bordi;
4. contrasto persistente;
5. contrasto congiunto;
6. distanza dal centro soltanto come ultimo tie-break.

Nessun secondo picco viene promosso automaticamente a witness. Il delta viene
quantizzato sulla griglia e deve lasciare dentro il passband, per entrambe le
orientazioni ancora possibili, prediction upstream, prediction channel-fixed,
wrong-sign, half-magnitude e off-feature control.

Se non esiste una feature o una geometria orientation-neutral, il risultato è
`NO_FALSIFIABLE_INTERVENTION` e diagnostic, freeze e confirmation restano
`NOT_EVALUATED`.

## Qualification del witness distribuito

La seconda capture pre-freeze contiene A1/B/A2 su reference e perturbed. I sei
artifact hash vengono legati prima dell'analisi. La qualification:

- costruisce una sola griglia comune;
- esclude il target in `0`, `±delta` e `±half-delta` sia sul vettore sorgente
  sia su quello osservato;
- richiede almeno 64 bin rimanenti;
- richiede lo stesso fingerprint A sui due rami;
- richiede reference fisso in A1/B/A2;
- richiede un'unica traslazione non-zero sul perturbed;
- confronta zero, wrong-sign e half-magnitude controls;
- richiede ritorno A2;
- richiede la stessa orientazione sui fold pari e dispari.

Il receipt impone sempre:

```text
target_evaluated = FALSE
target_bins_excluded = TRUE
```

Il test di non-interferenza altera fino a `10000` le ampiezze del target in
tutte le posizioni predefinite. Stato, orientazione, correlazioni e clausole del
witness rimangono identici. La qualification è quindi computazionalmente
indipendente dalla feature che la futura confirmation dovrà valutare.

Se il fingerprint resta channel-fixed anche sul perturbed, l'esito è
`INTERVENTION_NOT_QUALIFIED`; il piano non viene congelato e le fasi successive
restano `NOT_EVALUATED`.

## Piano materializzato

Quando discovery e witness passano, il piano congela:

- endpoint e due channel ID distinti;
- target fingerprint derivato;
- centro A e delta comandato;
- traslazione e orientazione osservate soltanto dal witness;
- intervalli distinti `TARGET_UPSTREAM_B` e `TARGET_CHANNEL_FIXED_B`;
- ritorno A2 e reference fisso;
- wrong-sign, half-magnitude e off-feature controls;
- soglie immutate;
- sei clausole della futura confirmation;
- un'unica confirmation window;
- zero retry post-freeze;
- insieme chiuso dei futuri outcome.

Gli outcome fisici consentiti restano:

```text
UPSTREAM_OF_CHANNEL_DDC_SUPPORTED
DOWNSTREAM_CHANNEL_FIXED_SUPPORTED
AMBIGUOUS
INTERVENTION_INVALID
NOT_DETECTABLE
```

“Upstream” continua a non significare “RF esterna”: antenna, front-end, ADC e
clock condivisi restano possibili.

## Confine raggiunto

Gate F2.5.23 produce in fixture:

```text
PREFREEZE_PLAN_MATERIALIZED_OFFLINE
```

La fase `ONE_CONFIRMATION` è deliberatamente `NOT_EVALUATED`. Il piano e il
contratto esistono, ma manca ancora l'evaluator post-freeze che deve:

1. rivalidare il fingerprint distribuito nella finestra indipendente;
2. rifiutare l'interpretazione del target se il witness non passa;
3. valutare reference, A1, B, A2 e controlli;
4. produrre esattamente uno degli outcome consentiti;
5. non consentire retry, reselection o seconda finestra.

Perciò il prossimo passo è ancora offline. Solo dopo l'integrazione e i test
dell'evaluator potrà essere creato un post-commit seal separato. Gate F2.5.23
non è ancora un live runner e non deve essere autorizzato come tale.

## Claim autorizzato

Una topologia dual-SND sintetica ammessa può attraversare discovery a una
feature, qualification del retune indipendente dal target e plan freeze senza
reintrodurre il secondo picco come requisito universale.

## Claim non autorizzati

Gate F2.5.23 non dimostra che:

- la capability live esponga di nuovo il fingerprint distribuito;
- la feature target ricompaia in una finestra futura;
- il retune live sia qualificato;
- una delle ipotesi fisiche sia supportata;
- il fenomeno sia RF esterno;
- la confirmation sia implementata o autorizzata.
