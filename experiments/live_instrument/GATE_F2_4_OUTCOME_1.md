# Gate F2.4 — primo e unico outcome live

Stato: **STOP**. È stata eseguita una sola sessione dal runtime congelato nel
commit locale `aa17ef153d3a50c9c63d1bfbed6e19d18d6949fe`. Non sono state aperte
altre directory, affordance, finestre o esecuzioni. Nessun push o PR.

## Outcome terminale

`NO_MULTI_CHANNEL_CAPABILITY`

Il significato autorizzato del label in questo receipt è soltanto:

> nessuno dei sei candidati congelati ha **dimostrato** due canali IQ
> simultanei nella sessione.

Non significa che i sei endpoint non possiedano o non consentano in generale
una capability multicanale. Tutti i tentativi si sono fermati per errore di
qualification prima dell'apertura dei due stream SND.

Non esistono channel ID, server-instance receipt, centro A, orientamento,
target, witness, `plan_hash`, segment receipt, intervention receipt o outcome
sulla posizione della feature rispetto al DDC.

## Bootstrap congelato prima della rete

- start: `2026-08-16T15:46:29.766160Z`;
- runtime commit: `aa17ef153d3a50c9c63d1bfbed6e19d18d6949fe`;
- bootstrap receipt hash:
  `b7b55dfd2c325bdcc31f6a3bba832d237b297ede1d827ce3fa0ba6a7ad78e89f`;
- candidate-set hash:
  `b5a4b7e133f10bcf019481e62ceae6c168aa8fd55aecb3601575e7b581c663d7`;
- qualification budget: 420 s;
- retry budget: due complessivi, massimo uno per endpoint;
- selection policy:
  `gate-f2.4-stability-guard-fingerprint-before-strength-v1`;
- transforms:
  `gate-f2:c40ecb471dce:4eb733e6b614:1` e
  `gate-f2.4-same-kiwi-ddc-v1`.

Ordine immutabile:

1. `dl1bajkiwisdr.ddns.net:8074`;
2. `g0ghk.uk:8050`;
3. `hill.n8ga.org:8073`;
4. `kiwisdr2blair.ddns.net:8073`;
5. `kiwisdr.kfsdr.com:8074`;
6. `va6ok.ddns.net:8073`.

La sessione è terminata a `2026-08-16T15:46:55.085551Z`, circa 25,3 s dopo
il bootstrap e molto prima del budget.

## Qualification effettivamente eseguita

Ogni endpoint ha restituito un documento `/status`, che è stato hashato. Il
codice entra nello scout automatico soltanto dopo aver letto `ext_api >= 2` e
non aver trovato una restrizione esplicita; è quindi derivabile che tutti e sei
hanno superato questo gate descrittivo. Questo non dimostra che due slot SND
fossero simultaneamente liberi.

Lo step immediatamente successivo era la waterfall coarse/fine usata dalla
selection policy per determinare il centro senza una frequenza manuale. In
ogni tentativo il WebSocket è stato chiuso dal peer prima che
`_automatic_center()` restituisse un artifact waterfall completo:

`WebSocketConnectionClosedException: Connection to remote host was lost.`

Poiché `_open_dual()` viene chiamato soltanto dopo il ritorno dello scout, il
codice e il ledger stabiliscono che nessun tentativo ha raggiunto l'apertura
dei due canali SND. Non si inferisce perché le connessioni W/F siano state
chiuse: policy dell'operatore, protocollo, stato transitorio e difetto client
restano compatibili.

| Endpoint | Attempt | Status hash | Qualification-error hash |
|---|---:|---|---|
| Hooksiel | 0 | `f53b1e2e…6387b6` | `21f295e6…ca9359` |
| Hooksiel | 1 | `d8d02c96…bb937` | `e4c8670d…b0d0c9a` |
| Doncaster | 0 | `93cff103…23c87` | `57f5e772…eea7` |
| Doncaster | 1 | `a07c8338…d90051` | `40343a90…c7fc67` |
| N8GA Ohio | 0 | `a86e7587…c7e75` | `f1ca0da4…033c4` |
| Blair Washington | 0 | `009f11b7…851fc` | `37d8bed6…8b560` |
| KFS California | 0 | `f2ebab26…421c` | `117a6b01…7cc04` |
| VA6OK Alberta | 0 | `327f8f09…02044` | `f6ed2c4a…e8774` |

I due retry globali sono stati consumati, nell'ordine congelato, da Hooksiel e
Doncaster. Nessun altro endpoint è stato ritentato. Non vi è stato retry dopo
un plan freeze perché nessun piano è esistito.

## Audit delle proprietà

### Valutata positivamente

- `status_access`: `SATISFIED` per tutti gli otto tentativi.

### Gate descrittivo superato, ma non prova della proprietà fisica

