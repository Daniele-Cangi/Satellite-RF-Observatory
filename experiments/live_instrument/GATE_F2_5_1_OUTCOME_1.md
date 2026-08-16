# Gate F2.5.1 — primo e unico outcome live

Stato: **STOP**. È stata eseguita una sola sessione dal runtime congelato nel
commit `892aa26dd7018e8d86c1eaedad0d0ae64b9a7273`. Non verranno aperte altre
connessioni o finestre per questo outcome.

## Outcome terminale

`QUALIFICATION_INCOMPLETE`

Il failure F2.5 è stato superato: tutti i sei candidati hanno raggiunto un
tentativo diretto e simultaneo dei rami SND reference e perturbed senza usare
`status.bandwidth`, `ext_api` o W/F come gate. Nessun candidato ha però
prodotto una coppia ammessa.

Un candidato ha restituito un rifiuto esplicito dell'accesso SND pubblico. Gli
altri cinque sono rimasti descrittivamente indeterminati per timeout o chiusura
del WebSocket; due di questi hanno consumato i due retry pre-freeze consentiti.
La presenza di errori di qualification vieta di promuovere il risultato a
`NO_MULTI_CHANNEL_CAPABILITY`.

Non sono state raggiunte feature discovery, qualification del retune, plan
freeze o confirmation. Nessuna ipotesi sul boundary DDC è stata valutata.

## Bootstrap congelato

- runtime commit: `892aa26dd7018e8d86c1eaedad0d0ae64b9a7273`;
- start: `2026-08-16T18:25:39.872981Z`;
- ultimo receipt di fase: `2026-08-16T18:26:09.435408Z`;
- durata coperta dai receipt: circa 29,56 s;
- bootstrap receipt hash:
  `13e4528c8aae9d13e43ed79f0e30c0b8f8bfc917fc60dcca15c040143cc8d004`;
- candidate-set hash:
  `b5a4b7e133f10bcf019481e62ceae6c168aa8fd55aecb3601575e7b581c663d7`;
- bootstrap invariant hash:
  `9b7e81f2c2ef4fe9b480046e6cc393e63c4cdef8db2e85c99145649f83c95960`;
- center policy: `kiwi-0-30mhz-interior-endpoint-hash-v2`;
- `status.bandwidth` usato come gate: no;
- `ext_api` usato come gate: no;
- W/F richieste: zero;
- retry budget: due complessivi, massimo uno per endpoint;
- retry post-freeze: non applicabile, perché nessun piano è stato congelato.

## Candidati e tentativi

| Endpoint | Centro bootstrap (Hz) | `ext_api` hint | Tentativi | Stato osservato |
|---|---:|---:|---:|---|
| `dl1bajkiwisdr.ddns.net:8074` | 16683606.560446203 | 4 | 2 | `QUALIFICATION_ERROR`: connessione remota persa in entrambi i tentativi |
| `g0ghk.uk:8050` | 11500110.870109279 | 4 | 1 | `UNSATISFIED`: rifiuto esplicito dell'accesso SND pubblico |
| `hill.n8ga.org:8073` | 11734409.992191182 | 4 | 2 | `QUALIFICATION_ERROR`: timeout, poi connessione remota persa |
| `kiwisdr2blair.ddns.net:8073` | 11649557.425400566 | 3 | 1 | `QUALIFICATION_ERROR`: connessione remota persa |
| `kiwisdr.kfsdr.com:8074` | 9379021.814441692 | 6 | 1 | `QUALIFICATION_ERROR`: connessione remota persa |
| `va6ok.ddns.net:8073` | 17349452.742300700 | 4 | 1 | `QUALIFICATION_ERROR`: connessione remota persa |

Per ogni riga `direct_reference_attempted = true` e
`direct_perturbed_attempted = true`. Gli hint `ext_api` sono stati registrati
ma non hanno cambiato ammissione, retry o classificazione.

## Artifact hash descrittivi

Ogni tentativo ha emesso l'hash dello status e della descrizione dell'errore.
Il medesimo errore del primo endpoint ha prodotto lo stesso error hash nei due
tentativi, mentre gli status sono stati nuovamente acquisiti e hashati.

| Endpoint/tentativo | Status hash | Error-description hash |
|---|---|---|
| `dl1baj…:8074` / 1 | `5417a711daff7bcd2ef9a89399f88d7ffc8e1e0f9a1e430b71d038e043ea7719` | `19c6c03cfca7247cb7a14dd102a8f8a6a38a1d83673b53502827fb200b6ee66f` |
| `dl1baj…:8074` / 2 | `44b162771bb07946179e0ab4ba1a92ebcafa2387c4ad158fbda9b642825a5f1e` | `19c6c03cfca7247cb7a14dd102a8f8a6a38a1d83673b53502827fb200b6ee66f` |
| `g0ghk.uk:8050` / 1 | `e8585be7e8a1fac8ec142ee058aaf6083020d959026ef516492f1bcaf260166f` | `e55aacaf97db2492d75f5393dfa0af19018a23a572528ad483d8b3f3633e3ed5` |
| `hill.n8ga.org:8073` / 1 | `e2193579ba8c3e1ddfd4379648b25c69f478cc1e31ba6b7c4e0abdc0f9546027` | `2e1dd89b9e0a1748ebfaea2be127fcf6b2bd87cf412a17b30152abf9db930b6d` |
| `hill.n8ga.org:8073` / 2 | `f7ba4ac8fd57f1066bc6427fff98bb77a2e551e3c6defff9f75eae217d92ab8d` | `f97991e13f6c5510153463cd3de079e3d97f4a6580ac2452b015db824346171d` |
| `kiwisdr2blair…:8073` / 1 | `f6f4287233e9c5a90b0adb8d15e5f7cdcaec155c4a7ae40e3262db12221c1fab` | `b31c07f790b6203c04b5a62016abb05631614bc6dfcce11ee3fa8c5bd08f746e` |
| `kiwisdr.kfsdr.com:8074` / 1 | `b79a3612ed743a32d3c9d7957e9be53ce856df920679106af834de1287b95188` | `004e774155bc85d0eb962722c029d88f393915a36331ce8865c75f48d04200ce` |
| `va6ok.ddns.net:8073` / 1 | `cdf1530616a50bf862cb31eadff67ec020facab0d514ec77c2cb8e97a5b17335` | `db0a5679a8b5a362455f7302f0d56ed682b63b63fc18da84a49b958ea914bb34` |

