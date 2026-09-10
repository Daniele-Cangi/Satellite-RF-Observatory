# S2b — Dai file RINEX alla verifica dei riferimenti

Consegna del 10 settembre 2026: importazione delle osservazioni e navigazione
dei soli riferimenti, stima dell'orologio dai codici, previsione del Doppler
escluso dal fit. I file di verifica sono interamente sintetici. Non è una nuova
stima del bersaglio e non completa S2 o autorizza una campagna S3.

## Informazione fisica verificabile

L'orologio ricavato dai codici e dalle effemeridi dei riferimenti deve spiegare
anche le variazioni Doppler, entro un errore dichiarato. Il Doppler non entra
nel fit dell'orologio: un segno incompatibile non può essere assorbito cambiando
la deriva. La prima prova usa quattro satelliti inventati, una stazione e
undici epoche, con tempo di volo, rotazione e orologi distinti.

L'esito `REFERENCE_MODEL_ACCEPTED` indica soltanto compatibilità condizionale
dei riferimenti con il modello fornito. Tutti gli esiti mantengono
`real_rf_qualified=false`. Il nome/modello/firmware nel file non sono una prova
della base temporale, della media o delle correzioni applicate al Doppler.

## Importazione delimitata e riproducibile

`rinex_observations.py` supporta il sottoinsieme dichiarato RINEX 3.04/3.05
osservazioni GPS, anche in un file osservativo misto. Legge header, continuazioni
dei tipi di osservazione, epoche e campi a larghezza fissa. Servono C1C/C2W,
D1C/D2W e L1C/L2W per i flag. I campi non GPS e quelli del bersaglio non
vengono interpretati numericamente.

Il chiamante dichiara prima dell'importazione: bersaglio escluso, lista esatta
dei riferimenti, epoca base GPST, tempi, cadenza e covarianza delle quattro
osservabili grezze. Viene letto anche un campione precedente per controllare
la continuità al primo istante. Non si scelgono finestre o segnali alternativi.
Il lettore termina al primo tempo successivo all'ultimo previsto, prima di
interpretare le misure che seguono.

