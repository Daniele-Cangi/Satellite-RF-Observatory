# S2a — Modello al tempo del ricevitore

Stato: prima consegna di S2, validata in simulazione il 10 settembre 2026.
S2 resta aperto. Il modulo non ammette campagne RF reali e non sostituisce v1.
S0/S1 e i cinque eventi storici conservano codice, risultati e significato.

## Informazione nuova verificata

Verificare se posizione, velocità e orologio si possono recuperare anche con
tempi di ricezione ed emissione distinti, rotazione durante il volo del segnale,
orologi diversi per stazione e rumore correlato. Il controllo indipendente usa
un generatore in assi inerziali; il fit usa assi terrestri e una derivata implicita.
Non viene utilizzata alcuna effemeride del bersaglio, reale o di inizializzazione.

## Tempi, assi e segni

Ogni tempo è un piccolo offset in secondi da un'epoca base GPST intera,
dichiarata insieme ai dati. `local_gpst_seconds` sottrae date e secondi interi
prima di lavorare con le frazioni; non converte GPST in UTC. Gli assi ECEF
ruotano uniformemente rispetto ad assi inerziali coincidenti all'epoca base.
È una Terra idealizzata: non sono applicati EOP, precessione, nutazione o maree.

Il vettore incognito contiene undici parametri:

`[p0_x, p0_y, p0_z, v0_x, v0_y, v0_z, a_x, a_y, a_z, b_s0, b_s1]`.

Posizione, velocità e accelerazione sono componenti ECEF. La velocità è la
derivata nelle coordinate rotanti, non la velocità inerziale. Gli errori di
orologio sono positivi se l'orologio è avanti rispetto a GPST. In metri:

```text
T               = tempo marcato dal ricevitore
B_r(T)          = a_r + d_r*T                     [m]
t_r             = T - B_r(T)/c                    [s GPST locali]
k               = dt_r/dT = 1 - d_r/c
p(t_s)          = p0 + v0*t_s + a*t_s²/2         [m ECEF]
B_s(t_s)        = b_s0 + b_s1*t_s                 [m]
tau             = t_r - t_s
y               = Rz(-omega*tau)*p(t_s)
rho             = |y - station| = c*tau
P(T)            = rho + B_r(T) - B_s(t_s)         [m]
```

`Rz` è una rotazione attiva, positiva antioraria. Il segno negativo trasforma
gli assi terrestri all'emissione negli assi terrestri alla ricezione. La radice
del tempo di volo dipende dalla geometria provata nel fit; non si assume che
`P/c` sia il tempo di volo geometrico. Gli orologi sono parte delle equazioni.

Con `n=(y-station)/rho`, `v_rot=Rz(-omega*tau)*v(t_s)` e
`A=n·(v_rot + omega_cross_y)`, la derivata implicita è:

```text
d(rho)/dt_r = (n·v_rot)/(1 + A/c)
dt_s/dT    = (1 - (d(rho)/dt_r)/c)*k
dP/dT      = (d(rho)/dt_r)*k + d_r - b_s1*(dt_s/dT)
```

Questa è una variazione istantanea per secondo del tempo marcato dal
ricevitore. Il denominatore del tempo ritardato e il fattore `k` sono inclusi.
In questa simulazione la fase senza ambiguità variabile segue la stessa
geometria del codice: non è una proprietà generale delle osservazioni RF.

