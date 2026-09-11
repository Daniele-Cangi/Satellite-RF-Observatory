# S2 — Calibrazione comune e residui differenziali

Il nuovo ponte statistico ricava clock compressi da 308 residui di codice
sintetici dei riferimenti, conservandone la correlazione con codice e fase
target. Gli otto criteri dello studio passano; tutti i cinque casi sono
conservati. La calibrazione compensa una deriva affine condivisa, ma non
rimuove automaticamente una variazione curva del cammino.

| Caso fissato | Esito | Errore posizione, m | Errore velocità, m/s |
| --- | --- | ---: | ---: |
| Nominale | Fit accettato | 0,0000030 | 8,59e-9 |
| Deriva 0,01 m/s condivisa riferimento/target, ricevitore 0 | Fit accettato | 0,000761 | 9,79e-8 |
| Stessa deriva soltanto sul target | Fit accettato | 3,34396 | 0,04756 |
| Curvatura condivisa di ampiezza 0,1 m | Fit accettato | 100,23673 | 0,01598 |
| Salto 300 m su un riferimento | Riferimenti respinti | Nessun fit | Nessun fit |

I valori sono errori di esperimenti inventati senza estrazioni casuali,
non accuratezze RF. Nel confronto affine i dati target sono identici e
la covarianza resta fissata: cambiano soltanto i residui dei riferimenti.
La stima del drift del ricevitore recupera l'incremento comune di 0,01 m/s.

Il caso curvo è il limite conservato: circa 100 m di errore pur passando
entrambi i controlli di residui eseguiti, quello dei codici di riferimento
e quello del fit target. Non è stato eseguito il gate degli incrementi
di fase dei riferimenti; il report non ne anticipa l'esito.

## Che cosa è stato collegato

La covarianza grezza include esplicitamente codice target, cammino di fase
target, residui dei riferimenti e coordinate. Una trasformazione unica
applica le differenze temporali alla fase e il guadagno GLS ai riferimenti.
La matrice risultante contiene anche i blocchi target/clock. Il contributo
comune non viene contato come se provenisse da due sorgenti indipendenti.

I riferimenti sono verificati prima che venga invocato il caricatore target.
Il salto da 300 m respinge la calibrazione e non produce alcuna posizione.
Le identità target nei riferimenti sono respinte prima della decodifica
numerica. Questo confine è verificato con input e caricatori che fallirebbero
se letti dopo un rifiuto.

## Riproduzione e limiti

La regressione completa passa con **254 test**. Nove nuovi test verificano
il guadagno GLS, i blocchi incrociati, il confronto
affine, la validazione dei dati e la covarianza compressa contro 12.000
estrazioni grezze. Il [JSON immutabile](shared_calibration_study_v1.json)
conserva tutti gli esiti, la matrice compressa, ipotesi, ambiente e sorgenti.
Gli hash dei sorgenti del nuovo studio e dei nove studi precedenti correnti
sono verificati e corrispondono ai file locali.

```text
python -m pytest research/kinematic/tests/test_shared_calibration.py -q
python -m research.kinematic.shared_calibration_study NUOVO_REPORT.json

SHA256 shared_calibration_study_v1.json:
b0d199e9722e374517f9b4b6f969e69f1f259ea96e0cb791ec67dce972a2c14b
```

Le ampiezze e il rumore restano ipotesi sintetiche. I residui di riferimento
sono già sottratti di una geometria ideale: non è implementata qui una nuova
catena RINEX, né una qualifica di propagazione o ricevitore. La covarianza è
marginale prima della selezione; la copertura dopo i gate rimane aperta.
Non viene prodotta una nuova previsione esclusa in questo studio.

Il prossimo passo è collegare il controllo inutilizzato delle fasi dei
riferimenti alla compressione comune e verificare quali errori differenziali
rimangono. S3, acquisizioni target e sito restano sospesi.

[Modello e confini](../S2_SHARED_CALIBRATION.md).
