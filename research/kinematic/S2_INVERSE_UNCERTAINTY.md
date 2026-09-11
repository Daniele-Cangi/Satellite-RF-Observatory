# S2 — Propagazione locale degli errori inversi

Questo blocco collega gli errori di osservazione, calibrazione e coordinate
alla posizione/velocità ricostruita e al residuo previsto su un ricevitore
escluso. Usa il fit S2a invariato; non completa la qualifica RF o il bilancio
totale richiesto per S3. Report: [results/S2_UNCERTAINTY_REPORT.md](results/S2_UNCERTAINTY_REPORT.md).

## Convenzioni e confini

`inverse_uncertainty.linearize` richiede un fit `CONDITIONAL_MODEL_ACCEPTED`
e una calibrazione accettata per ogni ricevitore, incluso quello escluso.
Non accetta un fit ambiguo, incompleto o respinto. I flag sono un contratto
del chiamante, non una verifica della provenienza fisica delle calibrazioni.
Non legge misure escluse, orbite del bersaglio o nuovi dati Internet.

Gli errori di ingresso sono perturbazioni dei valori forniti al software:

1. Codici e range rate, ordinati prima tutti i codici, poi tutti i rate;
   ciascun gruppo è ordinato per epoca e poi stazione.
2. Media della calibrazione di ogni clock: offset in metri, drift in m/s.
3. Coordinate ECEF delle stazioni di fit in metri.
4. Clock e coordinate della stazione esclusa.
5. Errore della futura misura esclusa: codice e rate, sottratti al predetto.

Le uscite sono xyz, velocità xyz, codice e rate predetti meno osservati.
Posizione e velocità sono valutate al tempo GPST specificato; la coppia RF
è valutata allo stesso offset numerico del tag del ricevitore, con la sua
correzione di clock. Questi due istanti fisici non sono identificati fra loro.
Il rumore della futura misura entra tramite la covarianza, senza leggerne il
valore. Una matrice completa può conservare correlazioni temporali, fra
stazioni, fra osservabili, fra calibrazione e osservazioni, e con il holdout.
Coordinate statiche incerte non equivalgono a un modello di moto terrestre.

## Derivata dell'estimatore e covarianza

Sia θ il vettore di stato e clock, J la derivata del modello rispetto a θ,
W lo sbiancamento delle osservazioni e delle calibrazioni usato dal fit S2a,
H la derivata rispetto alle coordinate delle stazioni. La risposta locale è

```text
δθ ≈ (W J)^+ W ([δosservazioni, δclock] − [H δstazioni, 0])
δuscita = G δθ + Gclock δclock_escluso + Gterra δterra_esclusa − δmisura_esclusa
Σuscita = M Σingresso Mᵀ
```

La pseudoinversa usa SVD in coordinate scalate, controllando il rango con
la stessa soglia S2a. Evita di formare le equazioni normali. È una risposta
Gauss–Newton a pesi fissi: trascura termini di curvatura legati a residui
non nulli e non ripete la ricerca dei rami dopo ogni possibile errore.
Le differenze centrali e i refit finiti ne verificano alcuni casi locali.

