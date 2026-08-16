# Gate B — Checkpoint 2

Stato: **STOP dopo la prima evidenza reale assimilata in ciascun ramo**.
Non sono stati avviati planner, loop, failover, persistenza, database o servizi.
Waterfall SatNOGS, campioni IQ Kiwi e grafo causale sono esistiti soltanto in
RAM; su disco rimangono codice, test e questo receipt descrittivo.

## Modifica minima del modello

È rimasto un solo insieme di record condivisi. `Intent.target` è ora
`str | None` e Probe B usa `target=None`. `DecisionContract`,
`ConstraintReceipt`, `EvidenceEvent`, `BeliefSnapshot` e `CausalGraph` non
conoscono una sorgente. SatNOGS e Kiwi sono invece due moduli separati, senza
`InternetSource`, registry o gerarchia di adapter.

Il grafo causale è un oggetto locale in RAM; distingue radici hardware della
misura e radici condivise del modello. Il receipt conserva event time, arrival
time, hash, trasformazioni, vincoli e caveat, ma non conserva i payload.
L'osservabilità non è uno stato globale: ogni clausola del `DecisionContract`
ha un esito `SATISFIED`, `UNSATISFIED`, `UNRESOLVED` o `UNOBSERVABLE`.

## Probe A — SatNOGS, TTL 600 s

Il probe ha interrogato le observation concluse entro `now`, ha filtrato
localmente per età dall'`event_end`, due stazioni distinte, distanza minima,
stesso controllo NORAD/transmitter e finestre sovrapposte. `good` e `unknown`
sono soltanto candidati: ogni PNG deve superare il controllo di struttura
interno. La prima versione del detector aveva scambiato i bordi del raster per
segnale; quel risultato è stato invalidato prima dell'assimilazione definitiva.

Prima evidence valida, assimilata alle 22:44:10 UTC del 2026-08-15:

| Observation | Stazione | Finestra evento UTC | Published UTC | Byte | SHA-256 |
|---|---|---|---|---:|---|
| 14784623 | 5087, Pi Station 1 | 22:34:34–22:42:56 | 22:43:41 | 1,651,141 | `ac076ac…121295a` |
| 14784570 | 4084, Astronomiemuseum Turnstile VHF (Test UHF) | 22:34:25–22:42:53 | 22:43:50 | 1,679,179 | `a2d58d…781607d` |

Il measurement age all'assimilazione era `77.638 s`, cioè 77.638 secondi,
quindi entro il TTL di 600 s. I JSON Lines conservano il numero come
`77.638`, con punto decimale e unità espressa dal suffisso `_s`. Le frazioni
temporali con struttura interna erano rispettivamente
0.009409 e 0.008766; le bande luminose normalizzate rispetto al centro erano
circa `[-0.3328, 0.2810]` e `[-0.3013, 0.3431]`.

La clausola `measurement_availability` è `SATISFIED`: due radici di stazione
hanno prodotto energia RF strutturata nella stessa finestra model-conditioned.
La clausola `emitter_identity` è invece `UNRESOLVED`.
NORAD, transmitter UUID `DKkitSYmcbsaMq7upo6Ldg`, famiglia GP e stato del job
non dimostrano l'identità dell'emettitore. Le radici fisiche sono
`station:5087` e `station:4084`; pipeline SatNOGS, catalogo transmitter e
famiglia GP rimangono radici condivise del modello.

## Probe B — dual Kiwi targetless

Due connessioni SND/IQ sono state aperte contemporaneamente verso Hooksiel e
Doncaster, entrambe sintonizzate nominalmente a 9.996 MHz. Ogni thread ha
atteso una barriera comune; i blocchi sono rimasti in un ring buffer temporale
in RAM e sono stati scartati alla chiusura.

Il campo Kiwi chiamato `last_gps_solution` nel server è l'età, in secondi,
dell'ultima soluzione GPS, saturata a 252; non è un codice qualità. Per questo
la precedente cattura Dortmund–Eindhoven, che mostrava 252 su un ricevitore, è
stata invalidata. La cattura definitiva ha età GPS 0–2 s su entrambi i lati e
nessun blocco con flag ADC overflow.

| Ricevitore | Event time UTC | Arrival time UTC | Campioni | Sample rate | GPS age | ADC overflow |
|---|---|---|---:|---:|---|---:|
| Hooksiel | 22:54:11.223922–22:54:19.203257 | 22:54:11.301443–22:54:19.315750 | 95,744 | 11,998.994 Hz | 0–2 s | 0 |
| Doncaster | 22:54:11.429627–22:54:19.451696 | 22:54:11.531646–22:54:19.582787 | 96,256 | 11,998.901 Hz | 0–2 s | 0 |

