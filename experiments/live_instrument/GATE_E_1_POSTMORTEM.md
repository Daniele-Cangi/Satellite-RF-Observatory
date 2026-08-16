# Gate E.1 — postmortem e hardening senza nuovi dati

Ambito: esclusivamente il primo outcome Gate E congelato nel commit locale
`a0838a1`. Nessuna nuova connessione Kiwi, nessuna nuova finestra WWV/WWVH e
nessuna modifica alle soglie dell'esperimento concluso.

## Outcome congelato

Gate E ha prodotto `FALSIFIABILITY_NOT_ENTERED` alle
2026-08-16T11:24:17.625952Z. Il piano definitivo non è stato congelato e la
finestra 28–31 non è stata aperta.

Questa è una decisione sul mancato ingresso nell'esperimento, non una misura
negativa di WWV o WWVH.

## I dodici candidati

Tutti i tentativi hanno aperto una capture effimera in RAM. Soltanto due hanno
raggiunto una qualificazione fisica descritta con metriche finite e audit
quantitativo; gli altri dieci non possono essere retroattivamente classificati
come rifiuti di capability.

| Endpoint | Frequenza | Categoria E.1 | Evidenza disponibile |
|---|---:|---|---|
| N8GA Ohio | 5 MHz | `QUALIFICATION_ERROR` | metrica non finita; JSON fallito |
| N8GA Ohio | 10 MHz | `QUALIFICATION_ERROR` | metrica non finita; JSON fallito |
| N8GA Ohio | 15 MHz | `QUALIFICATION_ERROR` | metrica non finita; JSON fallito |
| Blair Washington | 5 MHz | `QUALIFICATION_ERROR` | metrica non finita; JSON fallito |
| Blair Washington | 10 MHz | `CAPABILITY_REJECTED` | WWVH supportata; continuità 1.109 s < 3.0 s |
| Blair Washington | 15 MHz | `QUALIFICATION_ERROR` | metrica non finita; JSON fallito |
| KFS California | 5 MHz | `QUALIFICATION_ERROR` | segmento inferiore a un secondo; trasformazione interrotta |
| KFS California | 10 MHz | `QUALIFICATION_ERROR` | segmento inferiore a un secondo; trasformazione interrotta |
| KFS California | 15 MHz | `QUALIFICATION_ERROR` | segmento inferiore a un secondo; trasformazione interrotta |
| VA6OK Alberta | 5 MHz | `QUALIFICATION_ERROR` | metrica non finita; JSON fallito |
| VA6OK Alberta | 10 MHz | `QUALIFICATION_ERROR` | metrica non finita; JSON fallito |
| VA6OK Alberta | 15 MHz | `CAPABILITY_REJECTED` | WWV supportata; continuità 1.280 s < 3.0 s |

### Candidati fisicamente valutati

- Blair a 10 MHz: tick WWVH 18.924 dB, carrier 44.731 dB, time code
  6.789 dB.
- VA6OK a 15 MHz: tick WWV 6.463 dB, carrier 15.955 dB, time code
  6.333 dB.

Questi marker autorizzano l'affermazione che una firma station-specific era
presente nei rispettivi segmenti selezionati. Non autorizzano l'ammissione:
entrambi i segmenti erano più corti dei 3.0 s congelati.

### Continuità insufficiente

I due candidati descritti sopra sono rifiuti epistemici legittimi della
CapabilityOffer: il requisito era stato valutato e non soddisfatto.

I tre KFS hanno mostrato un sintomo di continuità ancora più breve, ma il
software ha sollevato un'eccezione prima di costruire audit e receipt completi.
Vengono quindi conservativamente classificati `QUALIFICATION_ERROR`, non
`CAPABILITY_REJECTED`.

### Non valutabili per errore software

Sette candidati hanno raggiunto valori `-inf`. Il confine JSON con
`allow_nan=False` ha correttamente rifiutato il token non JSON, ma il `try`
troppo ampio ha trasformato il fallimento descrittivo in
`capability_refused`. I campioni effimeri erano già stati distrutti e i loro
hash non erano entrati nel receipt finale: la decisione fisica non è
ricostruibile e non va inventata.

I tre KFS hanno fallito nella trasformazione prima della descrizione. In
totale, dieci candidati sono `QUALIFICATION_ERROR`.

## Clausole

### Valutate

A livello di ammissione sono state valutate:

- presenza di marker station-specific per i due candidati descritti;
- carrier e time code per gli stessi candidati;
- continuità minima, risultata falsa;
- disponibilità di almeno una CapabilityOffer qualificata, risultata falsa.

### Bloccate prima dell'ingresso

Le otto clausole dell'esperimento non sono state osservate come vere o false:

- `station_identity_supported`;
- `path_alive_before`;
- `positive_control_before`;
- `path_alive_during_target_window`;
- `standard_tone_absent`;
- `positive_control_after`;
- `receiver_health_continuous`;
- `negative_interpretable`.

Nel receipt storico erano `UNOBSERVABLE`. Gate E.1 corregge la semantica per le
esecuzioni future: quando l'ammissione non avviene, queste clausole sono
`NOT_EVALUATED`. L'outcome storico non viene riscritto.

## Affermazioni autorizzate

- È stata eseguita una sola discovery con dodici candidati.
- Due candidati contenevano marker station-specific e witness generici
  descrivibili.
- Quei due candidati non soddisfacevano la continuità congelata.
- Dieci qualificazioni non sono state completate dal software.
- Nessuna CapabilityOffer è stata ammessa dal runtime di quella sessione.
- Gate E non è entrato nello stato falsificabile e non ha aperto la finestra
  target.
- Non esiste un negativo WWV/WWVH prodotto da Gate E.

## Affermazioni non autorizzate

- Nessun Kiwi pubblico poteva osservare WWV o WWVH.
- I sette candidati con `-inf` non ricevevano il segnale.
- I tre candidati KFS erano fisicamente incapaci.
- La propagazione HF era assente o insufficiente.
- I toni NIST erano presenti o assenti nei minuti 29–30.
- Le soglie erano troppo severe.
- La previsione NIST o l'ipotesi fisica è stata falsificata.

## Hardening E.1

- NaN e infinities diventano oggetti JSON espliciti con `numeric_state`; non
  vengono sostituiti con valori numerici.
- Gli scalari NumPy vengono normalizzati a tipi JSON standard.
- Gli array NumPy sono vietati al confine descrittivo: RF e campioni non
  possono entrare accidentalmente nel JSON Lines.
- Ogni capture viene hashata prima dell'audit e delle trasformazioni. La
  qualification conserva l'hash, mai i campioni.
- `QUALIFICATION_ERROR` e `CAPABILITY_REJECTED` sono decisioni distinte.
- `DESCRIPTION_ERROR` è ortogonale e non può riscrivere la decisione fisica.
- Il receipt di mancata ammissione conserva gli hash dei candidati valutati.
- Le clausole downstream diventano `NOT_EVALUATED` se l'ammissione fallisce.

Gate E.1 si ferma qui. Non definisce una nuova discovery né sceglie una nuova
finestra. Il successivo problema architetturale resta separato: partire da una
capability realmente qualificata e lasciare che essa determini quale
esperimento falsificabile possa essere composto.
