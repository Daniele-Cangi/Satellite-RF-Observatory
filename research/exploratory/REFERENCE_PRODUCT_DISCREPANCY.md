# Discrepanze reali dei prodotti non bersaglio

Il confronto di sviluppo del 16 settembre 2026 usa le giornate già esposte
2026-09-03 (G14 escluso) e 2026-09-05 (G12 escluso). Il codice del confronto
e gli estratti sono nel commit `bf52a98`, precedente alle esecuzioni.

## Dati e separazione del bersaglio

Sono stati riscaricati esattamente i due prodotti IGS rapidi delle ricevute
storiche, verificando SHA-256 e dimensioni compressi. I file misti restano
fuori dal repository. Le righe di stato non appartenenti ai riferimenti sono
scartate come testo prima della conversione numerica: nessuna coordinata o
clock del bersaglio viene interpretata. Gli estratti conservati non sono SP3
completi; mantengono solo metadati globali, epoche e record P ammessi.

Le ricevute in `inputs/reference_products/{g14,g12}/` legano URL, hash del
prodotto originale, hash dell'estratto, bersaglio escluso e lista dei riferimenti.
I riferimenti sono quelli osservati dalle stazioni fit nell'input già ammesso,
con navigazione disponibile: 21 per G14 e 22 per G12. Nessuna nuova misura RF
o soluzione del bersaglio è stata acquisita o stimata.

## Confronto riproducibile

Per ciascuna delle 96 epoche originali a 15 minuti, su tutta la giornata:

- si confrontano le coordinate broadcast con quelle del prodotto IGS alla
  stessa epoca, senza interpolazione o adattamento di rotazioni/traslazioni;
- si sceglie il record broadcast sano con toc più vicino, entro 7200 s,
  come nel calibratore esistente; è un confronto storico, non una regola
  operativa che garantisca disponibilità del messaggio in tempo reale;
- si confronta il polinomio `af0 + af1*dt + af2*dt²` con il campo clock SP3;
  il termine relativistico periodico calcolato dal modello broadcast viene
  conservato separatamente, senza aggiungerlo a uno solo dei due prodotti;
- valori mancanti, flag di previsione/evento/manovra e record troppo vecchi
  rimangono nel denominatore con stato esplicito.

Le unità SP3 (km e microsecondi), sentinelle e flag seguono il
[formato IGS SP3](https://files.igs.org/pub/data/format/sp3d.pdf).
La [descrizione dei prodotti IGS](https://www.igs.org/products/) distingue
prodotti rapidi e finali e ne descrive la combinazione fra centri di analisi.
Le [convenzioni d'antenna IGS](https://igs.org/wg/antenna/) rendono necessario
considerare anche i punti di riferimento delle coordinate.

## Risultati

| Giornata | Coppie confrontate / previste | Orbita RMS / massimo (m) | Clock grezzo RMS / massimo assoluto (m) | Clock centrato RMS / massimo assoluto (m) |
|---|---:|---:|---:|---:|
| G14, 2026-09-03 | 2016 / 2016 | 1,707 / 4,267 | 0,676 / 2,149 | 0,331 / 2,001 |
| G12, 2026-09-05 | 2112 / 2112 | 1,800 / 4,477 | 0,451 / 1,267 | 0,193 / 0,819 |

Nessuna coppia scartata. Ogni riga, età broadcast, differenza xyz e componente
di clock è conservata nei rapporti
[G14](results/g14_reference_product_discrepancy_v1.json) e
[G12](results/g12_reference_product_discrepancy_v1.json).

Il clock centrato sottrae, a ogni epoca, la media dell'insieme fisso dei
riferimenti. La media sottratta viene conservata. Un'epoca con un riferimento
mancante non entra nelle statistiche centrate: non si cambia silenziosamente
l'insieme di confronto. La covarianza campionaria è calcolata sulle 96 epoche,
con sottrazione della media temporale di ciascuna colonna e divisore N-1.
L'ordine delle colonne è `references` nel rapporto.

Le massime correlazioni assolute fuori diagonale di queste serie centrate sono
0,858 (G14) e 0,751 (G12). La centratura stessa induce correlazioni e una
direzione nulla: questi numeri non provano la correlazione degli errori fisici.
Le epoche sono inoltre temporalmente dipendenti e non sono 96 prove indipendenti.

## Interpretazione e lavoro ancora necessario

Ora disponiamo di ampiezze di discrepanza osservate, oltre alle risposte a
perturbazioni inventate della prova precedente. Non sono tuttavia errori veri
dei prodotti: nessuna soluzione viene assunta come verità indipendente.
Non sono applicate correzioni di punto d'antenna, trasformazioni fra frame,
bias dei segnali o una qualificazione completa del datum degli orologi.
La differenza orbitale può quindi includere differenze di convenzione.

Non si moltiplicano automaticamente gli RMS giornalieri per il massimo gain
della prova precedente: quella perturbazione era costante, mentre queste
serie cambiano nel tempo e sono correlate; manca anche il trasferimento della
componente orbitale. I rapporti non modificano la stima, l'incertezza o gli
esiti degli eventi originali. `qualified_error_budget` rimane falso.

Il seguito concreto è armonizzare le convenzioni dei prodotti e proiettare
insieme scarti orbitali e clock sui cammini dei ricevitori, conservando le
dipendenze temporali e fra stazioni, prima della propagazione nella stima.

## Riproduzione offline

```text
python -m research.exploratory.reference_product_discrepancy experiments/positioning_g14_doy246_network research/exploratory/inputs/reference_products/g14/reference_extract.txt research/exploratory/inputs/reference_products/g14/receipt.json NUOVO_G14.json
python -m research.exploratory.reference_product_discrepancy research/exploratory/inputs/g12_doy248 research/exploratory/inputs/reference_products/g12/reference_extract.txt research/exploratory/inputs/reference_products/g12/receipt.json NUOVO_G12.json
```
