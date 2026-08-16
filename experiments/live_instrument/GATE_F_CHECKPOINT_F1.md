# Gate F — Checkpoint F1 offline

Stato: **PROPOSTO PER REVISIONE**. Questo checkpoint non contiene osservazioni,
connessioni di rete o modifiche ai runtime e alle soglie dei Gate precedenti.
Si ferma prima della discovery live di Gate F.

## F0 — chiusura del working tree

I tre artifact prospettici preesistenti sono stati valutati separatamente.
Tutti e tre appartengono alla catena epistemica che collega Checkpoint 3 alla
failure attribution e a Gate E. La decisione permanente è quindi `COMMIT` per
ciascuno; nessun artifact è stato cancellato o escluso.

| Artifact | Ruolo | SHA-256 prima del commit | Decisione | Ragione |
|---|---|---|---|---|
| `PROSPECTIVE_OUTCOME_1.md` | receipt narrativo del primo outcome prospettico | `7011502771e6573dd24763f8986c661e386206918a621a10660bc6eea842762d` | `COMMIT` | conserva prediction, finestra, clausole e interpretazione del negativo |
| `kiwi_prospective.py` | piano immutabile e valutatore che materializzano l'esperimento | `70d19660966c8677ff78f24cf79cfc4569269023eb3b65170caeac9fb3ff9df1` | `COMMIT` | rende verificabile il plan hash `d8cb7166...f362` e la separazione discovery/confirmation |
| `test_kiwi_prospective.py` | controlli offline del piano e dell'outcome | `b2681a083f0940d69991bd0f907423a48e785a7c78ee4487e6b2894d33112cc7` | `COMMIT` | prova immutabilità, indipendenza temporale e semantica del risultato |

Commit locale: `e655743` (`checkpoint: preserve first prospective Kiwi
outcome`). Nessun push. I cinque test prospettici passano.

## Intento e vincoli di Gate F

Gate F non cerca un sensore per una domanda già decisa. Cerca una capability
Internet viva e qualificabile che possa sostenere **adesso** un contrasto
fisico prospettico, incluso un negativo interpretabile. Target, identità,
endpoint, banda, frequenza e finestra possono comparire soltanto dopo la
qualificazione.

Le quattro semantiche fisiche usate sotto sono:

- `NOT_FALSIFIABLE`: prima del freeze manca un ponte necessario fra ipotesi e
  feature. Il candidato non può diventare un esperimento;
- `NOT_DETECTABLE`: durante la finestra congelata l'envelope osservativo o un
  witness necessario è violato. Non si valuta la previsione fisica;
- `NOT_DETECTED`: envelope e witness restano validi, ma la feature prospettica
  richiesta non compare. Questo può danneggiare l'ipotesi dichiarata;
- `DETECTED`: envelope e witness restano validi e compare la feature composta
  pre-registrata. Non implica automaticamente identità o causa unica.

Questi stati non sostituiscono le clausole: sono una sintesi derivata dai loro
esiti atomici. Un errore descrittivo o software resta separato dalla decisione
fisica.

## Meccanismo A — stato programmato self-witnessing scoperto live

### 1. Domanda fisica

Una struttura RF che espone una sequenza `presenza → stato selettivamente
assente → recupero` ripete nella prossima finestra indipendente lo stesso stato
fisico mentre un marker ortogonale della sorgente e del percorso resta presente?

### 2. Ipotesi

`H_A`: la sequenza osservata durante discovery e qualification è prodotta da
uno stato ricorrente della stessa emissione, non da dropout, retuning o
interferenza locale. Un negativo con marker, canale e trasformazioni integri
danneggia la previsione di ricorrenza per quella sola finestra.

### 3. Osservabile

Entro l'intervallo di fase appreso devono comparire: controllo positivo prima,
marker same-path durante, assenza selettiva della feature target e controllo
positivo dopo. Durate, ritardi, contrasto minimo e tolleranze di fase sono
intervalli congelati, non punti scelti dopo i campioni.