Intersezione GNSS: 7.773630 s. Measurement age al confronto: 0.557556 s.
Le proprietà calcolate sulla dinamica STFT, non sulla sola sintonia, sono:

| Proprietà | Valore | Soglia di supporto |
|---|---:|---:|
| correlazione dell'inviluppo, con piccolo lag | 0.352590 | 0.45 |
| correlazione dell'entropia spettrale | 0.665414 | 0.35 |
| correlazione della dinamica spettrale | 0.023713 | 0.35 |
| transienti robusti condivisi | 0.000000 | 0.05 |
| miglior shift spettrale esplorato | -23.435 Hz | stima, non voto autonomo |

Una proprietà su quattro sostiene l'ipotesi. La clausola
`measurement_availability` è `SATISFIED`: esistono due misure RF reali e
simultanee. La clausola `common_physical_cause` è `UNRESOLVED`: non esiste
abbastanza struttura comune per stabilire che descrivano lo stesso fenomeno.
La frequenza uguale è solo un requisito di controllo e non viene chiamata
«coincidenza».

Il risultato negativo non esclude una sorgente fisica comune. In HF multipath,
fading selettivo, polarizzazione, ritardi di cammino, Doppler, geometria ignota
e interferenza locale possono distruggere la correlazione. Viceversa due
emettitori non collegati, o rumore impulsivo comune, possono creare accordo
breve. Gli oscillatori non sono sincronizzati in fase, quindi la fase IQ non è
stata confrontata; lo shift trovato confonde oscillatori, canale e binning.

## Confronto dei due rami

| Astrazione | SatNOGS | dual Kiwi | Decisione al Checkpoint 2 |
|---|---|---|---|
| domanda con target opzionale | target usato solo per selezione/controllo | nessun target | **comune e necessaria** |
| event time separato da arrival time | finestra API e publication lag | GNSS SOW e arrival locale | **comune e necessaria** |
| `ConstraintReceipt` | due PNG lossily model-conditioned | due IQ e feature STFT | **comune e necessaria** |
| radici fisiche vs model roots | stazioni vs pipeline/catalogo/GP | front-end distinti vs Kiwi/DDC/codice feature | **comune e necessaria** |
| `BeliefSnapshot` | misura disponibile, identità unresolved | misure disponibili, causa comune unresolved | **mantenerla per clausole**, senza stato globale |
| `DecisionContract` | applica TTL e due radici | applica freschezza e requisiti del test | **mantenerlo ridotto** a criteri di accettazione/rifiuto, non source selection |
| target/identità orbitale | contesto del job e del controllo Doppler | assente dal percorso critico | **satellite-first, non comune** |
| kernel orbitale | può ricostruire il controllo SatNOGS | non serve per la domanda fisica iniziale | **strumento di ramo, non framework** |
| planner | non necessario per assimilare il pair locale | non necessario per aprire due lease esplicite | **eliminato dal Gate B corrente** |
| `CapabilityOffer`/`ObservationLease` formali | i candidati scadono con TTL | status/API/GPS/overflow cambiano per connessione | **non promossi a classi**: per ora sono eventi effimeri del probe |

La vera astrazione condivisa non è «osservazione satellitare»: è un enunciato
falsificabile con event time, receipt dei vincoli, trasformazioni esplicite e
radici causali. Target, orbita, transmitter identity, residuale Doppler e
planner target-first esistono soltanto perché il primo ramo nasce da un job
satellitare. Non devono governare il ramo Kiwi.

Il primo evento Kiwi non richiede di eliminare `BeliefSnapshot` o
`DecisionContract`: entrambi hanno impedito di promuovere una misura reale ma
insufficiente a «stesso fenomeno». Richiede invece di eliminare il planner dal
percorso corrente e di non materializzare le due astrazioni speculative
`CapabilityOffer` e `ObservationLease` finché più esperimenti non mostrino
semantica realmente comune.

L'invariante runtime del contratto rifiuta qualunque snapshot che tenti di
marcare `SATISFIED` una clausola usando un receipt oltre il TTL calcolato da
`event_end`; un arrival time recente non rinnova la misura.

## Condizione di arresto raggiunta

Checkpoint 2 termina qui. Non vengono eseguiti un secondo evento dual-Kiwi,
identificazione del segnale, triangolazione, associazione orbitale, polling,
retry/failover automatico o persistenza. Il prossimo passo richiede una nuova
decisione esplicita.
