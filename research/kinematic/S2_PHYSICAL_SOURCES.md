# S2 — Disponibilità degli osservabili e prima diagnostica fisica

L'audit dei soli header già archiviati di G14 mostra che la rete storica
non alimenta direttamente il fit Doppler: quattro stazioni dichiarano i
D1C/D2W richiesti, sei header disponibili non li dichiarano, uno manca.
Le dieci stazioni con header dichiarano invece C1C/C2W/L1C/L2W.
Il ricevitore escluso GOLD è fra quelli senza Doppler dichiarato.
Report riproducibile: [results/S2_PHYSICAL_REPORT.md](results/S2_PHYSICAL_REPORT.md).

Sono fatti sui file storici, non una nuova selezione di stazioni, una
qualifica RF o un cambiamento degli eventi chiusi. Non sono stati letti nuovi
payload target o prodotti orbitali. Le dichiarazioni non provano che ogni
campione esista, sia continuo o abbia l'incertezza richiesta.

## Contratto dell'alternativa di fase

`phase_rates.reference_phase_rates` implementa un osservabile distinto:
incremento di fase ionosphere-free diviso per la durata fra due tag.
L'ingresso è una griglia fissa di riferimenti non-target, con campi RINEX
L1C/L2W in cicli, flag di epoca e covarianza completa delle fasi.
Non è un nuovo lettore di file RINEX né un collegamento al fit inverso.
Non sostituisce automaticamente D1C/D2W quando mancano.

```text
Φ_IF(t) = α λ1 L1C(t) + β λ2 L2W(t)
α = f1² / (f1² − f2²), β = 1 − α
v_media[i] = (Φ_IF(t[i+1]) − Φ_IF(t[i])) / (t[i+1] − t[i])
```

Il risultato è in metri per secondo del tag ricevitore. Le ambiguità
costanti si cancellano solo sull'arco continuo. Anche lo stato previsto
deve produrre la differenza del **cammino di fase** agli stessi estremi.
Il codice e la fase non sono intercambiabili in generale: differiscono,
fra l'altro, per il contributo ionosferico. Il generatore sintetico usa
proprio segni ionosferici opposti e costanti di ambiguità distinte.

RINEX definisce la fase in cicli e il Doppler positivo in avvicinamento;
si vedano [RINEX 3.05, §§4.3–4.4 e 6.7](https://files.igs.org/pub/data/format/rinex305.pdf).
La frequenza di registrazione dell'header non basta a documentare la risposta
temporale effettiva del ricevitore e del convertitore. Il nuovo osservabile
ha invece estremi espliciti; non lo etichettiamo come istantaneo al termine
o al punto medio. Una curva cubica distingue anche la media dalla derivata
nel punto medio, come verificato da un test analitico.

Si eliminano target e riferimenti non dichiarati prima di leggere i loro
tag o valori numerici. Per i riferimenti, gli estremi esterni alla finestra
sono ignorati prima dei valori. Si rifiutano duplicati, epoche fuori griglia,
griglie non regolari, fasi mancanti/non finite/nulle, LLI diverso da zero o
blank e flag di evento/reset. Un solo estremo non valido respinge l'intero
arco: nessun ponte sui buchi, interpolazione, riparazione di slip o cambio
automatico della finestra. `REFERENCE_PHASE_RATE_AVAILABLE` non è qualifica.

Un salto non segnalato nei flag può superare questi controlli; lo studio
lo conserva esplicitamente come limite. Serviranno controlli indipendenti
dei residui dei riferimenti e ulteriori osservabili/indicatori di continuità.
L'assenza di un flag non certifica l'assenza di uno slip.

## Covarianze introdotte dall'operatore

L'ordinamento delle fasi è epoca/riferimento/banda. Se A è la combinazione
ionosphere-free seguita dalla differenza temporale:

```text
Σ_media = A Σ_fase Aᵀ
```

Anche fasi indipendenti producono correlazioni: due intervalli consecutivi
condividono un estremo con segno opposto. Per rumore IID ed epoche equispaziate
la correlazione fra intervalli adiacenti è −0,5. Non si possono fornire questi
rate al fit come misure indipendenti. La covarianza di ambiguità costanti
condivise nel tempo viene invece annullata dalla differenza.

L'adapter non propaga ancora il legame con i codici o con la calibrazione
dei clock. La matrice congiunta del futuro fit dovrà includere anche questi
blocchi, senza considerarli implicitamente indipendenti.

## Ritardo neutro come errore condiviso

`neutral_delay_basis` è una base di sensibilità a un errore di ritardo
zenitale affine: δz(t) = δz0 + t δz1. Assume, esplicitamente, una geometria
piano-parallela con m(e)=1/sin(e), limitata a elevazioni almeno 10°.
La base del cammino è [m(e), t m(e)]; la base del rate medio è la sua
differenza sugli stessi intervalli. Un errore zenitale comune introduce
covarianze fra riferimenti ed epoche, non solo varianze diagonali.

La decomposizione del ritardo neutro in componenti zenitali e funzioni di
mappatura è descritta da [ESA Navipedia](https://gssc.esa.int/navipedia/index.php/Galileo_Tropospheric_Correction_Model).
La base qui implementata non è il modello Galileo/Niell completo e non
stima componenti idrostatiche/umide da dati meteorologici. È un'approssimazione
di sensitività; non viene usata come nuova correzione nel fit storico o
nel solver in vuoto. I sigma zenitali dello studio sono inventati.

## Evidenze mancanti prima di una qualifica fisica

| Voce | Fatto disponibile | Evidenza ancora richiesta |
|---|---|---|
| Ricevitore e firmware | Identità riportate negli header | Documentazione e comportamento verificato della specifica configurazione/conversione |
| Doppler | Presenza/assenza dei codici di osservazione | Supporto temporale, segno effettivo e incertezza per il percorso reale |
| Incrementi di fase | Operatore, covarianza e stress sintetici | Importer di fase, continuità e controlli su riferimenti reali predefiniti |
| Antenna e segnali | Identità dell'antenna dichiarata | Correzioni/bounds per PCO/PCV, multipath, bias di codice e fase |
| Riferimenti non-target | Ponte broadcast e controlli S2b | Errori e correlazioni orbit/clock qualificati, indipendenti dalla conferma target |
| Coordinate | Modello congiunto di misure terrestri | Epoca, sistema di riferimento, movimenti e covarianza della stazione reale |
| Propagazione | Base di ritardo neutro condiviso | Meteo/prodotti ammessi, mapping qualificato, ionosfera residua e correlazioni |

Nessuna di queste voci diventa qualificata perché un test sintetico passa.
Il prossimo blocco utile è il ponte di calibrazione **sui riferimenti** con
l'osservabile medio di fase e controlli di continuità, prima di modificare
il modello inverso o scegliere nuove misure target. Restano anche qualifica
del test non lineare e inviluppo sistematico/troncamento. S2 e S3 non sono
completati da questa consegna; il sito resta sospeso.

```text
python -m pytest research/kinematic/tests/test_physical_sources.py -q
python -m research.kinematic.physical_source_study NUOVO_REPORT.json
```

Il writer rifiuta sovrascritture, registra hash dell'archivio e dei sorgenti
e conserva tutte le stazioni, i quattro stress e i limiti non risolti.
