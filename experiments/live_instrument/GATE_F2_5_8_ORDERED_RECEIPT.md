# Gate F2.5.8 — integrazione del receipt wire ordinato

Stato: **CONCLUSO OFFLINE**.

```text
ORDERED_WIRE_RECEIPT_IMPLEMENTED
```

Questo gate implementa il solo incremento autorizzato da F2.5.7. Non apre
connessioni reali, non acquisisce IQ, non cambia candidati, frequenze, soglie,
retry o domanda DDC. Il runtime e gli outcome storici restano identificabili
dai rispettivi commit.

Il nuovo percorso è un successore verticale in
[`kiwi_gate_f2_5_8.py`](kiwi_gate_f2_5_8.py), non una modifica retroattiva del
risultato F2.5.3.1 e non un adapter Kiwi generico.

## Sequenza implementata

Ogni ramo `reference` o `perturbed` esegue:

```text
WebSocket open
  -> auth send redatto
  -> MSG allowlisted preservati in ordine
  -> badp=0 + is_local channel + sample_rate tutti osservati
  -> comandi iniziali locali
  -> mod_iq send riuscito
  -> primo SND/IQ GNSS-valid hashato prima del decode
  -> WIRE_READY
```

La configurazione non parte più alla sola comparsa di `sample_rate`. Se manca
anche uno fra `badp=0`, channel number derivato da `is_local` e sample rate, il
comando `mod_iq` non viene inviato.

`audio_rate`, quando presente, produce il relativo `AR OK`; rimane un fatto di
control health e non sostituisce il primo IQ.

## Confine artifact/receipt

Ogni frame MSG, SND o close è hashato prima dell'analisi. Il receipt conserva:

- hash per-frame e hash incrementale length-delimited;
- byte e frame count;
- eventi wire allowlisted;
- hash canonici dei comandi locali;
- channel number, rate, sequence e metadati temporali della readiness;
- error type e hash descrittivo.

Non conserva:

- body MSG o close reason;
- password o auth raw;
- comandi raw;
- frame SND;
- campioni IQ;
- waterfall o STFT.

Il blocco IQ esiste soltanto in RAM durante il decode e viene eliminato dopo la
costruzione del witness. `raw_rf_persistence` resta `ZERO`.

## Failure semantics

La qualificazione distingue:

| Evento | Stato massimo |
|---|---|
| `badp!=0` o `too_busy` realmente osservato | `CAPABILITY_REJECTED` |
| field allowlisted malformato | `QUALIFICATION_ERROR` |
| errore locale durante `send` | `LOCAL_SEND_ERROR_OBSERVED` |
| scadenza o timeout di ricezione | `CONTROL_TIMEOUT_OBSERVED` |
| frame close con code e reason hash | `WEBSOCKET_CLOSE_OBSERVED` |
| perdita senza frame close | `TRANSPORT_LOSS_OBSERVED` |

Le ultime quattro classi sono alternative descrittive e ordinate. Nessuna
viene promossa a rifiuto epistemico in base al testo dell'eccezione.

L'implementazione ha quindi esteso il modello F2.5.7 con due terminali mancanti:
local send error e control timeout. Questa correzione non cambia l'esito
`SERVER_WIRE_CONTRACT_SUFFICIENT`; rende completo il confine descrittivo che
un'implementazione reale deve attraversare.

## Composizione duale

I due rami sono aperti contemporaneamente ma valutati atomicamente. La coppia
entra nella topologia soltanto se:

- entrambi sono `WIRE_READY`;
- entrambi hanno un vero channel number server;
- i channel number sono distinti.

Un sibling pronto viene chiuso senza cancellarne il receipt se l'altro fallisce.
Due receipt pronti con lo stesso channel number vengono entrambi chiusi come
`CLOSED_AFTER_TOPOLOGY_REJECTION`.

Questo autorizza soltanto la frase “due rami wire completi e distinti”. Non
autorizza ancora un outcome DDC.

## Test sintetici

I test offline verificano:

- prerequisiti remoti prima di `mod_iq`;
- channel identity dalla forma reale `is_local=channel,local,exempt`;
- hash SND eseguito prima del decode;
- `badp=5` e `too_busy` come rifiuti espliciti;
- NaN e field malformati come qualification error;
- local send error, timeout, close e transport loss distinti;
- distruzione dei valori MSG unknown dopo l'hash;
- due channel distinti ammessi e channel uguali rifiutati;
- strict JSON e assenza di superfici RF/credential;
- nessun I/O all'import, CLI o esecuzione automatica.

## Claim autorizzati

- Il successore locale implementa il receipt wire ordinato definito in F2.5.7.
- `mod_iq` viene inviato soltanto dopo auth, channel e rate osservati.
- Il primo IQ qualificante viene hashato prima del decode.
- Le quattro terminazioni descrittive restano separate.
- L'implementazione può essere sottoposta a review pre-live.

## Claim non autorizzati

- Il server ha ACKato un comando di configurazione.
- Il percorso è stato esercitato contro un endpoint reale.
- Esiste una capability dual-channel disponibile ora.
- Una feature, un witness o un piano A1/B/A2 sono stati prodotti.
- Una nuova sessione live è autorizzata da questo commit.

## Stop condition

Gate F2.5.8 si ferma dopo implementazione, test e commit. Il prossimo passaggio
deve essere un review offline del diff e della sua materializzazione nel runner
one-shot. Solo un'autorizzazione successiva e separata potrà aprire una singola
sessione.

## SHOCK

L'ordine causale non è soltanto metadata aggiuntivo. Cambia il comportamento:
aspettare il channel number e `badp=0` impedisce al client di inviare una
configurazione quando non possiede ancora le premesse per interpretarne un
fallimento. Il receipt corretto diventa quindi anche un guardrail operativo,
senza trasformarsi in un nuovo framework.
