# Gate F2.5.10 — outcome live 1

Stato: **ESEGUITO UNA VOLTA E CONGELATO**.

Non è autorizzata una seconda sessione. Questo documento descrive soltanto
l'esecuzione iniziata il `2026-08-17T09:34:14.925168Z` dal runtime:

`d636981ab6c71f3ca6c673c5cff072ccd7025dcd`

Il working tree era pulito, HEAD e upstream coincidevano, i guard non avevano
blocker e l'execution envelope aveva hash:

`e35aedb598a19c9ce9262e990abec2ff2f90e9fcd1ac7ed2406c9c85f09106ab`

Nessun candidato, centro, transform, threshold, retry o path è stato cambiato.

## Outcome

```text
QUALIFICATION_INCOMPLETE
```

I sei endpoint hanno ricevuto un vero tentativo dual-SND simultaneo. Nessun
ramo ha però prodotto il witness ordinato `IQ_FRAME_OBSERVED` richiesto per la
readiness, quindi nessuna topologia è stata ammessa.

Non esistono `plan_hash`, `physical_result` o measurement root. Discovery
locale, retune qualification, plan freeze e confirmation sono rimasti
`NOT_EVALUATED`. Nessuna ipotesi DDC è stata valutata.

`NO_MULTI_CHANNEL_CAPABILITY` non è autorizzato: cinque endpoint conservano
almeno un `QUALIFICATION_ERROR`. Soltanto il rifiuto osservato in un ramo o in
una coppia specifica è descrivibile; non può essere esteso alla capability
hardware generale.

## Materializzazione dell'envelope

- candidati: 6, nell'ordine congelato;
- tentativi dual-SND: 6;
- receipt atomici di ramo: 12;
- retry pre-freeze: 0;
- retry post-freeze: 0;
- rami `CAPABILITY_REJECTED`: 4;
- rami `QUALIFICATION_ERROR`: 8;
- rami `READY`: 0;
- plan freeze: 0;
- confirmation A1/B/A2: 0.

I close osservati hanno tipo `_ObservedWebSocketClose`, che non appartiene alla
allowlist di errori software/trasporto retryable congelata. Non è stato quindi
consumato alcun retry. Non è stato aggiunto un retry esterno.

## Receipt per candidato

| Endpoint | Reference | Perturbed | Stato fase |
|---|---|---|---|
| `dl1bajkiwisdr.ddns.net:8074` | channel 1, `mod_iq`, close 1005 prima della readiness | channel 0, `mod_iq`, close 1005 prima della readiness | `QUALIFICATION_ERROR` |
| `g0ghk.uk:8050` | `BADP_REJECTION_OBSERVED` code 1 | `BADP_REJECTION_OBSERVED` code 1 | `UNSATISFIED` |
| `hill.n8ga.org:8073` | channel 5, `mod_iq`, close 1005 prima della readiness | channel 4, `mod_iq`, close 1005 prima della readiness | `QUALIFICATION_ERROR` |
| `kiwisdr2blair.ddns.net:8073` | channel 0, `mod_iq`, close 1005 prima della readiness | `BADP_REJECTION_OBSERVED` code 5 | `QUALIFICATION_ERROR` |
| `kiwisdr.kfsdr.com:8074` | channel 1, `mod_iq`, close 1005 prima della readiness | `BADP_REJECTION_OBSERVED` code 5 | `QUALIFICATION_ERROR` |
| `va6ok.ddns.net:8073` | channel 0, `mod_iq`, close 1005 prima della readiness | channel 1, `mod_iq`, close 1005 prima della readiness | `QUALIFICATION_ERROR` |

Gli otto rami chiusi avevano osservato sample rate, channel allocation,
`BADP_OK` e local send di `mod_iq`. Il receipt conserva frame count, byte count,
hash incrementale e transcript allowlisted. Non conserva però i frame, e non
produce un evento IQ finché un blocco non supera il predicate GNSS/readiness.

È quindi autorizzato dire “nessun witness IQ qualificante”. Non è autorizzato
dire “nessun byte SND”, “nessun campione ricevuto” o “il server ha rifiutato il
tuning”. Il close code 1005 è un'osservazione del wire receipt; non ne viene
inferita la causa.

