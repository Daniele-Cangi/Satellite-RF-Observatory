# S2 — Gate di fase dei riferimenti collegato al fit condiviso

Il controllo della fase è ora eseguito prima del caricamento target.
Il clock resta stimato soltanto dai codici e, quando i riferimenti passano,
stato e covarianza del precedente fit vengono preservati. Tutti i nove
criteri dello studio passano; gli otto casi sono conservati senza selezione.

## Esiti sintetici

| Caso | Gate / fit finale | Caricamenti target | Errore posizione, m |
| --- | --- | ---: | ---: |
| Nominale | Accettato | 1 | 0,000003 |
| Deriva affine condivisa | Accettato | 1 | 0,000761 |
| Deriva solo sul target | Accettato | 1 | 3,34396 |
| Curvatura condivisa 0,1 m | Accettato | 1 | 100,23673 |
| Curvatura condivisa 1 m | Fase riferimenti respinta | 0 | Nessun fit |
| Salto di fase riferimento 0,5 m | Fase riferimenti respinta | 0 | Nessun fit |
| Ambiguità costante aggiunta | Accettato | 1 | 0,000003 |
| Salto nei codici riferimento | Codici respinti prima delle fasi | 0 | Nessun fit |

La fase inutilizzata rileva la curvatura da 1 m e il salto da 0,5 m: costi
rispettivamente 3432 e 5539,79 contro una soglia di circa 337,974, con 280
gradi di libertà e p < 0,01. I p-value numerici raggiungono underflow.
Le fasi alterate non modificano i coefficienti del clock ricavati dai codici.

La curvatura da 0,1 m resta sotto soglia, con costo 34,32. Il risultato
accettato ma distorto di circa 100 m rimane nel report. Il p-value numerico
arrotondato a uno non è una probabilità che la soluzione sia corretta:
si tratta di una perturbazione deterministica senza estrazioni del rumore
usato per definire la covarianza. La probabilità di rilevamento su dati
rumorosi richiede un'analisi distinta.

## Integrità del collegamento

La covarianza include rumore di fase riferimento di sigma 0,01 m,
correlazione codice/fase 0,1 e deriva casuale condivisa di sigma 0,01 m/s.
La trasformazione conserva covarianza fra residui del gate e dati target
compressi. I gate non sono statisticamente indipendenti; la covarianza del
fit resta marginale, senza rivendicare copertura dopo la selezione.

La regressione completa passa con **264 test**. Dieci nuovi test controllano
identità escluse, ordine dei gate, mancata
invocazione del caricatore target su rifiuto, annullamento delle ambiguità,
clock invariati e identità del fit col precedente quando il gate passa.
Una verifica su 12.000 estrazioni grezze controlla covarianza dei residui e
blocchi incrociati. Non misura la copertura dei gate su una popolazione RF.

Gli hash dei sorgenti del nuovo studio e dei dieci studi precedenti correnti
sono verificati; nessuna evidenza storica è stata modificata.

```text
python -m pytest research/kinematic/tests/test_shared_phase_gate.py -q
python -m research.kinematic.shared_phase_study NUOVO_REPORT.json

SHA256 shared_phase_gate_study_v1.json:
901731b8138ca3bc9184c7cfecd1c5fa069bf246842436f85f992e5217fd06f3
```

Il [JSON immutabile](shared_phase_gate_study_v1.json) conserva esiti, clock,
residui, conteggi di caricamento target, ipotesi, ambiente e hash dei sorgenti.
Il writer rifiuta sovrascritture.

## Conclusione operativa

Il collegamento richiesto è disponibile, ma il piccolo errore persistente
resta una debolezza documentata. Il passo seguente richiede un disegno separato
per stimare o limitare tali componenti condivise e differenziali, preservando
una valutazione esclusa e contabilizzando la selezione. Non si abbassa la
soglia usando il caso già visto come nuova prova.

Le osservazioni sono residui inventati dopo sottrazione geometrica ideale:
non è una pipeline target RINEX qualificata. Tutti i risultati mantengono
`real_rf_qualified=false`; S3, nuove acquisizioni target e sito restano sospesi.
[Modello e assunzioni](../S2_SHARED_PHASE_GATE.md).
