# Stato del progetto — 3 ottobre 2026

## Obiettivo

La direzione attiva e il [piano di sicurezza PNT](PNT_SECURITY_PLAN.md):
confrontare osservazioni GNSS locali e osservazioni esterne via Internet,
valutare geometria e tempo e produrre evidenze riproducibili per gli incidenti.
Il primo caso proposto e un ricevitore GPS fisso a coordinate note.

La [CLI PNT riutilizzabile](../pnt/README.md) ora analizza registrazioni RINEX
di un sito fisso: controlli locali e abbinati alla rete, doppie differenze,
clock relativo, disaccordo fra riferimenti e lacune in un unico rapporto.
La [verifica software sui tre file gia esposti]
(../research/exploratory/PNT_FIXED_SITE_ANALYSIS.md) produce diagnostica su
tutte le 20 epoche richieste; il report storico ds7 resta identico dopo il
riuso dei calcoli. Non e ancora un rilevatore qualificato: P2 richiede ancora
la prova del beneficio e il tempo assoluto un testimone indipendente.

Il [confronto di sviluppo riutilizzabile]
(../research/exploratory/PNT_COMPARISON_BENCHMARK.md) aggiunge `python -m pnt compare`:
baseline, calibrazione e valutazione separate, stesso supporto locale/rete e
rampe software nelle pseudodistanze prima del fit. Nel corpus gia esposto il
combinato supera la soglia in 9/60 epoche originali, il locale in 6/60; non si
dimostra un vantaggio a pari falsi allarmi. Le rampe confermano la cancellazione
del clock comune e del disturbo condiviso, e la contaminazione da un riferimento
alterato. Tutte le 15 varianti e i campioni non valutabili restano nel report.
Sono risposte a perturbazioni software, non prestazioni su attacchi RF reali.

La [prova di trasferibilita su intervalli successivi]
(../research/exploratory/PNT_REFERENCE_TRANSFER.md) aggiunge `python -m pnt transfer`:
un solo coefficiente locale/rete imparato sul training e applicato senza
adattamenti a epoche successive, confrontato con nessuna correzione e
sottrazione unitaria. Due intervalli disgiunti e le tre rotazioni delle stazioni
producono sei confronti, ciascuno con 60 epoche di training e 120 di valutazione.
La sottrazione unitaria peggiora tutti e sei; il coefficiente imparato migliora
tre casi e peggiora tre, con riduzioni dell'errore quadratico medio fra
-1,00% (peggioramento) e +2,24%. Le classi di supporto e i peggioramenti per epoca restano
visibili. Non emerge un beneficio ripetibile sufficiente a promuovere questa
correzione a rilevatore; nessuna soglia del confronto precedente e modificata.
Si tratta di previsione di residui su dati gia esposti, senza etichette benigne,
non di conferma prospettica. Su questa topologia non proseguire con altre
varianti della stessa regressione per cercare un risultato positivo: la
prossima estensione deve motivare un diverso effetto fisico o una topologia
di riferimenti che lo osservi, prima di valutarne il beneficio P2.

Il [confronto dei messaggi di navigazione]
(../research/exploratory/PNT_NAVIGATION_WITNESS.md) apre un meccanismo diverso:
`python -m pnt navigation` confronta la stessa issue GPS dichiarata localmente
con archivi esterni, mantenendo messaggi mancanti, discordanti e conflitti fra
fonti. Nel primo controllo software, una modifica comune di 0,954 microsecondi
dei clock satellitari sposta il clock stimato da codici TXAU reali di 285,905 m,
ma cambia i residui per satellite di meno di 1 mm. I campi alterati restano
discordanti rispetto all'archivio esterno. I messaggi locali sono varianti
**sintetiche** dell'archivio NOAA: questo dimostra un meccanismo e il codice,
non un beneficio su un attacco RF registrato o a pari falsi allarmi.
Il [confronto della registrazione JammerTest 2.1.1]
(../research/exploratory/PNT_NAVIGATION_JAMMERTEST_211.md) aggiunge l'adattatore
SFRBX GPS L1 C/A: 424 messaggi in 9.387 SFRBX multi-GNSS, due pacchetti
corrotti esclusi e conteggiati solo con recupero esplicito. Tre cicli completi
sono decodificabili senza riusare frammenti di altri cicli; 204 restano incompleti.
G17 e G21 concordano con il NAV NOAA dell'11 settembre 2024. G14 dichiara
invece il 1 ottobre e non trova la stessa issue nell'archivio del giorno: resta
evidenza insufficiente, non una discordanza fra campi della stessa issue.
La modalita UBX conserva l'intero file, anche i messaggi con `toc` fuori giorno;
la data dichiarata serve soltanto a risolvere l'era della settimana GPS.
La parita radio resta dichiarata dal ricevitore, non verificata indipendentemente.
L'episodio aveva gia anomalie locali evidenti: P2 non dimostra ancora beneficio
aggiuntivo a pari falsi allarmi. Il prossimo passo deve trovare un confronto
benigno/alterato abbinato che possa misurarlo, prima di moltiplicare analisi su
questo file. La concordanza dei messaggi non autentica distanze o tempo;
la provenienza indipendente delle fonti resta da qualificare.

