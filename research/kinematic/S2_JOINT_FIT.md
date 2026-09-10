# S2 — Fit congiunto di misure, clock e coordinate

`joint_fit.py` usa una singola covarianza dichiarata per le coppie codice/rate,
le calibrazioni dei clock e le coordinate terrestri. Lo stesso sbiancamento
determina stima, covarianza locale e test dei residui. Supera il limite del
precedente trasporto degli errori, che manteneva invariati i pesi S2a.
Il report è [results/S2_JOINT_REPORT.md](results/S2_JOINT_REPORT.md).

Il software resta un prototipo sintetico in vuoto: non certifica ricevitori,
propagazione o copertura globale. `receiver_time.py`, `inverse_uncertainty.py`
e tutti i sorgenti associati ai report precedenti rimangono invariati.

## Dati ammessi e parametri

Per N stazioni ed E epoche si forniscono, in ordine:

1. E×N codici, poi E×N rate, entrambi per epoca e poi stazione.
2. N coppie offset/drift del clock, in metri e m/s.
3. N coordinate terrestri xyz ECEF, in metri.

La covarianza ha dimensione (2EN+5N)² e può includere ogni correlazione fra
questi ingressi. Deve essere finita, simmetrica e definita positiva. Non viene
aggiunto jitter e non si stimano o aumentano varianze dai residui per ottenere
un'accettazione. Ingressi terrestri esattamente noti richiederebbero una
parametrizzazione ridotta; il nuovo fit non accetta una covarianza singolare.

Si stimano 11 parametri del bersaglio, 2N coefficienti dei clock e 3N coordinate
terrestri. Le coordinate sono parametrizzate come correzioni alle misure
fornite; sono vincolate dalle osservazioni terrestri e dalla covarianza, senza
un vincolo orbitale del bersaglio. I clock hanno analoga informazione dai
riferimenti. Stato iniziale e rami provengono esclusivamente dalle misure RF
e dai dati terrestri/calibrazioni consentiti: nessun seed orbitale del bersaglio.

La qualifica delle N calibrazioni è controllata prima di convertire in numeri
le misure del bersaglio. Un rifiuto interrompe il fit. I flag di qualifica sono
un contratto del chiamante: non provano da soli provenienza o qualità RF.

## Stima e test coerenti

Con y vettore dei dati, f(θ) modello congiunto e Σ = LLᵀ covarianza fissata:

```text
r(θ) = L⁻¹ (f(θ) − y)
θ̂ = argmin rᵀr
Jw = L⁻¹ J
Σθ ≈ (Jwᵀ Jw)⁻¹
K = Jw⁺ L⁻¹
Q = r(θ̂)ᵀr(θ̂)
ν = numero dati − rango Jw = 2EN − 11
```

La covarianza e il guadagno K sono calcolati via SVD scalata, senza formare
le equazioni normali e senza moltiplicare per Q/ν. Le differenze centrali
sulle coordinate terrestri usano un passo fisico di 1 m. Restano i controlli
di rango, i rami finiti e le soglie S2a; viene registrato ogni ramo fallito.

Nel problema **lineare gaussiano con covarianza nota**, Q ha distribuzione
χ² con ν gradi di libertà. Nel fit non lineare questa è un'approssimazione
locale, verificata qui con confronti finiti, non una copertura certificata.
La soglia resta p < 0,01. Gli esiti distinguono `MODEL_REJECTED`, `AMBIGUOUS`,
`BRANCH_SEARCH_INCOMPLETE` e `CONDITIONAL_JOINT_MODEL_ACCEPTED`.
Un fit numericamente indisponibile solleva un errore; non è accettato.

