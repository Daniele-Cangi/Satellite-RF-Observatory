# Gate B — checkpoint 1

Stato: **STOP prima del runtime**. Questo documento conserva le ipotesi iniziali
e le scelte sostituibili richieste dal Gate B. Il codice del runtime, il failover e
l'assimilazione non sono ancora implementati.

## 1. Kernel orbitale puro

Il kernel isolato accetta:

- un osservatore arbitrario `(latitudine, longitudine, quota)`;
- elementi orbitali OMM/JSON o TLE espliciti;
- un `event_time` UTC timezone-aware;
- un carrier opzionale in Hz.

Restituisce posizione e velocità geocentriche, azimuth/elevation, range,
range-rate e, quando esiste il carrier, Doppler con convenzione esplicita:
range-rate positivo significa allontanamento e quindi shift Doppler negativo.

Vincoli verificabili: nessun singleton, configurazione globale, Redis, database,
rete o clock implicito. Il kernel non sceglie un satellite, una stazione o una
frequenza e non trasforma un errore di propagazione in `0 Hz`.

## 2. Primitive epistemiche minime da implementare

Le primitive sono record in memoria, non una DSL e non un registry persistente.

| Concetto | Minimo contenuto e responsabilità | Cosa non deve fare |
|---|---|---|
| `DecisionContract` | domanda, `valid_at`, osservabili necessari, età massima, incertezza massima, regole di rifiuto | non prescrive una sorgente o un satellite |
| `CapabilityOffer` | osservabili disponibili ora, TTL calcolato da `event_end`, qualità dei transform, radici causali, costo e motivi di rigetto | non sopravvive al probe e non è un plugin registrato |
| `EvidenceEvent` | finestra dell'evento, arrival time, URL/hash/dimensione, stazione, transform ledger, radici e tag di circolarità | non equivale automaticamente a una credenza |
| `BeliefSnapshot` | esito separato per ogni clausola (`SATISFIED`, `UNSATISFIED`, `UNRESOLVED`), `valid_at`, measurement age, incertezza e radici attive | non comprime disponibilità e supporto causale in uno stato globale |
| `ObservationLease` | offer selezionata, scadenza, stato di accesso e motivo di revoca | non promette una prenotazione remota inesistente |
| `Transform` | operazione, input/output, stato `known/partial/unknown/model_conditioned`, parametri, modello e versione | non cancella dipendenze condivise |

`ExperimentReceipt` resta volutamente una proposta concorrente, non una settima
astrazione già stabilizzata.

## 3. Probe A

### Contratto iniziale

Domanda sperimentale: «esiste evidenza RF recente, osservata da almeno due radici
hardware distinte, compatibile con la stessa emissione prevista senza usare
l'identità del job come prova?»

- `max_measurement_age`: 600 s dall'`event_end`, non dall'arrivo;
- servono due stazioni distinte, waterfall accessibile e finestre sovrapposte;
- lo stesso NORAD/transmitter serve soltanto a trovare il caso e ricostruire il
  controllo;
- carrier da SatNOGS DB/metadata e OMM CelesTrak sono contesto/model roots;
- se non esistono due offerte valide, l'esito è `UNOBSERVABLE`.

Il client dovrà acquisire la prima pagina cursor-based e filtrare localmente: nel
probe manuale i parametri legacy di filtro del server non hanno ristretto la
risposta. Nessuna TTL verrà estesa da cache o arrival time.

### Evidenza reale osservata il 2026-08-15T22:08:43Z

Tre artifact dello stesso pass di NORAD 40014 e transmitter
`NSXo8tGxmxpTUMsmSH34FF` a 437.445 MHz erano realmente accessibili via HTTP 200:

| Observation | Stazione | Evento UTC | Last-Modified UTC | Publication lag | Measurement age al probe | Byte | HEAD |
|---|---|---|---|---:|---:|---:|---:|
| 14797857 | 4111, Plyachka, 42.48304/23.445813 | 21:52:09–22:01:30 | 22:02:15 | 45 s | 434 s | 1,677,658 | 469 ms |
| 14797848 | 4460, Sofia SAT Club - Bay Ivan, 42.999966/24.930954 | 21:53:09–22:00:37 | 22:03:03 | 146 s | 487 s | 1,679,978 | 913 ms |
| 14797854 | 4349, Sofia SAT Club - Hadji Boby UHF, 41.697669/24.95621 | 21:52:49–22:00:17 | 22:00:56 | 39 s | 507 s | 1,684,986 | 452 ms |

