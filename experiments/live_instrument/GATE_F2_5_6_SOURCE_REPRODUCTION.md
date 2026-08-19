# Gate F2.5.6 — riproduzione della base sorgente

Stato: **CONCLUSO, FAIL-CLOSED**.

```text
SOURCE_RETENTION_BLOCKED_BY_LICENSE
```

Questa fase ha effettuato una sola attività di rete autorizzata: recuperare da
GitHub i due repository ufficiali ai commit già congelati. Non ha contattato
alcun endpoint KiwiSDR, non ha acquisito RF o IQ e non ha modificato il runtime.

Commit verificati:

- KiwiSDR server: `c40ecb471dced33689e335689f8ffd35a54f47fa`;
- kiwiclient: `4eb733e6b6147f7fbeb97ced64cdac029b202d18`.

Il [manifest](protocol_sources/gate_f2_5_6/manifest.json) conserva repository,
commit, blob ID, byte count, SHA-256, intervalli rilevanti, stato di licenza e
decisione di retention. Il verificatore offline è
[`kiwi_gate_f2_5_6.py`](kiwi_gate_f2_5_6.py).

## Retention

Il server è conservato nel solo artifact necessario:

```text
protocol_sources/gate_f2_5_6/
  manifest.json
  kiwisdr-c40ecb471dced33689e335689f8ffd35a54f47fa.zip
```

SHA-256 dell'archive:

```text
d6a50adfce7f75133020de85635711dc6c2218e6f134d901ac13a450b57de7ea
```

Contiene `_LICENSE` e cinque file `rx/`. Tutti i file sorgente selezionati
portano un notice GNU Library GPL versione 2 o successiva. Il test verifica
hash e dimensione dell'archive, membership esatta e hash, byte count e line
count di ogni membro.

Il sorgente kiwiclient non è stato copiato. Al commit congelato non sono stati
trovati un file di licenza root, metadati licenza GitHub o notice nei file
selezionati. Questa constatazione non dimostra che nessun diritto possa
esistere altrove: significa soltanto che questo gate non dispone di una
concessione sufficiente per conservare il testo nella repository. Restano
soltanto provenienza e impronte dei file ispezionati:

- `kiwi/client.py`, blob `136babae…`, SHA-256 `96ca913c…`;
- `kiwi/worker.py`, blob `917d20aa…`, SHA-256 `77fe0518…`;
- `README.md`, blob `a8697316…`, SHA-256 `dfb9bea8…`.

Il risultato non viene promosso a `SOURCE_BASIS_REPRODUCIBLE`: un path e un
hash risolvono l'identità, ma non sostituiscono un artifact locale lecitamente
conservabile.

## Audit del server

| Taglio | Sorgente congelata | Conseguenza stretta |
|---|---|---|
| Auth prima dei comandi | `rx/rx_cmd.cpp:213-225`, `772-820` | Prima dell'auth sono ammessi soltanto keepalive, options e auth; un altro comando imposta `kick`. |
| Semantica `badp` | `rx/rx_cmd.h:31-44`, `rx/rx_cmd.cpp:704-791` | `badp=0` è `BADP_OK`; `badp=5` è `BADP_NO_MULTIPLE_CONNS` e può terminare la connessione. |
| Allocazione SND | `rx/rx_server.cpp:603-612`, `646-785` | Una nuova SND ottiene un `rx_channel` libero oppure una risposta di capacità, fra cui `too_busy`. |
| Retune per canale | `rx/rx_sound_cmd.cpp:73-85`, `116-178` | `SET mod … freq=…` usa `conn->rx_channel` nel comando di frequenza; il taglio DDC per-canale esiste nel server congelato. |
| Setup e IQ | `rx/rx_sound.cpp:154-162`, `214-245`, `564-600`, `1082-1136` | Il ramo espone rate, sequenza, tempo GNSS e IQ; questi witness restano distinti dall'auth. |
| Identità canale | `rx/rx_cmd.cpp:772-785` | Il canale è inviato nella forma `is_local=channel,is_local,tlimit_exempt`, non nei nomi generici cercati dal receipt congelato. |

