# S2 — Calibrazione quadratica dei ritardi condivisi

Il nuovo modello stima una componente quadratica di cammino dai soli codici
dei riferimenti, ne sottrae la media dal target e conserva l'incertezza della
correzione. Il caso curvo condiviso già noto migliora, con un costo esplicito
in incertezza. Tutti i sette criteri del confronto di sviluppo passano.

## Confronto sui cinque casi fissati

| Caso | Errore posizione affine, m | Errore posizione quadratico, m | Esito |
| --- | ---: | ---: | --- |
| Nominale | 0,0000030 | 0,0000046 | Entrambi accettati |
| Curvatura condivisa 0,1 m | 100,23673 | 0,0000046 | Entrambi accettati |
| Curvatura solo target 0,1 m | 100,20039 | 0,60139 | Entrambi accettati |
| Oscillazione condivisa 0,02 m | 80,11062 | 0,00564 | Entrambi accettati |
| Salto fase riferimento 0,5 m | Nessun fit | Nessun fit | Entrambi respinti prima del target |

Questi casi non sono una conferma indipendente: la base quadratica è stata
introdotta per affrontare un errore osservato nei precedenti studi sintetici.
Le soglie dei gate, le ampiezze e la covarianza grezza restano fissate; tutti
i confronti e le previsioni accettate sono conservati nel report.

Nel nominale, il raggio locale di posizione al 95% condizionato passa da
**921,919 a 947,714 m**; quello della velocità da **0,46345 a 0,73470 m/s**.
Il beneficio non è ottenuto trattando la correzione come esatta. La matrice
del fit contiene anche l'errore della stima quadratica e le sue correlazioni
con codici, fasi, clock e coordinate.

La componente condivisa esattamente quadratica viene recuperata dai
riferimenti. Per la curvatura presente soltanto sul target, invece, i
riferimenti non misurano il disturbo: il miglioramento deriva dai nuovi
pesi prodotti dall'incertezza della correzione. L'errore residuo di circa
0,60 m rimane conservato e non è una qualifica di tutti i bias differenziali.

## Previsione esclusa

Le previsioni sui tempi futuri 30 e 60 s dell'ottavo ricevitore sono hashate
prima del confronto con il generatore inerziale indipendente. I disturbi
specifici del ricevitore 0 sono assenti sul ricevitore escluso, la cui
calibrazione è assunta indipendente con covarianza dichiarata.

| Caso | Residuo codice escluso affine / quadratico, m |
| --- | ---: |
| Curvatura condivisa | −0,37012 / circa 0 |
| Curvatura solo target | −0,36720 / +0,00659 |
| Oscillazione condivisa | +0,29578 / −0,00049 |

Nel caso curvo condiviso il residuo quadratico del rate medio escluso è
circa 1,6e-9 m/s. Per la curvatura solo target rimane circa 0,0000236 m/s,
per l'oscillazione condivisa −0,00000567 m/s. Sono verifiche sintetiche
senza estrazioni casuali, non accuratezze RF né stime di copertura empirica.

## Evidenza riproducibile

La regressione completa passa con **275 test**. Undici nuovi test verificano
guadagno della calibrazione quadratica, recupero
del coefficiente, gate prima del caricamento target, input invalidi e
propagazione della covarianza contro 12.000 estrazioni grezze. La covarianza
nominale e quella del caso curvo sono identiche: non si ripesa dai residui.
Gli hash del nuovo studio e degli undici studi precedenti correnti corrispondono
ai sorgenti locali; nessuna evidenza precedente è modificata.

```text
python -m pytest research/kinematic/tests/test_slow_calibration.py -q
python -m research.kinematic.slow_calibration_study NUOVO_REPORT.json

SHA256 slow_calibration_study_v1.json:
eee1703da885067d5708bce893cbe27a7be7b225dfd562f24b15462136df9aa3
```

Il [JSON immutabile](slow_calibration_study_v1.json) conserva tutti i casi,
coefficienti, covarianze locali, previsioni, hash, ambiente e criteri. Il
writer rifiuta sovrascritture.

## Confine della conclusione

È disponibile una correzione condivisa più flessibile con costo d'incertezza
esplicito. Non è un inviluppo totale al 95%, una qualifica dei ritardi reali
o una dimostrazione di copertura dopo selezione. La base deve ora affrontare
un disegno separato di validazione su forme temporali non usate per costruirla,
con errori direzionali e differenziali, prima di acquisire dati target S3.
RINEX target reale, qualifica RF e sito rimangono fuori da questo risultato.

[Modello e assunzioni](../S2_SLOW_CALIBRATION.md).
