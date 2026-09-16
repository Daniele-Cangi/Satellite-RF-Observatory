# Struttura e prevedibilità dei residui dei riferimenti

Prova esplorativa del 16 settembre 2026, sorgenti eseguiti nel commit `3d817c9`.
Usa i prodotti e la calibrazione con PCO completo della
[prova d'assetto](REFERENCE_ATTITUDE.md), senza nuovi download e senza stimare
nuovamente il bersaglio. Gli archivi e i rapporti precedenti restano invariati.

## Domanda fisica

Un residuo di calibrazione può contenere effetti del satellite, del ricevitore,
delle coordinate, dell'antenna e della propagazione. Questa prova misura quanto
di tale struttura predice altri tempi della stessa breve finestra, prima di
trasformare una componente empirica in una correzione del ricevitore.

Le [note ESA sul multipath](https://gssc.esa.int/navipedia/index.php/Multipath)
descrivono effetti dipendenti dalla geometria e dalla frequenza, differenti per
codice e fase. Una dipendenza direzionale dei residui non identifica quindi
da sola la risposta dell'antenna. Anche un errore delle coordinate della stazione
genera, al primo ordine, una proiezione sulla direzione osservata.

## Input e coordinate osservabili

Il runner verifica gli hash degli input e dei sorgenti legati ai rapporti di
assetto. Ricostruisce i residui dal codice IF dei soli riferimenti e dal modello
CODE completo, tenendo fissi i clock della calibrazione precedente. La differenza
massima dal replay dei residui salvati è zero nei due casi eseguiti.
Le direzioni ENU sono calcolate al ricevitore, usando la stessa emissione e
rotazione terrestre del modello; non si usa geometria del bersaglio.

Si conserva ogni collegamento osservato: 716/734 valutati per G14 e 747/847
per G12. I 118 esclusi dai set broadcast originali rimangono espliciti.
Le serie stazione/satellite sono rispettivamente 66 e 69.

Per ogni stazione/epoca, con n riferimenti, si usa:

```text
P = I - 1*1.T/n
y = P*(codice_IF_corretto - modello)
X = P*(caratteristiche del modello descrittivo)
```

Il clock comune è già eliminato; non può essere ricostruito dai soli residui.
Si rimuovono 77 coordinate comuni per evento, lasciando 639/670 dimensioni
di contrasto. Anche errori originariamente indipendenti con varianza unitaria
produrrebbero covarianza P: varianza diagonale `1-1/n` e correlazione fuori
diagonale `-1/(n-1)`. Il termine comune `sigma²*1*1.T` scompare per qualunque
ampiezza. Non è possibile dedurre la covarianza totale degli errori da PΣP.T.
Questa è un'identità del confronto a geometria fissata, non una qualificazione
del trasferimento completo al bersaglio.

## Quattro modelli e due separazioni temporali

1. **Zero**: nessun termine descrittivo aggiuntivo.
2. **Satellite condiviso**: una costante per satellite, comune alle stazioni.
3. **Direzione per stazione**: tre coefficienti ENU moltiplicati per la direzione
   del collegamento. Possono descrivere più cause fisiche, non solo l'antenna.
4. **Stazione/satellite**: una costante distinta per ogni collegamento.

Il confronto principale stima i coefficienti sulle prime cinque epoche e li
applica alle ultime sei. Il controllo inverso usa le ultime cinque per predire
le prime sei. In ciascuna separazione i tempi sono disgiunti; i due confronti
riutilizzano la stessa finestra esposta e non sono repliche indipendenti.

Si usa least squares non pesato, con SVD e soglia relativa 1e-12. Le colonne
derivano soltanto dai dati di addestramento. La soluzione a norma minima fissa
una rappresentazione dei coefficienti; una previsione è accettata soltanto se
identificabile nello spazio delle righe di addestramento. Un collegamento nuovo
non riceve un bias inventato pari a zero. Tutti i casi e le previsioni non
disponibili restano nel rapporto.

Si verifica la previsione dei **contrasti tra riferimenti**, non delle misure
assolute: il termine comune viene eliminato anche ai tempi di verifica.
Nessun valore del bersaglio addestra i coefficienti o determina il loro punteggio.

## Risultati fuori dai tempi di addestramento

RMS dei contrasti residui dopo il termine descrittivo, in metri:

| Modello | G14 avanti | G14 inverso | G12 avanti | G12 inverso |
|---|---:|---:|---:|---:|
| Zero | 0,963590 | 0,955860 | 1,060907 | 1,018202 |
| Satellite condiviso | 0,907858 | 0,925193 | 1,015412 | **1,074368** |
| Direzione per stazione | 0,869403 | 0,921006 | 1,025813 | 1,007950 |
| Stazione/satellite | 0,910266* | 0,934408 | **1,061109** | **1,108391** |

I valori in grassetto peggiorano rispetto a zero. Le previsioni coprono
391/390 collegamenti di verifica G14 e 406/410 G12, salvo la cella con asterisco:
il modello stazione/satellite G14 avanti copre 382/391 collegamenti. Su questo
stesso sottoinsieme la baseline zero è 0,966780 m; l'RMS sull'intero insieme
resta non disponibile (`null`), non viene sostituito dal valore parziale.

La coppia BOGT/G19 compare solo nell'ultima epoca. Per quella stazione/epoca
manca quindi il contributo alla media del nuovo riferimento: tutte le nove
previsioni del blocco restano `UNSEEN_TRAINING_SUPPORT`. Gli altri modelli hanno
supporto sufficiente e non cambiano il denominatore.

Tutte le 16 combinazioni evento/separazione/modello sono `EVALUATED`; questo
significa che il confronto è stato eseguito, non che la correzione sia qualificata.
Il modello direzionale riduce l'RMS del 9,77%/3,65% su G14 e del 3,31%/1,01% su
G12. Peggiora tuttavia in 2–3 delle sette stazioni di ciascun confronto.
I risultati completi per stazione sono conservati, senza scegliere solo quelli
che migliorano. Il modello con una costante per collegamento ha il minor errore
di addestramento, ma non quello di verifica: su G12 inverso peggiora di circa 9%.

Il modello direzionale ha rango 21 e condizionamento 4,96–5,36; la sua
identificabilità numerica condizionale non identifica la causa fisica.
I modelli costanti conservano le libertà comuni: una per satellite condiviso,
sette per stazione/satellite. I coefficienti a norma minima non sono bias assoluti.

## Persistenza e correlazioni descrittive

| Quantità sull'intera finestra | G14 | G12 |
|---|---:|---:|
| RMS iniziale | 0,956775 m | 1,025025 m |
| Frazione dell'energia associata alle medie per collegamento | 33,83% | 32,25% |
| RMS dopo sottrazione della media di ogni serie | 0,778281 m | 0,843706 m |
| Separazione angolare mediana fra estremi della serie | 2,275° | 2,224° |
| Mediana della correlazione a 30 s | −0,026 | +0,106 |
| Correlazioni tra stazioni sullo stesso satellite disponibili / possibili | 125 / 441 | 106 / 462 |
| Mediana delle correlazioni disponibili tra stazioni | +0,057 | +0,111 |

Le medie e le correlazioni usano l'intera finestra solo come descrizione;
non entrano nei coefficienti dei confronti temporali. Le serie hanno al massimo
11 campioni; una serie G14 ne ha uno e non permette correlazione temporale.
Le correlazioni tra stazioni spaziano circa da −0,75 a +0,71 su G14 e da −0,74
a +0,64 su G12. Tutti i confronti con meno di tre campioni e le eventuali serie
degeneri restano espliciti. Questi numeri non provano né indipendenza né una
correlazione fisica stabile, e non sono usati per ridurre l'incertezza con √N.

Rapporti: [G14](results/g14_reference_residual_structure_v1.json) e
[G12](results/g12_reference_residual_structure_v1.json). Conservano righe,
direzioni, coefficienti, ranghi, previsioni, tutti i denominatori e hash.
`physical_covariance` resta esplicitamente nullo.

## Conseguenza per lo sviluppo

La struttura direzionale è una pista misurabile, con un beneficio modesto e
non uniforme; non viene trasformata in una correzione empirica del bersaglio.
Prima di attribuirla al ricevitore, il prossimo confronto concreto deve
verificare le coordinate terrestri e i riferimenti d'antenna ammessi contro
prodotti geodetici alla stessa epoca. La
[descrizione ESA di marker, ARP e APC](https://gssc.esa.int/navipedia/index.php/Receiver_Antenna_Phase_Centre)
chiarisce che coordinate del monumento, eccentricità e offset di fase sono
grandezze distinte: sostituirne una all'altra introdurrebbe un nuovo errore.

Servono poi finestre di soli riferimenti con maggiore copertura angolare per
verificare la trasferibilità. L'attuale prova non separa multipath, risposta
del codice, errore di posizione e mezzi di propagazione; S2/G3 restano incompleti.

Riproduzione offline, con output nuovo esterno all'archivio:

```text
python -m research.exploratory.reference_residual_structure experiments/positioning_g14_doy246_network research/exploratory/inputs/timed_reference_products/g14 research/exploratory/inputs/reference_biases/g14 research/exploratory/inputs/reference_antennas/g14 research/exploratory/inputs/reference_attitudes/g14 research/exploratory/results/g14_reference_attitude_v1.json NUOVO_G14.json
python -m research.exploratory.reference_residual_structure research/exploratory/inputs/g12_doy248 research/exploratory/inputs/timed_reference_products/g12 research/exploratory/inputs/reference_biases/g12 research/exploratory/inputs/reference_antennas/g12 research/exploratory/inputs/reference_attitudes/g12 research/exploratory/results/g12_reference_attitude_v1.json NUOVO_G12.json
python -m pytest research/exploratory/tests/test_reference_residual_structure.py -q
```