La propagazione con covarianze correlate segue la linearizzazione del
[JCGM 100:2008, §5.2](https://www.iso.org/sites/JCGM/GUM/JCGM100/C045315e-html/C045315e_FILES/MAIN_C045315e/05_e.html).
Questo riferimento motiva la formula, non certifica il modello o i numeri
di incertezza assunti in questo progetto.

Il fit S2a continua a usare blocchi osservazioni/calibrazioni indipendenti.
Trasportare una covarianza più generale **non lo trasforma in un fit GLS
ottimale per quella covarianza** e non ricalibra il suo p-value. Il test dei
residui resta quello nominale; nessuna nuova accettazione RF deriva dal
bilancio. Servirà un estimatore e un test coerenti con il modello completo.

Il raggio locale di posizione/velocità è sqrt(χ²₃(.95) λmax(Σ₃×₃)).
Gli intervalli RF usano 1,95996 sigma marginali: non sono una regione
simultanea codice+rate, né una banda simultanea su tutti i tempi.
L'interpretazione gaussiana è condizionale ai parametri e alla linearizzazione.
La matrice di ingresso può essere semidefinita: ingressi esattamente noti
sono ammessi; varianze negative e correlazioni impossibili vengono respinte.

## Errori sistematici e troncamento

Il chiamante dichiara colonne B di perturbazioni con coefficienti u in [-1,1].
Le colonne D rappresentano l'effetto diretto degli **stessi coefficienti**
sull'errore di uscita. Per un moto cubico, D sottrae la variazione della
posizione/velocità vera futura e della coppia RF vera. Si propaga quindi

```text
errore_locale = (M B + D) u
limite per componente = somma dei valori assoluti della riga
limite della norma xyz = somma delle norme xyz delle colonne
```

Questi limiti valgono per il modello affine dichiarato: la prima formula è
esatta per la scatola lineare, la seconda è conservativa per disuguaglianza
triangolare. Non sono limiti globali del fit non lineare. I sei assi e i
vertici usati nei test sono diagnostica, non una certificazione globale.
Il bilancio gaussiano e quello sistematico vengono riportati separatamente;
non produciamo un campo «incertezza totale 95%».

Lo studio fissa prima dei controlli:

- sette stazioni di fit, un holdout, l'arco S2a −300…0 s e previsione a +60 s;
- covarianza S2a codice/rate e calibrazioni sintetiche senza rumore estratto;
- sigma coordinate 0,5 m per asse, anche sul holdout; clock del holdout
  calibrato sugli stessi quattro riferimenti inventati, con errori nominali
  indipendenti nel caso base; rumore futuro sigma 20 m e 0,05 m/s, ρ = 0,2;
- un confronto fra clock con sigma condivisi 5 m e 0,02 m/s e clock con
  identiche varianze marginali ma privi di correlazioni;
- sei perturbazioni sistematiche: x della prima stazione +2 m, drift comune
  +0,02 m/s, scarto temporale del solo arco di fit +1 ms, tre componenti
  di jerk ECEF costante con modulo per asse 2×10⁻⁷ m/s³.

Le perturbazioni sistematiche sono diagnostiche distinte dagli errori
gaussiani: gli stessi nomi di clock non autorizzano a sommarli come se
fossero fonti indipendenti. Il caso temporale sposta la valutazione fisica
dell'intero osservabile: non qualifica averaging Doppler, UTC/GPST o firmware.
Il limite sul jerk è inventato per questo studio, non desunto da satelliti.
Un jerk costante a tre coefficienti non esaurisce tutte le funzioni con
terza derivata limitata. Restano da trattare anche la distorsione del fit
per jerk variabile e il resto non lineare.

Le differenze del generatore inerziale indipendente definiscono la risposta
del moto cubico. Poi si confrontano refit completi e due casi cubici
effettivi: il piccolo jerk dichiarato e il forte jerk già respinto in S2a.
Il secondo si arresta prima della previsione esclusa se il fit fallisce.
La verità sintetica è nota per costruire lo studio: l'hash prima dei controlli
è solo una ricevuta di sviluppo, non una prova di cecità sperimentale reale.

## Riproduzione e lavoro ancora necessario

```text
python -m pytest research/kinematic/tests/test_inverse_uncertainty.py -q
python -m research.kinematic.uncertainty_study NUOVO_REPORT.json
```

Il writer rifiuta sovrascritture; il report registra sorgenti, ambiente,
hash delle covarianze ricostruibili dalla ricetta, ipotesi, tutti i confronti
e tutti i criteri. I sorgenti e le evidenze S1/S2a/S2b restano invariati.

Prima di S3 servono qualificazione di ricevitori e tempi, errori dei
riferimenti/antenne/propagazione e loro correlazioni stimate o motivate,
un fit e un test dei residui coerenti con tali errori, controllo della
non linearità e del troncamento generale, infine manifest esatti congelati.
Il sito e le acquisizioni di nuovi bersagli restano sospesi.

Il successivo [fit congiunto](S2_JOINT_FIT.md) implementa un estimatore
separato che usa un'unica covarianza anche nell'ottimizzazione e nel test
locale dei residui. Questa estensione non modifica i risultati qui descritti
e non risolve ancora la qualifica fisica o la copertura non lineare totale.
