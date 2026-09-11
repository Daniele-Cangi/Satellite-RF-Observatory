# S2 — Controllo della fase prima del fit target condiviso

`shared_phase_gate.py` collega il controllo inutilizzato degli incrementi
di fase dei riferimenti al fit con calibrazione comune. Il clock resta
stimato dai soli codici. Il nuovo modulo usa residui sintetici dopo
sottrazione geometrica ideale: non è una nuova qualifica RINEX o RF.

## Ordine e covarianza

Si verificano le identità non-target, poi i residui di codice dei riferimenti.
Un rifiuto del codice ferma la procedura prima della decodifica delle fasi.
Superato il codice, si differenziano gli estremi delle fasi e della previsione
affine ricavata dai codici. Un rifiuto di fase impedisce il caricamento target.
Solo dopo entrambi i controlli si invoca il precedente fit condiviso immutato.

La covarianza estesa conserva il vecchio ordine grezzo e aggiunge i cammini
di fase dei riferimenti: 308 estremi in ordine epoca/ricevitore/riferimento.
Questi generano 280 incrementi. Con D differenza temporale, H matrice del
clock e K guadagno GLS dei codici, la mappa del residuo ha blocchi −D H K
sui codici dei riferimenti e D sui cammini di fase. La sua covarianza è
G C Gᵀ, inclusi i termini incrociati. Non si sommano errori indipendenti
quando il medesimo disturbo è condiviso.

La fase non stima coefficienti del clock: il test usa 280 gradi di libertà
e soglia p < 0,01, ossia costo maggiore di circa 337,974. Il codice mantiene
i precedenti 294 gradi di libertà e la stessa soglia marginale. Sono restituiti
anche i blocchi di covarianza fra residui del gate e dati compressi del fit.
I due test e il fit non sono indipendenti. Il fit conserva la covarianza
marginale originale, senza correzioni condizionate al passaggio del gate:
copertura dopo selezione e tasso globale di falso rifiuto restano aperti.

## Disegno fissato

Si riusano geometria inventata, finestre, codici, clock e covarianza del
precedente studio. Le nuove fasi di riferimento assumono sigma indipendente
0,01 m, correlazione codice/fase 0,1 e la stessa deriva casuale comune
di sigma 0,01 m/s già dichiarata. Queste sono ipotesi di progetto sintetiche.

Otto casi sono conservati: nominale, deriva affine condivisa, deriva solo
target, curvatura condivisa da 0,1 m, curvatura condivisa da 1 m, salto di
0,5 m in una fase di riferimento, ambiguità costante aggiunta e salto sui
codici dei riferimenti. Non si ritoccano soglie né ampiezze dopo gli esiti.
Non si eseguono estrazioni casuali nello studio dei casi; il rumore dichiarato
serve ai pesi e ai test. La verifica Monte Carlo separata controlla soltanto
la trasformazione della covarianza.

## Risultato e confine

Il salto da 0,5 m e la curvatura da 1 m sono respinti prima del target.
La curvatura da 0,1 m ha costo di fase 34,32, sotto la soglia 337,974, e
raggiunge ancora il fit con circa 100 m di errore posizione. Il p-value
vicino a uno in questo caso senza rumore non misura la probabilità che il
modello sia corretto. Non è una stima empirica della potenza del test.

Questa prova collega un controllo utile ma ne dimostra un limite. Abbassare
la soglia sulla base del caso già visto non fornirebbe una nuova validazione.
Prima di S3 occorre un disegno separato che tratti errori temporali piccoli
e persistenti, distinguendo la parte condivisa da quella differenziale e
misurandone l'impatto anche sul ricevitore escluso. Ampiezze fisicamente
giustificate e copertura totale non derivano dai residui da soli.

[Report e riproduzione](results/S2_SHARED_PHASE_REPORT.md). Tutti i risultati
restano `real_rf_qualified=false`; sito e acquisizioni target sono sospesi.