Le waterfall mostrano energia RF strutturata e burst quasi orizzontali fra circa
-20 kHz e -4 kHz. Questo è un controllo visivo, non ancora una misura automatica.
Il fatto che `status=good`, NORAD e transmitter siano pubblicati da SatNOGS non
costituisce una seconda prova fisica.

La prima lease proposta è 14797857: è la misura più fresca e non appartiene alle
due stazioni con lo stesso nome organizzativo. Se viene revocata, la selezione
non userà un fallback codificato: 14797848 vince fra le offerte rimanenti perché
mantiene l'osservabile richiesto e scade più tardi di 14797854. Al runtime questo
verrà ricalcolato dalle offerte presenti, non dagli ID qui fissati.

### Transform ledger minimo

1. campo RF al sito: osservato indirettamente, parametri del canale ignoti;
2. antenna/feedline/LNA/SDR/clock: hardware root della stazione, calibrazione e
   PPM in gran parte ignoti;
3. tuning e LO offset: parziali dai parametri/job/client;
4. Doppler compensation: `model_conditioned`, eseguita nel flowgraph usando
   elementi orbitali e posizione di stazione;
5. FFT/waterfall: nota in struttura (waterfall sink, FFT e raster), ma la PNG è
   quantizzata, colorizzata e non conserva IQ o fase;
6. upload/storage: post-evento, con lag misurato da `event_end` a `Last-Modified`.

Per 14797857 il metadata reale dichiara RTL-SDR, sample rate 2.048 MHz, tuning a
437.443 MHz, gain 42.7, PPM 0, LO offset nullo e `gr-satnogs`
`v2.3-compat-xxx-v2.3.5.0`; il carrier di catalogo è 437.445 MHz. Questi valori
rendono noto parte del controllo, ma PPM 0 è una configurazione dichiarata e non
una prova di calibrazione del clock.

Il kernel deve ricostruire il controllo con il TLE incorporato nell'observation
job. Il confronto reale ha mostrato che l'OMM CelesTrak aveva lo stesso epoch
`2026-08-15T13:50:21.777216` e gli stessi elementi numerici del TLE del job. È un
modello separatamente serializzato, ma in questo caso non è un'evidenza causale
indipendente: va rappresentato come la stessa model family GP.

## 4. Due rappresentazioni concorrenti di `ExperimentReceipt`

### A — residual series

Una serie di campioni `(event_time, residual_hz, power_db, uncertainty)` rispetto
al centro già Doppler-compensato, più artifact hash, radici, modello di controllo
e transform ledger.

Vantaggi: conserva dinamica, segno e discontinuità; permette confronti fra
stazioni. Svantaggi: estrarre numeri da una PNG implica calibrazione degli assi,
colormap e timestamp; il dato sembra più preciso di quanto sia.

### B — residual constraints

Segmenti di ridge/burst con intervallo temporale, banda di residuale, potenza
relativa, qualità e incertezza, più lo stesso envelope di provenienza.

Vantaggi: rappresenta ciò che la PNG supporta davvero e rende esplicite lacune e
quantizzazione. Svantaggi: perde struttura fine e rende più difficile una
successiva analisi Doppler quantitativa.

Ipotesi iniziale: B è il receipt legittimo per le PNG; A è ammesso solo per un
artifact HDF5/IQ o quando la mappatura pixel→tempo/frequenza è verificata. La
variazione da attaccare al primo run è quindi che il «segnale ricevuto assoluto»
potrebbe sparire come concetto: il residuale model-conditioned è l'osservabile
primario.

## 5. Grafo causale e rischi di circolarità

Radici fisiche distinte: hardware delle stazioni 4111, 4460 e 4349. Radici
condivise: SatNOGS client/flowgraphs, scheduler/API/storage, SatNOGS DB carrier,
catalogo orbitale GP e metodo di Doppler compensation.

Rischi da rigettare o contare una sola volta:

- NORAD/transmitter del job usato come conferma della stessa identità;
- una traccia resa orizzontale dal modello usata per provare quel modello;
- TLE del job e OMM CelesTrak contati come indipendenti senza verificarne la
  radice catalogo;
- `good`, decoded frames e waterfall dello stesso observation job trattati come
  tre evidenze indipendenti;
- due stazioni diverse trattate come completamente indipendenti ignorando
  software, cataloghi e pipeline condivisi;
- arrival time usato al posto dell'event time per far sembrare fresca una misura.

Il conteggio iniziale è quindi «due radici hardware osservative, una pipeline e
un model family condivisi», non quattro o cinque prove.

## 6. Ricognizione SHOCK iniziale

La ricognizione ha eseguito tre probe reali, senza credenziali e senza modifiche
remote.