### 4. Ponte fenomeno → feature

`stato ricorrente della sorgente` → `soppressione selettiva di una componente
RF e persistenza di un marker` → `propagazione nella banda qualificata` →
`antenna/front-end/ADC` → `DDC, timestamp, STFT e normalizzazione congelati` →
`sequenza positiva/null/positiva con marker`.

- noti prima del freeze: geometria STFT, regola di selezione, definizione del
  marker, trasformazioni e limiti di continuità;
- intervalli: fase, durata, drift, contrasto, latenza e larghezza di banda;
- apprendibili in sessione: periodo, fase futura, frequenza e morfologia della
  sequenza;
- aperti: identità del trasmettitore e meccanismo interno preciso;
- bloccanti: impossibilità di collegare marker e feature alla stessa emissione,
  o assenza di una futura fase indipendente entro il budget.

### 5. Detectability envelope

La banda deve contenere simultaneamente target, marker e guard band; il target
deve superare il contrasto conservativo derivato con un operatore fissato prima
della discovery; il marker deve restare sopra la propria soglia durante l'intera
sequenza; drift e phase error devono restare nei rispettivi intervalli; il
segmento continuo deve coprire pre, null e post. `NOT_FALSIFIABLE` se non esiste
un marker causalmente collegabile; `NOT_DETECTABLE` se il marker o il flusso
cade; `NOT_DETECTED` se il marker è sano ma la sequenza congelata manca;
`DETECTED` se l'intera sequenza e i controlli passano.

### 6. Same-path witnesses

Servono almeno un marker co-trasmesso persistente, energia/noise floor nelle
bande laterali, continuità GNSS e un secondo root indipendente se disponibile.
Il marker verifica canale e tuning; la continuità verifica dropout; una seconda
componente con trasformazione distinta verifica perdita selettiva; guard band e
secondo root riducono l'ambiguità da interferenza locale. Un semplice socket
aperto non qualifica nulla.

### 7. Capability admission

- `CAPABILITY_DISCOVERED`: il flusso dichiara banda e controllo, senza ancora
  valore epistemico;
- `CAPABILITY_QUALIFIED`: due sequenze complete mostrano marker, null e recupero
  entro envelope, con artifact hash e transform ledger;
- `CAPABILITY_ADMITTED`: esiste una terza finestra futura, indipendente e
  coperta dal TTL, e tutti i causal cut principali hanno witness;
- `QUALIFICATION_ERROR`: trasporto, descrizione o trasformazione impediscono la
  valutazione;
- `CAPABILITY_REJECTED`: la misura è valutabile ma manca ricorrenza, marker,
  continuità o margine.

### 8. Falsification power

Ordine: copertura completa; conservazione della separazione marker/target;
witness same-path; chiusura di dropout, retuning e interferenza; margine fra
contrasto minimo e sensibilità; capacità di distinguere stato della sorgente da
path fade; continuità/freschezza; infine costo e information gain. Non è un
punteggio probabilistico.

### 9. Piano prospettico minimo

Discovery di almeno due sequenze; qualification su una sequenza ulteriore;
freeze di banda, fase, feature, marker, trasformazioni e controlli; una sola
finestra futura; controlli wrong-time, wrong-frequency e perdita-marker; stop al
primo outcome o alla prima violazione dell'envelope.

### 10. Failure mode

Diventa un calendario hardcoded se il nome della sorgente precede la capability;
un detector post-hoc se periodo o marker cambiano dopo il freeze; un aggregatore
se unisce cicli incompatibili; una falsa conferma se marker e target sono due
derivate della stessa feature; un'assenza non interpretabile se il marker non
attraversa davvero la stessa catena emissiva e propagativa.

### 11. Astrazione eliminabile

Target e calendario esterno possono sparire. Se la capability espone già una
sequenza falsificabile, anche il planner centrale può ridursi a una semplice
decisione di ammissione.