Il [confronto abbinato OBS/NAV](../research/exploratory/PNT_NAVIGATION_COMPARISON.md)
aggiunge `python -m pnt navigation-compare`: soglie sui soli dati originali
di calibrazione, controlli locali sui residui e sul passo del clock, e
testimone esterno legato ai messaggi effettivamente usati. Su 120 epoche
successive della stazione NYA2, il bias comune sintetico nei messaggi NAV
lascia 7 superamenti locali come nell'originale, ma differisce dall'archivio
in tutte le epoche, incluse 113 senza superamenti locali. La deriva comune
ha 9 superamenti locali e 111 epoche discordanti senza superamenti; il
peggioramento resta visibile. Alterare invece solo i codici mantenendo il
NAV produce 74 superamenti locali e nessuna discordanza di messaggio:
la compatibilita NAV non convalida il segnale. Sono casi software su dati
gia esposti, con lo stesso archivio come origine delle varianti e testimone;
non un confronto benigno/attacco fisico, una fonte indipendente qualificata
o una misura dei falsi allarmi. P2 resta aperto, ma ora il confronto puo
essere applicato a un caso reale adeguato senza un nuovo esecutore o sigillo.

La [prova RF pubblica con ricevitore software]
(../research/exploratory/PNT_PUBLIC_RF_NAVIGATION.md) ha decodificato 100 secondi
di campioni GPS L1 senza nuovo hardware. La CLI ammette ora anche NAV RINEX 3
GPS, con gli stessi campi e criteri di confronto. Tutti i cinque messaggi
esportati da GNSS-SDR risultano discordanti con NOAA: il controllo dei bit
individua errori nell'esportazione del flag P e dell'URA, precisione degli
archivi e differenze nei codici L2 di tre satelliti. I risultati e i dieci
cicli completi, oltre ai cinque incompleti, restano visibili; non sono
rilevamenti di attacco. Prima della coppia benigno/attacco P2 serve un
confronto riutilizzabile che qualifichi queste rappresentazioni, conservando
variazioni reali di un bit e ambiguita. Non occorre acquistare sensori per
proseguire questo sviluppo; la concordanza NAV resta distinta dall'autenticita RF.

La [qualifica delle rappresentazioni LNAV]
(../research/exploratory/PNT_NAVIGATION_REPRESENTATION.md) aggiunge
`navigation --qualify-lnav`, conservando il confronto precedente. Ogni campo
deve ammettere un unico valore trasmissibile entro l'intervallo scritto;
nessuna correzione al bit piu vicino o precisione inferita. Sui dieci cicli
CTTC completi tutti i 270 campi locali sono risolvibili, ma le rappresentazioni
NOAA hanno 136 campi senza candidato, dieci zeri af2 ambigui e sei metadati L2
invalidi. Tutti i cicli restano non qualificati; le cinque discordanze native
restano invariate e non diventano attacchi. I test preservano cambiamenti di
un bit, conflitti e casi mancanti. La revisione V2 usa limiti razionali esatti
per la conversione angolare e rende espliciti URA/TGD indisponibili anche da
UBX, senza ammetterli nel confronto precedente. Il risultato V1 resta conservato;
la correzione non cambia gli esiti CTTC. Il prossimo prerequisito e un testimone
Internet che preservi i valori trasmessi o abbia limiti di conversione
documentati, prima del confronto benigno/attacco P2.

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

