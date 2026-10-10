# Tre nuove sessioni Android: valutazione condizionale

La domanda è se il contributo del riferimento Internet sugli scarti costanti
di UTC decodificato **±100 ms** si ripeta su tre sessioni nuove, senza aggiungere
allarmi sull'originale rispetto al controllo locale sullo stesso supporto.
La [configurazione](android_time_session_evaluation_v1.json) viene committata
prima di avviare o aprire i dati di valutazione. Git e gli hash degli input
sono sufficienti: nessun nuovo sigillo, esecutore o protocollo di replay.

## Scelta fissata prima della raccolta

Usare i primi tre ID avviati per questa valutazione sul Galaxy S21 FE,
all'aperto e fermo, con Internet e il raccoglitore 0.4.1 visibile. Ogni sessione
usa il calendario esistente di venti slot NTS; attendere 15 secondi fra
sessioni. Fermare dopo 120 secondi se non è terminata automaticamente.
Interruzioni, assenza GNSS e fallimenti restano nei tre slot: nessun rimpiazzo.
Conservare anche un avvio senza file come slot fallito, senza inventare un ID.
Il termine operativo usa l'orologio del PC, senza sostituire l'epoca GNSS.

Il solo profilo numerico è quello del JSON: associazione ipotetica di 25 ms,
un quarto della challenge software di 100 ms; gli altri parametri di sviluppo
restano fissi. Il disegno è informato dai log di sviluppo già esposti, che
non entrano nei tre slot. Nessuna calibrazione o qualifica indipendente è
affermata, e nessun budget viene adottato nell'app. I 25 ms non provengono
da un fit sui nuovi dati o dalla conversione della confidenza Android al 68%.
La conversione GPS-UTC usa la [tabella IERS C72](https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat)
verificata il 10 ottobre 2026, con 18 s per ottobre 2026.

Durante la raccolta si possono consultare stato del trasporto, nomi e
metadati. Copiare e calcolare gli hash degli originali prima di decodificarli
sul PC; aprire i valori numerici soltanto dopo la chiusura dei tre slot.
Conservare ID, ordine, orari operativi, motivi di stop, hash e precedenti
accessi nel fascicolo privato. La ricezione del file non è l'epoca GNSS.

## Analisi con i comandi esistenti

Estrarre `analysis_options` dalla configurazione in un file privato:

```python
import json
from pathlib import Path
plan = json.loads(Path("research/exploratory/android_time_session_evaluation_v1.json").read_text())
with Path("options.json").open("x", encoding="utf-8") as target:
    json.dump(plan["analysis_options"], target, indent=2, allow_nan=False)
```

Per ciascuno dei tre ZIP originali eseguire `android-session`, conservando
anche il codice di uscita e il rapporto insufficiente o gli errori:

```console
python -m pnt android-session session-1.zip --analysis-options options.json --output session-1-report.json
python -m pnt android-session session-2.zip --analysis-options options.json --output session-2-report.json
python -m pnt android-session session-3.zip --analysis-options options.json --output session-3-report.json
python -m pnt time-sensitivity session-1-report.json session-2-report.json session-3-report.json --offset-ns -100000000 --offset-ns 100000000 --local-counter-resolution-ns 1 --output session-summary.json
```

Un'intake senza confronto ammesso ferma il riepilogo esistente: conservare i
rapporti e dichiarare la valutazione non eseguibile, senza eliminare lo slot
per ottenere un totale. Un file assente o invalido resta nel fascicolo e
nella tabella finale. Non correggere originali, budget o assunzioni per
promuoverli. I rapporti rimangono privati; pubblicare solo un riepilogo
aggregato, con riferimenti/hash e indicazione degli input non pubblici.

## Regola di lettura dei risultati

Riportare prima ogni sessione: completamento, intake, ogni stato NTS, righe
GPS, gruppi clock dichiarati, righe senza identità e supporto comune.
Confrontare poi zero e i due scarti per locale, rete e combinato, con copertura
propria e denominatore comune fisso del replay. I gruppi con esiti diversi
restano misti; endpoint discordanti restano inconclusivi, senza voto.

La domanda è valutabile solo con tutte e tre le sessioni complete secondo
il calendario, confronto ammesso e almeno un gruppo comune per sessione.
Il vantaggio condizionale si ripete in questo insieme solo se, in ciascuna:

- non ci sono gruppi comuni inconclusivi o misti in nessuno dei tre casi;
- entrambi gli scarti rendono ogni gruppo comune discordante per rete e
  combinato, mentre i conteggi locali restano uguali all'originale;
- nell'originale il combinato non aggiunge gruppi discordanti al locale.

Riportare comunque gli allarmi originali, anche quando la condizione passa.
Un esito negativo o non valutabile chiude questo insieme senza ritocchi
o sostituzioni. Non stimare falsi allarmi verificati, percentuali di popolazione
o intervalli IID: stesso dispositivo, stesso blocco e due endpoint della
stessa autorità non costituiscono prove indipendenti. La trasformazione nota
modifica l'UTC decodificato, non l'RF. Questa prova non qualifica i margini
temporali e non chiude P2/P3.

## Stato alla preparazione, commit `035aa0a`

Preparazione prima della raccolta; nessun risultato ancora aperto o attribuito.
L'esito e i limiti saranno aggiunti separatamente dopo la prova, preservando
la configurazione committata.

## Esito del 10 ottobre 2026