Il calcolo segue le convenzioni geometriche descritte da
[ESA, coordinate satellitari](https://gssc.esa.int/navipedia/index.php/Satellite_Coordinates_Computation)
e [ESA, tempo di emissione](https://gssc.esa.int/navipedia/index.php/Emission_Time_Computation).
Le equazioni differenziali sopra sono la derivazione adottata dal prototipo.

## Confine dell'adattatore Doppler

`doppler.py` legge singoli campi RINEX e supporta solo GPS C1C/C2W/D1C/D2W,
con L1C/L2W per gli indicatori di aggancio. Non legge o qualifica file interi.
La conversione usa `range_rate = -c/f * D` e frequenze L1 1575,42 MHz,
L2 1227,60 MHz. Pesi ionosphere-free: `alpha=f1²/(f1²-f2²)`, `beta=1-alpha`.
La matrice di trasformazione propaga tutta la covarianza dei quattro valori,
comprese le correlazioni fra codice e Doppler. Non elimina altri errori RF.

Le regole derivano da [IGS, RINEX 3.05](https://files.igs.org/pub/data/format/rinex305.pdf),
sezioni 4.4 e 6.7, tabella 14: Doppler positivo in avvicinamento; LLI nei campi
di fase. La politica locale respinge campi mancanti/zero, epoche non normali,
interruzioni della cadenza e qualsiasi LLI di fase non nullo. È conservativa:
anche un Doppler realmente zero risulta ambiguo nella codifica dei mancanti.
Non si inventano campioni, non si cambia segnale e non si interpolano salti.
Un LLI assente o zero non dimostra da solo continuità fisica dell'aggancio.

Il futuro importatore deve verificare versione, GPST, `RCV CLOCK OFFS APPL`,
scala dei campi, correzioni DCB/PCV, cambi di header, contesto del campione
precedente e comportamento del ricevitore. Deve inoltre qualificare la base
temporale e l'intervallo di media effettivi del Doppler. RINEX stabilisce le
unità e il segno; questa sola conversione non dimostra che il Doppler di ogni
strumento coincida con la derivata istantanea per secondo marcato usata qui.

## Calibrazione e covarianze

`clock_drift.py` stima offset e deriva di una stazione con GLS su residui di
orologio derivati da riferimenti non bersaglio: almeno tre epoche e quattro
satelliti distinti a ciascuna. La matrice completa conserva correlazioni nel
tempo e fra riferimenti. Un salto non viene corretto tagliando residui: il
modello affine può fallire il controllo chi-quadro nominale all'1%.

L'ammissione elimina i record etichettati come bersaglio prima di accedere ai
valori; il confine numerico li rifiuta nuovamente. I test introducono payload
che genererebbero errore se interpretati numericamente. Ciò protegge questo
confine, senza provare la provenienza fisica dei residui forniti dal chiamante.
La rimozione testuale dei blocchi di navigazione v1 resta invariata.

Nel fit cinematico i coefficienti ricavati dai riferimenti entrano come dati
gaussiani indipendenti dalle misure del bersaglio. Sono stimati congiuntamente
alla traiettoria: la covarianza completa include i termini incrociati. Non si
trattano tempi corretti e coefficienti di orologio come esatti. Il chiamante
può fornire una covarianza comune fra tutte le stazioni; il caso registrato
usa calibrazioni sintetiche indipendenti tra stazioni.

La covarianza delle osservazioni ha ordinamento: tutti i codici, poi tutte le
variazioni; all'interno, epoca e stazione. Lo studio usa sigma 20 m / 0,05 m/s,
correlazione temporale esponenziale con scala 60 s, correlazione codice/rate
0,2 e componente comune alle stazioni 0,15. I residui dei riferimenti hanno
sigma 3 m indipendente. Sono assunzioni note della simulazione.

SVD del Jacobiano scalato controlla rango e covarianza locale del fit congiunto.
L'inizializzazione deriva solo da codici e variazioni. I rami trovati dal
solutore al singolo istante sono raffinati; un fallimento di raffinamento resta
esplicito. Questa ricerca finita non certifica l'unicità globale.

## Troncamento e prova sintetica

Per un limite `J` sulla norma della terza derivata ECEF, valido su tutto
l'intervallo, il resto di Taylor quadratico è al più `J*|t|³/6` per posizione
e `J*t²/2` per velocità. Includere anche gli istanti di emissione precedenti
al primo tempo di ricezione. Il controllo respinge budget insufficienti,
senza scegliere un nuovo arco dopo aver visto le conferme.

Questo limite riguarda il Taylor attorno a uno stato noto; **non** è un limite
sull'errore dei coefficienti stimati o una maggiorazione completa delle
osservazioni. Non è sommato alla covarianza come se certificasse copertura.
La propagazione dei difetti di modello nel problema inverso resta da costruire.

Disegno di sviluppo S2a: undici tempi da −300 a 0 s, sette stazioni del disegno
S1; ottava stazione e tempi +30/+60 esclusi dal fit. Traiettoria quadratica e
otto orologi inventati, dichiarati nel JSON. Quattro casi conservati: senza
rumore; rumore correlato con seme 20260910; jerk non modellato; salto non
segnalato di 300 m sul codice di una stazione. Il salto è un difetto sintetico
del dato, non una simulazione dettagliata del transitorio di un ricevitore.
Nessuna statistica di copertura viene ricavata da una sola replica rumorosa.

Il generatore risolve una radice scalare in assi inerziali, ruotando separatamente
trasmettitore e ricevitore; ricava il rate con una differenza a cinque punti.
Non richiama geometria, rotazione o derivata del modello da verificare.
Le predizioni vengono serializzate e improntate prima della generazione delle
conferme sintetiche. È un controllo locale riproducibile, non un sigillo pubblico.
Le predizioni dei casi respinti sono conservate solo come diagnostica.

## Lavoro S2b ancora necessario prima di S3

1. Importatore RINEX completo e fixture ammesse prima di nuove conferme;
   verifica di header, segnali, campioni mancanti, cambi d'aggancio e base
   temporale effettiva del Doppler. Nessun accesso improvvisato a nuovi bersagli.
2. Generazione dei residui di calibrazione da effemeridi dei soli riferimenti,
   con deriva, intervallo di validità e regole per le previsioni fuori arco.
   Il modulo attuale riceve residui già preparati e non li qualifica fisicamente.
3. Propagazione, antenna, coordinate terrestri, errori condivisi con i riferimenti,
   differenze fase/codice e relatività: budget e covarianze giustificati. L'ipotesi
   di indipendenza fra calibrazione e rumore del bersaglio va verificata o estesa.
4. Inviluppo dell'errore inverso dovuto a troncamento, scelta preventiva di arco
   e ordine, predizioni osservative con errore sistematico e orologio della
   stazione esclusa incerto. Qui l'orologio escluso è noto per costruzione.
5. Congelamento di questi criteri e dei manifest esatti S3 prima di acquisire
   i nuovi campioni di conferma. Il blueprint di 24 casi non è eseguibile.

## Riproduzione

Con `requirements-positioning.txt`, dalla radice della repository:

```text
python -m pytest research/kinematic/tests -q
python -m research.kinematic.s2_validation PERCORSO_NUOVO_REPORT.json
```

L'output rifiuta la sovrascrittura. Il report registra tutti i casi, le
predizioni, le covarianze, le impronte dei sorgenti e le versioni del runtime.
I confronti numerici fra piattaforme richiedono tolleranze; non si promettono
risultati byte-identici. Il report S1 e i suoi sorgenti non sono modificati.
