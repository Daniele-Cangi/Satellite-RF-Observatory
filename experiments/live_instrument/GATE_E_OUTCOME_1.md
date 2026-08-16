# Gate E — primo outcome prospettico WWV/WWVH

Stato: **STOP dopo il primo outcome**. Nessun retry, nessuna seconda finestra,
nessuna persistenza dei campioni IQ.

## Piano madre

- hash: `c5cdbd60f1e585c84cad185ad926e36e28a46c8ea1ec66ca4f08f5a6ae5d2f5d`;
- frequenze candidate: 5, 10 e 15 MHz;
- CapabilityOffer TTL: 600 s;
- durata scout per candidato: 4.5 s;
- continuità minima richiesta: 3.0 s;
- marker station-specific: 1000 Hz per WWV, 1200 Hz per WWVH;
- finestra che sarebbe stata usata: minuto 28 come controllo positivo,
  minuti 29–30 come silenzio target, minuto 31 come recupero.

Il piano madre è stato emesso prima di qualsiasi scout. Non è stato prodotto
un piano definitivo: nessuna CapabilityOffer ha superato le precondizioni.

## Outcome

`FALSIFIABILITY_NOT_ENTERED`

Motivo registrato:

> no fresh capability offer closes a station-specific causal path through
> minute 31

Tutte le otto clausole Gate E sono `UNOBSERVABLE`. Non è stata aperta la
connessione continua prevista per i minuti 28–31 e non esiste alcun risultato
su `standard_tone_absent`.

Questo outcome non è `NOT_DETECTED` e non è `NOT_DETECTABLE`: l'esperimento
non è mai entrato nello stato in cui un'assenza avrebbe potuto essere
interpretata.

## Evidence reale dello scout

Sono state tentate 12 coppie endpoint/frequenza. Due hanno prodotto offerte
descrittive con marker station-specific, ma l'audit di continuità le ha rese
inammissibili:

| Endpoint | Frequenza | Marker | Carrier | Time code | Segmento continuo | Esito |
|---|---:|---|---:|---:|---:|---|
| Blair, Washington | 10 MHz | WWVH, tick 18.924 dB | 44.731 dB | 6.789 dB | 1.109 s | non usabile |
| VA6OK, Alberta | 15 MHz | WWV, tick 6.463 dB | 15.955 dB | 6.333 dB | 1.280 s | non usabile |

La soglia di continuità era 3.0 s e non è stata modificata.

## Failure attribution

Dieci tentativi sono stati emessi come `capability_refused`, ma non tutti sono
fallimenti della capability RF:

- sette tentativi hanno raggiunto una metrica non finita (`-inf`) e sono stati
  rifiutati perché JSON Lines vieta valori non finiti. È un errore del percorso
  descrittivo/serializzazione; non dimostra assenza di marker o ricezione;
- tre tentativi KFS hanno prodotto meno di un secondo continuo utilizzabile per
  l'estrattore;
- le due offerte emesse avevano marker plausibili ma non la continuità minima.

Il rifiuto complessivo è quindi valido come decisione operativa di questa
esecuzione, ma non prova che nessun Kiwi pubblico potesse osservare WWV/WWVH.
In particolare, l'errore di serializzazione ha impedito a più candidati di
raggiungere il ranking.

Il receipt finale non conserva gli hash degli artifact dei candidati rifiutati,
anche se due hash erano presenti negli eventi intermedi. Questa è una lacuna di
lineage del receipt pre-falsificabilità, non una ragione per reinterpretare
l'outcome.

## Conclusione epistemica

Gate E ha rispettato la regola più importante: non ha trasformato una
capability non qualificata in un'assenza fisica. Il risultato riguarda il ponte
osservativo e la sua descrizione, non la previsione NIST e non la presenza dei
toni WWV/WWVH.

La sessione si è fermata a questo outcome. Nessun valore viene corretto e
nessuna nuova acquisizione viene avviata dopo averlo visto.
