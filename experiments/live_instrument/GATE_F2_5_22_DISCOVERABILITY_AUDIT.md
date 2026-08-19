# Gate F2.5.22 — discoverability e witness audit

Stato:

```text
OFFLINE_DISCOVERABILITY_AUDIT_COMPLETE
```

Gate F2.5.22 non ha effettuato connessioni, acquisizioni o probe live. Non ha
modificato l'outcome F2.5.21, le soglie congelate o l'autorità consumata. Il suo
scopo è stabilire che cosa il receipt precedente consenta realmente di
attribuire e se il requisito di due picchi stretti fosse causale oppure soltanto
una rappresentazione sufficiente del witness.

## Attribuzione del receipt congelato

L'artifact F2.5.21 resta identico:

```text
SHA-256: 5307caa715a1f18199a5f933e16ad0c64fb0ce2cfa7753cd254e54e01e9b49fb
outcome: NO_FALSIFIABLE_INTERVENTION
dual-SND: SATISFIED
local-IQ discovery: UNSATISFIED
retune qualification: NOT_EVALUATED
plan freeze: NOT_EVALUATED
confirmation: NOT_EVALUATED
```

La failure è quindi localizzata alla fase di discovery, ma la sua causa
sottostante non è attribuibile dal receipt. Il solo hash conservato dalla fase,

```text
a7ed0ed8e619a33d90876404a1d469d68cd9fef2993a4c1ddea83f703d83d01e
```

è riproducibilmente l'hash della descrizione `ValueError` e non uno dei due
artifact IQ. Sul ramo di eccezione gli artifact effimeri erano stati costruiti
e distrutti, ma i loro hash non sono entrati nel receipt.

Mancano inoltre:

- numero di peak sopra la soglia di contrasto;
- numero di neighbourhood completi;
- numero di candidati sopra la correlazione cross-branch;
- numero di candidati stabili in entrambe le metà della finestra;
- conteggio esatto delle feature ammesse, zero oppure una;
- margine numerico di ogni candidato rispetto alle soglie;
- geometrie target/witness/delta tentate e relative ragioni di rifiuto.

Possiamo quindi affermare soltanto che meno di due strutture hanno superato la
trasformazione congelata. Non possiamo inferire se non esistesse alcun segnale,
se fosse presente esattamente una feature, se il passband fosse fisicamente
povero oppure se correlazione, stabilità o estrazione abbiano eliminato i
candidati.

## Receipt descrittivo minimo

Il nuovo audit offline materializza, per un futuro successor, un receipt
scalare che conserva sempre prima della trasformazione:

- i due SHA-256 distinti degli artifact effimeri;
- griglia comune e risoluzione;
- conteggi monotoni `raw peaks → patch validi → correlation pass → half-window
  pass → feature ammesse`;
- per ogni candidato: posizione, contrasto, stabilità, correlazione, bandwidth e
  margine rispetto alla soglia;
- numero di geometrie ammesse per entrambe le orientazioni e neutralità della
  selezione;
- stato esplicito per ogni quantità non valutata;
- `raw_rf_persistence = ZERO`.

Nessun array spettrale, IQ, STFT, waterfall o campione entra nel receipt. Un
errore software resta distinto da un rifiuto epistemico.

## Difetto della trasformazione legacy

L'audit sintetico ha esposto un difetto separato. Il codice legacy calcola la
larghezza a metà altezza sul vettore usato per l'ammissione, nel quale i bin
esclusi valgono `-1e9`. Quella sentinella può diventare la base di prominenza e
gonfiare artificialmente una bandwidth fino a quasi tutto il passband,
eliminando poi ogni delta possibile.

Questo difetto non è la causa dimostrata dell'outcome F2.5.21: il relativo
messaggio è stato emesso prima della geometria, perché le feature ammesse erano
meno di due. Tuttavia impedirebbe di interpretare correttamente un futuro caso
con due feature. Il receipt F2.5.22 mantiene invariati peak e soglie, ma misura
la sola morfologia sull'array congiunto non mascherato nei peak già
preselezionati:

```text
peak_width_basis = UNMASKED_JOINT_AT_PRESELECTED_PEAKS
```

Non è una modifica retroattiva dell'outcome; è una trasformazione candidata per
un eventuale piano futuro separato.

## Il secondo picco era necessario?

No, non come tipo di oggetto. Due picchi stretti distinti sono una condizione
sufficiente per separare target e witness, ma il taglio causale richiede un
witness ortogonale, non necessariamente un secondo `FeatureFingerprint`.

La semplificazione “usa la stessa feature sia come target sia come witness”
resta inammissibile: permetterebbe alla qualification di apprendere in anticipo
il comportamento che la confirmation dovrebbe mettere alla prova.

L'alternativa minima valutata offline è:

```text
una feature target stretta
        +
fingerprint spettrale distribuito fuori dai bin del target
        +
ramo reference fisso
```

Il fingerprint non viene chiamato segnale né rumore fisico esterno. Può
contenere risposta analogica, spurs ADC, struttura RF e condizionamento comune.
Il suo solo claim è strumentale: testimoniare la trasformazione di coordinate
al boundary del channel DDC senza valutare il target.

## Clausole del witness distribuito

La qualification candidata usa profili effimeri A1/B/A2 e mantiene la soglia
esistente `minimum_fingerprint_correlation = 0.65`. Non introduce probabilità
calibrate né adatta il delta.

Prima di poter qualificare il retune devono essere soddisfatte tutte queste
clausole:

1. almeno 64 bin utilizzabili fuori dalla feature target e dai bordi;
2. fingerprint A condiviso fra reference e perturbed;
3. fingerprint stabile a zero lag sul reference in A1/B/A2;
4. fingerprint perturbed che ritorna a zero lag in A2;
5. una sola traslazione non-zero fra `+delta` e `-delta` che superi zero,
   wrong-sign e half-magnitude controls;
6. stessa orientazione su fold pari e dispari;
7. bin del target esclusi da ogni score;
8. sei artifact hash legati prima dell'analisi e nessuna persistenza RF.

Il ramo reference chiude il taglio “tutto il ricevitore si è spostato”. Il
ritorno A2 chiude il taglio “drift monotono”. I controlli di lag chiudono il
taglio “qualunque correlazione basta”. I fold pari/dispari impediscono che un
singolo gruppo di bin determini l'orientazione. L'esclusione del target mantiene
la qualification indipendente dalla futura domanda fisica.

## Esiti sintetici

I test offline producono tre esiti distinti:

| Fixture | Esito |
|---|---|
| fingerprint comune, reference fisso, perturbed traslato e ritorno A2 | `QUALIFIED_AS_FUTURE_WITNESS` |
| fingerprint valido ma channel-fixed anche sul perturbed | `INTERVENTION_UNRESOLVED` |
| fingerprint piatto o non stabile | `NOT_DETECTABLE` |

La fixture positiva dimostra soltanto la coerenza computazionale del nuovo
causal cut. Non qualifica la Kiwi live, non prova che quel fingerprint sarà
presente in una nuova finestra e non autorizza un'acquisizione.

## Conclusione

```text
two narrowband peaks: SUFFICIENT_BUT_NOT_CAUSALLY_NECESSARY
orthogonal witness: STILL_REQUIRED_AND_MUST_NOT_USE_TARGET_BINS
alternative live qualified: FALSE
old thresholds changed: FALSE
old outcome changed: FALSE
live execution authorised: FALSE
```

L'astrazione messa in discussione è l'equivalenza tra “witness” e “secondo
picco stretto”. Sopravvive invece la separazione epistemica fra qualification
dell'intervento e valutazione del target.

Un eventuale Gate successivo dovrà ancora essere offline: integrare il receipt
descrittivo e il witness distribuito in un nuovo successor, congelare i
controlli e dimostrare con socket sintetici che il target non influenza la
qualification. Soltanto dopo commit e seal separati si potrà chiedere una nuova
autorità live. Gate F2.5.22 non concede tale autorità.