- il codice ha osservato `ext_api >= 2` prima di entrare nello scout;
- non ha però aperto due stream, quindi
  `two_simultaneous_channel_slots` resta `NOT_EVALUATED`.

### Non valutate

- `same_server_instance`;
- `two_simultaneous_channel_slots` come disponibilità effettiva;
- `distinct_channel_ids`;
- `simultaneous_IQ_streams`;
- `event_time_valid`;
- `sequence_ranges_distinct`;
- `shared_clock_alignment`;
- `reference_channel_continuity`;
- `per_channel_retune_available`;
- `fixed_channel_unaffected_by_retune`;
- `retune_transform_witnessed`.

Tutte le venti clausole della confirmation sono correttamente
`NOT_EVALUATED`.

### Difetto descrittivo del receipt

Il JSON Lines live ha assegnato `QUALIFICATION_ERROR` alla prima proprietà
mancante, `same_server_instance`. È una collocazione descrittiva impropria:
l'errore è avvenuto nello scout W/F precedente e non costituisce una misura
negativa della server instance. La corretta failure attribution è:

- operation state: `QUALIFICATION_ERROR` durante automatic-center scout;
- `same_server_instance`: `NOT_EVALUATED`;
- tutte le proprietà downstream: `NOT_EVALUATED`.

Questo errore descrittivo non ha promosso alcuna clausola, non ha creato root e
non ha modificato una decisione RF: nessuna decisione RF è stata raggiunta.

## Artifact e persistenza

Sono presenti sedici hash descrittivi: otto documenti status e otto descrizioni
di errore. Non esiste un hash di waterfall completa, perché nessuna waterfall
ha completato il numero di frame richiesto. Non è possibile stabilire dal
receipt se siano transitati frame parziali prima della chiusura; eventuali byte
parziali non sono stati conservati e non vengono trattati come evidenza.

Persistenza RF:

- IQ: zero;
- waterfall: zero;
- sample array: zero;
- database/storage RF: assente;
- segment/intervention receipt: zero.

## Osservazioni, derivazioni e decisioni

### Osservato

- sei endpoint hanno risposto a `/status` nella sessione;
- otto tentativi W/F hanno perso la connessione prima di un artifact completo;
- i due retry consentiti sono stati consumati senza cambiare endpoint, soglie,
  ordine o selection policy;
- nessuno stream IQ è stato aperto.

### Derivato dal ledger del codice

- l'errore precede `_open_dual()`;
- non esiste prova di due channel branch o di un retune;
- non esiste una finestra prospettica sulla quale valutare
  `H_UPSTREAM_OF_CHANNEL_DDC` o `H_DOWNSTREAM_CHANNEL_FIXED`.

### Deciso prima della rete

- candidate set e ordine;
- budget e retry policy;
- waterfall coarse/fine come unico selettore automatico del centro;
- nessuna frequenza manuale;
- requisito topologico same-Kiwi/two-channel;
- stop al primo outcome globale.

## Claim autorizzati

- Il bootstrap receipt è stato emesso prima della rete dal commit pulito.
- Tutte le sei affordance congelate hanno risposto al probe `/status`.
- Nessuna ha dimostrato due canali simultanei entro questa sessione.
- La qualification è stata bloccata nello scout automatico precedente ai due
  stream.
- Non sono stati acquisiti IQ, creati measurement root o congelati piani.
- Il runner ha rispettato candidate order, budget di retry e stop condition.

## Claim non autorizzati

- I sei endpoint non supportano il multicanale.
- Due slot SND non erano disponibili.
- La waterfall è disabilitata per policy dell'operatore.
- Il server instance o il causal cut erano inammissibili.
- Il retune per-canale non funziona.
- Una feature è upstream o downstream del DDC.
- L'origine è RF esterna, un trasmettitore è identificato o esiste una causa
  fisica comune.

## Astrazione eliminata e limite empirico

Il runtime non richiede più localizzazione o due hardware root indipendenti.
Questo elimina il requisito universale a livello di progetto. L'esecuzione non
ha però ancora convalidato empiricamente la topologia sostitutiva: non ha
raggiunto due channel branch.

## Nuova variazione SHOCK

Il probe era stato reso indipendente da frequenze e target predeterminati, ma
ha introdotto un'altra dipendenza più precoce: la superficie W/F necessaria a
scegliere automaticamente il centro. In questa sessione quella capability
ausiliaria è stata più restrittiva della capability che si voleva realmente
qualificare e ha impedito perfino di porre la domanda multicanale.

Il risultato non dice che serva una frequenza hardcoded. Dice che
“selezionare dove guardare” e “dimostrare il causal cut dello strumento” sono
capability differenti, e che la prima non deve essere scambiata per evidenza
negativa sulla seconda.

Gate F2.4 si ferma qui. Non viene progettato né eseguito un Gate successivo.
