# Android: un limite causale alla ricezione, senza allineamento del chipset

Il nuovo modo esplicito controlla se il tempo GNSS dichiarato e successivo al
tempo indipendente della ricezione del callback. Non richiede un budget finito
di allineamento GNSS/BOOTTIME. Sulle quattro sessioni gia esposte, pero, **non
distingue la challenge di +100 ms**: il margine condizionale alla ricezione e
554,5-632,3 ms. Il confronto a due lati e i suoi risultati restano invariati.
Questo incremento software non chiude P2 fisica o P3.

## Relazione controllata

La documentazione di [GnssClock](https://developer.android.com/reference/android/location/GnssClock)
definisce il clock hardware e la conversione GPS tramite TimeNanos, FullBiasNanos
e BiasNanos. Il [callback dell'app](../../pnt/android-collector/app/src/main/java/org/satelliterf/observatory/clock/MainActivity.java)
legge questi campi e tutte le misure, poi registra `CallbackReadEndElapsedRealtimeNanos`
tramite `SystemClock.elapsedRealtimeNanos()`, sul contatore usato da NTS.

L'inferenza aggiunta e condizionale al collector e alla semantica del dispositivo:
lo snapshot consegnato rappresenta una lettura avvenuta prima della fine di
quel callback. **La ricezione non diventa l'epoca GNSS.** Non viene assunto
un ritardo massimo, ne una misura successiva all'inizio dell'acquisizione.

Sia C il tempo UTC GNSS decodificato, e il suo errore dichiarato e U il limite
UTC superiore NTS alla fine della lettura. Se `C - e > U`, la relazione causale
e contraddetta: `INCONSISTENT_WITH_CAUSAL_RECEIPT`. Negli altri casi il risultato
e `NO_FUTURE_CONTRADICTION`, senza convalida di tempo, posizione o origine RF.
Un tempo passato arbitrariamente vecchio non puo essere escluso. Ritardi del
callback o limiti NTS piu larghi possono nascondere anche un anticipo.

Gli intervalli NTS singoli e i bracket adiacenti sono quelli esistenti: nessuna
estrapolazione, voto fra endpoint, salto dei fallimenti o nuovo livello di replay.
Un callback mancante, invalido, fuori acquisizione o senza supporto temporale
resta insufficiente. Gli anchor incompatibili restano insufficienti. Si ignorano
il contatore stimato dal chipset e le sue incertezze riportate, senza promuovere
le stime al 68% a limiti fisici. Restano assunti collector/boot, contatore locale,
rate e risoluzione, accuratezza server, conversione GPS-UTC e errore UTC GNSS.
Una contraddizione puo dipendere dalla violazione di queste assunzioni: non
attribuisce un attacco e non prova da sola una manipolazione RF.

## Replay dell'11 ottobre 2026

Si riusano tutte le [tre sessioni di valutazione](PNT_ANDROID_SESSION_EVALUATION.md)
e la [sessione 0.4.2](PNT_ANDROID_NTS_COVERAGE.md), senza nuova acquisizione,
sostituzione o selezione per esito. Il [riepilogo pubblico]
(results/pnt_android_causal_receipt_v1.json) conserva gli hash degli archivi,
dei membri e dei rapporti, copertura per sessione/caso e tutti i margini dei
gruppi supportati. Originali e replay completo restano nel fascicolo privato:
senza gli input privati le osservazioni non sono integralmente riproducibili.

Si riusa la [challenge Raw](PNT_ANDROID_RAW_CLOCK_CHALLENGE.md) con zero e
gli stessi scarti +/-100 ms: FullBiasNanos e trasmissione GPS si spostano insieme,
con pseudorange identici verificati dal parser su tutte le 1.446 righe per caso.
Callback, BOOTTIME, NTS e altri budget restano invariati. Il budget di
allineamento di 25 ms viene rimosso esplicitamente; non e sostituito con zero.
Restano UTC GNSS/server 1 ms, rate 100 ppm, risoluzione 1 ns e bracket 15 s,
tutti non qualificati. Non e una simulazione RF o di un ricevitore completo.

| Sessione | Gruppi clock totali | Gruppi con supporto alla ricezione | Righe supportate | Margine condizionale, ms |
|---|---:|---:|---:|---:|
| Valutazione 1 | 48 | 3 | 30 | 627,4-632,3 |
| Valutazione 2 | 31 | 19 | 176 | 611,1-630,8 |
| Valutazione 3 | 38 | 26 | 190 | 562,5-629,0 |
| Copertura 0.4.2 | 39 | 18 | 157 | 554,5-622,0 |
| Totale descrittivo | 156 | 66 | 553 | 554,5-632,3 |

Per zero, -100 ms e +100 ms tutti i 66 gruppi supportati rimangono
`NO_FUTURE_CONTRADICTION`. Restano **90 gruppi / 893 righe insufficienti**,
con gli stessi 57 successi e 23 timeout nei 80 slot NTS. I gruppi riportati e
le righe non sono prove indipendenti; non si stima sensibilita di popolazione,
falsi allarmi o benignita verificata. Non ci sono disaccordi sui confronti
utilizzabili; se presenti, sarebbero riportati senza voto o scarto.

I margini sono calcolati dal caso zero, non sono nuovi parametri del rilevatore:
per ogni riga `max(0, U - (C - e) + 1 ns)` usando il limite superiore piu
stretto fra i confronti utilizzabili mantenuti. Per ogni gruppo si riporta il
massimo delle sue righe. Non si aggiungono scarti piu grandi per ottenere un
risultato positivo. Il supporto differisce dal precedente confronto all'epoca
GNSS perche ora l'evento associato a NTS e la fine del callback.

## Uso e riproduzione

Il [README PNT](../../pnt/README.md#one-sided-callback-receipt-diagnostic) documenta
`android-time-compare --causal-receipt-upper-bound`. La scelta e registrata nel
capture; e incompatibile con i budget `--epoch-alignment-*`. Il modo precedente
non cambia e non passa automaticamente al test causale quando manca un budget.
L'app, i rapporti ZIP e il monitor mantengono il loro comportamento precedente.
Il comando di sensibilita a due lati rifiuta i rapporti causali, evitando di
usare il callback come epoca nel controllo locale di continuita.

Per riprodurre i casi con un rapporto originale disponibile, copiare il suo
`comparison.receiver_capture`, impostare `time_association` a
`ANDROID_CALLBACK_UPPER_BOUND` e porre a `None` entrambi i campi
`epoch_alignment_error_ns` / `epoch_alignment_source` di ogni record.
Per ciascuno scarto, usare `pnt.android_raw.shift_android_raw_clock_capture`,
poi `pnt.gnss_time.compare_receiver_capture` con witness originale, errore UTC
e span registrati. Si mantengono tutti i confronti e le insufficienze.
Ogni rapporto causale si rigioca direttamente con quest'ultimo motore,
senza trasformazioni ulteriori. I quattro confronti originali sono stati
ricalcolati e risultano esattamente identici ai rapporti storici; archivi,
membri e rapporti originali restano invariati.

I test coprono la relazione unilaterale, uguaglianza/anticipo di 1 ns,
ritardo che indebolisce il controllo, callback invalidi, dominio/boot,
fallimenti e anchor incompatibili, mancato fallback e uso CLI senza dipendenze
geometriche. Il passo successivo per una prova fisica resta un evento verificabile
con associazione temporale indipendente adeguata all'errore dannoso scelto.
