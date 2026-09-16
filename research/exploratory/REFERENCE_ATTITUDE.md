# Assetto CODE e offset tridimensionale dei riferimenti

Prova esplorativa del 16 settembre 2026, eseguita con i sorgenti di `120e92a`.
Segue la [valutazione ai tempi osservati](REFERENCE_TIME_ALIGNMENT.md) sui due
eventi esposti G14/G12. Usa soltanto prodotti dei satelliti di riferimento.
Gli eventi chiusi, i risultati precedenti e il motore di produzione sono invariati.

## Informazione aggiunta

Prima, il PCO IF applicato era solo radiale e la componente trasversa aveva
un intervallo condizionale su tutto lo yaw. Ora si usa il prodotto di assetto
della stessa serie CODE per orientare tutte e tre le componenti ANTEX.
Questo determina una correzione coerente con l'elaborazione CODE: non misura
indipendentemente l'assetto fisico reale, né qualifica la risposta d'antenna
del codice o una covarianza fisica.

La [presentazione IGS di Loyer et al.](https://files.igs.org/pub/resource/pubs/workshop/2017/W2017-PS01-05%20-%20Loyer.pdf)
spiega perché distribuire l'assetto impiegato nell'elaborazione permette di
mantenere coerenza con orbite e clock, pur lasciando aperti errori del modello
d'assetto, specialmente durante le eclissi.

## Prodotti, estratti e convenzioni

Dal [catalogo BKG IGSac 2434](https://igs.bkg.bund.de/root_ftp/IGSac/products/2434/):

- `COD0OPSRAP_20262460000_01D_30S_ATT.OBX.gz`
- `COD0OPSRAP_20262480000_01D_30S_ATT.OBX.gz`

Le ricevute in `inputs/reference_attitudes/{g14,g12}/receipt.json` registrano
URL, byte e SHA256 del gzip e dell'estratto derivato. Restano 399/418 quaternioni,
19 per ciascuno dei 21/22 riferimenti. La finestra include 120 s prima e dopo
le osservazioni. Bersaglio e altri satelliti sono eliminati come testo prima
della conversione dei quaternioni. Gli estratti riscrivono esplicitamente
inizio/fine, lista satelliti e conteggi per epoca; non sono file originali integrali.

Il parser supporta il profilo CODE ORBEX 0.09 con GPST, ECEF, IGC20, record ATT
a 30 s e quaternioni unitari a scalare iniziale. Rifiuta convenzioni diverse,
duplicati, conteggi errati, campi riservati non vuoti e file troncati.
Nodi mancanti impediscono l'interpolazione sul collegamento interessato;
non vengono colmati né estrapolati. Riferimento al
[formato ORBEX 0.09](https://geodesy.noaa.gov/pub/ORBEX/ORBEX009.pdf).

La direzione è verificata sul prodotto effettivo: il suo header dichiara
ECEF→body. Si costruisce la matrice Hamilton del quaternion e se ne usa la
trasposta per portare il vettore PCO body in ECEF:

```text
antenna_ecef(t_tx) = com_ecef(t_tx) + R_ecef_to_body(q(t_tx)).T @ pco_IF_body
```

Non si deduce la direzione dal solo ordine dei quattro numeri. Le descrizioni
storiche di ORBEX e le proposte di convenzione possono usare un'altra direzione;
questo adattatore è limitato alla dichiarazione esplicita del prodotto CODE.
Un test con rotazione nota di 90° controlla il verso; un controllo separato
confronta l'asse Z con il nadir dei prodotti orbitali di riferimento.

Si interpola con SLERP sull'arco più corto, invariantemente rispetto a `q` e
`-q`. La valutazione usa gli stessi tempi di emissione risolti, clock a 30 s,
orbite a nove nodi, relatività e conversioni dei bias della prova precedente.
La rotazione terrestre porta poi il punto d'antenna agli assi di ricezione.
Non si introduce una nuova osservabile di fase o una correzione wind-up del codice.

## Varianti e risultati

Ogni evento conserva quattro ricalibrazioni/fit: radiale, PCO completo con
assetto a 30 s, PCO completo con assetto a 60 s, solo PCO Z orientato dall'assetto.
Restano fissi i set di riferimento scelti dalla calibrazione broadcast, i codici
bersaglio, i pesi di 20 m e tutte le soglie storiche. Un controllo indisponibile
rimane un caso fallito; non viene sostituito o eliminato.

| Quantità | G14 | G12 |
|---|---:|---:|
| Casi stimati / eseguiti | 4 / 4 | 4 / 4 |
| Collegamenti valutati / osservati | 716 / 734 | 747 / 847 |
| Spostamento completo rispetto al radiale | **0,818412 m** | **0,282720 m** |
| Variazione B | +0,808004 m | −0,268128 m |
| RMS calibrazione, radiale → completo | 0,954921 → 0,956775 m | 1,023831 → 1,025025 m |
| Massimo residuo fit bersaglio, radiale → completo | 0,431844 → 0,423523 m | 0,954990 → 0,956772 m |
| Correzione geometrica completo−radiale sui collegamenti | −0,071819…+0,093872 m | −0,084797…+0,088585 m |
| Spostamento fit: assetto a 60 invece di 30 s | 0,000392 m | 0,000041 m |
| Spostamento fit: solo Z rispetto al radiale | <0,000001 m | <0,000001 m |

Le differenze geometriche dei collegamenti tengono fisso il clock ricevitore
della calibrazione radiale; i fit includono invece la ricalibrazione completa.
I 118 collegamenti fuori dal set broadcast restano nel denominatore.
Tutte le 616 epoche di calibrazione degli otto casi passano i controlli.
Nessun confronto con orbita bersaglio o ricevitore escluso viene eseguito.

Il contributo aggiunto proviene quasi interamente dalle componenti trasverse
su queste finestre: l'asse Z CODE è quasi nadirale e il controllo Z riproduce
il modello radiale. Non si conclude che pitch/roll reali siano noti con questa
precisione. Il diradamento misura soltanto sensibilità numerica al campionamento.

Omettendo i nodi nativi a 30 s dalla griglia a 60 s si conservano 147/154
confronti, tutti disponibili. Il massimo scarto del vettore PCO è
0,00001870/0,00003757 m; quello angolare è 0,00006755/0,00018698 rad.
Questi numeri non sono incertezze fisiche dell'antenna o dell'assetto.

Rapporti completi: [G14](results/g14_reference_attitude_v1.json) e
[G12](results/g12_reference_attitude_v1.json), con varianti, denominatori,
controlli e hash di tutti gli input e sorgenti. La baseline riproduce il caso
preciso a nove nodi/clock a 30 s della prova precedente.

## Rilievi della revisione precedente

La revisione Copilot della PR #140 è arrivata dopo il merge. Nel nuovo percorso:

- il clock deve dichiarare il prodotto GPS `CODE.BIA`;
- le ricevute devono avere chiavi uniche e numeri finiti, incluso l'overflow;
- si rifiuta ogni confine di validità ANTEX interno alla finestra, anche se
  inizio e fine ritornassero alla stessa assegnazione;
- gli hash collegano i byte prevalidati a quelli caricati dal modello precedente.

Gli input effettivi di entrambe le prove superano questi controlli; non si
riscrivono sorgenti o risultati congelati per rafforzare l'importazione futura.
Il primo controllo locale aveva rifiutato l'header DCB per una disposizione
dei campi ipotizzata erroneamente: è stato corretto e testato prima del commit
di esecuzione; nessun fit scientifico è stato eseguito con quella versione.

Il rilievo sui flag SP3 non viene applicato: le colonne 75/76 riguardano il
clock SP3, che non è usato; 79/80 riguardano manovre/predizioni orbitali e sono
già rifiutate. La distinzione è esplicita nella
[specifica SP3-d, pp. 11–12](https://files.igs.org/pub/data/format/sp3d.pdf)
ed è ora coperta da un test dei quattro casi.

## Prossimo lavoro

La coerenza dell'orientamento PCO con il prodotto CODE è implementata.
Restano risposta direzionale del codice, errori dell'assetto, contributi delle
stazioni e dei mezzi di propagazione, bias dei ricevitori e correlazioni fisiche.
Il leggero aumento dei residui di calibrazione impedisce di presentare questo
come un miglioramento dimostrato dell'accuratezza. S2/G3 restano incompleti.

Riproduzione con destinazione nuova, fuori dagli archivi:

```text
python -m research.exploratory.reference_attitude experiments/positioning_g14_doy246_network research/exploratory/inputs/timed_reference_products/g14 research/exploratory/inputs/reference_biases/g14 research/exploratory/inputs/reference_antennas/g14 research/exploratory/inputs/reference_attitudes/g14 NUOVO_G14.json
python -m research.exploratory.reference_attitude research/exploratory/inputs/g12_doy248 research/exploratory/inputs/timed_reference_products/g12 research/exploratory/inputs/reference_biases/g12 research/exploratory/inputs/reference_antennas/g12 research/exploratory/inputs/reference_attitudes/g12 NUOVO_G12.json
python -m pytest research/exploratory/tests/test_reference_attitude.py -q
```
