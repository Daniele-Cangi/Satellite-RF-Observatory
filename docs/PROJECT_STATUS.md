# Stato del progetto — 17 settembre 2026

## Obiettivo

Ricostruire posizione e moto di un satellite da osservazioni RF pubbliche
ottenute via Internet, senza usare l'orbita del bersaglio nella stima. Prima
delle verifiche esterne, dichiarare incertezza e predizioni per dati esclusi.
Il risultato deve essere riproducibile, con fallimenti e limiti visibili.

Il prodotto finale potra offrire verifiche per satelliti ed epoche supportati.
Non abbiamo ancora un servizio generale di localizzazione in tempo reale.
Il sito resta in pausa: archivio di cinque eventi e worker locale sono consegnati,
ma la priorita e dimostrare la capacita scientifica su misure vere.

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

## Piano e stato

| Fase | Stato | Risultato necessario |
|---|---|---|
| S0: diagnosi | Consegnata | Cause e limiti degli eventi precedenti documentati |
| S1: cinematica sintetica | Consegnata | Posizione/moto con codice e variazione di distanza in simulazione |
| S2: misure vere | In corso | Calibrazione fisica, continuita delle osservabili e incertezza difendibile |
| S3: conferma su nuovi dati | Non ancora avviata | Campioni nuovi, regole fissate prima dei dati, verifiche escluse |
| S4: prestazioni e prodotto | Da affrontare dopo S3 | Disponibilita, errori, incertezza e dominio d'uso misurati |

La [roadmap scientifica](SCIENTIFIC_ROADMAP.md) resta il piano originale.
Il disegno di 24 tentativi contiene ancora parametri da fissare: non equivale
a una campagna gia pronta o validata. Nessuna percentuale di completamento
puo sostituire queste verifiche sperimentali.

## Prossimo tratto di lavoro

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
3. Trasportare errori e correlazioni fino a posizione e moto; validare le
   osservabili aggiuntive e l'incertezza senza aggiustarla dopo le conferme.
   Questo e ora il prossimo passo: misurare la sensibilita del solver a errori
   indipendenti, comuni per stazione e correlati nel tempo, mantenendo visibili
   anche i modi che i contrasti RF centrati non permettono di stimare.
4. Congelare il metodo e provarlo su dati nuovi, conservando tutti gli esiti.
5. Riprendere API e sito quando i risultati stabiliscono cosa il servizio puo
   promettere e quando deve dichiarare che non sa determinare una posizione.

Studi: [sensibilita zenitale](../research/exploratory/ATMOSPHERE_ZENITH.md) e
[calibrazione RF con VMF3](../research/exploratory/VMF3_REFERENCE_CALIBRATION.md).
Ultimo studio: [trasferimento a ricevitori esclusi](../research/exploratory/SPATIAL_REFERENCE_TRANSFER.md).
Commit, push, CI e merge ordinario restano parte del workflow; deploy separato.

The one-hour replay entry point is `research.exploratory.hour_reference_checked`: it pins auxiliary bias/antenna inputs and revalidates the existing frame/loading chains before unchanged v2 calculation. Frozen v1/v2 evidence is preserved.
