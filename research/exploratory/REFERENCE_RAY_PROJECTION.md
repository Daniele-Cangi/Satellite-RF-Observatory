# Proiezione congiunta orbita-clock verso i ricevitori

Prova di sviluppo del 16 settembre 2026, codice registrato in `19934ba` prima
delle due esecuzioni. Riutilizza solo input già ammessi ed estratti non bersaglio
della precedente [comparazione dei prodotti](REFERENCE_PRODUCT_DISCREPANCY.md).
Nessun nuovo download, accesso agli stati del bersaglio o modifica degli eventi.

## Che cosa viene confrontato

Si prendono i nodi SP3 che racchiudono la finestra originale:

- G14: 03:45 e 04:00 GPST, finestra originale 03:55–04:00;
- G12: 10:30 e 10:45 GPST, finestra originale 10:30–10:35.

Sono nodi di emissione per questa diagnostica geometrica. Non rappresentano
misure RF acquisite presso ciascun ricevitore a quelle epoche e non si
interpolano i clock a 15 minuti come se fossero misure a 30 secondi.

Per ogni stazione fit e riferimento dell'insieme ammesso si conserva un esito.
Entrano nelle statistiche solo riferimenti osservati dalla specifica stazione
nella finestra archiviata, con prodotto valido, broadcast entro 7200 s da toc
ed elevazione broadcast almeno 10 gradi al nodo geometrico. La maschera è
valutata sul broadcast senza selezionare in base all'entità dello scarto.

## Convenzioni esplicite e limiti dell'allineamento

Il tempo di volo nel vuoto è ricavato iterativamente dalla geometria broadcast.
Entrambi gli stati, alla stessa epoca di emissione, sono poi ruotati di
`Rz(-OMEGA*tau)` nello stesso sistema terrestre di ricezione, con tau congelato.
Questa rotazione segue la distinzione fra assi all'emissione e alla ricezione
descritta da [ESA Navipedia](https://gssc.esa.int/navipedia/index.php/Satellite_Coordinates_Computation).

La differenza proiettata, con segno broadcast meno preciso, è:

```text
orbitale = |R*x_b - receiver| - |R*x_p - receiver|
clock    = -c * (clock_polynomial_b - clock_field_p)
congiunta = orbitale + clock
```

Il termine orbitale usa la differenza esatta delle distanze, non la norma dello
scarto xyz. Si conserva anche la differenza rispetto alla proiezione lineare
lungo la direzione del prodotto preciso.

| Convenzione | Stato |
|---|---|
| Unità, GPST, epoca comune, segno del clock | Espliciti |
| Assi di ricezione e rotazione terrestre | Comuni, tau broadcast congelato |
| Punti orbitali/antenna, assetto satellitare e frame | Non ancora armonizzati |
| Bias dei segnali e datum dei clock | Non ancora qualificati |
| Relatività periodica differenziale | Non inclusa su nessuno dei due lati |
| Mezzi di propagazione, tempi osservati, ricalibrazione completa | Non inclusi |

Questa è quindi una proiezione **condizionale degli scarti grezzi**, non una
correzione delle misure pronta per il motore. La geometria a tempo di volo
congelato non risolve di nuovo l'emissione coerente con i codici osservati.
Le differenze dei punti d'antenna richiedono anche un modello di assetto:
si veda la [documentazione di rielaborazione IGS](https://www.igs.org/acc/reprocessing/).

## Risultati

| Evento | Proiezioni / combinazioni considerate | Non osservato nella finestra | Sotto maschera | RMS orbita (m) | RMS clock (m) | RMS congiunto (m) |
|---|---:|---:|---:|---:|---:|---:|
| G14 | 131 / 294 | 158 | 5 | 1,222 | 0,597 | 0,770 |
| G12 | 132 / 308 | 150 | 26 | 1,458 | 0,433 | 1,109 |

Nessun prodotto mancante o troppo vecchio nei casi considerati. Le statistiche
dei tre contributi usano esattamente gli stessi collegamenti. Orbita e clock
si compensano parzialmente in questo campione: sommare norme o massimi separati
perderebbe questa struttura. L'RMS è descrittivo e non una deviazione standard
di errori indipendenti. Le stazioni condividono gli stessi prodotti.

Ogni gruppo stazione-epoca ha almeno quattro riferimenti ammessi. Le medie
congiunte vanno da -0,764 a -0,433 m per G14 e da -1,114 a -0,680 m per G12.
A pesi uguali e insieme fisso, la media `M_b - M_p` sarebbe la variazione del
clock stimato del ricevitore sostituendo il modello broadcast con quello preciso
e mantenendo fissi i codici. Qui è soltanto una proiezione: nessuna calibrazione
o correzione del codice bersaglio è eseguita.

Rapporti completi: [G14](results/g14_reference_ray_projection_v1.json),
[G12](results/g12_reference_ray_projection_v1.json). Conservano tutti i 602
casi, contributi con segno, gruppi stazione-epoca, hash di input e sorgenti.
Il test analitico controlla cancellazione orbita-clock, segno, termine trasverso
di secondo ordine e rotazione rispetto alla formula di Sagnac al primo ordine.

## Seguito

La proiezione è consegnata; l'armonizzazione fisica non è completa. Prima di
usare questi valori nella stima occorre risolvere punto d'antenna/assetto/frame,
convenzioni dei clock e bias, relatività differenziale e valutazione ai tempi
delle osservazioni. Poi serve ricalibrare e propagare congiuntamente gli scarti
mantenendo le dipendenze. Non si moltiplicano queste medie per un gain massimo
per dichiarare un'incertezza. `qualified_error_budget` e `applied_to_estimator`
restano falsi.

Riproduzione offline, con output nuovo esterno agli archivi:

```text
python -m research.exploratory.reference_ray_projection experiments/positioning_g14_doy246_network research/exploratory/inputs/reference_products/g14/reference_extract.txt research/exploratory/inputs/reference_products/g14/receipt.json NUOVO_G14.json
python -m research.exploratory.reference_ray_projection research/exploratory/inputs/g12_doy248 research/exploratory/inputs/reference_products/g12/reference_extract.txt research/exploratory/inputs/reference_products/g12/receipt.json NUOVO_G12.json
```