La [verifica separata delle due stazioni]
(../research/exploratory/PNT_JAMMERTEST_211.md) evita che la mediana della rete
nasconda variazioni opposte: nella rampa 2.1.1 il disaccordo mediano sui 154
campioni supportati è 0,55 m, contro 0,42 m prima dell'evento. Il risultato
descrive contesto esterno per questo osservabile, non un'autenticazione del
segnale locale. Il confronto originario resta conservato e il nuovo output
versionato aggiunge il controllo di accordo, senza cambiare gli esiti chiusi.

Decisione P2: il risultato utilizzabile oggi è un **rapporto tecnico
riproducibile di contesto indipendente per un episodio offline**. Non
promuovere l'allarme a verifica del fix o
del timestamp e non dichiarare un beneficio di rilevamento della rete. La
prova successiva richiede nello stesso sito un periodo benigno e un attacco
meno evidente localmente, osservazioni grezze locali con qualità/clock/PVT,
due riferimenti contemporanei e una base temporale o verità indipendente.
Una [nuova qualifica TEXBAT/NOAA]
(../research/exploratory/PNT_TEXBAT_NOAA.md) ha trovato osservabili TEXBAT
gia elaborati e due stazioni fisicamente distinte con GPS C1 contemporaneo. Nel ds7
time-push, 110 coppie su dieci epoche mostrano una variazione mediana locale
di 168,86 m, contro 0,53 m nelle differenze fra satelliti: una modalita cieca
della sola geometria differenziale. Il confronto usa cleanStatic come
controfattuale esposto; non dimostra un allarme di rete, un clock indipendente
o un vantaggio a pari falsi allarmi. La combinazione completa richiesta da P2
resta dunque da dimostrare. [FGI-JSDR]
(https://www.maanmittauslaitos.fi/en/research/research/gnss-specialists/fgi-gnss-jamming-and-spoofing-dataset-repository-fgi-jsdr)
pubblica soprattutto RF da elaborare; il
[corpus di Kunming](https://pmc.ncbi.nlm.nih.gov/articles/PMC11220923/)
riporta osservabili ma anche forti distorsioni locali; i file completi di
[CG-SpoofGNSS](https://github.com/agilawood4/CG-SpoofGNSS) non risultano ancora
rilasciati. Il [confronto del clock TEXBAT/NOAA]
(../research/exploratory/PNT_TEXBAT_CLOCK_CONTEXT.md) usa le stesse 14 epoche
e un modello broadcast comune: il massimo pulito e 1,17 m sul solo ricevitore
e 1,23 m dopo la correzione di rete; durante il time-push ds7 entrambi i
canali arrivano a circa 312 m. Le due stazioni forniscono contesto stabile,
ma non un beneficio di rilevamento per questo attacco gia evidente localmente.
La posizione locale usata viene dal cleanStatic pubblicato, non da un rilievo
indipendente. Il passo ad alto valore e cercare un episodio con controllo
locale ambiguo e base fisica difendibile, non aggiungere altri sigilli o
varianti JammerTest.

La [qualifica mirata di una traiettoria simulata]
(../research/exploratory/PNT_P2_RECORDING_DECISION.md) mostra perché un'altra
registrazione dello stesso archivio non colma P2: nella finestra GPS 2.3.5
restano 33 coppie su 16 epoche, contro una sola coppia nella finestra Galileo
precedente. La pausa fra le due trasmissioni non è un controllo benigno
certificato; il CSV non identifica senza ambiguità i codici e il registro
secondario contraddice i nomi degli scenari. Il rapporto fissa i dati minimi da
ottenere per la prossima prova, senza introdurre nuovi sigilli o soglie.

L'[intake RINEX per sito fisso](../research/exploratory/PNT_FIXED_SITE_INTAKE.md)
riusa il parser e l'abbinamento esistenti: su tre stazioni pubbliche distinte
del giorno 255/2024 trova 28.515 righe satellite-epoca comuni in 2.880 epoche,
con 8–12 satelliti per epoca. È una verifica della disponibilità dei dati,
senza etichette d'attacco, verità locale indipendente o misura del beneficio
della rete. La registrazione decisiva descritta sopra resta da ottenere.

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
