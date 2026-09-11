# S2 — Risultati dell'estimatore inverso per intervalli

Il nuovo fit usa codici agli estremi e differenze di fase sugli stessi
intervalli, con covarianza completa e calibrazioni sintetiche compresse.
Nel disegno fissato la fase riduce l'incertezza locale di posizione e
velocità. Passano tutti i 13 criteri; tutti i casi e quattro confronti
rumorosi sono conservati nel [JSON](interval_inverse_study_v1.json).
Ogni risultato resta `real_rf_qualified=false`.

## Confronto nominale

| Grandezza locale al termine della finestra | Soli codici | Codici e fase |
| --- | ---: | ---: |
| Raggio posizione al 95% condizionato, m | 1785,412 | 990,744 |
| Raggio velocità al 95% condizionato, m/s | 9,90737 | 0,587779 |
| Errore posizione senza rumore, m | 2,58e-7 | 2,75e-5 |
| Errore velocità senza rumore, m/s | 4,22e-10 | 7,17e-8 |
| Gradi di libertà residui | 66 | 136 |

Questi raggi derivano dalla covarianza locale sotto le ipotesi dello studio;
non sono un inviluppo totale né accuratezza reale dimostrata. Gli errori
quasi nulli senza rumore verificano l'accordo con il generatore inerziale
indipendente, non la precisione di misure RF reali.

Sette ricevitori, undici epoche ogni 30 secondi e dieci intervalli producono
77 codici e 70 rate medi. I 46 parametri comprendono stato target, clock dei
ricevitori e correzioni terrestri. Le due stime hanno identica inizializzazione
dai codici e usano gli stessi dati non di fase e la stessa covarianza marginale.
La fase non viene decodificata nel braccio con soli codici.

## Quattro estrazioni fissate, senza selezione

Seed 20260912. Entrambi i fit sono accettati in tutti e quattro i confronti.

| Estrazione | Errore posizione codici / fase, m | Errore velocità codici / fase, m/s |
| --- | ---: | ---: |
| 0 | 1002,12 / 589,32 | 1,9324 / 0,2226 |
| 1 | 514,95 / 176,14 | 5,3917 / 0,0488 |
| 2 | 358,42 / 27,58 | 2,0337 / 0,0853 |
| 3 | 664,91 / 57,18 | 4,6332 / 0,1046 |

È un confronto di sviluppo limitato, non una stima della copertura al 95%
o della probabilità di miglioramento su una popolazione di eventi.

## Errori del modello e previsione esclusa

Il salto non segnalato di 0,5 m del cammino IF, il jerk non modellato e
l'uso scorretto di rate istantanei al posto delle medie sono tutti
`MODEL_REJECTED`. Il primo ha p circa 1,56e-259; gli altri raggiungono
underflow numerico del p-value. Nessuna finestra viene riparata o ritentata.
La classificazione conserva anche i candidati dei diversi inizi e le
diagnostiche di ambiguità, descritte nel documento del modello.

Nel nominale il fit prevede l'ottavo ricevitore agli estremi futuri 30 e
60 secondi. La previsione è hashata prima della valutazione indipendente:
l'errore del codice finale è circa −1,79e-7 m e quello del rate medio
−1,12e-9 m/s. La propagazione conserva covarianza di fit, clock, coordinate
e rumore escluso; questo studio dichiara indipendente il blocco escluso.
Il risultato è una verifica sintetica, non un nuovo ricevitore reale validato.

## Verifica e riproduzione

**236 test superati**, inclusi **21 nuovi test**: fisica indipendente,
confronto con soli codici, confini di calibrazione e previsione, errori di
forma/covarianza, guadagno locale contro refit non lineare e trasformazione
grezza della covarianza con 18.000 estrazioni Monte Carlo. Il test della
covarianza distingue l'anticorrelazione del rumore agli estremi dalla
correlazione totale, che può essere positiva per una deriva comune.

Tutti gli hash dei sorgenti del nuovo studio e dei sette studi precedenti
correnti corrispondono ai file locali. Il vecchio report S2a v1 resta il
checkpoint già diagnosticato e sostituito da v2; non è stato modificato.

```text
python -m pytest research/kinematic/tests/test_interval_fit.py -q
python -m research.kinematic.interval_study NUOVO_REPORT.json

SHA256 interval_inverse_study_v1.json:
75125fe6e1521d47da25fe9087702839007967307137048c8bf0824a954c0097
```

Il writer rifiuta sovrascritture. Il JSON registra sorgenti, ambiente,
ricetta della covarianza, seed, casi, candidati e previsione esclusa.

## Prossimo confine scientifico

La catena inversa per intervalli è disponibile, ma la sua alimentazione
con osservazioni target RINEX reali non è ancora qualificata. Il prossimo
lavoro riguarda errori fisici e calibrazione comune riferimento/target:
continuità delle fasi, ritardi variabili, bias, errori dei riferimenti e
relative correlazioni. Occorre quantificarne l'effetto sulla soluzione e
sulla previsione esclusa prima di fissare una nuova campagna S3.
Sito e acquisizioni target restano sospesi.

Dettagli: [modello e limiti](../S2_INTERVAL_INVERSE.md).
