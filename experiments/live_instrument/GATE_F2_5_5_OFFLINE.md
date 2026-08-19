# Gate F2.5.5 — base sorgente e receipt control-plane

Stato: **CONCLUSO OFFLINE, FAIL-CLOSED**.

Questo gate parte dall'exit F2.5.4
`STOP_PENDING_CONTROL_DISCRIMINATORS`. Non apre connessioni, non acquisisce IQ,
non modifica il runtime live e non autorizza una nuova sessione. Separa due
obblighi che prima erano impliciti:

1. una base ufficiale riproducibile per attribuire significato ai messaggi;
2. un receipt ordinato per sapere quale evento sia realmente avvenuto.

Uno non sostituisce l'altro.

## Outcome

```text
SOURCE_BASIS_INCOMPLETE
```

Il contratto del receipt è completo, ma la base sorgente non è riproducibile
dal repository corrente. L'implementazione e l'esecuzione live restano entrambe
non autorizzate.

## Base ufficiale richiesta

I commit congelati restano:

- Kiwi server `c40ecb471dced33689e335689f8ffd35a54f47fa`;
- kiwiclient `4eb733e6b6147f7fbeb97ced64cdac029b202d18`.

Per il server sono noti quattro punti già citati dall'audit F2.3:

- `rx/rx_sound_cmd.cpp:67-79`;
- `rx/rx_sound_cmd.cpp:151-175`;
- `rx/rx_sound.cpp:568-596`;
- `rx/rx_sound.cpp:1082-1136`.

Nessuno dei relativi artifact sorgente è conservato localmente con path e
SHA-256. Per kiwiclient il commit è noto, ma il file/simbolo esatto che definisce
auth, ordine MSG e control-state non era stato congelato. Il gate lo registra
come `UNRESOLVED`, senza inventare un path.

Un hash senza artifact locale non soddisfa la clausola: permetterebbe di
riconoscere un file futuro, ma non di rieseguire ora l'audit offline.

## Contratto minimo del receipt

Ogni ramo `reference` o `perturbed` deve produrre una sequenza contigua con
ordinal e tempo monotono. Gli eventi ammessi sono soltanto:

```text
WEBSOCKET_OPENED
AUTH_COMMAND_RESULT
CONFIG_COMMAND_RESULT
SERVER_FIELD_OBSERVED
IQ_FRAME_OBSERVED
WEBSOCKET_CLOSE_OBSERVED
TCP_LOSS_OBSERVED
```

Le separazioni causali preservate sono:

- risultato locale dell'auth versus campo osservato dal server;
- risultato locale della configurazione versus primo IQ remoto;
- campi MSG allowlisted e ordinati versus mapping aggregato;
- close frame WebSocket versus errore TCP/libreria;
- reference versus perturbed;
- tempo monotono di controllo versus futuro event time RF.

`AUTH_COMMAND_RESULT` conserva soltanto `auth_redacted`, digest canonico e
`SUCCEEDED`/`FAILED`. Le altre classi di comando sono allowlisted. Password,
comando raw e MSG raw non entrano nel receipt.

I soli campi server ammessi sono rappresentazioni minimali:

- `badp`: `ZERO` oppure `NONZERO`;
- `too_busy`: sola presenza;
- `audio_rate`, `sample_rate`, slot/user limit: numero positivo finito;
- channel identifier: sola presenza, non testo raw.

La loro registrazione non assegna ancora semantica di conformità. In
particolare, `badp=0` non viene promosso automaticamente ad auth acknowledgment:
questa relazione deve provenire dalla base ufficiale riproducibile.

## Invarianti di ordine

- il WebSocket open è il primo evento;
- segue esattamente un risultato auth redatto;
- configurazione di canale richiede un precedente `sample_rate` osservato;
- un IQ witness richiede un precedente `mod_iq` riuscito;
- close frame e perdita TCP sono terminali distinti;
- nessun evento segue la terminazione;
- una stessa trace non può dichiarare insieme refusal e IQ readiness;
- ordinal, ruolo e tempo monotono non possono cambiare retroattivamente.

Queste invarianti rendono finalmente rappresentabile il caso osservato in
F2.5.3.1: configurazione locale prima di un successivo `badp`, senza trasformare
la prima nell'accettazione remota della seconda.

## Persistenza vietata

Il contratto rifiuta:

- password;
- MSG e comandi raw;
- RF e IQ samples;
- waterfall.

Può conservare soltanto classi allowlisted, numeri finiti, error type e hash
degli artifact effimeri. Non aggiunge database o storage RF.

## Semantiche offline

- `SOURCE_BASIS_INCOMPLETE`: manca almeno un artifact/path ufficiale;
- `CONTROL_RECEIPT_SPEC_INCOMPLETE`: la sorgente è riproducibile ma il receipt
  non chiude i tagli causali minimi;
- `CONTROL_SPEC_READY_FOR_IMPLEMENTATION_REVIEW`: entrambi sono completi, ma
  serve comunque una nuova revisione prima di modificare il runtime.

Nessuno di questi stati autorizza rete o acquisizione.

Una trace futura potrà descrivere soltanto:

- `IQ_READY_OBSERVED`;
- `SERVER_REFUSAL_SIGNAL_OBSERVED`;
- `WEBSOCKET_CLOSED_WITHOUT_IQ`;
- `TRANSPORT_LOST_WITHOUT_IQ`;
- `CONTROL_INCOMPLETE`.

Sono osservazioni del controllo, non outcome DDC e non assenza RF.

## Claim autorizzati

- Il receipt proposto conserva i discriminatori mancanti di F2.5.4.
- La base sorgente ufficiale corrente non è riproducibile offline.
- `configuration_sent` può essere sostituito da risultati ordinati, senza
  alterare il significato dell'outcome congelato.

## Claim non autorizzati

- Il client locale è conforme o non conforme.
- `badp=0` è sufficiente a provare auth acceptance.
- Una nuova sessione è autorizzata.
- Una futura trace di controllo prova una feature RF o una posizione rispetto
  al DDC.

## Prossimo confine, non eseguito

Una fase separata e autorizzata dovrebbe ottenere gli esatti sorgenti ufficiali
ai commit congelati, trattenere solo i file necessari con path, byte count,
licenza e SHA-256, risolvere il path kiwiclient, quindi rieseguire l'audit
interamente offline. Solo dopo potrà essere revisionata l'integrazione del
receipt nel client. Nessun endpoint o campione RF serve a quel passaggio.

## SHOCK

La semantica del protocollo è parte della capability. Un endpoint vivo e un
socket aperto non bastano; persino un campo ricevuto è ambiguo se il legame tra
wire value e significato non è riproducibile. Il taglio causale più urgente è
quindi ancora prima dell'antenna: tra ciò che il client invia, ciò che il server
osservabilmente risponde e ciò che il nostro codice decide che quella risposta
significhi.
