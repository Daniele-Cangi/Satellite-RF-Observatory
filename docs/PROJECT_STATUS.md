# Stato del progetto — 27 settembre 2026

## Obiettivo

La direzione attiva e il [piano di sicurezza PNT](PNT_SECURITY_PLAN.md):
confrontare osservazioni GNSS locali e osservazioni esterne via Internet,
valutare geometria e tempo e produrre evidenze riproducibili per gli incidenti.
Il primo caso proposto e un ricevitore GPS fisso a coordinate note.

Il [primo ciclo esplorativo P0/P1]
(../research/exploratory/PNT_LOCAL_NETWORK_FEASIBILITY.md) confronta una
stazione fissa con altre sei su dati GPS gia esposti. Il prototipo mostra come
separare anomalie locali da anomalie condivise **nel modello ammesso**, ma non
dimostra un vantaggio di rilevamento a pari falsi allarmi ne identifica un
attacco. Quel ciclo non aveva una registrazione d'attacco locale abbinata a
riferimenti esterni contemporanei; manca ancora un clock indipendente. La rete sola
non verifica l'RF locale e la differenziazione non verifica il tempo assoluto.
Il passo P2 e un caso offline documentato con quelle misure abbinate, mantenendo
i controlli locali. Il [primo intake P2]
(../research/exploratory/PNT_JAMMERTEST_PAIRING.md) ha accoppiato 210
osservazioni GPS strutturalmente utilizzabili della vittima ferma a due stazioni esterne reali. Il registro
ufficiale JammerTest chiarisce che gli orari dei tre test sono CEST e li porta
nella finestra delle osservazioni GPST. Il CSV appiattito slitta alcune colonne
quando mancano misure: 12.012 righe GPS sono state escluse e non resta alcuna
coppia nei primi due test, una sola nel terzo. Il successivo
[recupero UBX](../research/exploratory/PNT_JAMMERTEST_RAWX.md) ha ricavato
317 coppie a tre ricevitori in 81 epoche, incluse 108 coppie nelle finestre
dei test, e ha osservato salti dell'ora interna nei due test GPS L1. L'ordine
dei pacchetti fornisce un tempo di acquisizione monotono provvisorio, non un
clock indipendente. Il [confronto esplorativo sui medesimi campioni]
(../research/exploratory/PNT_JAMMERTEST_CONTRAST.md) trova variazioni locali
molto maggiori di quelle esterne durante i test, ma la combinazione resta
simile al controllo locale: un vantaggio di rilevamento dato dalla rete non e
ancora dimostrato. Nessun tasso di rilevamento o falso allarme e misurato.
Il sito segue la prova fisica.

Il [secondo episodio stazionario P2]
(../research/exploratory/PNT_JAMMERTEST_211.md) aggiunge una rampa ufficiale
di 36 minuti dello stesso archivio. Il parser conserva due pacchetti UBX con
checksum errato come scarti espliciti e ricostruisce un intervallo RAWX mancante.
Si ottengono 231 coppie a tre ricevitori; nella rampa 154 coppie con supporto
pre-evento mostrano variazioni mediane di 0,71 m locali e 0,78 m combinate.
Il ricevitore presenta inoltre un salto del proprio tempo di circa 19 ore.
Neppure questo caso dimostra vantaggio di rilevamento della rete rispetto ai
controlli locali. P2 resta aperto: servono un controllo benigno abbinato e un
attacco in cui l'evidenza locale non sia già decisiva, oppure va limitata la
rivendicazione del prodotto al contesto indipendente dell'incidente. Ulteriori
varianti amministrative dello stesso confronto non sostituiscono quei dati.

Il lavoro inverso resta una base scientifica riutilizzabile, con i limiti sotto
riportati. Questa variazione non chiude S2 e non avvia la vecchia campagna S3.

## Cosa abbiamo dimostrato

- G14 DOY246: una dimostrazione storica condizionale, errore esterno 31.017 m,
  raggio prospettico 5755.157 m, residuo del ricevitore escluso -0.846 m.
  Il singolo errore di 31 m non e una precisione generale garantita.
- G08 DOY249 e G12 DOY248: posizioni ricostruite, ma incertezza oltre il limite
  dichiarato; esiti conservati come `UNCERTAINTY_TOO_LARGE`.
- G12 DOY250 e G13 DOY247: dati insufficienti; nessuna posizione qualificata.
- Sorgenti, clock, bias, assetto dei riferimenti, coordinate e spostamenti
  delle stazioni sono stati confrontati con prodotti precisi e replay verificabili.
  Questi controlli migliorano la base fisica, non certificano l'incertezza totale.
