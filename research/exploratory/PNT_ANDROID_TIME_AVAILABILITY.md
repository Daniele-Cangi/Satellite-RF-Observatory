# Disponibilità delle prove temporali Android — 11 ottobre 2026

**Esito esplorativo condizionale:** la rete fornisce prima la prova di una
discordanza in alcuni casi di deriva, dopo o contemporaneamente in altri.
L'epoca GNSS e l'arrivo del callback differiscono qui di circa 0,53–0,62 s;
considerare solo l'epoca non basta per confrontare i due controlli. Questi sono
tempi ricostruiti di disponibilità degli input, non latenze di allarmi misurati.

Il [riepilogo pubblico](results/pnt_android_time_availability_v1.json) conserva
conteggi, hash, primi tempi e tutte le transizioni per gruppo. Rapporti completi,
UTC e file originali restano privati. Il codice di calcolo è il commit
`6b115ff0d64862ff7ac26dd4a7e99e91897f4e91`; il JSON lega il rapporto privato
tramite SHA-256. Le valutazioni concluse restano in
[tre sessioni](PNT_ANDROID_SESSION_EVALUATION.md),
[copertura 0.4.2](PNT_ANDROID_NTS_COVERAGE.md) e
[deriva offline](PNT_ANDROID_TIME_DRIFT.md).

## Domanda e metodo

Quando erano disponibili gli input necessari alla prima nuova discordanza
locale, esterna o combinata? Si riusano **tutte e quattro le sessioni già
esposte**, la deriva software ±5 ms/s e lo stesso profilo non qualificato della
prova precedente. Nessuna nuova raccolta, adattamento del budget o selezione
di sessioni favorevoli. L'origine software resta il primo midpoint ammesso
per ciascuna sessione; i domini del contatore non vengono uniti.

L'opzione `time-sensitivity --evidence-availability` ricostruisce prefissi
degli intervalli e dei controlli locali esistenti. Ogni confronto entra solo
quando sono disponibili il callback GNSS e tutte le autenticazioni NTS che
richiede. Si usano `CallbackReadEndElapsedRealtimeNanos` e
`finished_monotonic_ns`, nello stesso dominio dichiarato `CLOCK_BOOTTIME`.
La sola ricezione del pacchetto NTS non prova che l'autenticazione sia finita.
Per ammettere l'epoca si attende inoltre la fine della sua finestra dichiarata:
il terminale futuro della raccolta non restringe retroattivamente un prefisso.

L'adiacenza conserva gli slot falliti e futuri, senza saltare un timeout per
costruire un bracket. Un endpoint lento non blocca le prove già complete
dell'altro. Ricevute mancanti o invalide restano ignote; non si sostituisce
l'epoca GNSS o la ricezione NTS. Una ricevuta GNSS ignota interrompe il segmento
locale; callback riordinati impediscono questa ricostruzione. Il locale riusa
gli ancoraggi fissi e attende conservativamente le righe precedenti ricevute.

I gruppi e il denominatore comune sono quelli del rapporto completo:
**selezione descrittiva retrospettiva, non una regola online**. Tutte le righe
del gruppo devono essere ricevute. Una nuova discordanza richiede originale
compatibile e caso alterato discordante nello stesso prefisso, senza trasformare
allarmi originali o gruppi misti in rilevazioni. Si conservano gli esiti successivi,
compresa una revisione inconclusiva; nessun voto fra endpoint.

## Risultato

Tutte le 1446 righe GPS e gli 80 tentativi hanno ricevute utilizzabili. Questo
non elimina i **91/156 gruppi insufficienti nel combinato**: restano 65 gruppi
comuni, 57 scambi NTS autenticati e 23 timeout. I conteggi finali dei prefissi
coincidono con quelli del replay offline precedente, compresi i casi inconclusivi.

La tabella riporta secondi dall'origine della deriva. Ogni coppia è
**negativa / positiva**. Le prime discordanze dei due controlli possono
riguardare gruppi differenti; il supporto comune resta fisso.

| Sessione | Comune / dichiarati | Locale, supporto proprio | Locale, supporto comune | Rete, supporto comune |
|---|---:|---:|---:|---:|
| 1, collector 0.4.1 | 3/48 | 10,630 / 12,633 | 36,634 / 36,634 | 36,662 / 36,662 |
| 2, collector 0.4.1 | 18/31 | 10,594 / 12,608 | 17,602 / 17,602 | 17,602 / 17,602 |
| 3, collector 0.4.1 | 26/38 | 10,443 / 13,449 | 10,443 / 13,449 | 11,798 / 12,437 |
| 4, collector 0.4.2 | 18/39 | 11,915 / 11,915 | 11,915 / 11,915 | 11,136 / 11,136 |

Su supporto comune la rete precede il locale in tre coppie sessione/segno,
il locale precede la rete in tre e due sono simultanee. Sul supporto proprio
la rete precede ancora in tre coppie, il locale nelle altre cinque. Le otto
coppie non sono incidenti indipendenti né una stima di prestazione. Nella quarta
sessione la prova esterna è disponibile circa 0,779 s prima del locale, per
entrambi i segni; nella terza circa 1,012 s prima per il positivo e 1,355 s dopo
per il negativo. Nelle prime due sessioni le lacune esterne lasciano il locale
avvertire prima sul proprio supporto.

Nella terza sessione negativa un gruppo inizialmente discordante nel combinato
diventa **inconclusivo** quando arriva un'altra prova esterna. La transizione
rimane nel JSON: il primo allarme non viene presentato come definitivo.

## Verifica e limite pratico

Il comando termina con codice 0 e coincide esattamente con l'API. I test
confrontano entrambi i lati di ogni istante di disponibilità con prefissi
costruiti direttamente nel motore esistente, e verificano che dati futuri,
autenticazioni tardive, ricevute mancanti e timeout non anticipino le prove.
Suite PNT: **783 passati, cinque saltati** perché richiedono fixture native o
interoperabilità Java eseguite nella matrice Android Linux/Windows già esistente.
Passano anche nove controlli di conservazione/provenienza storica.

Gli hash dei quattro rapporti originali sono invariati. Rimuovendo la sola
diagnostica opzionale, il payload coincide esattamente con la prova di deriva
precedente. Anche i due rapporti chiusi con scarti costanti si riproducono
identicamente. Nessuna modifica alla copertura CI o agli esiti storici.

Questo risolve la domanda di **disponibilità condizionale degli input** su questi
log. Non misura calcolo, salvataggio o consegna dell'allarme, non qualifica i
budget e non dimostra autenticità RF, beneficio operativo o P2/P3. Le ricevute
restano affermazioni del collector e i due endpoint PTB condividono l'autorità.

Il passo utile successivo è portare il confronto condizionale nel monitor di
sessione, riusando il motore e trattando gli esiti come revisionabili quando
arrivano nuove prove. Si dovrà misurare la consegna effettiva del risultato;
altre raccolte equivalenti o altre matrici di budget non risolvono quel limite.
Qualifica indipendente, casi benigni/challenge verificati e sito restano separati.
