# S2 — Bias nascosti nei residui del fit per intervalli

Il nuovo studio mostra che piccoli errori temporali del cammino possono
spostare la posizione senza produrre un rifiuto del fit. Sei perturbazioni
sintetiche fissate vengono trasportate localmente e verificate con entrambi
i segni mediante dodici refit non lineari. Tutti i refit risultano accettati;
tutti i dieci criteri diagnostici passano. Non è una nuova qualifica RF.

## Risultati per ampiezza unitaria dichiarata

| Perturbazione | Norma bias posizione, m | Norma bias velocità, m/s | Probabilità locale di rifiuto |
| --- | ---: | ---: | ---: |
| Deriva comune fase 1 mm/s | 0,00055 | 7,0e-8 | 1,0003% |
| Curvatura comune codice/fase 10 cm, ricevitore 0 | 113,744 | 0,01330 | 2,0825% |
| Oscillazione fase 2 cm, ricevitore 0 | 91,029 | 0,01116 | 1,6236% |
| Errore drift calibrazione 1 mm/s, ricevitore 0 | 0,0911 | 0,00293 | 1,0009% |
| Ambiguità fase costante 5 m | circa zero | circa zero | 1% |
| Offset comune codice 10 m | 0,000058 | 5,1e-8 | 1% |

I bias sono risposte lineari locali, non errori misurati su un satellite.
Le probabilità derivano dalla distribuzione chi-quadro non centrale sotto
il rumore gaussiano fissato nello studio precedente; non sono frequenze
stimate dai dodici refit senza rumore. La soglia nominale resta p < 0,01.

Il risultato informativo è soprattutto la curvatura da 10 cm: circa 114 m
di bias posizione, ma solo il 2,1% di potenza locale del test dei residui.
Anche un'oscillazione da 2 cm può produrre circa 91 m. Il solver può assorbire
parte dell'errore nei suoi parametri; residui piccoli non ne limitano da soli
l'effetto. Gli offset comuni sono in larga parte assorbiti nei clock, mentre
un'ambiguità di fase costante si cancella già nella differenza.

## Previsione esclusa e limite affine

Il ritardo curvo sul ricevitore 0 produce localmente circa −0,415 m sul codice
escluso e −0,000622 m/s sul rate medio escluso. L'oscillazione di fase produce
circa +0,334 m e +0,000504 m/s. La deriva di fase comune è condivisa anche dal
ricevitore escluso: il suo effetto sul residuo di fase quasi si cancella,
pur producendo circa +0,210 m nel residuo di codice previsto.

Si propagano i coefficienti condivisi con il segno della previsione meno
misura. Le verifiche centrali con refit concordano entro 1 cm nel codice
escluso e 0,1 mm/s nel rate. La differenza centrale può cancellare termini
pari: questo controllo non certifica tutti i resti non lineari.

Con tutti i sei coefficienti indipendenti in [-1,1], la disuguaglianza
triangolare fornisce un limite affine di **204,865 m** per il contributo
sistematico alla posizione al termine del fit e **0,02739 m/s** alla velocità.
Questi valori restano separati dal raggio gaussiano del precedente studio.
Non costituiscono un inviluppo totale o una garanzia di copertura al 95%.

## Evidenza e riproduzione

Il [JSON immutabile](interval_systematics_study_v1.json) conserva ampiezze,
matrici, probabilità locali, entrambi i refit di ogni modo, risposte della
previsione, ambiente e hash dei sorgenti. Tutti i sorgenti registrati negli
otto studi precedenti correnti e nel nuovo studio corrispondono ai loro hash.

```text
python -m pytest research/kinematic/tests/test_interval_systematics.py -q
python -m research.kinematic.systematics_study NUOVO_REPORT.json

SHA256 interval_systematics_study_v1.json:
62ad15a7dbbba71fda942b56b84a1d2dc7650750ec82ef20b6518c5c8803f7b0
```

La regressione completa passa con **245 test**. Il writer rifiuta sovrascritture.
Nove nuovi test controllano guadagno locale,
direzioni assorbite, legge quadratica della non centralità, tutti i vertici
del box affine come regressione, cancellazione delle ambiguità, segno degli
errori esclusi e rifiuto di input incompatibili. Il limite del box deriva
algebricamente, non dalla sola enumerazione dei vertici.

## Prossimo passo

Le ampiezze sono ipotesi di sensibilità, non limiti misurati per troposfera,
ricevitori o riferimenti. Occorre ora costruire la calibrazione comune
riferimento/target, stabilire quali ritardi può rimuovere e quali errori
residui lascia, con ampiezze e correlazioni giustificate. Questa verifica
precede una campagna S3; non sono state acquisite nuove misure target.

[Modello, assunzioni e limiti](../S2_INTERVAL_SYSTEMATICS.md).