## Meccanismo B — ricorrenza targetless senza calendario esterno

### 1. Domanda fisica

Una struttura RF anonima mostra una dinamica ricorrente sufficientemente stabile
da vincolare, prima dei nuovi campioni, tempo, banda e morfologia del prossimo
evento?

### 2. Ipotesi

`H_B`: la struttura deriva da un processo ricorrente stabile nella sessione e
non da una singola fluttuazione o dalla ricerca adattiva. L'assenza nella fase
futura danneggia solo questa ipotesi di ricorrenza locale, non l'esistenza del
fenomeno in generale.

### 3. Osservabile

Nella finestra di fase `[t_min,t_max]` deve apparire una regione con banda,
durata, direzione di drift e contrasto entro intervalli congelati. Una feature
ortogonale deve testimoniare che la medesima porzione di percorso rimane
osservabile.

### 4. Ponte fenomeno → feature

`processo ricorrente ignoto` → `emissione o perturbazione spettrale ripetuta` →
`propagazione` → `sensore live` → `segmentazione, STFT, griglia event-time,
template robusto` → `evento entro fase e morfologia`.

- noti: algoritmo di discovery, numero minimo di ricorrenze, split temporale,
  controlli e trasformazioni;
- intervalli: periodo, jitter, bandwidth, durata, drift e contrasto;
- apprendibili: template, fase e prossima finestra;
- aperti: identità, origine e legge generativa;
- bloccanti: nessun witness ortogonale, instabilità del periodo o assenza di un
  ciclo held-out prima del freeze.

### 5. Detectability envelope

Il piano richiede più ricorrenze di discovery e almeno una qualification
held-out, un limite conservativo al phase jitter, sensibilità sotto il contrasto
minimo, durata futura inferiore alla continuità già dimostrata, drift contenuto
nella griglia comune e soglie congelate. `NOT_FALSIFIABLE` se il modello può
ancora cambiare forma o fase; `NOT_DETECTABLE` se witness o continuità falliscono;
`NOT_DETECTED` se la finestra valida non contiene il template; `DETECTED` se il
template supera anche i null wrong-time e wrong-frequency fissati.

### 6. Same-path witnesses

Servono un componente RF ortogonale che condivida offset e drift con il target,
continuità dei blocchi, stabilità del noise floor, controllo di tuning e,
preferibilmente, un secondo root che osservi la stessa ricorrenza. Senza un
legame osservabile fra witness e target, il negativo resta
`NOT_FALSIFIABLE`.

### 7. Capability admission

`DISCOVERED` dopo una struttura saliente; `QUALIFIED` solo dopo ricorrenze
multiple e ciclo held-out; `ADMITTED` solo se periodo e TTL lasciano una nuova
finestra; `QUALIFICATION_ERROR` per fallimento software/trasporto;
`CAPABILITY_REJECTED` per instabilità fisica, margine insufficiente o witness
mancante.

### 8. Falsification power

La copertura della fase futura domina. Seguono conservazione del template,
witness ortogonale, controllo del look-elsewhere, margine, distinzione da rumore
e AGC, continuità e costo. La ricchezza dei dati non compensa una fase larga o
un modello ancora adattabile.

### 9. Piano prospettico minimo

Discovery su più cicli; qualification su un ciclo non usato per il template;
freeze del modello di intervallo; una sola confirmation futura; null con
phase-shift e frequency-shift predefiniti; stop dopo il primo outcome.

### 10. Failure mode

È il meccanismo più esposto a detector post-hoc, multiple testing, database
mascherato di ricorrenze e falsa conferma da AGC comune. Diventa un calendario
implicito se si accumulano cicli finché uno passa.

### 11. Astrazione eliminabile

Elimina target, modello orbitale e identità del fenomeno. Un `BeliefSnapshot`
generale è superfluo: bastano prediction congelata e receipt della singola
finestra.

## Meccanismo C — contrasto relazionale fra capability

### 1. Domanda fisica

