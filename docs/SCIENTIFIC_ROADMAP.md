# Satellite-RF-Observatory — Posizione, movimento e verifica predittiva

Progetto approvato il 10 settembre 2026. Priorità: sviluppo scientifico del
software. Sito, API, Docker e hosting sono sospesi; l'archivio privato resta una
documentazione dei cinque eventi conclusi. Nessuna modifica a quegli eventi.

## Obiettivo misurabile

Passare dalla dimostrazione di una posizione storica a un motore che ricostruisce
posizione e movimento su un intervallo, prevede misure escluse dal calcolo e
quantifica i propri limiti. La determinazione di orbite GNSS è un campo già
consolidato: questo progetto non assume una novità assoluta del principio fisico.
Il contributo da verificare è un percorso aperto, riproducibile e con esclusione
dello stato del bersaglio, valutato su casi dichiarati in anticipo.

La versione di riferimento è il codice al commit
`dd101e4384911c1c5afb2d1670454f903a0cd5c2`. Il primo prototipo nuovo vive in
`research/kinematic/`; non sostituisce `positioning/` e non modifica i protocolli
congelati. Una simulazione non è una nuova prova satellitare.

## Consegne e condizioni di avanzamento

| Blocco | Consegna | Condizione per proseguire |
|---|---|---|
| S0: diagnosi | Rapporto dei cinque eventi; geometria e incertezza delle soluzioni con artefatti disponibili | Hash verificati, metriche mancanti esplicite, nessuna ristima degli eventi |
| S1: prototipo sintetico | Stima cinematica con codice e variazione di pseudodistanza; confronto controllato con solo codice | Recupero senza rumore, rango, unità e derivate verificati; risultati di tutti i casi; vantaggio predittivo nominale misurato |
| S2: modello osservativo reale | Doppler RINEX, convenzioni, tempi di emissione/ricezione, rotazione terrestre, calibrazione della deriva degli orologi | Controlli indipendenti e simulazioni complete; bilancio degli errori di modello prima di ogni conferma |
| S3: campagne preregistrate | Riferimento omogeneo v1 e confronto v1/v2 su dati di conferma nuovi | Tutti i tentativi registrati, previsioni congelate, nessuna selezione basata sull'orbita |
| S4: valutazione | Rapporto su errori, incertezze, disponibilità, fallimenti e costi | Una decisione motivata: consolidare, correggere il modello o fermare la direzione |

## S0 — Cosa possiamo concludere dagli eventi esistenti

Leggere i ricevuti originali e verificare le impronte, senza eseguire di nuovo
acquisizione, stima o rivelazione. Riportare errore osservato, raggio condizionale,
componente statistica, inviluppo degli errori sistematici e margine, quando
presenti. Analizzare autovalori della covarianza locale e orientamento dell'asse
meno vincolato rispetto alla direzione geocentrica del risultato già rivelato.
Quest'ultima analisi è diagnostica di sviluppo e non selezione di nuovi eventi.

Non trasformare il conteggio dei cinque eventi, con regole differenti, in una
percentuale di successo del servizio. Le componenti dell'inviluppo non sono
errori reali misurati e non si sommano in quadratura se il protocollo le somma
linearmente. La covarianza locale non certifica un limite globale.

## S1 — Protocollo del primo esperimento sintetico

Questo blocco verifica informazione e implementazione in un problema ideale,
prima dell'adattatore RF. Coordinate cartesiane in metri; ricevitori fissi;
tempi comuni ideali in secondi; pseudodistanza in metri; sua derivata in m/s.
Non sono dati RINEX, né una simulazione completa del tempo di volo, della Terra
rotante, dell'atmosfera o della calibrazione dei ricevitori.

Il modello quadratico stima 11 parametri: posizione, velocità e accelerazione
cartesiane all'ultimo istante del fit, più offset e deriva di orologio espressi
in metri e m/s. Il confronto con moto rettilineo stima 8 parametri. Nessuna
orbita o stato vero entra nell'inizializzazione: posizione e offset vengono
ricavati dalle pseudodistanze; gli altri parametri dai dati o da valori neutri.

Disegno fissato prima dell'esecuzione:

- Sette stazioni sintetiche distribuite su una sfera di raggio 6.371.000 m;
  un'ottava stazione è esclusa da fit e inizializzazione.
- Fit a 11 tempi da −300 a 0 secondi, ogni 30 secondi. Verifica a +30 e +60
  secondi; quelle misure non entrano nel fit. Un arco di cinque minuti non
  giustifica automaticamente un modello a velocità costante.
- Traiettoria inventata: posizione [26.000.000, 2.000.000, 4.000.000] m,
  velocità [−250, 2300, 500] m/s, accelerazione [−0,52, −0,04, −0,08] m/s²;
  offset 75.000 m e deriva 12 m/s. Non è una vera effemeride satellitare.
