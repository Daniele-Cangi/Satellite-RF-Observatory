# Gate F2.5.7 — necessità del client e contratto wire server

Stato: **CONCLUSO OFFLINE**.

```text
SERVER_WIRE_CONTRACT_SUFFICIENT
```

Questo gate non apre socket, non acquisisce IQ, non modifica il runtime live e
non rilegge gli outcome congelati. Parte dall'esito F2.5.6
`SOURCE_RETENTION_BLOCKED_BY_LICENSE` e pone una domanda più stretta:

> Il sorgente ufficiale kiwiclient deve essere una root epistemica della prova
> DDC, oppure il significato server-side e un receipt wire osservabile sono
> sufficienti?

La risposta è: il client ufficiale è un riferimento implementativo utile, ma
non è necessario per sostenere i claim fisici ammessi da Gate F2.

## Perché la sorgente client non è necessaria

Il ponte causale minimo usa tre tipi di fatto indipendenti:

1. **semantica server**, riproducibile dall'archive F2.5.6;
2. **azioni locali osservate**, registrate dopo il ritorno dell'operazione di
   invio e mai rinominate “accettazione remota”;
3. **conseguenze remote**, in particolare un frame IQ hashato e sequenziato
   ricevuto dopo l'azione locale.

Conservare kiwiclient non renderebbe osservabile un ACK di configurazione che
il protocollo non emette. Potrebbe mostrare come un altro client si comporta,
ma non provare che il server abbia applicato il comando in una specifica
sessione. Quella transizione può essere sostenuta soltanto dal comportamento
successivo dell'IQ e, nel futuro esperimento DDC, dal witness di retune.

La licenza mancante resta un limite reale alla riproduzione del reference
client, ma non blocca più il receipt necessario alla domanda fisica.

## Bridge claim → witness

| Claim stretto | Radice server | Witness del receipt | Serve kiwiclient? |
|---|---|---|---|
| Sessione aperta e auth accettata/rifiutata | `AUTH_GATE_ORDER`, `BADP_SEMANTICS` | open, auth redatta, `badp=0` oppure `badp!=0`/`too_busy` | No |
| Canale SND allocato | `CHANNEL_ALLOCATION`, `CHANNEL_IDENTIFIER_GAP` | `is_local=channel,is_local,tlimit_exempt` ridotto al numero del canale | No |
| Comando IQ indirizzato al ramo | `PER_CHANNEL_RETUNE` | rate osservati e ritorno locale di `mod_iq` sul ramo | No |
| Ramo configurato che produce dati | `SND_SETUP_AND_IQ` | primo SND/IQ successivo, hash prima del decode, sequence e futuro tempo GNSS | No |
| Terminazione descritta | API di trasporto locale | close frame/code/reason hashato oppure errore di trasporto tipizzato | No |

Il massimo claim del terzo punto resta “invio locale riuscito”. Il quarto punto
aggiunge “un IQ successivo è arrivato”; non crea retroattivamente un generico
ACK server.

## Contratto wire minimo

Per ciascun ramo `reference` o `perturbed`:

```text
WEBSOCKET_OPENED
  -> AUTH_SENT_REDACTED
  -> remote prerequisites all observed:
       BADP_OK_OBSERVED
       CHANNEL_ALLOCATED_OBSERVED (from is_local)
       SAMPLE_RATE_OBSERVED
  -> MOD_IQ_SENT
  -> IQ_FRAME_OBSERVED (pre-decode hash + sequence)
```

`is_local` e `badp` conservano il loro ordine reale; il valutatore non impone
un ordine artificiale fra i prerequisiti, ma pretende che tutti precedano
`MOD_IQ_SENT`. `AUDIO_RATE_OBSERVED` è un witness di control health quando
presente, non un sostituto dell'IQ.

Le alternative negative sono eventi separati:

- `BADP_REJECTION_OBSERVED`;
- `TOO_BUSY_OBSERVED`;
- `WEBSOCKET_CLOSE_OBSERVED` con code e reason hash;
- `TRANSPORT_LOSS_OBSERVED` con error type.

Un field allowlisted malformato è un description/qualification error. Non può
diventare `CAPABILITY_REJECTED`.

## Transcript sintetici

