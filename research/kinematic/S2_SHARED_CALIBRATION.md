# S2 — Calibrazione comune di riferimenti e target

Il nuovo modulo `shared_calibration.py` costruisce le calibrazioni compresse
a partire da residui di codice espliciti dei riferimenti. Propaga la loro
covarianza con le misure target invece di assumere i clock indipendenti.
Questa è una verifica sintetica del collegamento statistico, non una nuova
catena RINEX qualificata. Tutti i risultati conservano `real_rf_qualified=false`.

## Dati e ordine causale

Si dichiarano quattro identità di riferimento distinte ed escluse dal target,
sette ricevitori e undici epoche da −300 a 0 secondi. I 308 residui di codice
dei riferimenti sono inventati dopo una sottrazione geometrica ideale.
Non vengono generate o lette effemeridi target. Il modello dei residui è
offset + drift del clock per ricevitore, per un totale di 14 coefficienti.

La covarianza grezza ha ordine: 77 codici target, 77 cammini IF di fase target,
308 residui riferimento (epoca/ricevitore/riferimento), 21 coordinate terrestri.
Prima dei valori target si controllano identità e residui dei riferimenti.
Il test GLS ha 294 gradi di libertà e soglia p < 0,01. Un rifiuto impedisce
l'invocazione della funzione che carica i valori target, verificata da un test.

Un riferimento accettato qui soddisfa solo un controllo sintetico sui codici.
Questo modulo non sostituisce il gate degli incrementi di fase dei riferimenti,
né ne attribuisce automaticamente lo stato `REFERENCE_PHASE_MODEL_ACCEPTED`.
Il fit inverso riceve lo stato di calibrazione sintetica compressa già previsto.

## Compressione con correlazioni

Con H matrice dei clock e Crr covarianza dei residui di riferimento, il guadagno
è K = (Hᵀ Crr⁻¹ H)⁻¹ Hᵀ Crr⁻¹, calcolato mediante SVD senza equazioni normali.
La matrice completa T contiene identità per codici e coordinate, differenze
per i cammini di fase e K per i riferimenti. Il fit riceve T C Tᵀ.

Sono mantenuti sia gli estremi condivisi delle fasi sia i blocchi target/clock.
Nello studio una deriva casuale comune per ricevitore di sigma 0,01 m/s
compare nei codici target, nella fase e nei residui dei riferimenti. La sua
covarianza fase-rate/clock-drift è 0,0001 (m/s)²; il codice a −300 s ha
covarianza −0,03 m²/s con il drift stimato. Nove test controllano la trasformazione,
anche con 12.000 estrazioni grezze.

Il modello assume inoltre sigma codice target 20 m, fase 0,01 m, residuo
riferimento 3 m e coordinate 0,5 m. Sono ipotesi sintetiche fissate, non
prestazioni empiricamente accertate. Il rumore non è ristimato dai residui.
La covarianza compressa è marginale non condizionata al passaggio del gate:
selezione, copertura e test congiunti rimangono da calibrare. Non si afferma
che scartare i residui dei riferimenti sia una compressione sufficiente per
ogni modello possibile di errori condivisi.

## Cinque casi senza selezione

Si conservano nominale, deriva lineare di 0,01 m/s condivisa sul ricevitore 0,
la stessa deriva solo sul target, ritardo curvo 0,1 (t/300)² m condiviso e
salto di 300 m su un riferimento. Le perturbazioni deterministiche sono
aggiunte ai cammini, non a una simulazione completa dell'elettronica del clock:
le piccole differenze di tempo fisico di ricezione non vengono modificate.
Per questo la compensazione affine non è matematicamente identica a un
cambio esatto del clock del ricevitore nel generatore.

Il confronto affine usa gli stessi dati target e la stessa covarianza;
cambiano solo i residui dei riferimenti. Non si ampliano finestre, non si
scambiano ricevitori, non si ritoccano soglie dopo l'esito.

Il risultato mostra che la parte comune affine può essere compensata, mentre
una curvatura condivisa non rientra nel modello di clock affine. Il caso curvo
resta accettato nel presente gate di soli codici, ma sposta la posizione di
circa 100 m. Non deduce quale esito avrebbe il separato gate di fase, che
qui non viene eseguito. Risultati nel [report](results/S2_SHARED_CALIBRATION_REPORT.md).

## Prossimo collegamento

Occorre integrare il controllo inutilizzato della fase dei riferimenti con
questa compressione e verificarne l'effetto sugli errori differenziali prima
di una catena RINEX target. Restano aperti i ritardi dipendenti dalla direzione,
i bias variabili, la qualifica delle ampiezze e il bilancio totale degli errori.
Il nuovo studio non acquisisce misure target, non esegue una nuova conferma
esclusa e non autorizza S3 o il sito.
