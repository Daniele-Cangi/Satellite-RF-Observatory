# Gate F2.5.2 — primo e unico outcome live

Stato: **STOP**. È stata eseguita una sola sessione dal runtime congelato nel
commit `64a717b8dcd13ec0c09cd7b87388986bdb2ffbb3`. Non verranno aperte altre
connessioni o finestre per questo outcome.

## Outcome terminale

`QUALIFICATION_INCOMPLETE`

Nessuna coppia SND simultanea è stata ammessa. Feature discovery, retune,
plan freeze, confirmation e ipotesi sul boundary DDC sono rimasti
`NOT_EVALUATED`.

Il risultato non è però una ripetizione di F2.5.1. I receipt atomici hanno
preservato almeno un'asimmetria reale che il runtime precedente avrebbe
cancellato:

```text
kiwisdr.kfsdr.com:8074
  reference = READY
  perturbed = CAPABILITY_REJECTED
  pair       = NOT ADMITTED
```

Il reference ha ricevuto due frame IQ, li ha hashati prima del decode e ha
prodotto un readiness witness GNSS-valido. Quando il peer è stato rifiutato,
il composer ha chiuso il reference ma ha conservato il suo receipt.

## Bootstrap congelato

- runtime commit: `64a717b8dcd13ec0c09cd7b87388986bdb2ffbb3`;
- start: `2026-08-16T19:26:28.160082Z`;
- ultimo receipt visibile: `2026-08-16T19:26:45.320138Z`;
- durata coperta: circa 17,16 s;
- bootstrap receipt hash:
  `60125375a6dddb4dc63150ac81b0b27969a8ff85d0f3ca1e7bdbd26a79c17717`;
- candidate-set hash:
  `b5a4b7e133f10bcf019481e62ceae6c168aa8fd55aecb3601575e7b581c663d7`;
- center policy: `kiwi-0-30mhz-interior-endpoint-hash-v2`;
- atomic branch receipts: richiesti;
- hashing SND pre-decode: richiesto;
- W/F: zero;
- persistenza RF: zero;
- `ext_api`: descrittivo e non-gating;
- retry budget dichiarato: due complessivi, massimo uno per endpoint;
- retry realmente emessi: zero.

## Receipt reference `READY`

Endpoint: `kiwisdr.kfsdr.com:8074`.

- role: `reference`;
- state: `READY`;
- pair disposition: `CLOSED_AFTER_PEER_FAILURE`;
- WebSocket aperto: sì;
- configurazione inviata: sì;
- sample rate: `11998.917796 Hz`;
- handshake messages: 22;
- handshake hash:
  `31f9a9abec7e61ee52f5c8030f420783cb41f62e68aa2cbb3c1e62e601720a7e`;
- channel ID: `snd-allocation:aeea94cb`;
- channel ID basis: token della distinta allocazione SND, non ID esplicito del
  server;
- IQ frame count: 2;
- raw bytes attraversati in RAM: 4136;
- stream artifact hash:
  `3ba0e9f591b8964dff5ebb728ce3c0d550c0c80c2169e74c880fa9e542ff288b`;
- readiness frame hash:
  `97c8bb2273f8ae16d4ade2ca8095272ab5457fd38e5076833d16b8b44154b1b8`;
- readiness event start: `2026-08-16T19:26:40.702228Z`;
- readiness event end: `2026-08-16T19:26:40.744899Z`;
- readiness sequence: 2;
- GPS solution age: `0 s`;
- branch receipt hash:
  `bd307b1db9d6e1d90110d822ca5a00a9c775a534b46576d077baf015ec463744`.

Il receipt autorizza “un'allocazione SND ha raggiunto IQ readiness in quel
momento”. Non autorizza “il server aveva due canali”, perché il peer non è
stato ammesso. Il channel ID fallback non prova inoltre un ID hardware o FPGA
esplicito.

## Receipt perturbed rifiutato

Per lo stesso endpoint:

- role: `perturbed`;
- state: `CAPABILITY_REJECTED`;
- error: `kfs-california rejected public SND access`;
- sample rate negoziato: `11998.917796 Hz`;
- IQ frame count: 0;
- handshake hash:
  `0503dcecb1343932ed16b1ebcc7ad868329ba9175c98b3fee13d5255fca50a3a`;
- error-description hash:
  `e67cc868900c217f649454d51eb8e2960e9af64f6392f569e30ecd15ed1adf4a`;
- branch receipt hash:
  `ab53568cb5f037eaa5b7a142556070ce5ae51d6d46a142050b308555fa6b43de`.

Questo è un rifiuto osservato per quel ramo e quel tentativo, non una
incapacità universale del server.

## Altri receipt preservati

I receipt visibili autorizzano inoltre:

