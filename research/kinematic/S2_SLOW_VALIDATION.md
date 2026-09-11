# S2 — Validazione sintetica su forme esterne alla base

`slow_validation.py` confronta gli estimatori affine e quadratico congelati
senza modificarne base, pesi o soglie. Il piano locale
`slow_validation_plan.json`, scritto prima della prima esecuzione, fissa
casi, seed, numero di estrazioni e hash dei sorgenti precedenti. Ogni run
verifica quegli hash; una modifica del modello impedisce l'esecuzione.
È un congelamento locale riproducibile, non una preregistrazione pubblica
con timestamp fidato o una conferma RF indipendente.

## Casi ed estrazioni

Si mantengono undici epoche t da −300 a 0 s e u = (t+300)/300. Il ricevitore
0 riceve uno dei seguenti disturbi additivi ai cammini di codice e fase:

- Nessun disturbo.
- Cubica condivisa: 0,1 u³ m, anche su tutti i suoi riferimenti.
- La stessa cubica solo sul target.
- Esponenziale condivisa: 0,1 (exp(u)−1)/(exp(1)−1) m.
- Triangolo condiviso: 0,1 max(0, 1−|u−0,5|/0,3) m.
- Oscillazione solo target: 0,05 sin(2 pi 1,3 u+0,4) m.

Le cinque forme non nulle non appartengono allo spazio quadratico sulla
griglia dichiarata, verificato dai test. Non si introduce una nuova geometria
target: questa validazione esplora forme temporali, non la generalizzazione
a satelliti, reti, atmosfere o ricevitori diversi.

Ai sei confronti senza rumore si aggiungono quattro coppie nominali e quattro
con cubica condivisa, seed 20260914. Il rumore viene estratto dalla covarianza
grezza completa di target, riferimenti, fasi e coordinate; si aggiungono errori
indipendenti di clock, coordinate e misura del ricevitore escluso. I modelli
ricevono lo stesso vettore per ciascuna coppia. Non si selezionano estrazioni,
non si sostituiscono rifiuti e non si adattano ampiezze. Riprodurre lo stesso
seed è un replay, non un nuovo campione di conferma.

## Valutazione esclusa e selezione

Solo un fit accettato produce una previsione sul ricevitore 7 ai tempi futuri
30 e 60 s. I disturbi deterministici del ricevitore 0 sono assenti lì; clock,
coordinate e rumore esclusi seguono il blocco indipendente dichiarato. Si
registra l'hash della previsione prima di valutare le misure escluse con il
generatore inerziale indipendente e gli errori casuali previsti.

Si conservano stato dei gate, numero di caricamenti target, fit disponibili,
errori, raggi locali e indicatori delle bande marginali escluse. I rifiuti non
vengono eliminati dai conteggi complessivi; non esistono previsioni dopo un
rifiuto. Gli errori numerici eventuali sono esiti espliciti, non retries.

La selezione dei gate influisce sul campione accettato. La covarianza resta
marginale e il campione è piccolo: osservare otto posizioni entro un raggio
non dimostra copertura al 95%. Le due bande escluse sono marginali e non
costituiscono una banda congiunta al 95%. I criteri automatici dello studio
verificano integrità e conservazione degli esiti, non successo universale.

## Risultato e seguito

Il quadratico riduce i bias dei casi fuori base senza rumore, ma una coppia
nominale rumorosa peggiora e una sua previsione di rate escluso esce dalla
banda marginale. L'affine respinge quattro casi cubici rumorosi, mentre il
quadratico li ammette. Il confronto va letto con questa differenza di selezione.

Il modello congelato ha affrontato nuovi disturbi sintetici; non ha ancora
qualificato gli errori reali. Occorre progettare un campione più ampio con
geometrie e disturbi direzionali diversi, criteri di selezione e copertura
definiti prima delle nuove prove, poi giustificare le ampiezze tramite fonti
fisiche. S3, acquisizioni target e sito restano sospesi.

[Report completo](results/S2_SLOW_VALIDATION_REPORT.md).
