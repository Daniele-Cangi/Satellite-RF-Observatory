# S2 — Calibrazione dei ritardi lenti condivisi

Il nuovo modulo `slow_calibration.py` aggiunge un coefficiente quadratico
di cammino per ricevitore, stimato dai soli codici dei riferimenti. Il modello
target di posizione, velocità, accelerazione e clock resta quello precedente.
La flessibilità aggiunta riguarda la calibrazione, con incertezza propagata.

## Modello e ordine

La base per ogni ricevitore è [1, t, (t/|t_iniziale|)²]. I primi due
coefficienti sono offset e drift del clock; il terzo rappresenta un ritardo
additivo del cammino, non un clock fisico quadratico. Si usa la stessa base
per codice e fase IF solo sotto l'ipotesi sintetica di ritardo condiviso.
La base è fissata prima del fit e non scelta dai valori target.

I 308 residui sintetici di codice dei riferimenti stimano 21 coefficienti
via GLS/SVD. Il test dei codici ha 287 gradi di libertà. Le 280 differenze
di fase dei riferimenti restano inutilizzate nella stima e verificano la
previsione quadratica sugli stessi estremi. I due test mantengono p < 0,01.
Un rifiuto ferma la catena prima del caricamento target.

Il ritardo quadratico stimato viene sottratto da codice e cammino di fase
target; i rate sono differenze delle fasi corrette. Il fit usa gli offset e
drift ricavati dagli stessi riferimenti. Nessuna fase target stima direttamente
i coefficienti della correzione di calibrazione.

## Errore della correzione e covarianza

La correzione non viene trattata come esatta. Con K guadagno dei riferimenti
e Q matrice della base quadratica target, la trasformazione dei codici corretti
ha blocco identità sul codice target e −Q Kq sui codici dei riferimenti.
La fase ha blocchi D e −D Q Kq. I clock sono Kc sui riferimenti; le coordinate
restano identiche. La covarianza del fit è T C Tᵀ della matrice grezza completa.

Questa operazione conserva rumore della correzione, correlazioni con clock,
target e coordinate. Il test della fase usa a sua volta D fase −D H K codice
con covarianza completa. Sono registrati anche i blocchi gate/fit: covarianza
marginale e tassi dopo selezione non vengono confusi. Non si ricalibrano
le soglie dal risultato dei casi.

La correzione quadratica incerta modifica anche i pesi del fit. Per questo
può ridurre la sensibilità a un errore presente soltanto sul target anche
quando i riferimenti non ne stimano alcuna correzione media. Non significa
che tale errore sia stato misurato o fisicamente rimosso dalla calibrazione.

## Disegno di sviluppo e verifica esclusa

Si confrontano due modelli sugli stessi cinque casi: nominale, curvatura
condivisa da 0,1 m, curvatura solo target da 0,1 m, oscillazione condivisa
da 0,02 m e salto di fase nei riferimenti. Le curve note sono test di sviluppo
già osservati; migliorare questi esempi non costituisce conferma indipendente.
La covarianza grezza e le soglie sono quelle dello studio precedente.

Quando il fit è accettato, si prevede un ottavo ricevitore sugli estremi
futuri 30 e 60 secondi. I disturbi di questo studio riguardano il ricevitore 0
e sono assenti su quello escluso, la cui calibrazione è assunta con covarianza
indipendente dichiarata. La previsione viene serializzata e hashata prima
della valutazione con il generatore inerziale indipendente. Non si rilegge
un'orbita target e non si accede a nuovi dati reali.

## Conclusione e lavoro aperto

Il bias noto da 100 m viene rimosso nel caso esattamente quadratico condiviso,
ma aumenta l'incertezza locale. Il residuo differenziale non scompare e il
modello non qualifica qualunque errore lento, direzionale o dispersivo.
Servono ampiezze giustificate, un disegno di conferma non usato per costruire
la base e verifiche di copertura, selezione e resto non lineare. I residui
geometrici dei riferimenti qui sono ancora inventati; una pipeline RINEX
target e la qualifica RF restano aperte. S3 e sito restano sospesi.

[Risultati e riproduzione](results/S2_SLOW_CALIBRATION_REPORT.md).