| Endpoint | Reference | Perturbed | IQ readiness visibile |
|---|---|---|---|
| `dl1bajkiwisdr.ddns.net:8074` | `QUALIFICATION_ERROR` | `QUALIFICATION_ERROR` | nessuna nei due receipt |
| `g0ghk.uk:8050` | `CAPABILITY_REJECTED` | `CAPABILITY_REJECTED` | nessuna |
| `kiwisdr2blair.ddns.net:8073` | `CAPABILITY_REJECTED` | `QUALIFICATION_ERROR` | nessuna nei due receipt |
| `kiwisdr.kfsdr.com:8074` | `READY` | `CAPABILITY_REJECTED` | reference, due frame |
| `va6ok.ddns.net:8073` | `QUALIFICATION_ERROR` | `QUALIFICATION_ERROR` | nessuna nei due receipt |

Il runtime ha attraversato anche `hill.n8ga.org:8073`, ma la porzione centrale
del JSONL è stata troncata dal trasporto della console e non era stata
persistita in un artifact descrittivo. Questo documento non ricostruisce né
indovina i suoi due stati. La perdita è `RECEIPT_RETENTION_ERROR`, non un
risultato di capability.

## Failure attribution: retry policy

Il bootstrap dichiarava due retry pre-freeze. Nessuno è stato emesso.

La causa è nel ponte fra il nuovo receipt e il runner legacy:

1. i branch receipt classificano correttamente timeout/connessione chiusa come
   `QUALIFICATION_ERROR`;
2. il decoratore aggregato sostituisce lo statement con
   `atomic branch receipts leave pair availability indeterminate`;
3. `_retryable_phase()` non legge i branch receipt o `error_type`; cerca
   parole come `timeout`, `connection` e `closed` nello statement aggregato;
4. quelle parole non sono più presenti e il retry non viene selezionato.

Questo è un errore software nella trasformazione receipt → retry eligibility.
Non prova che un retry avrebbe ammesso una coppia e non autorizza un nuovo
tentativo dopo la sessione conclusa. Rende però il negativo meno utilizzabile:
il piano congelato non è stato materializzato integralmente.

## Failure attribution: retention descrittiva

Il runner ha emesso JSON Lines rigorosi su stdout, ma l'esecuzione non ha
conservato un artifact receipt-only della sessione. L'output ha superato la
dimensione resa disponibile dalla console e una parte è stata troncata.

La persistenza zero riguardava RF, IQ, waterfall e STFT; non richiedeva di
distruggere i receipt descrittivi. La mancata retention non modifica gli esiti
fisici già prodotti, ma impedisce l'audit completo di un candidato. Un futuro
runtime deve conservare in modo bounded il JSONL rigoroso e soltanto quello,
senza campioni o frame raw.

## Clausole valutate

- status/accesso dei candidati attraversati;
- tentativo atomico reference e perturbed;
- handshake e sample-rate negotiation per ciascun ramo;
- classificazione per ramo;
- hashing pre-decode degli eventuali frame SND;
- composizione della coppia dai due receipt;
- distinzione fra peer rifiutato e sibling pronto.

## Clausole non valutate

- due rami `READY` nello stesso intervallo;
- channel ID distinti ammessi alla coppia;
- continuità duale, overlap, clock e overflow;
- feature e witness targetless;
- retune per-canale;
- plan freeze e A1/B/A2;
- `H_UPSTREAM_OF_CHANNEL_DDC`;
- `H_DOWNSTREAM_CHANNEL_FIXED`.

## Claim autorizzati

- I receipt atomici hanno preservato un ramo `READY` che F2.5.1 avrebbe
  aggregato dentro un failure duale.
- Quel ramo ha ricevuto e hashato due frame IQ prima del decode e ha prodotto
  un readiness witness GNSS-valido.
- Il peer perturbed è stato esplicitamente rifiutato.
- Nessuna coppia è stata ammessa e nessuna ipotesi DDC è stata valutata.
- Nessun RF, IQ, waterfall, STFT o frame raw è stato persistito.
- Il retry budget congelato non è stato materializzato a causa di un errore
  software nel selector.

## Claim non autorizzati

- Il server KFS supporta o non supporta due canali in generale.
- Il ramo rifiutato era necessariamente “il secondo” in senso hardware.
- Il fallback allocation token identifica un canale FPGA esplicito.
- Il retry avrebbe prodotto una coppia.
- I candidati con errori di trasporto non possiedono multicanalità.
- Il candidato con receipt non trattenuti aveva uno stato particolare.
- È stata osservata una feature RF, una sorgente esterna o un comportamento
  upstream/downstream del DDC.

## SHOCK

La decomposizione atomica ha funzionato e ha cambiato il massimo claim: ora
sappiamo che “pair fallita” può contenere un sensore operativo e un peer
rifiutato. Ma ha anche mostrato che il controllo non può restare testuale. La
retry policy deve derivare dagli stati e dagli error type atomici, non dalla
prosa di un receipt aggregato.

Inoltre zero persistenza RF non significa zero persistenza epistemica: senza
un artifact JSONL bounded, receipt validi possono essere prodotti e poi persi
dal canale descrittivo.

Il prossimo cambiamento minimo deve essere offline: retry eligibility
strutturale e sink receipt-only completo. Non deve cambiare candidati, centri,
soglie, budget o domanda fisica e non autorizza un nuovo live run.

Gate F2.5.2 outcome 1 si ferma qui.
