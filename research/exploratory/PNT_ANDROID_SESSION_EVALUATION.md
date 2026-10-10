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

## Stato

Preparazione prima della raccolta; nessun risultato ancora aperto o attribuito.
L'esito e i limiti saranno aggiunti separatamente dopo la prova, preservando
la configurazione committata.