Una relazione RF osservata fra due capability indipendenti — simultaneità,
ordine di intensità o presenza/assenza — persiste nella prossima finestra e
distingue un fenomeno condiviso da un effetto locale?

### 2. Ipotesi

`H_C`: la relazione, non l'identità dei segnali, è un'invariante fisica dei due
percorsi entro l'envelope appreso. Un negativo con entrambi i percorsi sani
danneggia questa ipotesi relazionale.

### 3. Osservabile

Una relazione pre-registrata: per esempio una stessa evoluzione spettrale in A
e B entro un ritardo limitato, oppure presenza in A e assenza in B mentre marker
same-path distinti provano sensibilità in entrambi. Segno, ritardo, banda,
durata e contrasto devono essere intervalli congelati.

### 4. Ponte fenomeno → feature

`fenomeno condiviso o path-selective` → `campi RF nei due siti` → `propagazioni
distinte` → `due front-end indipendenti` → `trasformazioni esplicite su griglia
comune` → `relazione ordinale/temporale`.

- noti: indipendenza hardware, event-time, mappature di frequenza, test
  relazionale e alternative considerate;
- intervalli: ritardo, offset, drift, contrasto e rapporto fra siti;
- apprendibili: tipo di relazione e banda che la sostiene;
- aperti: geometria del trasmettitore e propagazione HF completa;
- bloccanti: relazione che può essere spiegata indifferentemente da AGC,
  interferenza locale o trasformazioni comuni.

### 5. Detectability envelope

Serve overlap continuo comune, sensibilità sufficiente in entrambi, griglia
event-time/frequency allineabile, ritardo entro il limite e witness locale per
ogni root. `NOT_FALSIFIABLE` se le alternative producono la stessa relazione;
`NOT_DETECTABLE` se uno dei due percorsi perde witness; `NOT_DETECTED` se i
percorsi sono sani ma la relazione congelata manca; `DETECTED` se la relazione
e i controlli differenziali passano.

### 6. Same-path witnesses

Ogni capability deve avere il proprio marker di tuning, continuità e
sensibilità; un witness presente solo nell'altra non salva un negativo. Sono
necessari controlli per interferenza locale, software/protocollo condiviso e
perdita selettiva. In HF restano aperti multipath, fading indipendente,
assorbimento e differenze d'antenna: devono entrare nell'ipotesi, non essere
spiegazioni aggiunte dopo.

### 7. Capability admission

Una coppia è `DISCOVERED` quando esiste overlap; ciascun root è `QUALIFIED`
separatamente; la coppia è `ADMITTED` solo se la relazione aggiunge potere di
discriminazione e tutti i witness sono simultanei. Errore su un root è
`QUALIFICATION_ERROR`; un root fisicamente insufficiente è
`CAPABILITY_REJECTED`, senza contaminare l'altro.

### 8. Falsification power

Prima copertura simultanea; poi conservazione della relazione; witness per
entrambi; chiusura delle cause locali e comuni di trasformazione; margine;
divergenza fra ipotesi alternative; freschezza; costo. Due root non valgono più
di uno se condividono il taglio causale decisivo.

### 9. Piano prospettico minimo

Discovery della relazione; qualification su segmento successivo; freeze di
relazione, ritardi e controlli; una confirmation comune; stop al primo esito.
Nessuna ricerca di lag o frequency shift dopo il freeze.

### 10. Failure mode

Può diventare un aggregatore di stazioni, una correlazione massimizzata
post-hoc, un client di una sola rete o una falsa conferma dovuta a software
comune. Una semplice frequenza uguale non è una relazione fisica sufficiente.

### 11. Astrazione eliminabile

L'oggetto `strumento` come unità monolitica può sparire: contano i percorsi
causali e i ruoli asimmetrici di misura e controllo. Anche l'identità del
fenomeno può restare assente.

## Meccanismo D — invarianza RF sotto retuning controllato

### 1. Domanda fisica

