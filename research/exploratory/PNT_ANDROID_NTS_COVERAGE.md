# Android 0.4.2: isolamento dei timeout e copertura osservata

La prova dell'11 ottobre 2026 verifica sul Galaxy S21 FE che i due endpoint
NTS possano avanzare separatamente durante un timeout. **Il comportamento è
osservato, ma la copertura rimane parziale:** 13/20 scambi autenticati e
18/39 gruppi clock confrontabili da tutti i metodi. Non è una dimostrazione
di un miglioramento stabile rispetto alla versione precedente.

Il [riepilogo pubblico](results/pnt_android_nts_coverage_v1.json) conserva
conteggi, hash, versione, profilo e limiti. Questa è una singola prova
ingegneristica esplorativa; la [valutazione precedente su tre sessioni](PNT_ANDROID_SESSION_EVALUATION.md)
resta chiusa e invariata.

## Raccolta e riproduzione

Il raccoglitore 0.4.2 e il motore provengono dal commit
`e28f4cbb6f740e4dbe341fa22c892ec3f01c838f`. Il telefono è un SM-G990B con
Android 16, fermo all'aperto secondo la conferma dell'utente, con Internet
attivo e app visibile. Prima dell'avvio si sono scelti una sola prima sessione,
nessun rimpiazzo, limite operativo di 120 secondi e il profilo numerico
esistente. La sessione termina automaticamente con `SCHEDULE_COMPLETED`
dopo 39,118 secondi, conservando tutti i venti slot dei dieci round.

La distanza minima fra avvii dello stesso endpoint resta di tre secondi;
i tentativi in ritardo partono senza recuperi compressi. I fallimenti
interrompono ancora l'adiacenza del replay sullo stesso endpoint: nessun ponte
attraverso il timeout, voto fra server o riferimento sostitutivo. I due server
PTB appartengono alla stessa autorità temporale.

Gli originali sono stati copiati in binario e confrontati con gli SHA-256
calcolati sul telefono prima e dopo la copia, prima della decodifica sul PC.
I 27 file originali precedenti rimangono identici dopo installazione e prova.
ZIP, originali, rapporti completi e ledger restano privati. Il riepilogo
pubblico permette di ispezionare conteggi e provenienza; il replay integrale
richiede gli input privati.

Si riusano senza modifiche le `analysis_options` della
[configurazione precedente](android_time_session_evaluation_v1.json), compresi
associazione ipotetica di 25 ms, budget non qualificati e scarti software
±100 ms. Estratte queste opzioni in `options.json`, i comandi eseguiti sono:

```console
python -m pnt android-session session.zip --analysis-options options.json --output session-report.json
python -m pnt time-sensitivity session-report.json --session-summary --offset-ns -100000000 --offset-ns 100000000 --local-counter-resolution-ns 1 --output session-summary.json
```

Entrambi terminano con codice 0, senza intake issues. Il confronto e il payload
del riepilogo coincidono esattamente con il replay delle API esistenti.
Un primo controllo dell'helper fallisce perché confronta l'intero output CLI
con il payload API, che non contiene le ricevute `sources` aggiunte dalla CLI.
Il payload viene quindi confrontato separatamente e la ricevuta verificata
contro l'hash del rapporto. Questo errore di verifica resta nel ledger e nel
riepilogo; non cambia raccolta, input, parametri o risultato.

## Esiti e denominatori

| Endpoint | Autenticati / slot | Timeout | Minimo fra avvii |
|---|---:|---:|---:|
| `ptbtime1.ptb.de` | 5/10 | 5 | 3001,527 ms |
| `ptbtime2.ptb.de` | 8/10 | 2 | 3001,460 ms |

Ci sono nove coppie di tentativi sovrapposti fra endpoint distinti. Il secondo
endpoint completa scambi mentre il primo attraversa un timeout. Tutti e sette
i fallimenti riportano `SocketTimeoutException: Poll timed out`: la separazione
dei calendari evita il blocco dell'altro endpoint, non elimina i timeout di rete.

Le 39 callback producono 1119 righe Raw: 372 GPS normalizzate e 747 di altre
costellazioni non supportate dal controllo UTC GPS, conservate nell'intake.
I gruppi clock dichiarati sono 39; nessuna riga GPS è priva d'identità.
Il supporto comune è fissato sull'originale: 167 righe GPS in 18 gruppi.

| Metodo | Gruppi con supporto proprio | Gruppi insufficienti | Righe GPS con supporto proprio | Righe insufficienti |
|---|---:|---:|---:|---:|
| Locale | 38/39 | 1 | 371/372 | 1 |
| Esterno | 19/39 | 20 | 168/372 | 204 |
| Combinato | 18/39 | 21 | 167/372 | 205 |

Sull'originale tutti i gruppi valutabili, compreso il supporto proprio fuori
dal comune, sono `NOT_DISTINGUISHABLE`; non ci sono discordanze o inconclusivi.
Su ciascuno degli scarti ±100 ms, esterno e combinato sono `INCONSISTENT` su
tutti i 18 gruppi comuni, mentre il locale resta invariato. Sul supporto
proprio l'esterno distingue 19 gruppi e il combinato 18. Gli insufficienti
restano nel denominatore in ogni caso. Questi gruppi non sono prove indipendenti.

La copertura comune osservata è 18/39 (46,2%), contro 47/117 (40,2%) nel blocco
storico 0.4.1; le tre sessioni storiche variavano dal 6,3% al 68,4%.
Gli scambi autenticati sono invece 13/20 (65,0%), **meno** del precedente
44/60 (73,3%). Sono periodi diversi, senza confronto A/B abbinato: nessuno
dei due cambiamenti dimostra un effetto causale o una prestazione stabile.

## Conseguenza per il lavoro

L'isolamento del timeout è verificato su questa esecuzione reale e la
sensibilità condizionale agli scarti costanti resta presente dove c'è supporto.
Restano 21 gruppi insufficienti, budget non qualificati e nessuna verità benigna
indipendente. Non è una challenge RF, autenticazione universale del segnale,
stima di falsi allarmi o chiusura di P2/P3.

Il prossimo quesito è quando una **deriva graduale dell'UTC decodificato**
diventa distinguibile dal controllo locale e dal riferimento Internet, e come
le lacune ritardino la rilevazione. Si può sviluppare la trasformazione nota
sui dati già esposti, riusando confronto e replay, senza una nuova matrice di
budget o altre ripetizioni equivalenti dello scarto costante. Una futura
conferma richiederà dati esclusi e criteri appropriati fissati prima del reveal.