- I recenti studi di maree e moto polare non spiegano i residui di riferimento
  ancora intorno a 0.9–1.0 m nelle due finestre esplorative di cinque minuti.
- Il nuovo confronto meteorologico conserva 72 campioni su nove stazioni e due
  giorni: differenze zenitali fino a 12.54 cm dal modello semplice, equivalenti
  fino a 70.02 cm a 10 gradi usando la medesima funzione di elevazione. E una
  sensibilita del modello. Il successivo replay RF con VMF3 completo misura
  miglioramenti dello 0.134%/0.838%, con tre stazioni peggiorate per giorno.

## Stato della ricerca inversa precedente

| Fase | Stato | Risultato necessario |
|---|---|---|
| S0: diagnosi | Consegnata | Cause e limiti degli eventi precedenti documentati |
| S1: cinematica sintetica | Consegnata | Posizione/moto con codice e variazione di distanza in simulazione |
| S2: misure vere | Aperta; avanzamento subordinato al nuovo obiettivo | Calibrazione fisica, continuita delle osservabili e incertezza difendibile |
| S3: conferma su nuovi dati | Non ancora avviata | Campioni nuovi, regole fissate prima dei dati, verifiche escluse |
| S4: prestazioni e prodotto | Da affrontare dopo S3 | Disponibilita, errori, incertezza e dominio d'uso misurati |

## Esito della fase reale su G12

La [prova sugli intervalli RF reali](../research/exploratory/REAL_TARGET_INTERVAL.md)
ha portato il codice e gli incrementi di fase di G12 nel solver esistente,
senza orbita del bersaglio nel fit. Il primo insieme di cinque stazioni fallisce
per geometria o fase assente (20/20 casi conservati). Una variante esplorativa
separata usa BOGT, con header GPS verificato: venti finestre complete, codice
accettato condizionalmente in 20/20, codice+fase in 5/20 e rigettato in 15/20.
Nei cinque casi ammessi la fase migliora le previsioni RF escluse, ma la
posizione rispetto all'oracolo storico migliora soltanto in 3/5 e peggiora in
2/5. L'RMS di posizione accoppiato e 49,88 m col solo codice e 55,41 m con
la fase; un caso di fase arriva a 120,68 m. L'oracolo e un confronto
retrospettivo, non un raggio d'incertezza.

**S2 rimane aperta per un motivo preciso:** gli incrementi di fase non
identificano il bias assoluto del codice specifico della stazione. La sua
ampiezza fisica e la covarianza completa non sono ancora vincolate; un metro
ipotetico di bias puo spostare la posizione fino a circa 70 m nel trasferimento
gia misurato. Una futura chiusura della ricostruzione indipendente richiede un
limite indipendente a quel modo o un'altra osservabile/geometria. Nel pivot
PNT si qualifica invece il budget del test di sicurezza specifico, senza
trasferire a esso una precisione orbitale non dimostrata. La campagna inversa
S3 resta subordinata a un inviluppo totale credibile con margine utile.

Il [controllo diretto di identificabilita](../research/exploratory/REAL_TARGET_BIAS_IDENTIFIABILITY.md)
conferma il limite sulla geometria G12 reale: aggiungendo quattro contrasti
liberi di bias per stazione, il rango numerico e 38/40 col codice in 20/20
archi e 39/40 nei cinque archi di fase ammessi. La fase recupera una direzione,
ma ne lascia una che accoppia bias e posizione. La risposta a +1 m omesso resta
circa 70–77 m; nessuna ampiezza fisica del bias e stata misurata.

La [roadmap scientifica](SCIENTIFIC_ROADMAP.md) resta il piano originale.
Il disegno di 24 tentativi contiene ancora parametri da fissare: non equivale
a una campagna gia pronta o validata. Nessuna percentuale di completamento
puo sostituire queste verifiche sperimentali.

## Consegne e passi residui del percorso inverso

Il riepilogo seguente conserva il percorso S2/S3. La priorita operativa e P2
nel piano PNT, non la prosecuzione automatica di ogni voce storica.

1. Collegamento meteorologico consegnato sulle due finestre esposte: griglie
   alle coordinate ammesse, 88 confronti numerici con la routine originale e
   616 calibrazioni riuscite. Il modello completo riduce i residui soltanto
   dello 0.134%/0.838%; tre stazioni peggiorano per ciascun giorno. Lo scarto
   del catalogo ALGO viene evitato usando le griglie, senza modificarne i dati.