Una struttura targetless, comune a due percorsi live, resta ancorata alla
frequenza RF assoluta quando un ricevitore viene retuned secondo una traslazione
congelata, mentre un secondo percorso resta come riferimento non perturbato?

### 2. Ipotesi

`H_D`: la struttura è un fenomeno RF esterno al DDC e presente nel percorso del
ricevitore di intervento; deve quindi restare a frequenza assoluta costante e
spostarsi di `-Δf` nelle coordinate baseband quando il centro cambia di `Δf`.
Una feature che resta a coordinata baseband fissa è più compatibile con un
artefatto interno. L'assenza alla coordinata prevista, con riferimento e
witness integri, danneggia `H_D` per quella finestra e quel percorso.

### 3. Osservabile

Una sequenza `center_0 → center_0 + Δf → center_0` congelata. La struttura deve:

1. essere presente prima in entrambi i root;
2. restare presente nel root non perturbato;
3. comparire alla stessa frequenza RF assoluta, ma alla baseband traslata, nel
   root perturbato;
4. recuperare la coordinata baseband iniziale al ritorno.

La struttura minima comprende larghezza, contrasto, durata e deriva entro
intervalli fissati; non richiede identità o decodifica.

### 4. Ponte fenomeno → feature

`campo RF esterno quasi stazionario` → `struttura spettrale a frequenza
assoluta` → `due percorsi propagativi` → `front-end di riferimento e front-end
retuned` → `ADC/DDC con traslazione nota` → `STFT su assi RF e baseband
espliciti` → `invarianza RF + traslazione baseband + recupero`.

- noti: segno e geometria della traslazione DDC, sequenza di controllo,
  trasformazioni, griglia, controlli e regola di confronto;
- intervalli: frequenza assoluta, larghezza, drift, contrasto, event-time
  alignment, latenza di retune e stabilità del path;
- apprendibili: struttura targetless, banda comune, `Δf` ammissibile ed envelope
  conservativo;
- aperti: identità ed emission mechanism;
- bloccanti: nessun witness indipendente del retune, nessun riferimento live,
  feature troppo larga/instabile o impossibilità di separare RF assoluta da
  baseband.

### 5. Detectability envelope

Sia `W` la larghezza superiore della feature, `R` la risoluzione comune e `G`
la guard band disponibile. L'intervento è ammissibile soltanto se
`2·max(W,R) ≤ |Δf| ≤ G` e target più witness restano nei passband. La durata
della sequenza deve stare dentro il limite inferiore di continuità dimostrata;
drift RF più errore di griglia deve essere inferiore alla tolleranza congelata;
il limite inferiore di contrasto deve superare il limite superiore di rumore e
distorsione con margine conservativo. L'operatore che costruisce questi limiti è
definito prima della discovery.

- `NOT_FALSIFIABLE`: non è possibile predire coordinate RF e baseband distinte;
- `NOT_DETECTABLE`: riferimento, witness di retune, continuità, sensibilità o
  transform ledger falliscono nella finestra;
- `NOT_DETECTED`: tutti i witness restano validi ma la struttura non appare
  nella coordinata RF prevista o non recupera;
- `DETECTED`: invarianza RF, traslazione baseband, riferimento e recupero
  soddisfano tutte le clausole e i controlli.

### 6. Same-path witnesses

- il root non perturbato prova che la struttura esterna non è scomparsa durante
  l'intervento;
- una seconda struttura RF nel passband del root perturbato, distinta dal
  target, deve subire la traslazione prevista e testimonia tuning e DDC;
- sequenze e timestamp verificano dropout e latenza di controllo;
- noise floor e componenti laterali verificano che il front-end resti vivo;
- il ritorno a `center_0` verifica il recupero della trasformazione;
- controlli baseband-fixed e wrong-translation separano artefatti interni;
- root hardware indipendenti e guard band riducono interferenza locale.