**Il criterio predefinito è soddisfatto nelle tre sessioni**, sotto il solo
profilo condizionale fissato prima della raccolta. Il
[riepilogo pubblico](results/pnt_android_session_evaluation_v1.json) conserva
configurazione di riferimento, hash degli input privati e tutti i conteggi
per sessione/caso/metodo. Il motore è `a2fc757`; non sono cambiati codice,
budget, scarti, calendario, selezione o regola di lettura durante la prova.
I log di sviluppo precedenti non sono stati riutilizzati nei tre slot.

| Sessione | Durata NTS | Callback / Raw / GPS | Gruppi dichiarati | Gruppi comuni | NTS autenticati / falliti |
|---|---:|---:|---:|---:|---:|
| 1 | 48,887 s | 48 / 1445 / 474 | 48 | 3 | 12 / 8 |
| 2 | 32,067 s | 32 / 856 / 285 | 31 | 18 | 15 / 5 |
| 3 | 38,082 s | 38 / 963 / 315 | 38 | 26 | 17 / 3 |

Tutte chiudono Raw e NTS con `SCHEDULE_COMPLETED`, senza slot sostitutivi
né intake issues. Le 3264 righe Raw includono 1074 GPS normalizzate e 2190
righe di altre costellazioni, conservate nell'intake ma non nel controllo UTC
GPS. Le 118 callback producono 117 gruppi di metadati clock dichiarati:
neppure questi sono prove indipendenti. Il collettore dichiara la stessa
versione 0.4.1, revisione `1322d20` e contatore di boot in tutti i log;
queste dichiarazioni non attestano il binario o l'hardware.

Il supporto comune è **393/1074 righe GPS, 47/117 gruppi clock**. Ogni
sessione conserva il suo denominatore: 3, 18 e 26 gruppi. Su questi gruppi:

| UTC decodificato | Locale | Rete | Combinato |
|---|---|---|---|
| Originale | 47 non distinguibili | 47 non distinguibili | 47 non distinguibili |
| −100 ms | 47 non distinguibili | 47 discordanti | 47 discordanti |
| +100 ms | 47 non distinguibili | 47 discordanti | 47 discordanti |

Non compaiono gruppi comuni misti o inconclusivi. I conteggi locali non
cambiano e il combinato non aggiunge allarmi all'originale. Anche sulla
copertura propria non si osservano discordanze originali: locale 1053 righe /
114 gruppi valutabili, rete 405 / 49, combinato 393 / 47. Questo non verifica
che il log originale sia benigno né misura un tasso di falsi allarmi.

### Lacune e condizioni operative conservate

**681 righe GPS / 70 gruppi restano insufficienti nel confronto abbinato.**
Per la sola rete sono 669 righe / 68 gruppi; per il locale 21 / 3, inclusi
gli anchor senza confronto relativo. I 60 slot NTS conservano 44 scambi
autenticati e 16 timeout, nessuno cancellato o sostituito. La prima sessione
ha soltanto 3/48 gruppi comuni: il risultato positivo non è copertura continua.

Il calendario nativo esegue i tentativi in sequenza e recupera gli avvii in
ritardo senza sostituzione. I timeout e gli scambi ravvicinati lasciano finestre
senza bracket ammessi; il replay non scavalca il tentativo fallito. Nella
prima sessione, per esempio, gli invii autenticati arrivano a grappoli intorno
a 6–7 s e 36–38 s dall'avvio. Questi metadati documentano un limite della
raccolta, non provano che ogni lacuna abbia una sola causa.

Dopo la prima chiusura automatica, durante la pausa lo schermo si è bloccato.
È stato sbloccato prima del secondo avvio; lo spegnimento è stato portato
temporaneamente a dieci minuti e ripristinato a un minuto dopo la terza
chiusura. Nessuna registrazione è stata riavviata o interrotta per questo
intervento. Le pause effettive sono conservate nel fascicolo privato; quella
dopo la prima sessione è più lunga dei 15 secondi minimi per lo sblocco.

### Verifica, riproduzione e decisione

Gli hash dei sei originali coincidono prima/dopo la copia dal telefono;
sono stati salvati prima della decodifica numerica sul PC e dopo la chiusura
dei rispettivi slot. Tutti e tre gli slot erano terminati prima dell'analisi.
Il replay dei tre confronti con `compare_receiver_capture` e del riepilogo
con `assess_time_sensitivity_sessions` coincide esattamente con i rapporti
salvati. I quattro comandi CLI terminano con codice 0. Il JSON di
configurazione rimane quello del commit `035aa0a`.

ZIP, CSV/JSON originali, rapporti completi, ledger di raccolta e opzioni
restano nel fascicolo privato sul PC; i digest sono nel riepilogo pubblico.
Senza questi input privati il lettore può ispezionare metodo e conteggi,
ma non riprodurre integralmente le osservazioni. Usare i comandi sopra con
i tre ZIP corrispondenti e il motore `a2fc757`; non cambiare gli originali
per allinearli al risultato.

La domanda circoscritta è risolta per questo insieme: il test esterno distingue
lo scarto costante noto dove il controllo locale relativo rimane cieco,
senza allarmi originali osservati nei confronti valutabili. Non si deducono
prestazioni di popolazione, margini fisici qualificati o resistenza RF.
I 25 ms e gli altri budget restano assunzioni; P2 forte e P3 sono aperte.

Il prossimo intervento utile è ingegneristico: evitare che il timeout di un
endpoint blocchi tutta la raccolta NTS e comprima gli scambi successivi.
Servono test riutilizzabili su calendario, cancellazione e conservazione
dei fallimenti; questo esito rimane chiuso, senza una nuova matrice di budget.