L'approssimazione e la ricerca finita dei minimi sono limiti usuali del
[fit non lineare](https://www.itl.nist.gov/div898/handbook/pmd/section1/pmd142.htm).
Per gli insiemi di problemi del NIST, trovare un minimo locale diverso
non prova di aver trovato il minimo globale: si veda la
[nota sui test di regressione non lineare](https://www.nist.gov/itl/sed/statistical-reference-datasets/strd-background-information/nonlinear-regression).
Questi riferimenti non qualificano i nostri ricevitori o le nostre ipotesi.

Il conteggio include le coordinate: 189 dati e 46 parametri nel caso a sette
stazioni e undici epoche, quindi **143 gradi di libertà**. Usare le coordinate
come nuisance non sottrae 21 gradi di libertà senza contare anche le loro
21 osservazioni. I clock seguono lo stesso principio.

## Previsione esclusa

`forecast_joint` richiede un fit accettato e una calibrazione accettata del
holdout. Il clock e le coordinate del holdout non entrano nell'ottimizzazione.
Non viene letto alcun codice/rate escluso. La covarianza estesa contiene il
blocco esatto usato dal fit, seguito da clock escluso (2), coordinate (3)
e rumore della futura coppia RF (2). Un hash impedisce di cambiare a posteriori
la covarianza dei dati di fit attraverso questa API.

La risposta è G K per i dati di fit, più gli effetti diretti di clock,
coordinate e rumore esclusi, con segno negativo per la misura futura.
L'intera matrice viene propagata, comprese le correlazioni fit/holdout.
Cambiare solo queste correlazioni cambia la covarianza prevista, non il
valore centrale né lo stato ricostruito. Non si applicano correzioni del
holdout stimate dai suoi residui o dai residui del fit.

Si riporta la covarianza locale dell'errore di previsione **non condizionata**
ai residui osservati o al superamento del test. Non è una promessa di copertura
del 95% per il sottoinsieme di prove accettate: selezione e non linearità
richiedono una qualifica aggiuntiva. Posizione/velocità sono al tempo GPST
richiesto; la coppia RF è al corrispondente offset numerico del tag ricevitore.

## Disegno sintetico fissato

`joint_study.py` usa l'arco, le stazioni e il generatore inerziale indipendente
S2a. Le calibrazioni sono dati gaussiani compressi **assunti ammessi**: non
si ripete qui l'importazione RINEX e non si simula un nuovo superamento della
qualifica dei riferimenti. Nessuna epoca, stazione o estrazione viene scelta
perché produce un risultato favorevole.

La base usa la covarianza codice/rate S2a, sigma clock 2 m e 0,01 m/s,
sigma coordinate 0,5 m, e il rumore futuro 20 m / 0,05 m/s con ρ = 0,2.
Per ciascuna stazione, due modi gaussiani indipendenti aggiungono:

- codice 30 m, calibrazione clock 25 m e coordinata x 2 m, con lo stesso
  coefficiente casuale;
- codice T×0,1 m/s, rate 0,1 m/s, calibrazione drift 0,08 m/s e coordinata y
  1 m, con un secondo coefficiente comune.

Un ulteriore modo di clock di 5 m è condiviso fra calibrazioni di fit e
holdout. Questi sono modi inventati di errore, non errori fisici misurati.
Le ampiezze non dipendono da orbita del bersaglio o residui osservati.

Il confronto mantiene identiche tutte le varianze e le covarianze interne
ai tre blocchi RF/clock/coordinate; solo le covarianze **fra** quei blocchi
vengono eliminate nell'ablazione. Anche in quel caso le coordinate restano
parametri incerti: non è un confronto confuso fra due geometrie diverse.

Sedici estrazioni, seed 20260911, sono fornite a entrambi gli estimatori.
Si conservano entrambe le stime e tutti i rifiuti. Solo i fit congiunti
accettati producono previsioni, registrate con hash prima della valutazione
sintetica esclusa. Gli errori di fit e holdout sono estratti congiuntamente;
il generatore conosce la verità sintetica, quindi non è una nuova prova cieca
su un satellite. Sedici casi non qualificano code di probabilità all'1%.

Due stress separati conservano il salto di codice di 300 m e il forte jerk
S2a. Il confronto non aumenta il rumore dichiarato per farli passare.
Per diagnosticare il test dei residui, si calcolano inoltre i momenti esatti
della forma quadratica **linearizzata** sotto la covarianza generatrice:
E[Q] = tr(A) e Var[Q] = 2 tr(A²). La loro corrispondenza con ν e 2ν vale
nel modello locale corretto, non automaticamente nell'ablazione.

## Riproduzione e prossimi passi

```text
python -m pytest research/kinematic/tests/test_joint_fit.py -q
python -m research.kinematic.joint_study NUOVO_REPORT.json
```

Il writer rifiuta sovrascritture. Il report include sorgenti, ambiente,
ricetta e hash della covarianza, momenti, nominale, tutte le coppie e stress.
Resta necessario qualificare la covarianza fisica dalle fonti non-target,
ricevitori e propagazione, controllare la calibrazione non lineare/selezione
del test e integrare un inviluppo sistematico e di troncamento generale.
Nessun completamento S2, acquisizione S3 o riavvio del sito è implicito.