Il riferimento remoto non elimina fading e propagazione HF specifici del sito
perturbato. Perciò l'ipotesi include un intervallo di stabilità del path appreso
prima del freeze e la sequenza deve essere molto più breve di tale limite. Se
questa condizione non è dimostrabile, il candidato non è falsificabile.

### 7. Capability admission

- `CAPABILITY_DISCOVERED`: root live con banda/controllo dichiarati e overlap
  potenziale;
- `CAPABILITY_QUALIFIED`: IQ event-timed continuo, assi RF verificati, artifact
  hash, contrasto e drift finiti, retune testimoniato da una feature distinta;
- `CAPABILITY_ADMITTED`: coppia riferimento/intervento, target comune, envelope
  completo, TTL sufficiente e futura sequenza indipendente entro budget;
- `QUALIFICATION_ERROR`: trasporto, serializzazione o trasformazione non
  permettono la valutazione; retry soltanto pre-freeze entro budget;
- `CAPABILITY_REJECTED`: misura valida ma overlap, margine, stabilità, witness o
  controllo fisico sono insufficienti.

### 8. Falsification power

La graduatoria è lessicografica, non un punteggio:

1. copertura completa di pre/intervento/post sul root perturbato e sul
   riferimento;
2. conservazione della distinzione frequenza RF/baseband;
3. witness di retune che attraversa antenna, front-end, ADC e DDC;
4. chiusura di dropout, tuning errato, trasformazione interrotta, artefatto
   baseband e scomparsa globale del target;
5. margine conservativo di contrasto e guard band;
6. capacità di distinguere `RF esterna` da `artefatto interno`;
7. continuità, event-time, TTL e freschezza;
8. costo e information gain.

### 9. Piano prospettico minimo

Discovery trova, senza identità, una struttura comune e un witness distinto.
Qualification verifica continuità, stabilità e una traslazione diagnostica che
non usa la finestra finale. Il piano congela root, banda, `Δf`, sequenza,
coordinate, envelope, trasformazioni, controlli e stop. La confirmation usa una
nuova finestra e una sola sequenza `A→B→A`. Non esiste seconda finestra.

### 10. Failure mode

Diventa un client Kiwi se la semantica viene codificata come adapter permanente
anziché come esperimento usa-e-getta; un detector post-hoc se `Δf` o target
cambiano dopo il risultato; una falsa conferma se ci si fida del comando di
retune senza witness RF; un'assenza ambigua se il riferimento non vede più il
target; un database mascherato se si accumulano feature finché una trasla; un
aggregatore se si combinano root non simultanei.

### 11. Astrazione eliminabile

Target, identità, modello orbitale, calendario e `BeliefSnapshot` possono essere
eliminati. Il planner centrale è sfidato: la coppia di affordance
`riferimento live + retune verificabile` genera direttamente il contrasto.

## F2 — confronto per falsification power

| Meccanismo | Negativo interpretabile | Assunzioni non controllate | Causal cut dominante | Costo causale | Giudizio |
|---|---|---|---|---|---|
| A — stato self-witnessing | molto alto se marker e stato sono realmente co-emessi | riconoscimento dello stato e ricorrenza della sorgente | marker non davvero same-source | medio | forte, ma dipende dalla disponibilità fortuita di una state machine |
| B — ricorrenza targetless | medio | stazionarietà, periodicità, template stability | modello ricavato dagli stessi dati | basso | importante come fallback concettuale, troppo esposto a libertà post-hoc |
| C — relazione fra capability | medio-alto | propagazione differenziale e stabilità fra siti | fading/path-specific loss | alto | discrimina alternative, ma due root non chiudono da soli il modello di propagazione |
| D — retuning controllato | alto | stabilità breve del path e correttezza della traslazione verificata | perdita selettiva nel sito perturbato | medio | **raccomandato**: introduce un intervento controllato e un riferimento, senza calendario o identità |

