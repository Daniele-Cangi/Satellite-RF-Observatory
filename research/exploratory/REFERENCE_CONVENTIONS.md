# Antenna e relatività: allineamento parziale dei riferimenti

Sviluppo esplorativo del 16 settembre 2026; sorgente di esecuzione `2e6ce7d`.
Si riutilizzano gli stessi 263 raggi geometrici della
[proiezione grezza](REFERENCE_RAY_PROJECTION.md), conservando tutti i 602 casi
e le esclusioni originali. Nessun accesso a orbite del bersaglio, ricalibrazione,
nuovo fit o modifica dei risultati storici.

## Modello d'antenna effettivamente acquisito

Gli SP3 dichiarano `PCV:IGS20_2425`. Si usa pertanto
[igs20_2425.atx.gz nell'archivio IGS](https://files.igs.org/pub/station/general/pcv_archive/igs20_2425.atx.gz),
non l'alias aggiornabile `igs20.atx`. Il file compresso ha 7.660.658 byte e SHA256
`cc15ff342305278fc818b7300453b02068b5f8e7393b03c9aa98b70918ba7260`.
Le richieste iniziali alla directory corrente restituivano 404: la versione
richiesta era stata spostata nell'archivio. Nessun modello alternativo è usato.

Gli estratti e le ricevute in `inputs/reference_antennas/{g14,g12}/` conservano
solo i blocchi dei riferimenti ammessi; gli altri sono scartati come testo prima
di convertire valori numerici. Il parser sceglie l'assegnazione PRN/SVN valida
al nodo, richiede un solo modello e le frequenze G01/G02. I blocchi storici sono
conservati per rendere verificabile la selezione temporale. Ad esempio, G01
nel 2026 è G080, non il precedente G063.

Il [formato ANTEX 1.4](https://files.igs.org/pub/station/general/antex14.txt)
specifica gli offset satellitari rispetto al centro di massa, in assi corporei
XYZ e millimetri. La [guida IGS, §5.1.1 e §5.3.4](https://files.igs.org/pub/resource/pubs/UsingIGSProductsVer21_cor.pdf)
distingue centro di massa dei prodotti precisi e antenna broadcast; richiede
inoltre la correzione relativistica periodica anche per i clock precisi.

## Geometria applicata e orientamento non inventato

Si forma il PCO ionosphere-free con gli stessi coefficienti L1/L2 del codice:
`pco_IF = alpha*pco_G01 + beta*pco_G02`. La componente Z è applicata al prodotto
preciso assumendo l'asse corporeo Z verso il centro terrestre. Restano gli stessi
tempo di volo broadcast e assi di ricezione della proiezione precedente.

Per le componenti X/Y non si inventa un orientamento solare: si calcola l'intero
intervallo geometrico consentito da una rotazione yaw arbitraria. Posti
`q = precise + pco_Z*z - station`, `a = q.z`, `rho = |q-a*z|` e
`h = hypot(pco_X,pco_Y)`, gli estremi esatti della distanza sono
`hypot(a,rho-h)` e `hypot(a,rho+h)`. Gli estremi dello scarto broadcast meno
preciso hanno ordine invertito. Gli intervalli delle medie sono conservativi:
non impongono lo stesso yaw alle diverse stazioni che vedono un satellite.

Questo intervallo riguarda **solo il PCO trasverso sotto l'ipotesi di puntamento
nadir**. Non limita pitch/roll, errori d'orbita o risposta del codice. Gli offset
di fase ANTEX costituiscono un allineamento convenzionale del punto geometrico,
non una misura della risposta dell'antenna al codice. Le PCV non sono applicate
automaticamente come correzioni dei codici osservati.

## Clock e controllo numerico

Il clock broadcast usa il polinomio più il termine periodico già presente nel
modello storico. Al campo SP3 si aggiunge `-2*r.v/c^2`; la formula e l'equivalenza
fra velocità inerziale e terrestre nel prodotto scalare sono descritte da
[ESA Navipedia](https://gssc.esa.int/navipedia/index.php/Relativistic_Clock_Correction).
La velocità viene dalla derivata del polinomio su nove nodi SP3 centrati,
spaziati di 900 s. Campioni assenti o segnalati invalidano lo stencil; non si
estrapola. Si conserva il confronto con sette nodi sugli stessi prodotti.

Il termine aggiunto al precedente scarto di modello è
`-(relativity_broadcast_m - relativity_precise_m)`. Il nuovo scarto è quindi:

```text
radial_aligned_joint = raw_joint - radial_PCO_range_change
                      - (relativity_broadcast_m - relativity_precise_m)
```

Il confronto fra stencil controlla la sensibilità numerica della derivata;
non misura l'errore dell'orbita. I clock SP3 restano ai nodi originali: nessuna
interpolazione dei clock a 15 minuti è presentata come dato a 30 secondi.

## Risultati sullo stesso insieme di raggi

| Quantità | G14 (131 raggi) | G12 (132 raggi) |
|---|---:|---:|
| RMS congiunto prima dell'allineamento | 0,769715 m | 1,109146 m |
| RMS contributo geometrico del PCO radiale | 1,248127 m | 1,442318 m |
| RMS contributo relativistico differenziale | 0,010323 m | 0,009679 m |
| RMS congiunto dopo PCO radiale e relatività | 0,687503 m | 0,495219 m |
| Massima escursione trasversa consentita dallo yaw | 0,093169 m | 0,093196 m |
| Massima differenza relativistica fra stencil 9/7 | 0,000069 m | 0,000065 m |

Tutti i 263 raggi proiettati hanno antenna valida e stencil disponibile. Le
medie stazione-epoca dopo l'allineamento sono 0,469–0,721 m per G14 e
0,224–0,513 m per G12. Il cambio di segno rispetto alle precedenti medie grezze
mostra perché non si potevano usare direttamente quelle differenze per
ricalibrare. Non è dimostrato che la nuova posizione sarebbe più accurata.

Rapporti completi: [G14](results/g14_reference_conventions_v1.json) e
[G12](results/g12_reference_conventions_v1.json). Mantengono valori grezzi,
contributi, intervalli, SVN, selezioni e hash di tutti gli input/sorgenti.
Le statistiche `rms_m` e le precedenti medie mantengono il significato grezzo;
`alignment_rms_m` e le nuove medie sono separati. Il replay confronta l'intero
contenuto, con tolleranza numerica di un micrometro sui valori in metri.

## Lavoro ancora necessario

La componente radiale e la relatività periodica sono implementate. Prima della
ricalibrazione restano bias dei segnali/clock datum (in particolare C1C rispetto
al riferimento dei clock), assetto reale e risposta dell'antenna al codice,
coerenza del frame e dei mezzi di propagazione, valutazione ai tempi osservati.
Il prossimo passo concreto è acquisire bias dei riferimenti compatibili con i
prodotti e confrontare la convenzione del codice usato, mantenendo distinti
offset comuni e dipendenze fra satelliti. La risposta finita agli offset clock
del precedente studio non sostituisce questa calibrazione.

`qualified_error_budget`, `applied_to_estimator` e `new_confirmation` restano
falsi. S2/G3 e il piano di conferma restano aperti; nessuna pubblicazione del sito.

Riproduzione offline con un nuovo output:

```text
python -m research.exploratory.reference_conventions experiments/positioning_g14_doy246_network research/exploratory/inputs/reference_products/g14 research/exploratory/inputs/reference_antennas/g14 NUOVO_G14.json
python -m research.exploratory.reference_conventions research/exploratory/inputs/g12_doy248 research/exploratory/inputs/reference_products/g12 research/exploratory/inputs/reference_antennas/g12 NUOVO_G12.json
python -m pytest research/exploratory/tests -q
```