La condivisione di antenna, front-end, ADC e clock resta consentita per la
domanda DDC. Il server conferma che le connessioni SND indipendenti ricevono
rami `rx_channel` distinti e che il retune è indirizzato al ramo. Non conferma
che una particolare sessione abbia raggiunto quel punto.

## Audit del client senza retention

Il path prima irrisolto è ora localizzato:

- auth e invio comandi: `kiwi/client.py:187-203`;
- tuning/configurazione: `kiwi/client.py:313-371`;
- parsing ordinato dei campi MSG e mapping errori: `434-527`, `585-592`;
- sequence, IQ e GNSS: `594-718`;
- apertura/auth e terminazione: `887-925`;
- concorrenza e retry: `kiwi/worker.py:14-100`.

Il client ufficiale elabora le coppie MSG in ordine, tratta `too_busy` e i
valori `badp` non-zero come errori tipizzati, reagisce a `sample_rate`
inviando la configurazione e distingue terminazione pulita da terminazione
inaspettata. Il mancato testo locale impedisce di rieseguire integralmente
questo lato dell'audit senza una nuova acquisizione del repository.

## Effetto sull'outcome congelato

L'audit F2.5.4 non viene riscritto.

- Le quattro rejection già esplicite restano rejection.
- Il timeout prima di qualsiasi MSG resta un timeout di trasporto.
- Le undici chiusure post-configurazione restano
  `NOT_DIAGNOSABLE_WITH_CURRENT_RECEIPT`.

Ora è autorizzato interpretare un `badp=0` **ordinato e realmente ricevuto**
come successo auth del server congelato. Non è autorizzato usarlo come prova di
configurazione accettata, canale distinto, IQ pronto o retune valido. Il vecchio
campo aggregato `configuration_sent=true` descrive ancora soltanto un'azione
locale.

La sorgente ha inoltre esposto due discriminatori mancanti nel receipt
congelato:

1. l'identificatore di canale è incluso nel campo `is_local`, non nei nomi
   generici precedentemente cercati;
2. close WebSocket pulito e perdita inaspettata devono restare eventi distinti.

Questi risultati spiegano cosa un futuro receipt dovrebbe poter descrivere;
non autorizzano ancora la sua implementazione.

## Claim autorizzati

- L'archive server è riproducibile byte per byte e include i notice dei file.
- I path esatti del control-state kiwiclient sono risolti e hash-auditati.
- Nel server congelato `badp=0`, `badp=5`, `too_busy`, allocazione del canale e
  retune per-canale hanno la semantica stretta descritta sopra.
- La base completa non è riproducibile localmente a causa del confine di
  retention del client.

## Claim non autorizzati

- Una causa unica per le undici chiusure congelate.
- Conformità o non conformità del client locale.
- Accettazione della configurazione dedotta dal solo invio locale.
- IQ readiness, multicanalità o outcome DDC.
- Implementazione del receipt F2.5.5 o una nuova esecuzione live.

## Verifica e distruzione

I test sono esclusivamente offline e rifiutano:

- modifica dell'archive o della sua membership;
- hash, byte count o line count incoerenti;
- JSON non finito o con chiavi duplicate;
- assenza dell'artifact;
- promozione a implementazione o live execution.

Dopo la generazione e la verifica dell'archive server, i due clone temporanei
devono essere distrutti. Nessun RF, waterfall, IQ, credential o sorgente client
entra nella repository.

## SHOCK

Il limite non è più soltanto tecnico. L'analisi può risolvere la semantica da
un checkout effimero, ma la riproducibilità futura dipende anche dal diritto di
conservare ciò che rende l'analisi verificabile. “Conosciamo il path e l'hash”
e “possiamo riprodurre offline l'audit” sono clausole diverse.