- Rumori nominali indipendenti: sigma codice 20 m, sigma variazione 0,05 m/s.
  Sono assunzioni della simulazione, non prestazioni misurate dei ricevitori.
- 20 repliche accoppiate, semi 20260910–20260929: stesse pseudodistanze per
  confronto con e senza variazioni, nessuno scarto di repliche sfavorevoli.
- Casi aggiuntivi dichiarati: rete concentrata, moto lineare applicato alla
  traiettoria accelerata, jerk non modellato e bias persistenti per stazione.
  Questi casi misurano fragilità; non si cancellano perché peggiorano il report.

Condizioni nominali di S1: recupero senza rumore entro 0,1 m e 0,001 m/s;
rango pieno con geometria adeguata; almeno dimezzamento della mediana del
raggio locale al 95% per la velocità aggiungendo variazioni; errore mediano di
posizione a +60 s non peggiore rispetto al modello quadratico con solo codice.
Il moto lineare inadeguato deve essere respinto dal controllo residui con
soglia chi-quadro nominale all'1%. I test sul rango devono respingere ricevitori
coincidenti. I risultati sono condizionali al rumore e al modello dichiarati;
20 repliche non dimostrano copertura statistica generale al 95%.

Se S1 fallisce, registrare il motivo. Correggere difetti di implementazione
con test mirati; cambi di disegno o criteri richiedono una revisione esplicita,
non la riscrittura del risultato precedente.

## S2 — Il ponte necessario verso misure vere

Verificare segno e unità del Doppler per ogni osservabile supportata. Modellare
offset e deriva degli orologi, correlazioni nel tempo e fra code e variazioni,
perdita di aggancio, valori mancanti e discontinuità. Calibrare i ricevitori con
soli riferimenti non bersaglio. Dimostrare che l'esclusione dei record del
bersaglio resta valida anche per le nuove correzioni.

Lavorare su tempi di emissione e ricezione distinti; includere rotazione durante
il tempo di volo e un limite dell'errore di troncamento cinematico. Congelare
durata dell'arco, ordine del modello, parametri di disturbo e controllo residui.
La fase portante è una direzione successiva, con ambiguità e cycle slip propri.
Non importare precisioni di altri metodi come promesse del nostro motore.

## S3 — Due campioni e regole contro la selezione opportunistica

Prima campagna proposta: 24 tentativi v1, quattro PRN fissati e sei giorni
completi. Prima dei download, un manifest deve contenere i 24 piani esatti,
codice, fonti, rete, stazione esclusa, prior access e regole di arresto. Per
rendere controllabile l'assenza di accessi pregressi, preferire giorni successivi
al congelamento del manifest. Nessun download viene autorizzato da un manifest
con date o satelliti ancora simbolici: completarlo è parte del lavoro S3.

Il campione v1 misura disponibilità e ripetibilità del metodo attuale; dopo
rivelazione può servire allo sviluppo, non come conferma incontaminata di v2.
Un secondo campione distinto confronta v1 e v2: entrambi congelano risultati e
predizioni prima dell'accesso comune alle conferme. La popolazione del confronto
(supporto codice e supporto codice+Doppler) va distinta dalla disponibilità
complessiva, senza eliminare gli eventi che v2 non riesce ad ammettere.

Per v2 congelare previsioni delle osservazioni escluse a +30 e +60 s e della
stazione esclusa; poi rivelare quelle misure e infine il riferimento orbitale.
Qualunque variazione degli orizzonti deve precedere l'acquisizione di conferma.
Non propagare un'orbita esterna per inizializzare, scegliere o regolarizzare il
fit. Riferimenti orbitali che condividono dati di terra non sono prove
statisticamente disgiunte.

## S4 — Decisione finale e ritorno al prodotto

Pubblicare tutti i terminali, denominatori separati per disponibilità e
qualificazione, distribuzioni degli errori e delle incertezze, verifica
predittiva, sensibilità ai bias e costi misurati. Il campione limitato consente
un primo confronto, non una garanzia universale di copertura o prestazioni.

Riprendere il sito quando esiste una capacità nuova verificata su misure vere
e un dominio di utilizzo documentato. I risultati negativi possono richiedere
un'altra osservabile o una diversa rete, anziché più infrastruttura.

## Riferimenti e stato

- [ESA, osservabili GNSS](https://gssc.esa.int/navipedia/index.php/GNSS_Basic_Observables): codice, fase e Doppler; termini di propagazione e orologio.
- [ESA, determinazione precisa delle orbite](https://gssc.esa.int/navipedia/index.php/Precise_Orbit_Determination): contesto del lavoro già esistente nel settore.

Il report di esecuzione S0/S1 viene salvato separatamente in
`research/kinematic/results/`. Questo piano non è una preregistrazione completa
di una campagna reale. La prima consegna comprende S0, S1 e l'identificazione
esplicita dei requisiti ancora aperti per S2/S3.
