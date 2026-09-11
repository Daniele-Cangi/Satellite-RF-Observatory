# S2 — Validazione dei modelli congelati su nuovi disturbi sintetici

Sono conservati sei confronti senza rumore e otto coppie rumorose. Base,
stimatori, covarianza e soglie sono rimasti immutati. Le forme non nulle
sono esterne alla base quadratica, ma la geometria è quella sintetica già
usata: il risultato non è una conferma RF né una prova di generalizzazione
su satelliti e reti diversi.

## Casi fissati senza rumore

| Forma | Errore posizione affine, m | Errore posizione quadratico, m |
| --- | ---: | ---: |
| Nominale | circa zero | circa zero |
| Cubica condivisa, 0,1 m | 145,196 | 0,267 |
| Cubica solo target, 0,1 m | 145,823 | 1,433 |
| Esponenziale condivisa, 0,1 m | 48,246 | 0,044 |
| Triangolo condiviso, 0,1 m | Fase riferimenti respinta | 0,193 |
| Oscillazione solo target, 0,05 m | 266,328 | 0,983 |

Il quadratico accetta tutti e sei i casi; l'affine ne accetta cinque.
La flessibilità aggiunta riduce la sensibilità ai disturbi, anche attraverso
la covarianza della correzione. Non significa aver misurato nei riferimenti
gli errori presenti soltanto sul target. Il bias cubico differenziale rimane
circa 1,43 m, non viene annullato.

## Otto coppie rumorose conservate

Seed 20260914: quattro nominali e quattro con cubica condivisa. Ogni coppia
usa identici errori grezzi di target, riferimenti e coordinate, più errori
indipendenti del ricevitore escluso.

| Coppia nominale | Errore posizione affine / quadratico, m |
| --- | ---: |
| 0 | 19,65 / 37,33 |
| 1 | 348,11 / 338,41 |
| 2 | 323,24 / 312,23 |
| 3 | 58,70 / 31,58 |

Il quadratico peggiora la prima coppia nominale; questo esito non viene
escluso. Nelle quattro coppie cubiche rumorose, l'affine respinge la fase
dei riferimenti prima del caricamento target. Il quadratico le accetta, con
errori posizione rispettivamente 281,41, 55,51, 272,02 e 127,18 m. Questi
quattro errori non sono confrontabili con fit affini inesistenti.

L'affine produce quattro fit rumorosi accettati, il quadratico otto. Tutte
le loro posizioni rientrano nel rispettivo raggio locale dichiarato. Il
campione è troppo piccolo e selezionato dai gate per affermare copertura
al 95%; il conteggio non è una garanzia scientifica.

## Ricevitore escluso: anche gli esiti fuori banda

Ogni previsione accettata sui tempi futuri 30 e 60 s viene hashata prima
della valutazione. Una previsione del rate escluso supera la banda marginale
del 95% per ciascun modello: coppia nominale 3 per l'affine e coppia nominale
0 per il quadratico. Tutti i codici esclusi restano nelle rispettive bande.
Le due bande sono marginali, non una regione congiunta al 95%.

I disturbi deterministici riguardano il ricevitore 0 e sono assenti su
quello escluso. La sua calibrazione è indipendente e assunta con covarianza
dichiarata. La validazione non copre ancora errori comuni all'intera rete
o una calibrazione esclusa ricavata da dati RINEX reali.

## Integrità e riproduzione

La regressione completa passa con **282 test**.
Il [piano locale](../slow_validation_plan.json) è stato scritto prima della
prima esecuzione. Ogni replay verifica gli hash degli stimatori congelati.
Sette nuovi test controllano forme fuori base, identità dei dati target
nei confronti condiviso/differenziale, separazione dei blocchi di rumore,
validazione degli input e arresto prima del target sui riferimenti respinti.

Il [JSON completo](slow_validation_study_v1.json) conserva tutti gli esiti,
hash del piano, seed, hash delle perturbazioni, previsioni prima della
valutazione e diagnostiche. I criteri automatici controllano integrità,
assenza di errori numerici e conservazione degli esiti: non dichiarano
successo fisico universale o copertura empirica.

```text
python -m pytest research/kinematic/tests/test_slow_validation.py -q
python -m research.kinematic.slow_validation NUOVO_REPORT.json

SHA256 piano:
b6f386d51cb87fcd5d3be512ea38edad68e109a7c3fa6c5c7e8aacbf70331859
SHA256 report:
3205cbb8e101f4d0695d0b89e84925320b251b65000ecc3bcd5b2fc614c10901
```

Il writer rifiuta sovrascritture. Riprodurre lo stesso piano e seed non
aggiunge nuove prove indipendenti.
Gli hash dei sorgenti del nuovo report e dei dodici studi precedenti correnti
corrispondono ai file locali; tutte le evidenze precedenti restano immutate.

## Passo successivo

La validazione temporale separata è favorevole al modello quadratico in
questo disegno, con peggioramenti e mancate bande esplicitamente conservati.
Occorre ora un disegno più ampio che vari geometria ed errori direzionali,
contabilizzi i gate e definisca prima delle prove quali limiti statistici
si vogliono sostenere. Le ampiezze devono poi essere giustificate da fonti
fisiche; sito, acquisizioni target e S3 restano sospesi.

[Assunzioni e dettagli](../S2_SLOW_VALIDATION.md).
