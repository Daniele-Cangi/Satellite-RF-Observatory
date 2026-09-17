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
  sensibilita del modello; il miglioramento dei residui RF non e ancora misurato.

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

1. Collegare meteorologia, coordinate e ritardi secchi/umidi alla calibrazione
   dei soli riferimenti; risolvere lo scarto geografico ALGO nei dati VMF3.
2. Ampliare gli archi RF e le elevazioni; distinguere atmosfera, risposta del
   ricevitore/antenna e multipath, verificando predizioni su tempi esclusi.
3. Trasportare errori e correlazioni fino a posizione e moto; validare le
   osservabili aggiuntive e l'incertezza senza aggiustarla dopo le conferme.
4. Congelare il metodo e provarlo su dati nuovi, conservando tutti gli esiti.
5. Riprendere API e sito quando i risultati stabiliscono cosa il servizio puo
   promettere e quando deve dichiarare che non sa determinare una posizione.

Dettagli del nuovo studio: [atmosfera zenitale](../research/exploratory/ATMOSPHERE_ZENITH.md).
Commit, push, CI e merge ordinario restano parte del workflow; deploy separato.