2. Prima estensione temporale consegnata: un'ora G14, sette stazioni, 847
   calibrazioni qualificate. Stima delle correzioni nella prima mezz'ora e
   verifica nella seconda: RMS dei contrasti 0.974 -> 0.938 m con offset
   condivisi per satellite. Secondo arco 05:00–06:00 completato: altre 847
   calibrazioni valide, RMS 1.047 -> 1.003 m con stima recente (−4.15%) e
   1.015 m trasferendo le correzioni precedenti (−3.04%). Il modello direzionale
   trasferito peggiora tutte le stazioni; quello per coppia stazione/satellite
   non supporta nessun blocco completo del test. Verifica del 5 settembre
   consegnata: altre 847 calibrazioni, RMS 1.010 -> 0.931 m (−7.80%), tutte le
   stazioni migliorate; anche le cinque comuni migliorano (−5.77%). Cambiano
   due stazioni, riferimenti e bersaglio escluso: replica del metodo su un altro
   campione esposto, non effetto isolato del giorno né conferma indipendente.
   Confronto rapid/final CODE consegnato sugli stessi dati e collegamenti:
   RMS di base 1.010 -> 0.988 m (−2.17%), ma dopo correzione condivisa resta
   0.931 m in entrambi i casi. Anche trasferendo le correzioni rapid ai dati
   final si migliora: 0.935 m, −5.38%, tutte le stazioni. Il cambio di prodotti
   non risolve la struttura dominante; due prodotti CODE non sono una verita
   indipendente. Trasferimento alla settima stazione esclusa ora consegnato:
   RMS 0.953 m con entrambe le famiglie, miglioramento aggregato 5.64% rapid
   e 3.55% final, tutti i 3942 campioni supportati. Migliorano sei/cinque
   stazioni: AREQ peggiora in entrambi i casi, DRAO leggermente con i final.
   La correzione non va promossa come beneficio universale. I prodotti a monte
   possono ancora includere la stazione esclusa dalla stima locale.
3. Collegamento errori-posizione/moto consegnato su geometrie sintetiche:
   cinque casi validi e uno sotto la maschera, tutti conservati. Un modo comune
   per stazione di ampiezza ipotetica 1 m produce 11–166 m sulla posizione,
   pur essendo invisibile nei contrasti centrati. Non sono errori misurati o
   raggi al 95%; il budget reale e i suoi limiti restano invariati.
   Test con riferimenti esclusi consegnato: 22 rotazioni, 3942 percorsi valutati
   e 5452 assenze conservate. Ricalibrando senza il satellite in esame, RMS
   1.135 -> 1.132 m: beneficio della correzione condivisa soltanto 0.26%,
   con BOGT e BRAZ peggiorate. I contrasti fra stazioni migliorano dello 0.86%.
   Manteniamo quindi la versione senza correzione come base; nessuna riduzione
   del limite di errore o promozione della correzione in produzione.
   Collegamento fase reale consegnato sui due cohort esposti: 6299 intervalli
   valutati, sette/cinque stazioni utilizzabili; due esclusioni del 5 settembre
   conservate. La componente differenziale della fase e circa 0.19–0.24 mm/s,
   ma quella comune alla stazione resta circa 14 mm/s. Trasferendo questi errori
   nel modello a intervalli esistente, su traiettorie sintetiche e coordinate
   reali, la fase grezza viene rigettata in 12/12 finestre. Corretta con gli
   altri riferimenti, migliora la velocita in 9/12, ma peggiora la posizione
   iniziale in 8/12 e quella futura in 5/12. Un bias costante ipotetico di 1 m
   conserva fino a circa 70 m di risposta sulla posizione, quasi invariata.
   Questo e un risultato ibrido di sensibilita, non una nuova ricostruzione
   indipendente o una covarianza qualificata. L'integrazione successiva sul
   bersaglio reale e descritta sopra; resta da vincolare il bias assoluto.
   Nessuna riduzione del limite storico di 20 m sulla misura.
4. Congelare il metodo e provarlo su dati nuovi, conservando tutti gli esiti.
5. Riprendere API e sito quando i risultati stabiliscono cosa il servizio puo
   promettere e quando deve dichiarare che non sa determinare una posizione.

Studi: [sensibilita zenitale](../research/exploratory/ATMOSPHERE_ZENITH.md) e
[calibrazione RF con VMF3](../research/exploratory/VMF3_REFERENCE_CALIBRATION.md).
Ultimo studio: [fase reale e trasferimento al modello a intervalli](../research/exploratory/REAL_PHASE_INFORMATION.md).
Risultato piu recente: [G12 reale, fit RF e confronto retrospettivo](../research/exploratory/REAL_TARGET_INTERVAL.md).
Commit, push, CI e merge ordinario restano parte del workflow; deploy separato.

The one-hour replay entry point is `research.exploratory.hour_reference_checked`: it pins auxiliary bias/antenna inputs and revalidates the existing frame/loading chains before unchanged v2 calculation. Frozen v1/v2 evidence is preserved.
