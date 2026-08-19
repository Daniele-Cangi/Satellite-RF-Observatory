# Gate F2.5.9 — review pre-live e runner ordinato

Stato: **CONCLUSO OFFLINE**.

```text
ORDERED_ONE_SHOT_RUNNER_MATERIALIZED
```

Questo gate verifica e materializza il collegamento fra il receipt wire ordinato
di F2.5.8 e il runner prospettico one-shot. Non apre connessioni, non acquisisce
IQ, non cambia candidati, centro, feature, soglie, retry, domanda DDC o stop
condition. Gli outcome precedenti restano congelati ai rispettivi commit.

## Audit del call graph

Il runner terminale F2.5.3.1 conservava correttamente JSONL, manifest e hash, ma
iniettava ancora il qualificatore F2.5.2. Quel qualificatore raggiungeva il
vecchio opener atomico e quindi non materializzava il nuovo ordine causale
server-wire verificato in F2.5.8.

Il successore [`kiwi_gate_f2_5_9.py`](kiwi_gate_f2_5_9.py) sostituisce soltanto
quel bordo:

```text
f25.run_once
  -> direct_ordered_snd_qualification
  -> f258._open_dual_ordered
  -> due transcript wire ordinati e receipt atomici
  -> stessa discovery / retune qualification / freeze / confirmation F2.5
  -> primo outcome
  -> manifest terminale F2.5.3.1
```

Il modulo non contiene un riferimento AST al vecchio opener, non espone CLI e
non esegue I/O all'import. Il bootstrap dichiara separatamente la lineage
storica e i due transform attivi F2.5.8/F2.5.9.

## Semantica dei receipt

Il receipt di fase incorpora entrambi i `F258BranchReceipt`. Lo stato aggregato
non viene più dedotto dal testo di `OrderedDualOpenError`:

| Receipt atomici | Stato della fase |
|---|---|
| almeno un `QUALIFICATION_ERROR` | `QUALIFICATION_ERROR` |
| nessun error e almeno un `CAPABILITY_REJECTED` | `UNSATISFIED` |
| due rami ready ma channel allocation non distinta | `UNSATISFIED` |
| due rami ordinati ammessi e IQ topology valida | `SATISFIED` |

Hash incrementale wire, hash del primo IQ, hash descrittivo e hash del receipt
entrano nel receipt di fase. Nessun frame o campione entra nel JSONL.

Il retry selector legge esclusivamente lo stato e l'`error_type` dei receipt
ordinati. `TimeoutError`, errori WebSocket/trasporto e gli altri tipi già
congelati in F2.5.3 possono consumare il budget pre-freeze. Un `ValueError`, un
rifiuto server o una topologia fisicamente insufficiente non possono farlo.
Budget globale, massimo per endpoint e zero retry post-freeze restano invariati.

## Guard di autorità

`run_once()` richiede `live_authorised=True`. Senza quel valore solleva
`PermissionError` prima di:

- leggere il commit runtime;
- creare il file JSONL;
- entrare nel runner fisico;
- aprire status o WebSocket.

Questo booleano non autorizza da solo una sessione: materializza il punto nel
quale una successiva autorizzazione umana separata dovrà essere applicata. Il
modulo non ha `main` e Gate F2.5.9 mantiene `live_execution_authorised=False`.

## Invarianti conservati

- stesso candidate set e stesso ordine ereditati;
- bootstrap center F2.5.1 invariato e targetless;
- nessun W/F nel causal path;
- `ext_api` soltanto hint;
- due SND simultanei e channel number server distinti;
- discovery STFT/PSD locale soltanto in RAM;
- retune qualification prima del freeze;
- una sola conferma A1/B/A2;
- zero retry, endpoint/frequenza/transform/soglia change dopo freeze;
- terminal manifest e strict receipt-only JSONL;
- zero persistenza RF.

## Test offline

I test verificano:

- bootstrap e transform attivi;
- injection esclusiva dell'opener ordinato, con il legacy reso esplosivo;
- mapping separato di qualification error, rejection e topology rejection;
- retry da error type e non da prose;
- rifiuto pre-I/O senza autorità;
- injection del runner, event prefix e terminal instrument congelati;
- chiusura del manifest anche su eccezione runtime;
- assenza di CLI, import-time I/O e riferimento AST al legacy opener.

## Claim autorizzati

- Il runner one-shot locale è materializzato sul receipt ordinato F2.5.8.
- Il vecchio opener non è raggiungibile dal nuovo wrapper.
- Retry, terminal closure e stop al primo outcome sopravvivono alla sostituzione.
- Una chiamata non autorizzata si ferma prima di rete e artifact creation.
- Il runner è pronto per una review finale di autorità live.

## Claim non autorizzati

- Un endpoint reale è stato contattato.
- Una capability dual-channel è disponibile ora.
- Il server ha accettato auth, tuning o `mod_iq`.
- Una feature o un witness sono rilevabili.
- Una delle ipotesi DDC ha ricevuto supporto.
- Gate F2.5.9 autorizza una sessione live.

## Stop condition

Il gate termina dopo codice, test, documento e commit. La prossima attività può
essere soltanto una review del piano eseguibile e, se approvata separatamente,
una singola invocazione con l'autorità live esplicita. Nessuna nuova finestra è
stata aperta in questo gate.

## SHOCK

Il problema residuo non era più nel detector o nella capability: era un bordo
di composizione. Un receipt epistemicamente migliore resta inerte se il runner
continua a raggiungere il precedente opener. Il cambiamento sufficiente è
quindi una sostituzione di dipendenza verificabile, non un nuovo runtime né un
nuovo framework.
