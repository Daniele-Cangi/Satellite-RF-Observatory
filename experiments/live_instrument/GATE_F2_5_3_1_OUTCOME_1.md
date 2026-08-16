# Gate F2.5.3.1 — outcome live 1

Stato: **ESEGUITO UNA VOLTA E CONGELATO**.

Non è autorizzata una seconda sessione. Questo documento descrive soltanto
l'esecuzione iniziata il `2026-08-16T20:42:47.641290Z` dal runtime:

`aec6da247aa6edb3e180aa848cc05aa2d7f49e2b`

Il piano, i candidati, l'ordine, i centri, le soglie, il budget di retry e la
domanda DDC non sono stati modificati dopo l'autorizzazione.

## Outcome

```text
QUALIFICATION_INCOMPLETE
```

Nessuna coppia dual-SND ha raggiunto readiness IQ. La disponibilità di una
topologia multicanale resta quindi indeterminata. `NO_MULTI_CHANNEL_CAPABILITY`
non è autorizzato perché in ogni candidato è rimasto almeno un errore di
qualification; un errore di trasporto non è un'assenza fisica di capability.

Non esistono `plan_hash` o `physical_result`. Feature discovery, qualification
del retune, plan freeze e confirmation sono tutte `NOT_EVALUATED`.

## Materializzazione del controllo congelato

- candidati: 6, nell'ordine congelato;
- tentativi dual-SND: 8;
- receipt atomici di ramo: 16;
- retry pre-freeze: esattamente 2;
- massimo retry per endpoint: 1;
- retry post-freeze: 0, perché nessun plan è stato congelato;
- finestre di confirmation: 0.

I retry strutturali sono avvenuti su:

1. `dl1bajkiwisdr.ddns.net:8074`;
2. `g0ghk.uk:8050`.

Entrambi sono stati attivati da
`WebSocketConnectionClosedException` nei receipt atomici, non dalla prosa
aggregata. Il budget globale è poi arrivato a zero e nessun altro endpoint è
stato ritentato.

## Receipt per candidato

| Endpoint | Tentativi | Reference | Perturbed | IQ frame | Stato massimo autorizzato |
|---|---:|---|---|---:|---|
| `dl1bajkiwisdr.ddns.net:8074` | 2 | connection closed in entrambi | connection closed in entrambi | 0 | `QUALIFICATION_ERROR` |
| `g0ghk.uk:8050` | 2 | connection closed in entrambi | accesso SND rifiutato in entrambi | 0 | `QUALIFICATION_ERROR` |
| `hill.n8ga.org:8073` | 1 | connection closed | timeout | 0 | `QUALIFICATION_ERROR` |
| `kiwisdr2blair.ddns.net:8073` | 1 | accesso SND rifiutato | connection closed | 0 | `QUALIFICATION_ERROR` |
| `kiwisdr.kfsdr.com:8074` | 1 | accesso SND rifiutato | connection closed | 0 | `QUALIFICATION_ERROR` |
| `va6ok.ddns.net:8073` | 1 | connection closed | connection closed | 0 | `QUALIFICATION_ERROR` |

Le connessioni WebSocket e i handshake sono stati osservati, la configurazione
è stata inviata e il sample rate è stato negoziato. Nessun ramo ha però
prodotto un frame IQ, un readiness witness GNSS o un channel ID utilizzabile.

I quattro `BranchCapabilityRejected`, distribuiti su tre endpoint, sono
evidenza locale del rifiuto di quel ramo in quel tentativo. Non dimostrano che
il server sia universalmente incapace di multicanalità. Le chiusure e il
timeout sono descrizioni del trasporto; non ne viene inferita la causa.

## Artifact receipt verificato

File congelato:

`session_receipts/gate-f2-5-3-1-20260816T204247.641290Z.jsonl`

- righe: 53;
- byte: 130382;
- righe evento prima del manifest: 52;
- byte prima del manifest: 129791;
- SHA-256 del prefisso:
  `f7af85b7e95bac171e35804cdf5904e687d15849d24440a6ce4a27789ab94fe0`;
- SHA-256 dell'intero artifact:
  `be4b10781928eb01a464175c9674681facca4aa30c6541a5e8ba8278ecd78ca5`;
- manifest terminale: presente come ultima riga;
- prefix hash ricomputato: corrispondente;
- stato retention: `COMPLETE`;
- errori descrittivi del sink: 0;
- campi RF vietati trovati: 0;
- persistenza RF: `ZERO`.

L'output terminale è stato troncato dall'interfaccia, ma questa volta ciò non
ha perso l'evidenza: il JSONL completo contiene ogni receipt e il manifest
verificabile. L'hash complessivo ricomputato dal filesystem coincide con il
receipt di chiusura emesso dalla CLI.

## Clausole e fasi

| Fase | Stato |
|---|---|
| status e tentativo direct dual-SND | eseguiti per tutti i candidati |
| atomic branch readiness | nessun ramo `READY` |
| simultaneous dual-IQ topology | non ammessa |
| local IQ feature discovery | `NOT_EVALUATED` |
| per-channel retune qualification | `NOT_EVALUATED` |
| plan freeze | `NOT_EVALUATED` |
| A1/B/A2 confirmation | `NOT_EVALUATED` |
| ipotesi DDC | `NOT_EVALUATED` |

Le 24 clausole downstream `NOT_EVALUATED` corrispondono alle quattro fasi
bloccate per ciascuno dei sei candidati.

## Claim autorizzati

- Il retry strutturale ha materializzato esattamente il budget congelato.
- Tutti i candidati hanno ricevuto almeno un vero tentativo dual-SND.
- In questa sessione nessun ramo ha consegnato un frame IQ.
- Quattro tentativi di ramo, su tre endpoint, hanno restituito un rifiuto
  esplicito di accesso SND.
- Gli altri failure osservati sono chiusure o timeout di trasporto.
- La qualification è terminata prima di determinare la disponibilità fisica
  multicanale.
- Il receipt artifact è completo, hashato e privo di RF persistita.

## Claim non autorizzati

- Nessuno dei sei server possiede una capability multicanale.
- Le chiusure hanno una causa comune o dipendono dal protocollo client.
- Un secondo tentativo fuori budget avrebbe avuto successo.
- Una frequenza o un centro diverso avrebbe prodotto IQ.
- Una feature fisica era assente.
- Una feature è upstream o downstream del DDC.
- La RF è esterna, identificata o localizzata.

## SHOCK

Il nuovo controllo ha funzionato, ma il risultato ha spostato nuovamente il
confine: il sistema sa ora distinguere e conservare perfettamente il proprio
fallimento di qualification, non ancora osservare l'intervento fisico. La
precisione del receipt impedisce una falsa conclusione importante:
“nessun IQ consegnato” non può diventare “nessuna capability multicanale” né
“nessun fenomeno RF”.

Gate F2.5.3.1 si ferma dopo questo primo outcome. Nessun rerun è autorizzato.
