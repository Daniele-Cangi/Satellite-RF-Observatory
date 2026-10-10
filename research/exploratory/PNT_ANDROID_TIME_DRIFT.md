# Deriva graduale Android: sensibilità e disponibilità del riferimento

La deriva software **±5 ms/s** diventa distinguibile anche dal controllo
locale, a differenza dello scarto costante di origine UTC. La rete separa
alcune epoche prima e altre dopo il locale, ma il replay usa ricevute NTS
successive: **non è dimostrato un allarme operativo più rapido**.
È un risultato misto utile per distinguere i compiti dei due canali.

## Metodo e dati già esposti

La prova di sviluppo dell'11 ottobre 2026 riusa tutte le
[tre sessioni condizionali](PNT_ANDROID_SESSION_EVALUATION.md) e la
[sessione di copertura 0.4.2](PNT_ANDROID_NTS_COVERAGE.md). I quattro rapporti
erano già decodificati e pubblicamente descritti: nessun nuovo dato, selezione
per esito o rimpiazzo. Il [riepilogo pubblico](results/pnt_android_time_drift_v1.json)
riporta hash, conteggi, tempi relativi e riferimenti alle ricevute originali.
Il replay integrale richiede gli input privati.

Il motore `54fee778ba3f56557390e1952f9e0bff46f9fa34` estende il comando
`time-sensitivity`, senza un secondo rilevatore o protocollo di replay:

```console
python -m pnt time-sensitivity session-1-report.json session-2-report.json session-3-report.json coverage-report.json --drift-ppm -5000 --drift-ppm 5000 --local-counter-resolution-ns 1 --output session-drift-summary.json
```

I due segni hanno la stessa intensità, scelta prima di applicare questa
trasformazione: 5 ms/s raggiunge 100 ms in 20 secondi. Si conserva il controllo
zero e il precedente profilo non qualificato, compresa l'associazione di 25 ms.
Nessuna matrice di budget, calibrazione o scelta di una pendenza vincente.
L'origine è il primo midpoint di epoca ammesso in ciascuna sessione, senza
unire domini del contatore. Dopo l'origine lo scarto è
`sign(ppm) * floor(abs(ppm) * elapsed_ns / 1000000)`; prima è zero.
Solo l'UTC decodificato cambia: originali, contatori, segmenti locali,
incertezze, adiacenze, timeout e supporto rimangono identici.

La prima nuova discordanza richiede un gruppo interamente compatibile
nell'originale e interamente discordante nel caso alterato. Allarmi originali,
gruppi misti e discordanza fra endpoint non diventano rilevazioni nuove.
Si riportano supporto proprio e comune fisso; nessun voto o fallback.

## Risultato e tempi

Ci sono 156 gruppi dichiarati e 1446 righe GPS: il supporto comune comprende
65 gruppi e 560 righe. Restano **91 gruppi/886 righe insufficienti nel combinato**
e 23 timeout su 80 slot NTS. Il controllo locale ha supporto proprio su 152
gruppi, l'esterno su 68 e il combinato su 65. Gli originali valutabili non
mostrano discordanza; non sono dati benigni certificati.

| Deriva | Locale: discordanti comuni | Rete: discordanti comuni | Combinato: discordanti comuni | Inconclusivi rete/combinato |
|---|---:|---:|---:|---:|
| −5 ms/s | 40/65 | 40/65 | 40/65 | 1/65 |
| +5 ms/s | 37/65 | 40/65 | 40/65 | 1/65 |

Il combinato conserva inoltre 24 gruppi comuni non distinguibili per ciascun
segno. Questi conteggi descrivono epoche della stessa rampa, non incidenti
indipendenti o percentuali di prestazione. I conteggi propri, tutti gli esiti
per sessione e le righe corrispondenti sono nel JSON.

La tabella riporta secondi dall'origine software. Ogni coppia è **negativa /
positiva**. La colonna NTS è l'ultima ricevuta usata per la prima discordanza
esterna; non è l'istante misurato di un allarme.

| Sessione | Comune / dichiarati | Prima epoca locale, proprio | Prima epoca locale, comune | Prima epoca rete, comune | Ultima ricevuta NTS usata |
|---|---:|---:|---:|---:|---:|
| 1, collector 0.4.1 | 3/48 | 10,026 / 12,021 | 36,024 / 36,024 | 36,024 / 36,024 | 36,659 / 36,659 |
| 2, collector 0.4.1 | 18/31 | 10,009 / 12,004 | 17,006 / 17,006 | 17,006 / 17,006 | 17,519 / 17,519 |
| 3, collector 0.4.1 | 26/38 | 9,846 / 12,850 | 9,846 / 12,850 | 10,848 / 11,847 | 12,182 / 14,830 |
| 4, collector 0.4.2 | 18/39 | 11,323 / 11,323 | 11,323 / 11,323 | 10,319 / 9,315 | 11,799 / 11,799 |

Nelle prime due sessioni la mancanza di supporto esterno lascia il locale
separare la deriva prima sul proprio supporto. Nella quarta la rete distingue
epoche precedenti, ma la ricevuta necessaria arriva a 11,799 s, dopo l'epoca
locale a 11,323 s. Nella terza l'esito dipende dal segno e resta un gruppo
inconclusivo per ciascuno. Il tempo di callback GNSS e la latenza di elaborazione
non sono misurati qui: non si ricava da questi numeri un confronto live.

## Verifica e conseguenza

Il comando termina con codice 0. Il payload coincide esattamente con le API
esistenti estese alla deriva; hash dei rapporti e degli originali verificati.
Il replay delle due valutazioni chiuse con scarti costanti resta esattamente
uguale ai rapporti salvati. La suite PNT passa con 771 test e cinque controlli
dei produttori nativi/interoperabilità saltati, eseguiti nella matrice Android CI;
la copertura CI Linux/Windows resta invariata.

Questa trasformazione mostra complementarità, senza dimostrare che la rete
sia sempre migliore: un'origine UTC costante è invisibile al controllo locale
relativo, una deriva sufficientemente grande no. I budget restano ipotetici,
i log già esposti e la challenge software; nessuna qualifica RF o P2/P3.

Il prossimo limite concreto è la **disponibilità causale del risultato**:
misurare quando le prove necessarie erano effettivamente disponibili, usando
prefissi temporali del replay esistente e conservando le lacune. Il confronto
offline di epoche resta distinto da quella futura misura, senza cambiare questo
esito o aprire altre raccolte equivalenti.