La raccomandazione non deriva dalla facilità di codice né dalla forza del
segnale. D è preferito perché rende diversa, prima dei campioni, la previsione
per una feature RF esterna e per un artefatto baseband. Il negativo non è una
semplice mancata presenza: è il fallimento di una trasformazione fisica
direzionale sotto un intervento testimoniato.

## Esperimento verticale minimo raccomandato

### Meccanismo scelto

Una struttura RF targetless viene scoperta su due root indipendenti. Uno resta
fermo come riferimento; l'altro esegue una singola sequenza di retuning
`A→B→A`. La proprietà testata è l'invarianza della frequenza RF assoluta sotto
traslazione DDC, non l'identità della struttura.

### Capability minime

- due root hardware contemporanei con banda sintonizzabile sovrapposta;
- IQ event-timed, continuità dimostrabile e assi RF espliciti;
- controllo di centro su uno dei root e witness RF indipendente del retune;
- struttura target comune, riferimento persistente e margine sufficiente;
- artifact hash prima dell'analisi e distruzione dei campioni dopo il receipt.

Non sono prefissati rete, endpoint, frequenza, target o finestra. Se nessuna
capability offre questa combinazione entro il budget, Gate F termina senza
sintetizzare.

### Detectability envelope iniziale

L'envelope è interval-based: overlap di banda; `2·max(W,R) ≤ |Δf| ≤ G`;
contrasto target e witness sopra i limiti superiori di rumore/errore;
sequenza più breve del limite inferiore di stabilità e continuità; drift entro
una tolleranza geometrica; event-time alignment entro metà del passo comune;
assenza di gap, overflow invalidante o trasformazioni non verificate. Operatori
di stima, minimi di ammissione e regole di margine sono congelati prima della
discovery; i limiti capability-specific sono calcolati da tali operatori durante
la qualification, congelati nel piano e mai riadattati nella confirmation.

### Witness e causal cuts

| Causal cut | Witness richiesto | Esito se manca |
|---|---|---|
| target scomparso globalmente | root di riferimento vede il target per tutta la sequenza | `NOT_DETECTABLE` |
| tuning errato | struttura distinta segue `-Δf` in baseband | `NOT_DETECTABLE` |
| receiver/dropout | sequenza continua, RF background e marker persistenti | `NOT_DETECTABLE` |
| trasformazione interrotta | assi RF/baseband e ledger verificano andata e ritorno | `NOT_DETECTABLE` |
| artefatto baseband | controlli baseband-fixed e wrong-translation | alternativa discriminata |
| perdita selettiva/interferenza locale | guard band, witness distinto, recupero e root indipendente | se non chiusa: `NOT_FALSIFIABLE` prima del freeze |
| fading HF specifico del sito | stabilità pre-freeze, sequenza breve e recupero | se fuori envelope: `NOT_DETECTABLE`, mai `NOT_DETECTED` |

### Capability admission e massimo cambiamento consentito

La discovery può soltanto produrre candidati effimeri. La qualification può
misurare intervalli e scartare candidati. L'admission richiede tutte le clausole
di envelope e falsification power; information gain non può compensarne una.

Prima dell'esecuzione è consentito cambiare **quale capability candidata viene
valutata**, entro il budget e senza cambiare la domanda fisica, l'operatore che
costruisce gli intervalli, i controlli o l'ordine di ranking. Dopo l'admission si
possono soltanto materializzare nei campi congelati endpoint, banda, `Δf`,
finestra e intervalli misurati. Questo è il massimo cambiamento consentito.

### Budget temporale e retry policy

Budget proposto per la singola esecuzione successiva:

- massimo 12 minuti pre-freeze complessivi;
- al massimo 4 minuti di discovery e 6 minuti di qualification;
- massimo 2 minuti per admission, serializzazione rigorosa e plan freeze;
- confirmation `A→B→A` entro il TTL dell'offer e comunque non oltre 3 minuti;
- una sola confirmation e stop immediato dopo il receipt.

