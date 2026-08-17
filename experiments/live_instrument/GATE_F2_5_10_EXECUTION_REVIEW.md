# Gate F2.5.10 — review finale dell'envelope eseguibile

Stato: **CONCLUSO OFFLINE**.

```text
REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY
```

Nessuna connessione Kiwi, status request o acquisizione è stata effettuata.
Questo gate non aggiunge logica RF: congela e verifica l'unico modo ammesso di
entrare nel runner F2.5.9 dopo una futura autorizzazione separata.

## Correzione pre-live

La review ha trovato una libertà residua. `kiwi_gate_f2_5_9.run_once()` espone
argomenti tecnici utili ai test (`mother`, `runtime_commit`, `receipt_path`), ma
un caller live avrebbe potuto usarli per cambiare durate, soglie, lineage o
destinazione del receipt pur impostando `live_authorised=True`.

Il modulo [`kiwi_gate_f2_5_10.py`](kiwi_gate_f2_5_10.py) introduce un solo shim
gate-specifico:

```python
run_reviewed_once(*, live_authorised: bool = False)
```

Non accetta altri parametri. Non è un nuovo detector, adapter o framework:
dopo i guard locali crea il terminal emitter, scrive l'envelope nel JSONL e
invoca una volta lo stesso control flow F2.5 con qualificatore e retry F2.5.9.

## Envelope congelato

| Dimensione | Valore |
|---|---:|
| candidate set hash | `b5a4b7e133f10bcf019481e62ceae6c168aa8fd55aecb3601575e7b581c663d7` |
| MotherPlan hash | `6f4b367d3b32cf6bfc362c14882f2e0822f33d3f0893b22df58a138f7caf5f9a` |
| qualification budget | 420,0 s |
| candidati | 6, ordine immutabile |
| endpoint concorrenti | 1 |
| slot SND simultanei per tentativo | 2 |
| retry pre-freeze | 2 globali, massimo 1 per endpoint |
| tentativi candidati massimi | 8 |
| WebSocket connect timeout | 8,0 s |
| ordered-control deadline | 12,0 s |
| topology capture | 1,5 s |
| local IQ discovery | 4,0 s |
| retune qualification A1/B/A2 | 9,1 s |
| capture pre-freeze totale | 14,6 s |
| confirmation indipendente | 10,6 s |
| capture massima con candidato ammesso | 25,2 s |
| retry post-freeze | 0 |
| persistenza RF | zero |
| stop | primo outcome, poi close |

I separatori decimali nella tabella sono descrittivi italiani. Nei receipt
JSON Lines i numeri restano JSON standard con punto decimale.

## Ordine e centri bootstrap

I centri sono coordinate di qualification derivate deterministicamente
dall'endpoint dentro l'intervallo Kiwi congelato. Non identificano un target e
non leggono status, W/F o IQ.

| Ordine | Endpoint | Centro Hz |
|---:|---|---:|
| 1 | `dl1bajkiwisdr.ddns.net:8074` | 16683606.560446203 |
| 2 | `g0ghk.uk:8050` | 11500110.870109279 |
| 3 | `hill.n8ga.org:8073` | 11734409.992191182 |
| 4 | `kiwisdr2blair.ddns.net:8073` | 11649557.425400566 |
| 5 | `kiwisdr.kfsdr.com:8074` | 9379021.814441692 |
| 6 | `va6ok.ddns.net:8073` | 17349452.742300700 |

Un endpoint che dichiara accesso ristretto viene rifiutato prima degli slot e
non può sostenere `NO_MULTI_CHANNEL_CAPABILITY`. `ext_api` resta un hint. Per
gli endpoint ammissibili, la verità multicanale viene soltanto dal tentativo
diretto dei due rami SND ordinati.

## Guard prima della rete

Una futura chiamata autorizzata esegue, in ordine:

1. confronto dei 13 file sul causal path con il commit fisico revisionato
   `4eed64a2adc53e7535adbb8d5f7e8967d204b6a8`;
