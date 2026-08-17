# Gate F2.5.12 — receipt semantico hash-bound, solo offline

Stato:

```text
HASH_BOUND_SEMANTIC_RECEIPT_IMPLEMENTED
```

Questo Gate implementa il cambiamento minimo emerso dalla failure attribution
F2.5.11. Non modifica il runner o l'outcome F2.5.10, non apre connessioni e non
acquisisce RF. Il modulo non espone `run`, `main` o entry point live.

## Problema chiuso

Il receipt precedente hashava ogni frame prima dell'analisi, ma per i frame
non ammessi conservava soltanto hash, conteggio e byte totali. Dopo la
distruzione non era più possibile distinguere:

```text
nessun SND osservato
```

da:

```text
SND osservato → decode valido → predicate GPS non soddisfatto
```

F2.5.12 associa allo stesso hash pre-analisi una transizione semantica per ogni
clausola necessaria alla readiness. Non conserva il frame né i sample.

## Receipt atomico per frame

Ogni frame transiente produce esclusivamente:

- SHA-256 calcolato prima di tag parsing, decode e predicate;
- classe `MSG`, `SND`, `CLOSE`, `OTHER` o `MALFORMED`;
- numero di byte, senza contenuto;
- stato separato delle clausole;
- sequence e GPS solution age soltanto per un header SND valido;
- event time soltanto quando tutte le clausole di readiness sono soddisfatte;
- eventuale tipo e hash dell'errore descrittivo;
- `raw_rf_persistence = ZERO`.

Non esistono campi per body, payload, IQ, sample, STFT o waterfall.

## Clausole SND

Le clausole sono valutate separatamente:

```text
SND_HEADER
→ IQ_MODE
→ SAMPLE_DECODE
→ GPS_SECONDS_PRESENT
→ GPS_AGE_WITHIN_30_S
→ READINESS
```

Ogni clausola assume uno dei soli stati:

- `SATISFIED`;
- `UNSATISFIED`;
- `NOT_EVALUATED`;
- `QUALIFICATION_ERROR`.

Il limite GPS rimane esattamente 30 secondi e non è un parametro del caller.
F2.5.12 non modifica alcuna soglia congelata.

## Semantica delle decisioni

| Condizione | Disposition | Readiness |
|---|---|---|
| `MSG`, altro control frame o close valido | `DESCRIPTIVE_CONTROL` | `NOT_EVALUATED` |
| SND valido e tutte le clausole soddisfatte | `READINESS_ADMITTED` | `SATISFIED` |
| SND valido ma IQ/GPS clause non soddisfatta | `SND_NOT_ADMITTED` | `UNSATISFIED` |
| header, decode, sample rate o close malformed | `QUALIFICATION_ERROR` | `NOT_EVALUATED` |

Un errore descrittivo non può essere riclassificato come rifiuto fisico. Il
vocabolario di disposition non contiene `CAPABILITY_REJECTED`; tale decisione
resta affidata soltanto a un rifiuto server esplicito osservato nel control
receipt.

Le invarianti rifiutano inoltre:

- event time quando readiness non è soddisfatta;
- sequence o GPS age su un frame non-SND;
- readiness soddisfatta senza tutte le clausole upstream;
- `SND_NOT_ADMITTED` senza una readiness realmente `UNSATISFIED`;
- un peer status inventato su un close senza status.

## Correzione permanente del close vuoto

Un close con payload vuoto produce:

```text
close_payload_state = EMPTY_NO_STATUS
peer_close_status_code = null
```

Non viene più sintetizzato `1005`. Un payload contenente realmente almeno due
byte produce invece `STATUS_PRESENT` e conserva il codice ricevuto. Un payload
di un byte è `QUALIFICATION_ERROR`, non un peer status.

L'artifact hash resta compatibile con la rappresentazione precedente:

```text
SHA256(b"CLOSE" + payload)
```

## Cosa diventa falsificabile nella qualification

In una futura sessione il ledger potrebbe ora separare senza ambiguità:

- `NO_SND_OBSERVED`: nessun receipt con classe `SND`;
- `SND_NOT_IQ`: `IQ_MODE = UNSATISFIED`;
- `SND_WITHOUT_GPS_SECONDS`: GPS seconds clause non soddisfatta;
- `SND_GPS_STALE`: age oltre 30 secondi;
- `SND_TRANSFORM_ERROR`: decode descrittivo e readiness `NOT_EVALUATED`;
- `SND_READY`: tutte le clausole soddisfatte e event time disponibile.

Questo risolve l'ambiguità specifica di F2.5.10 senza affermare che il comando
`mod_iq` sia stato applicato remotamente.

## Causal cut ancora aperti

Il nuovo receipt non prova:

- che un send locale di `mod_iq` sia stato applicato dal server;
- quale componente remoto causi un close;
- che un endpoint possieda due branch simultanei prima di due receipt ready;
- che una feature RF sia presente;
- che la feature sia upstream o downstream del channel DDC.

Questi cut appartengono rispettivamente alla qualification del controllo, alla
composizione dual-branch e al futuro esperimento A1/B/A2. Non vengono compressi
nel frame receipt.

## Zero persistenza

I test costruiscono frame SND sintetici, li decodificano in RAM e verificano
che il risultato serializzabile non contenga byte, array NumPy o campi RF. I
sample temporanei sono distrutti prima del ritorno. La serializzazione passa
attraverso il confine strict JSON già congelato.

Non viene scritto alcun JSONL di sessione perché non esiste una sessione.

## Integrazione differita

F2.5.12 materializza la primitive e le sue invarianti, ma non sostituisce
ancora `_open_channel_ordered()` nel runner live. L'integrazione nel causal
path dovrà essere un Gate offline separato, seguito da una nuova review
pre-live. Questa implementazione non autorizza rete, retry o rerun.

## SHOCK

Un witness positivo `IQ_FRAME_OBSERVED` non basta a rendere interpretabile la
sua assenza. Perché un negativo sia utilizzabile, ogni trasformazione che può
escludere il witness deve lasciare una transizione negativa o non valutata,
legata allo stesso artifact hash.

La primitive minima è quindi:

```text
artifact hash
+ frame class
+ clause-by-clause transition
```

Non è una nuova classe generica di sorgenti o un framework di esperimenti.
Gate F2.5.12 si ferma prima dell'integrazione live.