Prima del freeze: massimo due retry complessivi e massimo uno per candidato,
soltanto per timeout, trasporto interrotto, description error,
serializzazione o trasformazione fallita per ragione software. Il retry conserva
candidate, domanda, banda di qualification, trasformazioni e soglie; non
allarga finestre né promuove insufficienza fisica.

Dopo il freeze: zero retry, zero nuova finestra, zero cambio root/endpoint,
frequenza, `Δf`, feature, trasformazione o soglia.

### Outcome semantics di Gate F

- `NO_CAPABILITY_ADMITTED`: nessun candidato supera qualification/admission
  entro budget;
- `NO_FALSIFIABLE_EXPERIMENT_AVAILABLE`: esistono capability fisicamente
  ammesse, ma nessuna chiude i causal cut necessari a rendere interpretabile il
  negativo;
- `EXPERIMENT_SYNTHESIZED`: un solo piano completo è hashato e congelato; Gate F
  può fermarsi qui prima della confirmation;
- `EXPERIMENT_OUTCOME`: una sola finestra produce `DETECTED`, `NOT_DETECTED` o
  `NOT_DETECTABLE` per clausole. Un receipt invalido resta descrittivo e non
  riscrive la decisione fisica.

Gate F deve terminare senza esperimento se scade il budget, nessuna coppia ha
overlap e continuità, manca un witness di retune, il path non è stabile, il
margine è insufficiente, il TTL non copre la finestra, le alternative restano
indistinguibili o servirebbe cambiare domanda/soglie per far passare un
candidato.

### Astrazione messa alla prova

Il test può distruggere il planner centrale. Non serve che un planner possieda
un target o scelga una fonte per information gain: due affordance effimere
qualificate possono generare direttamente una singola prediction fisica. Anche
`BeliefSnapshot` e identità del fenomeno non hanno un ruolo necessario. Restano
provvisoriamente necessari event time, receipt atomici, clausole, transform
ledger, causal lineage, hash e separazione fra descrizione e decisione perché
sono proprio ciò che rende interpretabile il contrasto.

## Principale SHOCK

Una capability non è principalmente un sensore o una sorgente di dati. È un
insieme effimero di **controfattuali eseguibili e testimoniabili**. Banda larga,
sample rate e disponibilità hanno poco falsification power se la capability non
può dire che cosa sarebbe rimasto osservabile quando la feature attesa manca.
Il retune verificato vale più di molti stream perché genera due predizioni
divergenti (`RF-fixed` contro `baseband-fixed`) e include un intervento.

## Cosa non implementerei più partendo oggi

Non partirei da un catalogo di target, un calendario di emittenti, un requisito
universale di due sensori, un `BeliefSnapshot` obbligatorio, un adapter
`InternetSource`, un ranking per information gain o un planner che sceglie
frequenze. Non renderei neppure Kiwi un'infrastruttura permanente: il prossimo
codice, se approvato, deve essere il solo esperimento di traslazione e può essere
scartato se la qualification non trova l'affordance richiesta.

## Piano per la singola esecuzione successiva

1. Congelare offline operatori di envelope, ordine di admission, causal cuts,
   budget e retry consentiti.
2. Nel budget pre-freeze, scoprire in RAM capability correnti senza target,
   endpoint o frequenze preimposti.
3. Qualificare soltanto coppie che espongono overlap, controllo di retune,
   riferimento, target comune e witness distinto; hashare e distruggere ogni
   artifact RF subito dopo il receipt.
4. Se nessuna coppia chiude i cut, emettere uno dei due outcome `NO_*` e fermarsi.
5. Se una coppia passa, materializzare e hashare un unico piano con
   `A→B→A`, poi fermarsi a `EXPERIMENT_SYNTHESIZED` se l'autorizzazione copre
   soltanto la sintesi.
6. Solo con successiva autorizzazione, aprire una finestra indipendente, produrre
   un solo `EXPERIMENT_OUTCOME` e fermarsi senza retry.

Questo checkpoint si ferma al punto 1. Nessuna rete o acquisizione è stata
aperta.