## Disponibilità della misura e supporto dell'ipotesi

Il risultato mantiene separati i due livelli:

- control evidence disponibile: auth locale, allowlisted server fields,
  allocation, rate, send di configurazione, rejection o close;
- measurement evidence disponibile: nessuna measurement root ammessa;
- supporto per `H_UPSTREAM_OF_CHANNEL_DDC`: `NOT_EVALUATED`;
- supporto per `H_DOWNSTREAM_CHANNEL_FIXED`: `NOT_EVALUATED`.

La quantità di frame hashati non può sostituire la readiness temporale. Allo
stesso modo, due channel ID distinti non bastano a provare due stream IQ
utilizzabili.

## Clausole downstream

| Fase | Stato |
|---|---|
| direct dual-SND qualification | 6 valutate: 1 `UNSATISFIED`, 5 `QUALIFICATION_ERROR` |
| local IQ feature discovery | 6 `NOT_EVALUATED` |
| per-channel retune qualification | 6 `NOT_EVALUATED` |
| plan freeze | 6 `NOT_EVALUATED` |
| one confirmation | 6 `NOT_EVALUATED` |

Le 24 clausole downstream bloccate sono materializzate nel receipt. Nessun
errore descrittivo è stato promosso a decisione fisica.

## Artifact receipt verificato

File congelato:

`session_receipts/gate-f2-5-10-20260817T093414.925168Z.jsonl`

- righe totali: 46;
- righe evento prima del manifest: 45;
- byte totali: 241467;
- byte evento prima del manifest: 240876;
- SHA-256 del prefisso:
  `58a3835a75b7c07faf39dbf7d41d126b43b425fe30bdeb362a6a7a6fb9dd6911`;
- SHA-256 dell'intero artifact:
  `cb8e63dd0dfcf8affebf98bc63cf9fbae640f426383a9badb2670a33632b1f1d`;
- prefix hash ricomputato: corrispondente;
- terminal manifest: ultima riga;
- retention: `COMPLETE`;
- error count del sink: 0;
- strict JSON non standard trovato: 0;
- campi RF vietati trovati: 0;
- persistenza RF: `ZERO`.

L'output dell'interfaccia è stato troncato, ma il JSONL completo ha conservato
tutti i 45 eventi e il manifest. Il primo evento contiene envelope, hash e
authority surface; l'ultimo chiude crittograficamente il prefisso.

## Claim autorizzati

- L'unica sessione autorizzata ha materializzato l'envelope congelato.
- Tutti i sei candidati hanno ricevuto due tentativi di ramo simultanei.
- Quattro rami hanno restituito un rifiuto `badp` esplicito in quel tentativo.
- Otto rami hanno raggiunto allocation e local `mod_iq`, poi un close osservato
  prima di una readiness IQ qualificante.
- Nessun retry è stato applicato.
- La qualification è terminata senza measurement root e senza plan freeze.
- L'artifact receipt è completo, strict JSON e privo di RF persistita.

## Claim non autorizzati

- I server chiusi hanno accettato o rifiutato remotamente il tuning.
- Il close 1005 ha una causa specifica o comune.
- Nessuno dei server possiede due channel capability.
- Un nuovo client, centro, timeout o retry produrrebbe readiness.
- Una feature RF era presente o assente.
- Una feature è upstream o downstream del DDC.
- La RF è esterna, identificata o localizzata.

## SHOCK

La distinzione più importante non è più “uno o due hardware root”, ma
“allocazione di due branch” contro “due measurement root utilizzabili”. Cinque
endpoint hanno mostrato almeno una vera channel allocation e tre hanno mostrato
due channel ID distinti nello stesso tentativo, ma nessuno ha attraversato il
predicate di readiness. L'allocazione multicanale è quindi un affordance di
controllo, non ancora una capability di misura.

Il prossimo lavoro, se autorizzato, deve essere esclusivamente offline: capire
che cosa i transcript e il predicate possono attribuire ai close prima della
readiness. Questo outcome non autorizza un rerun.