[`kiwi_gate_f2_5_7.py`](kiwi_gate_f2_5_7.py) implementa soltanto un modello
offline gate-specifico. Non importa il runtime Kiwi e non contiene networking.

I test dimostrano che:

- due transcript completi con channel number distinti producono
  `DUAL_WIRE_READY`;
- lo stesso channel number produce `ADMISSIBLE_TOPOLOGY_MISSING`;
- `mod_iq` prima di auth/channel/rate produce `CONTROL_ORDER_INVALID`, anche
  se un IQ compare più tardi;
- un IQ precedente a `mod_iq` non può testimoniare quel comando;
- `badp=5` resta un rifiuto server esplicito;
- close pulito e perdita di trasporto restano distinguibili;
- valori unknown o raw non entrano nel receipt;
- NaN, infiniti, campioni, waterfall, password e comandi raw non hanno una
  superficie serializzabile.

## Gap del runtime corrente

Il runtime F2.5.2 congelato:

- aggrega i MSG in un mapping, perdendo l'ordine fra risposte;
- invia la configurazione appena vede `sample_rate`;
- non attende esplicitamente `badp=0` e `is_local` prima di `mod_iq`;
- cerca `rx_chan`, `chan` o `channel`, mentre il server congelato espone il
  numero dentro `is_local`;
- non conserva close frame e perdita TCP come eventi distinti.

Questa constatazione non dichiara il runtime conforme o non conforme e non
attribuisce le undici chiusure storiche. Definisce soltanto cosa dovrà cambiare
in un gate di implementazione separato.

## Outcome offline

- `SERVER_WIRE_CONTRACT_SUFFICIENT`: archive server valido, ogni claim ha i
  propri witness e nessun claim richiede il reference client;
- `CLIENT_SOURCE_REQUIRED`: almeno un claim indispensabile dipende davvero
  dal testo client non conservabile;
- `PROTOCOL_WITNESS_INCOMPLETE`: sorgente server o discriminatori wire
  insufficienti.

L'esito corrente autorizza **soltanto** la futura implementazione offline del
receipt ordinato. Non autorizza rete, acquisizione, retry o una nuova finestra.

## Claim autorizzati

- Il contratto wire server è sufficiente per implementare un receipt locale
  ordinato senza copiare kiwiclient.
- Il reference client non è una root fisica necessaria alla prova DDC.
- Auth, channel identity, sample rate, invio locale di `mod_iq` e IQ successivo
  devono restare witness distinti.
- Un gate successivo può integrare e testare offline questi receipt.

## Claim non autorizzati

- Il runtime live corrente implementa già il contratto.
- Il server ACKa o accetta un comando di configurazione.
- L'invio locale prova che il retune sia stato eseguito.
- Le undici chiusure congelate condividono una causa specifica.
- Una nuova connessione Kiwi o acquisizione RF è autorizzata.

## Prossimo confine

Il prossimo gate, se approvato, potrà modificare soltanto il percorso locale di
receipt per:

1. preservare le coppie MSG allowlisted nell'ordine di arrivo;
2. estrarre il channel number da `is_local`;
3. attendere `badp=0`, channel e sample rate prima di inviare `mod_iq`;
4. hashare il primo IQ successivo;
5. distinguere close frame e transport loss;
6. dimostrare tutto con transcript sintetici e zero rete.

Solo dopo un nuovo review checkpoint potrà essere chiesta l'autorizzazione a
una singola sessione live.

### Nota di implementazione F2.5.8

L'integrazione successiva ha reso espliciti anche
`LOCAL_SEND_ERROR_OBSERVED` e `CONTROL_TIMEOUT_OBSERVED`. Sono terminali
descrittivi distinti da close frame e perdita TCP. Non cambiano la decisione
sulla sufficienza della sorgente server; completano il receipt quando il
controllo fallisce prima di un IQ.

## SHOCK

La conformità a un reference client e la falsificabilità dell'esperimento non
sono la stessa proprietà. Per questa domanda conta che il receipt colleghi
azioni locali a conseguenze remote secondo la semantica del server. Aggiungere
un'altra implementazione client come autorità avrebbe introdotto una root
epistemica non necessaria senza creare il witness che manca davvero.
