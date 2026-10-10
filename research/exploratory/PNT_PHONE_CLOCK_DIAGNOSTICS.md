# Diagnosi dei clock Android sul log esposto

Il replay originale del Galaxy S21 FE del 10 ottobre 2026 contiene 51 righe,
9 epoche distinte, discordanti nel controllo locale. Questa analisi scompone
quello scarto senza correggerlo, cambiare i budget o attribuirgli una causa RF.
Il [confronto abbinato](PNT_PHONE_PAIRED_TIME.md) e i suoi risultati restano
invariati. Si usa solo il caso zero, su dati gia esposti.

## Scomposizione riutilizzabile

L'opzione `--android-clock-diagnostics` di `time-sensitivity` riusa la baseline
ricalcolata e gli stessi anchor del controllo locale. Non introduce un nuovo
scorer, un fit, un sigillo o un protocollo di replay. Le differenze sono relative
all'anchor del segmento, sulle stesse claim ammesse:

```text
delta UTC = delta TimeNanos - delta FullBiasNanos
            - delta ceil(BiasNanos) - delta(GPS-UTC in ns)
scarto relativo = delta UTC - delta ChipsetElapsedRealtimeNanos
```

Il GPST intero gia decodificato determina il termine fine-bias: non si ripete
la conversione e il margine di arrotondamento esistente resta conservato.
La diagnostica descrive gli input originali; offset e salti software delle
challenge non vi entrano. Record esclusi, segmenti interrotti ed epoche ripetute
non acquistano un confronto locale. Le incertezze riportate dal ricevitore
restano metadati e non diventano limiti indipendenti.

## Risultato e limite individuato

Restano 479 righe GPS. Delle 262 claim ammesse, 6 righe della prima epoca hanno
solo metadati e 256 righe/43 epoche hanno una scomposizione temporale. Sono 44
epoche ammesse in totale; le altre 217 righe rimangono escluse. La ripetizione
dello stesso clock per piu satelliti non fornisce campioni indipendenti.

| Quantita rispetto all'anchor | Intervallo osservato |
|---|---:|
| `delta TimeNanos - delta ChipsetElapsedRealtimeNanos` | -9,025255 .. +3,283083 ms |
| `delta FullBiasNanos` | -235 .. -3 ns |
| `delta ceil(BiasNanos)` | 0 ns |
| Variazione della conversione GPS-UTC dichiarata | 0 ns |
| `delta UTC - delta ChipsetElapsedRealtimeNanos` | -9,025204 .. +3,283180 ms |

La variazione della correzione di conversione e al massimo **235 ns**: la
relazione fra clock hardware e contatore Android domina lo scarto di diversi
millisecondi. Questo identifica il termine nei dati registrati, senza stabilire
quale clock, firmware o associazione rappresenti male l'epoca fisica. La
scomposizione non fornisce la verita indipendente per attribuire la causa.

Il log non conserva `TimeUncertaintyNanos` valorizzato ne l'incertezza di
allineamento elapsed-realtime, su nessuna delle 262 righe ammesse. La presenza
di `BiasUncertaintyNanos` non risolve questa diversa assenza. Android descrive
[`getElapsedRealtimeUncertaintyNanos()`](https://developer.android.com/reference/android/location/GnssClock#getElapsedRealtimeUncertaintyNanos())
come una precisione di allineamento con confidenza del 68%, disponibile solo
quando il relativo flag e presente: anche registrandola, non si ottiene
automaticamente un limite deterministico di 1 ms.

I budget restano quelli originali: UTC GNSS e server 1 ms, associazione 1 ms,
deriva 100 ppm e risoluzione locale 1 ns. Le **51 discordanze/9 epoche** restano
visibili, come la compatibilita NTS originale. Con associazione ignota, tutte
le 479 righe restano insufficienti e senza scomposizione ammessa. Non si
stima un tasso di falsi allarmi e P2 non e chiusa.

## Decisione e riproduzione

Il log attuale non permette di qualificare indipendentemente l'associazione
di 1 ms. Altri scarti software sullo stesso log non risolvono questa assenza.
Il prossimo incremento utile riguarda l'acquisizione: conservare disponibilita
e incertezza dell'epoca elapsed-realtime, insieme ai contatori della callback e
alle sonde NTS contemporanee. Epoca GNSS, callback e scrittura devono restare
distinte; i nuovi metadati aiutano la diagnosi, senza sostituire la qualifica
indipendente del budget. La raccolta richiedera il telefono disponibile e
verifichera se il dispositivo espone quei campi; qui non ne e iniziata una.

Il [riepilogo](results/pnt_phone_clock_diagnostics_v1.json) conserva tutte le
epoche relative ammesse, conteggi, esclusioni e hash. Originali con posizione
e rapporti completi restano privati; il riepilogo non e un benchmark pubblico
integralmente riproducibile. Entrambi i rapporti privati di diagnosi hanno replay
esatto. Le versioni precedenti di confronto e challenge non sono modificate.

```console
python -m pnt time-sensitivity phone-time-outdoor-01-development-alignment.json --offset-ns 0 --local-counter-resolution-ns 1 --android-clock-diagnostics --output clock-diagnostics.json
```

Usare un output nuovo. Senza associazione ammessa il comando conserva il
rapporto e restituisce uscita 2. Senza il flag diagnostico, i precedenti
rapporti di sensibilita e confronto abbinato rimangono identici.
