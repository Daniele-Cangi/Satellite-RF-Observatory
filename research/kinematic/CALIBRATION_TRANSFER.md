# Trasferimento degli errori di calibrazione

Questo incremento sostituisce una valutazione solo qualitativa con un operatore
numerico verificabile. È ricerca locale lineare su dati inventati: nessun nuovo
download RF, nessuna orbita bersaglio, nessuna qualificazione fisica o S3.
DOY240 e i suoi audit restano immutati; non sono stati reinterpretati come
misure di covarianza o come vincoli sugli errori comuni.

## Modello e quantità calcolate

La distinzione tra orologi, propagazione ed errori delle misure segue la
[descrizione delle osservabili GNSS di ESA](https://gssc.esa.int/navipedia/index.php/GNSS_Basic_Observables).
Le equazioni seguenti sono la nostra derivazione locale, non una nuova legge
fisica né una stima di ampiezze ottenuta da quella fonte.

Siano `y_r = A theta + e_r` le osservazioni di riferimento e
`y_t = B theta + e_t` quelle del bersaglio, dopo sottrazione del modello nominale.
`theta` contiene i parametri di orologio/nuisance; `A` e `B` sono Jacobiani
dichiarati. Con pesi GLS fissati prima dei dati, `theta_hat = K y_r`.

- Residui dei riferimenti: `r = (I - A K) e_r`.
- Errore dell'osservabile bersaglio corretta: `d = e_t - B K e_r`.
- Operatore congiunto: `J = [-B K, I]`, dunque `Cov(d) = J Cov(e_r,e_t) J^T`.

`calibration_transfer.py` calcola questi operatori con whitening e SVD. Richiede
una covarianza di peso esplicita e un fit numericamente di rango pieno; rifiuta
matrici incomplete, non finite o non valide. La covarianza fisica congiunta
deve essere fornita separatamente: quella usata per pesare il fit non ne
certifica la correttezza. Le correlazioni incrociate non vengono azzerate.
Matrici semidefinite sono ammesse per modi perfettamente condivisi, entro una
tolleranza numerica relativa dichiarata nel codice. Non si ricava una
covarianza fisica da un massimo aggregato di residui.

Per ogni `e_r = A q`, il residuo è zero al primo ordine, ma la correzione al
bersaglio è `-B q`. Se anche `e_t = B q`, il modo comune si cancella. La base
calcolata da `residual_blind_modes` rende esplicito questo sottospazio: non
stima le sue ampiezze, non certifica tutti i modi ciechi del modello completo
e non autorizza a chiamare errore orbitale un errore di osservabile.

## Risultati riproducibili

Eseguire `python -m research.kinematic.calibration_transfer_study`.
La [ricevuta sintetica](results/calibration_transfer_study_v1.json) registra
gli hash dei due sorgenti. Undici endpoint a 30 s, quattro riferimenti e
orologio affine sono tutti costruiti senza geometria di un satellite reale.
Le righe codice e tasso di fase hanno unità distinte e non vengono sommate.

| Iniezione inventata | Residuo massimo dei riferimenti | Errore di codice bersaglio | Errore del tasso di fase |
| --- | --- | --- | --- |
| Offset solo nei riferimenti: 100 m | < 3e-14 m | -100 m | circa zero |
| Deriva solo nei riferimenti: 0,1 m/s | < 5e-15 m | circa zero | -0,1 m/s |
| Offset e deriva identici anche nel bersaglio | < 3e-14 m | circa zero | circa zero |

Secondo esempio: quattro codici, rumore indipendente inventato di 1 m e modo
comune marginale di 3 m. La varianza dei residui resta 0,75 m² per riferimento,
ma quella del codice bersaglio corretto è 37,25, 19,25 oppure 1,25 m² per
correlazioni riferimento-bersaglio rispettivamente -1, 0, +1. Non sono stime
GNSS né quantili al 95%: dimostrano che gli stessi residui non identificano
il trasferimento. Il test confronta inoltre l'operatore con la propagazione
correlata già presente in `phase_reference_bridge.py`, senza modificarla.

## Informazione mancante e prossimo esperimento utile

Un altro massimo dei residui, anche su più riferimenti, non misura un modo
che il fit assorbe. Il prossimo disegno deve distinguere almeno due contributi:

1. Errori dei prodotti dei soli satelliti di riferimento, proiettati nei
   codici attraverso i Jacobiani e poi attraverso `-BK`. Il confronto fra
   prodotti deve fissare convenzioni di orologio, frame, tempo e dipendenze;
   il disaccordo fra prodotti non è automaticamente il loro errore assoluto.
2. Errori condivisi del ricevitore e termini specifici della direzione, con
   un modello congiunto codice/fase/riferimenti/bersaglio. Una componente
   comune può cancellarsi; una differenziale può trasferirsi. La stessa
   iniezione a tutte le stazioni può anche essere assorbita dal nuisance del
   fit finale: occorre propagare attraverso quel fit prima di parlare di xyz.

Prima di nuove acquisizioni, dichiarare un esperimento di qualificazione
su un giorno distinto, con riferimenti esclusi a rotazione secondo regola
fissa, diagnostiche individuali conservate e prodotto indipendente ammesso
solo per riferimenti. Separare sviluppo e conferma futura e dichiarare gli
accessi: un riferimento usato in questa qualificazione non diventa una nuova
conferma incontaminata per lo stesso evento. Le rotazioni verificano errori
differenziali; non risolvono da sole il modo comune a tutti i prodotti.
Questo è un disegno da completare, non un'autorizzazione al download.

Restano aperti ampiezze fisiche, atmosfera, PCV/multipath, continuità di fase,
correlazioni tra stazioni, dipendenza dei Jacobiani dalla soluzione e resto
nonlineare. Nessuno di questi termini viene assegnato a zero da questo lavoro.