2. confronto dell'environment con Python 3.13.5, NumPy 2.3.3, SciPy 1.17.1 e
   websocket-client 1.8.0;
3. verifica che il processo parta dalla root della repository;
4. ricostruzione e validazione dell'envelope;
5. scrittura dell'envelope e del suo hash come primo receipt;
6. invocazione singola del control flow F2.5 con opener/retry F2.5.9.

Qualunque mismatch produce `EXECUTION_ENVELOPE_MISMATCH` prima di status,
WebSocket o creazione del receipt live. Senza `live_authorised=True`, il rifiuto
avviene ancora prima dei guard.

## Percorso della singola esecuzione futura

```text
separate human authority
  -> local source/environment/envelope guards
  -> candidate 1..6, sequentially
      -> status/access description
      -> ordered SND R + SND P direct attempt
      -> at most one typed pre-freeze retry for that endpoint
  -> first admitted two-channel topology, if any
      -> 1.5 s topology capture
      -> 4.0 s local targetless discovery
      -> 9.1 s witness-only retune qualification
      -> immutable plan freeze
      -> 10.6 s independent A1/B/A2 confirmation
  -> exactly one outcome
  -> both channels closed
  -> terminal receipt manifest
```

Se nessun candidato entra, il primo outcome è comunque terminale. Il runner non
è obbligato a sintetizzare un esperimento.

## Outcome ammessi

- `QUALIFICATION_INCOMPLETE`
- `NO_MULTI_CHANNEL_CAPABILITY`
- `NO_ADMISSIBLE_CAUSAL_TOPOLOGY`
- `NO_FALSIFIABLE_INTERVENTION`
- `UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`
- `DOWNSTREAM_CHANNEL_FIXED_SUPPORTED`
- `AMBIGUOUS`
- `INTERVENTION_INVALID`
- `NOT_DETECTABLE`

Nessun outcome autorizza da solo “external RF”, identità del trasmettitore,
geolocalizzazione o causalità oltre il boundary del DDC per-canale.

## Receipt e distruzione

Il path è quello default sotto `experiments/live_instrument/session_receipts` e
non è sovrascrivibile dal caller live. Il JSONL conserva soltanto receipt,
transcript allowlisted, metadata e hash; termina con prefix hash e manifest. IQ,
frame, STFT, PSD e waterfall restano effimeri in RAM e vengono distrutti.
Il primo evento conserva l'intero execution envelope, il suo hash e il nome
dell'authority surface; così i guard applicati non restano una premessa esterna
al receipt fisico.

## Massimo cambiamento consentito prima dell'esecuzione

Nessuno sui file causali, sul `MotherPlan`, sull'environment, sull'ordine dei
candidati o sulla working directory. Un mismatch non può essere “corretto” e
ritentato nella stessa autorità: richiede un nuovo gate offline e una nuova
review.

## Claim autorizzati

- L'envelope eseguibile è completo e attualmente riproducibile offline.
- Il caller live non può cambiare piano, path, commit o retry tramite lo shim.
- Il carico massimo e lo stop al primo outcome sono espliciti.
- La prossima azione può essere una richiesta separata per una singola
  esecuzione live da questo stato Git pulito.

## Claim non autorizzati

- Una capability è viva o disponibile adesso.
- I sei endpoint accetteranno due slot.
- Una feature target/witness esisterà.
- Un intervento sarà falsificabile.
- Questa review costituisce autorizzazione live.

## Stop condition

Gate F2.5.10 si ferma dopo audit, guard, test e commit. La forma esatta della
futura invocazione, non eseguita qui, è:

```text
python -c "from experiments.live_instrument import kiwi_gate_f2_5_10 as gate; gate.run_reviewed_once(live_authorised=True)"
```

## SHOCK

Il booleano di autorità non basta se la stessa funzione lascia modificare il
metodo autorizzato. L'unità da autorizzare non è “accesso alla rete”, ma una
specifica transizione da codice, environment ed envelope revisionati verso un
solo outcome. Eliminare gli override ha più valore epistemico di aggiungere un
altro controllo sul sensore.