| Sorgente | Verdetto osservato | Event time/lag | Quantità e trasformazioni | Indipendenza e failure semantics |
|---|---|---|---|---|
| [KiwiSDR](https://kiwisdr.com/ks/using_Kiwi.html) | **live RF verificato** su due ricevitori distinti | IQ di 3 s con GNSS seconds-of-week e GPS solution 2; trasporto apparente sub-secondo | antenna → front-end/ADC → FPGA channel/DDC/tuning/gain → IQ/FFT → websocket/client | hardware/operatori distinti, hardware/software/protocollo condivisi; directory, `/status`, slot API, GPS e overload vanno verificati a ogni lease |
| [NOAA SWPC GOES XRS](https://www.swpc.noaa.gov/products/goes-x-ray-flux) | **physical near-live verificato**, non RF | ultimo campione 189.6 s vecchio | irradiance → fotodiodi XRS → calibrazione/correzione elettroni → media 1 min → primary selection → JSON | indipendente da SatNOGS/CelesTrak; stale time, contamination, canale mancante e cambio satellite sono failure espliciti |
| [e-CALLISTO](https://www.e-callisto.org/Data/data.html) | **RF near-live verificato**, non live | measurement age 646.7 s, publication lag ~545 s | antenna/sweep spectrometer → ADC → blocco FITS 15 min → gzip/archive; spesso ampiezza in `digits` non calibrati | hardware di stazione distinto, firmware/formato/archive condivisi; servono due stazioni prima di chiamare una struttura “solare” |

### Dettagli dei probe Kiwi

- Dortmund: status 0–30 MHz e API attiva; S-meter di 6 s a 10 MHz con
  -85.9 dB e 5.4 misure/s; IQ di 3 s con 35,328 campioni GNSS.
- Eindhoven: hardware/operatore/antenna distinti; IQ di 3 s con 34,816 campioni
  GNSS. Lo status mostrava però 8,081,222 ADC overflow: tempo valido non implica
  ampiezza valida.
- Bad Bentheim: waterfall live da 1024 bin e SNR dichiarato 23–26 dB, ma
  `gps_good=0`; va rigettata per un contratto che richiede event time difendibile.
- Un proxy ufficiale è entrato in loop HTTP 307; Baunatal dichiarava status
  attivo ma `ext_api=0` e ha chiuso il client; una seconda connessione allo
  stesso IP è stata rifiutata. La directory genera candidati, non offer valide.

I ricevitori sono intenzionalmente pubblici, ma password, limiti e preemption
sono decisi dall'operatore. Il probe dovrà usare lease brevi e cortesi,
identificazione/consenso per automazione sostenuta e non registrare comunicazioni
private o protette. Per NOAA i dati sono pubblici; per e-CALLISTO vanno rispettati
credito e condizioni del gestore/host, non presunta una licenza universale sui
contenuti.

### Miglior pista live e variazione che distrugge un'astrazione

La pista iniziale è una lease dual-station Kiwi con IQ GNSS. L'osservabile non è
«stato del satellite X», ma una coincidenza/residuale RF targetless allineata in
event time. Ogni `/status` produce un `CapabilityOffer` effimero con banda, slot
API, GPS solution, overload, antenna e limiti; GPS/API/overload insufficienti
causano rigetto e replan esplicito.

Questo risultato elimina dalla pista SHOCK il planner target-first: prima si
stabilisce che un cambiamento RF fisico live è avvenuto, poi si collegano
spiegazioni opzionali. NOAA XRS resta contesto fisico indipendente a circa tre
minuti; e-CALLISTO resta corroborazione RF ritardata. Un picco o RSSI non viene
mai promosso a identità del trasmettitore.

## Ipotesi da conservare fino al primo run

1. Due waterfall simultanee possono sostenere «emissione RF presente», ma non
   ancora l'identità del satellite.
2. Il residuale dopo la compensazione è utilizzabile solo con il modello di
   controllo e la catena dei transform espliciti.
3. Due stazioni aumentano l'indipendenza fisica ma non quella di software e
   modello.
4. Un TTL di 600 s è una soglia del DecisionContract da misurare e attaccare, non
   una costante architetturale.
5. Se il probe pubblico non offre una coppia valida, il comportamento corretto è
   rifiutare; nessuna predizione orbitale sostituisce una misura.
6. La pista live può non avere target né kernel orbitale nel percorso critico:
   questa ipotesi nasce dai due stream Kiwi GNSS realmente osservati e dovrà
   competere con Probe A, non essere forzata dentro la sua astrazione.