Le regole usano il formato e le convenzioni di
[IGS, RINEX 3.05](https://files.igs.org/pub/data/format/rinex305.pdf),
sezioni 5.2–5.3, 6.7 e appendici A2/A3/A6. Sono scelte di supporto del
prototipo, non affermazioni che gli altri file RINEX siano illegali:

- GPS esplicito, marker GEODETIC, identità completa del ricevitore, coordinate
  terrestri e offset d'antenna finiti, intervallo uguale al piano.
- Rifiuto di clock già applicati, fattori di scala, DCB/PCV applicate, header
  sconosciuti o semanticamente non gestiti, tipi di osservazione incompleti.
- Rifiuto dell'arco per ogni evento 1–6, incluso un aggiornamento dell'header.
  Non si riprende automaticamente dopo reset, perdita d'aggancio o cambio.
- Ogni campione/riferimento previsto deve essere presente e ammissibile.
  Mancanti, Doppler zero ambiguo e flag di fase producono motivi di rifiuto;
  nessun riempimento, scarto silenzioso o ricerca di una rete migliore.

Eventuali offset di clock riportati ma non applicati sono conservati come
contesto del formato e non usati come calibrazione. `SYS / PHASE SHIFT` è
metadato costante: i valori di fase non entrano nella stima; si usano i flag.
Il supporto non include Hatanaka/gzip, ogni costellazione o tutti gli header.

L'impronta `source_sha256` è sui byte UTF-8 del testo fornito al parser, non
sull'originale compresso o su byte eventualmente normalizzati dal chiamante.
L'impronta separata `admitted_observations_sha256` riguarda solo il contenuto
ammesso e il suo contesto. Alterare numeri esclusi cambia la prima e lascia
invariata la seconda, come verificato dai test.

## Navigazione e modello dei riferimenti

`reference_bridge.py` importa il sottoinsieme di navigazione GPS RINEX 3.04/
3.05 a blocchi di otto righe. Scarta il blocco del bersaglio e dei satelliti
non dichiarati prima della conversione numerica, poi verifica campi mancanti,
finitudine, salute, settimana e intervallo di validità dei riferimenti.
L'input di navigazione misto non è ancora supportato.

Viene scelto un solo record per riferimento, quello con toc più vicino al
centro dell'arco, e mantenuto per tutte le derivate. Non vengono cambiate
effemeridi dentro una differenza temporale. Il limite è il minore tra l'età
massima dichiarata (7200 s nello studio) e metà dell'intervallo di fit. Sono
controllati sia toc sia toe con settimana completa, senza ricondurre una
settimana sbagliata a un'età artificialmente piccola.

Il modello usa la propagazione broadcast GPS già presente in `positioning/`,
inclusa la correzione relativistica del clock dei riferimenti. Quella libreria
rimane invariata. La propagazione del bersaglio è rifiutata di nuovo al confine
numerico. La posizione terrestre proviene dall'header e dall'offset d'antenna;
non viene adattata ai dati del bersaglio.

La nuova funzione risolve geometricamente il tempo di volo per ogni ricezione,
con il clock del ricevitore espresso come `B_r(T)=a+d*T`. Può includere il
modello troposferico nominale v1 sia nel codice sia nel tempo di volo; lo studio
registrato usa il vuoto. L'opzione troposferica non è una calibrazione meteo,
un bilancio dei bias o una qualificazione dei dati reali.

## Calibrazione e verifica del Doppler

Le sole pseudodistanze dei riferimenti stimano offset e deriva con GLS. La
covarianza deve essere fornita esplicitamente e ordinata per tutti i codici,
poi tutti i Doppler, ciascuno nell'ordine epoca/riferimento. Sono controllati
completezza, rango, elevazione e residui nominali con soglia p = 0,01.

Se i codici falliscono, il controllo Doppler non viene eseguito. Se passano,
la derivata temporale prevista viene confrontata con il Doppler non usato nel
fit. Una differenza a cinque punti usa lo stesso record broadcast nell'intero
stencil e include l'evoluzione della geometria e dei clock.

La covarianza del residuo Doppler include l'incertezza dei clock stimati e la
correlazione tra codice e Doppler. Indicando con `K` il guadagno GLS del fit
dei codici e con `J_r` la sensibilità del rate ai clock:

```text
errore residuo Doppler = errore Doppler - J_r K errore codice
A                     = [-J_r K, I]
Sigma_residuo         = A Sigma_osservazioni A^T
```

La formula evita di sommare due varianze ignorando i termini incrociati. Un
test con 60.000 realizzazioni gaussiane e fit lineari separati ne controlla
la covarianza; è un controllo numerico della propagazione, non copertura RF.
Un altro test verifica che un errore comune ai riferimenti non scompaia
mediando più campioni.

## Dati e prove

Le fixture in `tests/fixtures/s2b_*.rnx` contengono solo dati inventati:
orbite circolari dei quattro riferimenti, stazione [6378137, 0, 0] m e clock
14000 m + 0,73 m/s × T. Il generatore usa assi inerziali e una radice scalare,
indipendenti dal modello broadcast del calibratore. I numeri vengono arrotondati
al formato RINEX F14.3. Gli osservabili hanno termini ionosferici con segno
opposto tra codice e fase/rate; la combinazione duale li cancella al primo
ordine. G08 non ha una traiettoria: contiene deliberatamente testo non numerico.

La covarianza sintetica grezza è diagonale: sigma 1 m per ciascun codice e
0,01 Hz per ciascun Doppler. Non rappresenta una precisione misurata. I sei
casi sono nominale quantizzato, Doppler invertito su un riferimento, salto di
300 m sui codici di un riferimento, Doppler mancante, reset ed effemeride fuori
dal limite di età. Tutti restano nel report.

```text
python -m pytest research/kinematic/tests/test_reference_bridge.py -q
python -m research.kinematic.s2b_validation NUOVO_REPORT.json
```

Il writer rifiuta sovrascritture. I report e i sorgenti S1/S2a sono preservati.

## Prossimo lavoro necessario

Questa consegna collega lettura, calibrazione e controllo indipendente dei
riferimenti. Restano aperti la caratterizzazione del Doppler di ricevitori
reali, errori delle effemeridi dei riferimenti e dei segnali, DCB/antenne,
propagazione, coordinate terrestri incerte e correlazioni condivise.

Occorre poi propagare questi errori e il troncamento cinematico nel problema
inverso del bersaglio, includendo clock incerto della stazione esclusa e
previsioni fuori arco. Non basta sommare il resto di Taylor a una covarianza.
L'API numerica non certifica questi limiti: prima di una campagna servono
bilancio verificato, regole di qualifica e manifest S3 esatti congelati.