Questi sono hash descrittivi, non hash di artifact RF.

## Clausole valutate

- accesso e parsing dello status: soddisfatti per tutti i tentativi;
- applicazione della coordinata bootstrap senza `status.bandwidth`:
  soddisfatta;
- tentativo di entrambi i rami SND: completato per tutti i candidati;
- ammissione di una coppia SND simultanea: non soddisfatta per il candidato con
  rifiuto esplicito, indeterminata per gli errori di trasporto/protocollo;
- indipendenza dei channel ID, simultaneità dei campioni, event time,
  sequence, continuità, clock condiviso e overflow: non valutati, perché
  `_open_dual()` non ha restituito una coppia.

## Clausole bloccate prima dell'ingresso

Per tutti i candidati sono `NOT_EVALUATED`:

- `LOCAL_IQ_FEATURE_DISCOVERY`;
- `PER_CHANNEL_RETUNE_QUALIFICATION`;
- `PLAN_FREEZE`;
- `ONE_CONFIRMATION`;
- `H_UPSTREAM_OF_CHANNEL_DDC`;
- `H_DOWNSTREAM_CHANNEL_FIXED`.

Non esiste `plan_hash` e `physical_result` è `null`.

## Limite del receipt emerso dal live

`_open_dual()` apre i due rami concorrenti, ma se uno fallisce chiude anche
l'eventuale ramo già pronto e propaga un solo errore. Il receipt terminale
registra entrambi i tentativi, ma non conserva separatamente per ciascun ramo:

- handshake raggiunto;
- channel ID assegnato;
- primo blocco IQ GNSS-valido ricevuto;
- motivo e istante della chiusura.

Inoltre `_open_channel()` usa un primo blocco IQ GNSS-valido come condizione di
readiness, ma quel blocco non attraversa l'artifact hasher se l'altra apertura
fallisce. Perciò i receipt non permettono di sapere se, in alcuni tentativi,
un singolo ramo fosse già operativo prima del fallimento dell'altro.

Non è autorizzato affermare “nessun IQ è stato ricevuto”. È autorizzato
affermare che nessun IQ è entrato nella capture duale, nella feature analysis o
nella persistenza, e che nessun RF artifact hash è stato emesso. La
persistenza RF su filesystem o database è rimasta zero.

## Affermazioni autorizzate

- F2.5.1 ha eliminato il blocco causato da `status.bandwidth`.
- Tutti i candidati hanno raggiunto veri tentativi dei due rami SND.
- W/F ed `ext_api` non hanno deciso la multicanalità.
- Un candidato non ha ammesso una coppia durante il tentativo per rifiuto
  esplicito dell'accesso SND pubblico.
- Gli altri candidati restano indeterminati a causa di errori descrittivi di
  trasporto/protocollo.
- Nessuna topologia simultanea è stata ammessa e nessuna ipotesi DDC è stata
  valutata.
- Nessun dato RF, IQ, waterfall o STFT è stato persistito.

## Affermazioni non autorizzate

- Nessun candidato supporta due canali SND.
- I server hanno certamente rifiutato il secondo canale anziché il primo.
- Un singolo ramo non ha mai raggiunto IQ readiness.
- `ext_api` predice correttamente slot realmente disponibili.
- Il centro bootstrap era o non era occupato da una feature RF.
- Il retune per-canale è supportato o non supportato.
- Una feature è upstream o downstream del DDC.
- È stata osservata una sorgente RF esterna o identificabile.

## SHOCK

Il descrittore di banda non era necessario: una capability diretta può essere
interrogata senza waterfall e senza un target preliminare. Una volta rimosso
quel blocco, però, il nuovo collo di bottiglia è diventato visibile: “dual-SND
fallito” è ancora troppo aggregato per distinguere primo ramo, secondo ramo,
readiness IQ e trasporto.

Il prossimo cambiamento minimo deve essere esclusivamente offline: produrre un
receipt atomico per ciascun ramo durante l'apertura, hashare il primo artifact
IQ effimero prima di usarlo come readiness witness e comporre la topologia solo
dopo. Non deve cambiare candidati, centri, retry, soglie o domanda fisica e non
autorizza un nuovo live run.

Gate F2.5.1 outcome 1 si ferma qui.
