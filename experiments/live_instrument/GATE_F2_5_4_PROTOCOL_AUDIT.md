# Gate F2.5.4 — audit offline del confine di controllo SND

Stato: **CONCLUSO OFFLINE**.

Questo gate analizza soltanto il codice e l'artifact congelato dell'outcome
F2.5.3.1. Non ha aperto socket, non ha interrogato endpoint, non ha acquisito
IQ e non ha modificato il runtime live, i candidati, le frequenze, le soglie o
la domanda DDC.

## Evidenza vincolante

- runtime dell'outcome: `aec6da247aa6edb3e180aa848cc05aa2d7f49e2b`;
- commit dell'outcome: `6776c19b97246822217f91612959c3a49174876e`;
- artifact JSONL: `session_receipts/gate-f2-5-3-1-20260816T204247.641290Z.jsonl`;
- SHA-256 verificato:
  `be4b10781928eb01a464175c9674681facca4aa30c6541a5e8ba8278ecd78ca5`;
- receipt atomici di ramo: 16, su sei endpoint;
- frame IQ: 0.

Il nuovo codice di audit riceve mapping JSON già decodificati. Non legge file
e non possiede alcuna superficie di rete.

## Failure attribution

| Receipt | Numero | Fatto osservato | Attribuzione massima |
|---|---:|---|---|
| `BranchCapabilityRejected` dopo configurazione locale | 4 | WebSocket aperto, MSG e sample rate ricevuti, comandi inviati, rifiuto esplicito | `SERVER_REPORTED_CAPABILITY_REJECTION` per quel ramo e tentativo |
| `WebSocketTimeoutException` prima di MSG | 1 | WebSocket aperto, nessun MSG, nessuna configurazione, nessun IQ | `TRANSPORT_TIMEOUT_BEFORE_HANDSHAKE` |
| `WebSocketConnectionClosedException` dopo configurazione locale | 11 | sample rate negoziato, comandi inviati, nessun IQ, connessione persa | `NOT_DIAGNOSABLE_WITH_CURRENT_RECEIPT` |

Quindici rami hanno `configuration_sent=true`. Questo è un fatto sul client,
non un acknowledgment remoto. Lo dimostrano direttamente i quattro receipt in
cui un rifiuto esplicito coesiste con `configuration_sent=true`: l'ordine dei
MSG non è conservato e la configurazione può essere inviata prima che un MSG
successivo renda visibile `badp`.

Le undici chiusure non vengono rinominate “chiusura dopo setup valido”. Il
receipt non permette di distinguere:

- policy o limite concorrente del server;
- sequenza client non accettata;
- close frame WebSocket;
- perdita TCP o altro failure di trasporto.

Non esiste evidenza per scegliere una di queste cause.

## Audit del protocol surface locale

La sequenza post-`sample_rate` usata dal percorso dual-SND ha le stesse otto
classi di comando del precedente percorso locale SND a canale singolo:

```text
squelch -> genattn -> gen -> ident_user -> mod -> agc -> compression -> keepalive
```

Questo autorizza soltanto:

`CONSISTENT_WITH_PRIOR_LOCAL_SINGLE_CHANNEL_PATH_NOT_OFFICIALLY_REPRODUCIBLE_FROM_THIS_REPOSITORY`

Le revisioni ufficiali già citate dagli audit precedenti sono:

- Kiwi server `c40ecb471dced33689e335689f8ffd35a54f47fa`;
- kiwiclient `4eb733e6b6147f7fbeb97ced64cdac029b202d18`.

Quegli oggetti sorgente non sono presenti nel repository corrente e i commit
non sono oggetti Git locali. Perciò F2.5.4 non converte il precedente audit
documentale in una nuova prova riproducibile di conformità. Non è dimostrato
né che il client sia conforme né che sia non conforme.

## Discriminatori mancanti

Un futuro receipt di controllo, prima di qualsiasi nuova domanda fisica,
dovrebbe conservare soltanto metadata allowlisted e hashati:

1. outcome auth esplicito e ordinato, distinto dall'invio locale di `SET auth`;
2. chiavi MSG allowlisted e transizioni di stato, con ordine;
3. tipo/hash dei comandi, tempo d'invio e risultato locale;
4. close code/reason WebSocket distinto dalla perdita TCP;
5. timestamp monotoni per gli stadi;
6. limiti slot/user riportati nello stesso handshake, quando presenti.

Non servono body MSG completi, credenziali, RF, waterfall, IQ o campioni.

## Root causali

I sei endpoint sono root remote distinte, ma tutti i sedici rami attraversano
la stessa implementazione locale
`kiwi_gate_f2_5_2._atomic_open_channel` e la stessa libreria WebSocket. Quindi
la ripetizione su sei endpoint non costituisce sei conferme indipendenti
contro l'ipotesi di un failure del client. Allo stesso modo, non prova che il
client sia la causa: espone soltanto una root condivisa non tagliata.

## Outcome ed exit rule

L'outcome F2.5.3.1 resta immutato:

```text
QUALIFICATION_INCOMPLETE
```

L'esito dell'audit è:

```text
STOP_PENDING_CONTROL_DISCRIMINATORS
```

Le semantiche offline sono:

- `PHYSICAL_EXPERIMENT_MAY_PROCEED` soltanto con reference e perturbed entrambi
  `READY` sullo stesso endpoint;
- `NO_CAPABILITY_ADMITTED` soltanto se ogni ramo tentato termina con un
  rifiuto esplicito, senza errori descrittivi o di trasporto residui;
- `CLIENT_CORRECTION_REQUIRED` soltanto dopo una non conformità dimostrata,
  mai dedotta dalle chiusure correnti;
- altrimenti `STOP_PENDING_CONTROL_DISCRIMINATORS`.

## Claim autorizzati

- Quattro rami hanno ricevuto un rifiuto esplicito in quella sessione.
- Un ramo ha aperto il WebSocket senza ricevere un MSG prima del timeout.
- Undici rami hanno inviato localmente la configurazione senza produrre IQ e
  sono non diagnosticabili con il receipt corrente.
- “Configurazione inviata” e “configurazione accettata” sono eventi distinti.
- Tutti i failure condividono una root client; le cause remote restano aperte.
- Nessuna clausola fisica DDC è entrata in valutazione.

## Claim non autorizzati

- Il client è conforme o non conforme al server ufficiale congelato.
- Le undici chiusure sono rifiuti di policy, errori di protocollo o perdita di
  rete: il receipt non distingue queste alternative.
- I sei endpoint non supportano due SND simultanei.
- Un setup remoto valido è stato completato.
- Una feature RF era assente.
- Una delle ipotesi DDC ha ricevuto supporto.

## Decisione

Non si aggiungono endpoint e non si ripete la sessione. Prima di una futura
attività live servono una base ufficiale riproducibile e un receipt capace di
tagliare il failure di controllo senza conservare RF. F2.5.4 si ferma qui: non
implementa quel nuovo probe e non riapre l'esperimento fisico.

## SHOCK

L'artifact è sufficientemente forte da impedire una falsa inferenza fisica,
ma non abbastanza ricco da attribuire il proprio failure di controllo. La
moltiplicazione degli endpoint non sostituisce un discriminatore sul ramo
client condiviso. Il prossimo incremento utile, se autorizzato, non è “più
radio”: è rendere osservabile l'accettazione del protocollo.
