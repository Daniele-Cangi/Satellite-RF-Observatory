# Stato del progetto — 17 ottobre 2026

## Priorita attiva: ricostruzione orbitale, 12 ottobre 2026

La priorita scientifica e risolvere S2 dell'inversa: identificabilita,
ricostruzione reale di posizione/moto, previsioni RF escluse e incertezza totale.
Poi conferma su dati nuovi (S3) e consegna utilizzabile con dominio dichiarato,
copertura e fallimenti (S4), oppure conclusione scientifica motivata se manca
l'informazione. I protocolli e gli esiti storici restano invariati.

Il [controllo fisico G12](../research/exploratory/G12_BIAS_GEOMETRY_DECISION.md)
verifica copertura e informazione sui bias senza modificare il solver o leggere
l'orbita del bersaglio. Legare i bias fra archi aggiunge informazione locale, ma
la direzione debole resta scarsamente vincolata: scala formale condizionale
circa 16 km sui bias nei cinque fit con fase accettati, non errore di posizione
o limite fisico. Tutti i quindici fit fase rifiutati restano tali.

La [qualifica dell'ora completa](../research/exploratory/G12_FULL_HOUR.md)
riusa la calibrazione reference-only e gli stessi fit brevi: 33 fit codice e
12 con fase accettati; sei finestre sotto maschera e un fallimento nella
previsione codice restano visibili. Le stime clock della seconda mezz'ora sono
identiche alle precedenti. Il profilo su sei stazioni ha rango locale completo,
ma la scala formale debole e ancora circa 2 km sui bias con fase, non sulla
posizione. S2 resta aperta.

Il [test di trasferibilita reference-only](../research/exploratory/REFERENCE_BIAS_TRANSFER.md)
esclude ciascun satellite dalla calibrazione numerica e dal fit direzionale:
3.942 previsioni RF peggiorano da 1,135 a 1,168 m RMS. La proiezione sulla
direzione debole G12 peggiora da 0,868 a 0,929 m, con appena 32 blocchi
valutabili su 1.342 e due satelliti di riferimento. Tutti i casi mancanti e i
peggioramenti restano nel rapporto. La selezione storica e i prodotti condivisi
rendono il test esplorativo e condizionale, non una conferma indipendente.
La legge direzionale non diventa una correzione o un prior del solver.

La [fattibilita dinamica G12](../research/exploratory/G12_DYNAMICS_FEASIBILITY.md)
mostra maggiore informazione locale con una traiettoria condivisa: la scala
formale del bias debole con fase passa da circa 1.993 a 217 m. Non e errore di
posizione o un fit orbitale comune. L'orbita nota non entra nel calcolo; tutti
i fallimenti storici restano tali. Gravita centrale e centrale+J2, dallo stesso
stato RF, divergono fino a 318 m in posizione e 296 m nel codice previsto:
sono separazioni fra modelli, non errori irriducibili dopo una nuova stima.

Il [fit RF dinamico condiviso G12](../research/exploratory/G12_DYNAMIC_FIT.md)
e implementato senza orbita nota o stato precedente come seed, con bias liberi
e finestre alternate per escludere globalmente i campioni di verifica. Con solo
codice e J2, 85 previsioni passano da 2,684 a 1,071 m RMS; l'ultima previsione
oltre tutti i dati usati peggiora da 2,108 a 2,334 m. La ricerca dei rami resta
incompleta per un ramo iniziale non propagabile. Con fase, il codice peggiora
e il modello e rifiutato dai pesi originali (p circa 2e-14), pur migliorando
alcune previsioni fase. Tutti i fallimenti numerici precedenti sono conservati.
La review ha rilevato una dipendenza dalle correzioni di un fit storico:
i risultati v1-v3 non sostengono piu la dichiarazione di indipendenza dalla
geometria precedente. Il risultato corrente v4 ricalcola VMF3 dentro il fit
e i clock dai riferimenti, senza usare quelle correzioni; gli esiti restano tali.

S2 resta aperta: residui migliori non dimostrano accuratezza della posizione.
Il [confronto fase agli stessi tempi](../research/exploratory/G12_PHASE_DIAGNOSTIC.md)
localizza il problema: per J2 il contrasto temporale scende da 2,422 a 0,720 mm/s
sottraendo la variazione reference-only; il 97,8% del residuo resta comune alle
stazioni. Non e prova di una causa clock-only o di accuratezza orbitale.
L'estrapolazione del trend clock peggiora 28/40 controlli sui riferimenti.
La prossima correzione riguarda gli incrementi clock per intervallo e la loro
covarianza congiunta, lasciando libera la componente comune clock/percorso.
Tutti i rifiuti e i risultati precedenti restano invariati; nessuna riduzione
dei floor o modifica al solver di produzione.

Il [fit con clock per intervallo](../research/exploratory/G12_INTERVAL_CLOCKS.md)
usa gli stessi otto archi fase, senza orbita o stato precedente del bersaglio.
Con J2 il codice escluso migliora rispetto a v4 da 1,111 a 0,882 m RMS, ma la
fase peggiora da 8,076 a 8,358 mm/s. Il costo condizionale scende a 0,212 su
165 gradi di liberta; non e prova di accuratezza. La scala formale debole della
posizione cresce da 1,39 a 1,51 km e un ramo iniziale resta non propagabile.
Le due ipotesi sulla covarianza clock, incluso un processo comune, non sono un
bilancio fisico qualificato. S2 resta aperta: prossimo controllo utile, errore
assoluto e incertezza su riferimenti reali esclusi dalla propria calibrazione.
Nessun risultato storico o floor viene modificato.

Il [controllo degli stati sui riferimenti](../research/exploratory/REFERENCE_STATE_VALIDATION.md)
ricostruisce ciascun candidato escludendo i suoi prodotti dalla propria
calibrazione e dal fit. La v3 recupera G11 sui nove archi originali con una
velocita iniziale riferita all'epoca finale, ricavata dai soli tre campioni RF
di training. Non cambia maschera, floor, pesi, modello o criterio finale.
G11 ha uno scarto CODE di 88,51 m RMS in posizione e 0,0130 m/s in velocita,
con asse formale condizionale 1-sigma di 4,12 km non qualificato.
Le traiettorie disponibili passano da quattro a cinque su 22 candidati;
restano 17 casi senza archi sufficienti e un ramo interno non propagabile
per ciascun fit. Il fallimento G11 a 9,996 gradi resta nella v2 originale.
Le preparazioni e tutte le 440 finestre restano identiche alla v2, inclusi
i casi di geometria RF ambigua. Le incertezze formali sono ancora ampie e
CODE non e verita indipendente. S2 resta aperta: qualificare il bilancio
fisico congiunto di clock, bias e propagazione prima di S3.

Il [profilo del ritardo umido condiviso](../research/exploratory/REFERENCE_WET_FIT.md)
rimuove la correzione umida esatta con un parametro libero per stazione,
propagato sia nella ricalibrazione reference-only dei clock sia nel percorso
RF del candidato. Riusa gli stessi 22 candidati, 440 finestre e 63 archi;
cinque fit convergono, 17 candidati restano senza supporto sufficiente e i
cinque seed interni alla Terra falliscono ancora. Tutti i cinque fit liberi
implicano almeno un ritardo umido totale negativo: sono sensibilita algebriche,
non correzioni fisiche accettate. Gli scarti CODE migliorano in tre casi e
peggiorano in G11 e G20; per G20 il RMS di posizione cresce da 66,20 a 148,29 m.
I 26 confronti RF realmente futuri passano da 0,8403 a 0,8309 m nel codice,
ma peggiorano da 6,9795 a 7,0115 mm/s nella fase. Gli assi formali di posizione
crescono in tutti i casi; non sono un bilancio totale qualificato.
La scomposizione locale attribuisce ai pesi dei clock medi di intervallo
l'81-97% della varianza nella direzione debole del modello fisso. Nemmeno
misure umide esterne ipotetiche a 1 mm risolvono quel limite. Il prossimo
ostacolo concreto e una calibrazione congiunta codice/fase dei soli riferimenti
che sostenga la dipendenza temporale e differenziale dei clock, insieme a
informazione giustificata sui bias stabili o geometria che li vincoli. Nessun
floor, esito storico o orbita G12 viene modificato; S2 resta aperta.

Il [calibratore di rete codice/fase](../research/exploratory/REFERENCE_NETWORK_CLOCKS.md)
stima insieme clock dei ricevitori, errori comuni dei riferimenti e ambiguita
libere per segmento, propagando covarianza offset/incrementi e fra archi nel
fit orbitale esistente. Mantiene 22 candidati, 440 finestre, 63 archi e cinque
traiettorie; i 17 casi senza supporto e i rami iniziali falliti restano visibili.
La variante con bias costanti peggiora lo scarto CODE in quattro candidati su
cinque; quella con deriva libera migliora tre e peggiora G11/G20. Per G11 il
RMS di posizione passa da 88,51 a 305,96 m con deriva libera. Il codice
realmente futuro peggiora da 0,8403 a circa 0,887 m RMS; la fase migliora da
6,9795 a 6,8972/6,9303 mm/s. Le covarianze formali si restringono, ma solo
54/126 posizioni CODE rientrano nei relativi ellissoidi condizionali al 95%
in ciascuna variante, contro 126/126 nel baseline: non sono una copertura
indipendente o un budget fisico qualificato.
I controlli di rete mantengono 544/3589 codici esclusi senza supporto in
entrambe le varianti; per la fase sono 544/3589 con bias costanti e 548/3589
con deriva libera. La correzione v2 invalida solo quattro estrapolazioni di
fase non identificabili, preservando i relativi codici e il risultato originale.
La deriva libera G19 ha un RMS fase esclusa di 0,567 m e massimo 7,865 m.
Misure ipotetiche indipendenti del clock medio a 0,1 mm/s porterebbero gli
assi maggiori a circa 41/202/338/185/64 m, ancora condizionali: stringere i
clock da soli non risolve i modi di bias, geometria e propagazione. Il prossimo
ostacolo concreto sono continuita e termini temporali codice/fase, con il
trasferimento comune attraverso riferimenti e percorso del candidato.
Nessuna variante diventa correzione fisica qualificata; default, floor,
risultati storici e orbita G12 restano invariati. S2 aperta, nessuna S3.

Il [trattamento della continuita geometry-free](../research/exploratory/REFERENCE_PHASE_CONTINUITY.md)
spezza le ambiguita ai passaggi segnalati e ricalcola clock e covarianza fino
all'orbita. Cinque passaggi distinti dei riferimenti sono riusati in 19 casi
fra i fold; nessuno dei 680 incrementi di training dei candidati viene tolto.
Con bias costanti lo scarto CODE migliora in quattro traiettorie, ma G19
peggiora da 50,16 a 87,99 m RMS e la velocita peggiora in tre casi.
I 26 confronti RF realmente futuri peggiorano: codice da 0,8876 a 0,9036 m,
fase da 6,8972 a 7,8139 mm/s. Con deriva libera, rispetto alla precedente
variante libera, la posizione migliora solo in G11/G20 e peggiora negli altri
tre. La fase esclusa di G19 resta a 0,589 m RMS, con massimo 7,875 m; G20
raggiunge 0,730 m. I 402 ulteriori controlli fase senza segmento assegnabile
restano nel denominatore, preservando i codici valutabili. Nessuna variante
diventa correzione fisica qualificata. I modi quasi nulli GF richiedono una
combinazione complementare e un budget temporale codice/fase: per il caso
9/7, MW richiederebbe circa 0,285 m di rumore per banda nelle ipotesi dichiarate.
MW usa gli stessi dati, quindi deve conservarne covarianza e rango, non puo
valere come misura indipendente aggiunta. Il termine comune clock-like resta
non qualificato. Floor, risultati storici e orbita G12 invariati; S2 aperta,
nessuna S3.

La [combinazione congiunta IF/MW](../research/exploratory/REFERENCE_RF_COMBINATIONS.md)
usa i quattro canali RF con la loro covarianza, senza contare GF e MW come
osservazioni indipendenti. Mantiene 22 candidati, 440 finestre, 63 archi,
cinque traiettorie e 17 casi senza supporto. Con bias costanti MW sposta lo
stato iniziale di soli 0,006-0,034 m e restringe gli assi formali di circa
0,0033%; il codice realmente futuro passa da 0,903614 a 0,903600 m RMS.
Non e un avanzamento orbitale fisicamente significativo. Le grandi variazioni
con deriva libera riproducono quasi interamente il precedente effetto dei
bias IF. Le nuove previsioni MW peggiorano con deriva libera da 6,073 a
7,600 mm/s sui 26 confronti realmente futuri, 18 dei quali peggiorano.
La rete prevede MW anche in 508 casi senza clock di epoca osservato, ma
restano 438 segmenti MW senza supporto e quattro ulteriori derive non
identificabili. G19 mantiene fase esclusa a 0,589 m RMS e massimo 7,875 m.
I controlli sintetici GF-nulli rifiutano il modello contaminato: non e un
rilevatore o una riparazione automatica dei salti. Il prossimo ostacolo e
qualificare stabilita temporale e covarianza condivisa codice/fase; per il
caso 9/7 la precisione ipotetica richiesta resta circa 0,285 m per banda.
Il termine comune clock-like, il budget totale e S2 restano aperti. Nessuna
S3; floor, artefatti precedenti e orbita G12 invariati.

La [covarianza RF temporale e condivisa](../research/exploratory/REFERENCE_TEMPORAL_SHARED_RF.md)
propaga gli errori grezzi attraverso anche ambiguita e clock stimati, con i
termini incrociati riferimento-candidato. I floor marginali restano invariati.
La forma temporale reference-only stima rho a 30 s fra 0,183 e 0,249; migliora
il variogramma escluso in quattro fold, ma peggiora G21 e non descrive bene
la scala a 300 s. Tutti i cross-momenti di training fra gruppi disgiunti sono
non-PSD: non qualificano una varianza fisica condivisa positiva e non vengono
forzati a diventarlo. La quota condivisa del 50% resta sensibilita dichiarata.
Sotto tale ipotesi, eliminare il solo blocco RF-clock allarga gli assi formali
di posizione di 1,60-1,63 volte; questo mostra l'effetto della falsa indipendenza,
non un miglioramento fisico dell'incertezza. Con correlazione temporale del
codice la posizione CODE peggiora in quattro dei cinque casi. Il codice RF
realmente futuro migliora poco, da 0,903600 a 0,901966 m; la fase da 7,81384
a 7,80327 mm/s. Con condivisione ipotetica sono 0,898541 m e 7,77001 mm/s,
ma nessuno dei cinque stati futuri rientra nell'ellissoide congiunto nominale
al 95% in alcuna variante. Rimangono 22 candidati, 440 finestre, 63 archi,
cinque traiettorie e 17 casi senza supporto. G19 conserva due seed falliti
nelle varianti temporali; non sono due orbite fisiche dimostrate. S2 resta
aperta: identificare struttura di errore ammissibile e dipendenza dal link,
validando G21 e tempi piu lunghi prima di qualificare ampiezze condivise.
Risultati precedenti, floor e orbita G12 invariati; nessuna S3.

La [struttura degli errori condivisi](../research/exploratory/REFERENCE_SHARED_ERROR_STRUCTURE.md)
ora dispone di un fit differenziale reference-only con predizione fra gruppi
su tempi esclusi: quattro partizioni fisse, lag di 30 e 300 s, momento comune
PSD confrontato con indipendenza e dipendenza di segno libero. Restano 22
candidati, 440 finestre e 63 archi. Dei 40 confronti, 38 sono valutabili e due
hanno grafi disconnessi in G19: nessun ancoraggio o split sostitutivo. Nessuna
componente supera i controlli di trasferimento e stabilita. A 300 s cinque
momenti positivi di training diventano non-PSD in validazione; G21 conserva
un momento positivo anche nelle delezioni di training, ma peggiora fuori
training. Il modello di segno libero peggiora 58/76 predizioni direzionali.
D/MW osservano tre combinazioni dei dieci termini della covarianza grezza:
sette direzioni restano non identificate. Un controllo sintetico completo
ricalibra i disturbi comuni ai ricevitori; errori non dispersivi dipendenti
dal link possono invece imitare 137,48 m e 26,93 mm/s senza cambiare D/MW/GF.
Nessuna nuova covarianza grezza viene ammessa, nessun fit o scoring CODE del
candidato viene rifatto e nessun floor cambia. La quota .5 della #230 resta
sensibilita. S2 aperta: vincolare i contrasti non dispersivi di collegamento
che sopravvivono a clock/bias e calibrazione, con geometria reference-only,
closure di rete e propagazione della risposta fino allo stato. G12 e S3 invariati.

Il [contrasto non dispersivo di rete](../research/exploratory/REFERENCE_NONDISPERSIVE_CLOSURES.md)
compone geometria ammessa, calibrazione e risposta dello stato, con nuovi
fit reference-only e traiettorie RF a ogni perturbazione. Nei cinque fold il
99,53-99,83% dell'energia della risposta in posizione appartiene al sottospazio
assorbito dai clock: e una proprieta condizionale dell'estimatore, non una
frazione di varianza fisica. Probe coerenti reference-only da 1 cm RMS, con
picchi fino a 9,62 cm, spostano lo stato di 0,69-3,72 km senza cambiare i
contrasti calibrati. Sono sensibilita costruite, non errori orbitali osservati;
un disturbo fisico comune al ricevitore richiede anche il contributo del
candidato e puo cancellarsi. Nei probe ciclici restano 1 cm RMS nel codice,
ma i bias float assorbono quasi tutta la fase e lo stato cambia di 48-260 m.
Piccoli residui fase non qualificano quindi il budget di calibrazione.
I link esclusi nell'ultimo terzo hanno 1.316/1.494 predizioni condizionali;
178 campioni restano senza clock osservabile. Gli incrementi fase esclusi
hanno RMS 7,81-9,86 mm a 30 s e 13,72-18,38 mm a 300 s, usando altri link
RF agli stessi tempi: non e previsione dell'intera rete senza RF futura.
Il codice realmente futuro peggiora da 0,9036 a 1,0237/0,9219 m RMS nei due
probe; tutti i peggioramenti e i rami falliti restano visibili. Nessuno score
CODE nuovo, floor o covarianza fisica ammessa; S2 aperta e G12 non rivelato.
Il prossimo incremento utile deve assegnare ai modi una geometria di sorgente
e un accoppiamento reference/candidato fisicamente sostenuti, prima di usare
i contrasti per qualificare propagazione, bias o clock.

La [geometria della sorgente umida](../research/exploratory/REFERENCE_SOURCE_GEOMETRY.md)
ora stima sei residui zenitali costanti per stazione dai soli riferimenti,
profilando tutti i clock e bias float. I cinque fold hanno rango condizionale
6/6; i ritardi umidi totali campionati restano positivi. La precisione formale
1,6-19,1 mm dipende dai pesi storici, non e una covarianza meteorologica fisica.
Restano 22 candidati, 440 finestre, 63 archi e 17 preparazioni insufficienti.
La forma predice 1.316/1.494 campioni su link esclusi; 178 clock restano non osservati.
A 300 s il RMS fase migliora in tutti i fold, da 15,113 a 14,595 mm aggregati;
a 30 s peggiora in tre fold, da 9,247 a 9,274 mm. Il codice e misto e nessun
floor viene ritarato. Sono predizioni condizionali con altri RF contemporanei.
Lo stesso probe da 1 cm RMS zenitale attraversa la ricalibrazione completa e
il percorso del candidato: le variazioni in posizione si sommano nei cinque
modi selezionati, producendo 3,38-17,09 m e 0,137-2,089 mm/s. Sono sensibilita
costruite, non errori orbitali osservati. I due percorsi separati non sono
copie indipendenti della sorgente. Il codice realmente futuro peggiora da
0,903600 a 0,904373 m RMS nel probe congiunto; tutti i peggioramenti sono
conservati. I coefficienti stimati non diventano correzioni del candidato.
S2 resta aperta: separare la forma umida da geometrie orbita/antenna dei soli
riferimenti e bias stabili, con il corretto accoppiamento e informazione
indipendente sui funzionali umidi richiesti. Nessuno score CODE nuovo,
covarianza fisica ammessa, rivelazione G12 o avanzamento S3.

Il [confronto congiunto delle sorgenti](../research/exploratory/REFERENCE_SOURCE_SEPARATION.md)
ora compete la forma umida con spostamenti APC dei soli riferimenti in RTN,
offset antenna nel corpo satellite e bias IF stabili, profilando clock e float.
Restano 22 candidati, 440 finestre, 63 archi, 17 preparazioni insufficienti e
cinque traiettorie BRANCH_SEARCH_INCOMPLETE. Il rango umido resta 6/6, ma la
precisione marginale condizionale peggiora da 1,6-19,1 mm a 14,2-3268,9 mm;
l'inflazione massima per stazione raggiunge 227 volte. G19 produce ritardo
umido totale negativo. I rappresentanti algebrici dei modelli piu liberi
richiedono bias e spostamenti enormi: fino a 2,13 milioni di metri per RTN,
fuori dal significato di una perturbazione APC locale. Non sono errori misurati.
I 68-72 modi sorgente irrisolti del modello completo quasi si cancellano nel
trasferimento congiunto al candidato per il probe da 1 cm di norma totale;
il limite serio resta nelle combinazioni deboli ancora risolte, non si cura
fissando a zero un alias. Nessuna ampiezza diventa correzione del candidato.
Su 1494 righe escluse il modello completo emette 1292 coppie, conserva 178
clock assenti, 18 prefissi fase assenti e sei predizioni non identificabili.
A supporto comune, la fase a 300 s peggiora in tutti i cinque fold, da 14,567
a 113,850 mm RMS; i peggioramenti e tutti i denominatori restano nel rapporto.
La stima non qualifica una separazione fisica umidita/orbita/antenna/bias.
S2 resta aperta: risolvere le combinazioni deboli con validita fisica finita
e informazione indipendente o maggiore leva geometrica, senza floor ad hoc.
Nessuno score CODE nuovo, rivelazione G12, covarianza fisica o campagna S3.

Il [recupero fisico delle combinazioni deboli](../research/exploratory/WEAK_SOURCE_RECOVERY.md)
conserva 22 candidati, 440 finestre e 63 archi; per entrambe le ampiezze RF
restano 17 casi insufficienti e cinque BRANCH_SEARCH_INCOMPLETE. I sottospazi
sono stabili per coordinate equivalenti e per la stessa base clock, ma i modi
selezionati cambiano molto con la soglia di rango. I 30 controlli lineari
recuperano la proiezione nota; i 20 probe fisici deboli falliscono il recupero
del funzionale iniettato, mentre il controllo forte lo recupera in 10/10 casi.
Il difetto fisico meno lineare profilato supera il segnale debole di 14-1282
volte: il calcolo differenziale deve essere qualificato prima del recupero.
Le variazioni finite di posizione dei dieci fit RF da zero sono 43-493 um,
con discrepanza dalla derivata fino a 106 um; non sono errori orbitali osservati.
Nessuna singola famiglia, ne umidita+orbita o un solo funzionale debole,
raggiunge il benchmark condizionale 1 m / 1 mm/s nella griglia testata.
Misurare ogni coordinata sorgente e uno scenario sufficiente, fino a 1 mm
per tutte le 182/198 coordinate di G19/G20; non e un prior ammesso o un
requisito strumentale necessario. Il caso clock osserva idealmente lo shift
di calibrazione indotto dalle sorgenti, non una misura esterna reale del clock.
S2 resta aperta: valutazione differenziale stabile e osservabili fisiche
complementari con modello congiunto dei nuisance e delle correlazioni.
Nessun nuovo score CODE, stato G12, floor, covarianza fisica o campagna S3.

Il [calcolo differenziale stabile e le osservabili complementari](../research/exploratory/STABLE_SOURCE_DIFFERENTIAL.md)
(18 ottobre 2026) conserva i 22 candidati, 440 finestre, 63 archi e tutti i
precedenti esiti RF. I 200 campioni di precisione concordano a 35/50 cifre;
a parita di proiettore clock il difetto differenziale debole scende da
14-1282 volte il segnale a 2,21e-8--6,44e-5. La derivata clock stabile cambia
pero il sottospazio risolto: le proiezioni identificate dei 20 probe deboli
recuperano, mentre tutti i 20 funzionali completi restano irrisolti alla
soglia dichiarata. Quattro dei dieci probe forti falliscono ancora il recupero
della proiezione completa per curvatura finita; lo scalare forte passa 10/10.
Nella griglia ipotetica nessuna singola famiglia basta. Orbita+antenna+bias
basta per G05/G11/G21; G19/G20 richiedono anche la componente umida negli
operatori testati. Liberare gli zeri di calibrazione impedisce il benchmark
G19 fino a 0,1 mm. Il clock esterno ora osserva il nuisance clock in una
likelihood congiunta con rumore RF e offset strumentali liberi: nessun caso
clock solo passa; clock+umidita+antenna+bias passa solo per G05 e G21 nella
griglia. Sono immagini informative della sensibilita RF nominale fissata,
non covarianze di un nuovo fit assistito, prior o requisiti strumentali.
S2 resta aperta: operatori fisici indipendenti con geometria, livelli assoluti
e correlazione temporale verificabili. Nessun nuovo fit/score RF o CODE,
stato G12, floor, covarianza fisica ammessa o campagna S3.

Ordine del lavoro: ricostruzione come sviluppo principale; poi RF/previsione
orbitale verso osservatori indipendenti; PNT quando dispone dei riferimenti
fisici adeguati. Android resta acquisizione trasversale e manutenzione.
Un'eventuale risposta FGI si valuta senza interrompere questa priorita.

## Ecosistema e stato dei verticali

Riferimento: commit `d11c24a` dell'11 ottobre 2026. Satellite comprende tre
percorsi scientifici e l'acquisizione Android come capacita trasversale, con una
propria evoluzione ingegneristica. I primitivi tecnici sono riutilizzabili;
le domande fisiche e i criteri scientifici restano distinti. L'app continua a
evolvere; la ricerca orbitale non dipende dalla sua conclusione o da P2/P3 PNT.
Il sito resta una consegna successiva.

| Percorso / capacita condivisa | Risultato consegnato | Limite e prossimo avanzamento |
|---|---|---|
| Ricostruzione orbitale | Snapshot storici condizionali e prototipi di posizione/moto; G14 raggiunge il proprio criterio, altri eventi conservano fallimenti e incertezza eccessiva | S2 aperta: vincolo indipendente ai bias assoluti di stazione/codice o geometria/modello che li renda identificabili; poi inviluppo totale prima di S3. [Piano](SCIENTIFIC_ROADMAP.md), [limite misurato](../research/exploratory/REAL_TARGET_BIAS_IDENTIFIABILITY.md). |
| Osservazione RF e previsione orbitale | Un evento DRAO reale preferisce la geometria orbitale congelata sulle alternative in un intervallo escluso | Risultato condizionato ai PRN e a una stazione, non identita indipendente o conferma distribuita. Nuova ricerca solo su una domanda fisica e un'osservabile identificabile; esiti chiusi e dati sigillati restano tali. [Esito](../experiments/orbital_discriminability/GNSS_DRAO_LABELLED_FORWARD_DOY234_OUTCOME_REPORT.md), [roadmap](../ROADMAP.md). |
| Sicurezza PNT | Diagnostica locale/rete/tempo, challenge software condizionali e analisi di registrazioni fisiche | Beneficio fisico aggiuntivo e conferma P3 aperti; budget temporali e verita di riferimento non si ricavano dal successo software. [Piano PNT](PNT_SECURITY_PLAN.md). |
| Android: acquisizione trasversale | Ciclo sperimentale GNSS/NTS -> ZIP -> analisi PC -> rapporto sul telefono e monitoraggio LAN opzionale implementati | Affidabilita/usabilita possono avanzare normalmente. Qualifica del tempo, rilevamento RF e latenza fisica richiedono evidenza propria. [App](../pnt/android-collector/README.md). |

Il nucleo condiviso comprende parser applicabili, gestione degli input,
provenienza, qualificazione, replay e workflow richiesta/risultato gia esistenti.
Riusarli non rende intercambiabili i modelli fisici o i loro criteri.

**Percorso senza Finlandia:** i dati pubblici acquisiti restano disponibili;
manca soprattutto il chiarimento indipendente del clock nel caso JammerTest.
La [consegna diagnostica e i percorsi alternativi](PNT_SECURITY_PLAN.md#avanzare-senza-ulteriori-dati-dalla-finlandia)
non dipendono da una risposta FGI. Una conferma anti-spoofing resta aperta finche
la prova non documenta riferimenti adeguati, controllo/challenge e beneficio
aggiuntivo rispetto al locale; il solo chiarimento del PPS non basta.
Nessuna nuova prova scientifica e avviata da questo aggiornamento.

## Incremento attuale: limite causale alla ricezione Android

La [diagnostica alla ricezione](../research/exploratory/PNT_ANDROID_CAUSAL_RECEIPT.md)
aggiunge un test esplicito per tempi GNSS impossibilmente futuri, senza budget
finito di allineamento GNSS/BOOTTIME. Riusa gli intervalli e il replay NTS;
il callback non sostituisce l'epoca GNSS e i tempi passati restano non delimitati.
Sulle quattro sessioni gia esposte, 66/156 gruppi e 553/1.446 righe hanno
supporto: zero e +/-100 ms non generano contraddizioni. I margini condizionali
alla ricezione sono 554,5-632,3 ms; restano 90 gruppi insufficienti e 23 timeout
NTS su 80 slot. Tutti i confronti e gli input originali rimangono invariati.
Il nuovo modo riduce le assunzioni in una direzione, senza qualificare gli altri
budget o chiudere P2 fisica/P3. Il prossimo valore scientifico resta una prova
fisica verificabile con un confine temporale adeguato all'errore dannoso scelto.

## Incremento precedente: limite temporale del file SBF

Il [vaglio del file originale Septentrio]
(../research/exploratory/PNT_JAMMERTEST_2025_CLOCK_SOURCE.md) copre tutti i
21.355.148 byte e 138.447 blocchi, senza salti o errori CRC. Nei 901 stati il
riferimento esterno a 10 MHz non risulta rilevato; un impulso PPS IN e rilevato,
ma origine, associazione a UTC e incertezza non sono documentate. Il clock
risulta regolato verso GNSS e il PPS di uscita non misura il tempo indipendente
di acquisizione. Sono conservati anche il flag di errore software gia presente
e i 45 stati PVT non validi. Nessun nuovo parser o dipendenza di produzione.
Il cesio dichiarato nel log non colma il limite per questa registrazione:
serve un'associazione temporale indipendente documentata alle misure attaccate.
Il confronto geometrico precedente resta invariato; P2 fisica e P3 aperte.

## Incremento precedente: registrazione coerente FGI 2025

Il [caso FGI JammerTest 2025 GPS-only]
(../research/exploratory/PNT_JAMMERTEST_2025_COHERENT.md) aggiunge una registrazione
fisica con 899 epoche native a 1 Hz e segnali identificati. Riusando TRO1/KIRU
della stessa giornata, 30/30 richieste a 30 secondi sono valutabili, con 283
righe satellite-epoca comuni. Il controllo locale a coordinate fisse mostra
gia l'anomalia: residuo mediano 297,561 m contro 295,475 m combinato, 27 epoche
migliorate e tre peggiorate. La rete fornisce contesto stabile, senza dimostrare
un vantaggio aggiuntivo di rilevamento. Il parser condiviso conserva ora i tag
nativi con opzione esplicita e legge osservazioni RINEX 4.00/4.01; la griglia
predefinita, i controlli scientifici e gli esiti storici restano invariati.
Le coordinate pubblicate non hanno un budget di rilievo qualificato; il log
EXTERNAL CESIUM non documenta il legame con UTC e i timestamp acquisiti.
Il piano di trasmissione non misura indipendentemente l'attivita RF, e le
epoche fuori piano non sono benignita certificata. P2 fisica e P3 restano
aperte; il sito viene dopo. Il prossimo valore deve venire da un limite fisico
indipendente o da un caso ambiguo localmente, non da altre varianti di soglia.

## Incremento precedente: challenge sui campi Raw GPS

La [challenge clock/trasmissione](../research/exploratory/PNT_ANDROID_RAW_CLOCK_CHALLENGE.md)
riusa quattro sessioni esposte con gli stessi budget: sposta insieme clock GPS
e tempo di trasmissione di �100 ms, conservando gli pseudorange di tutte le
1.446 righe GPS. Sui 65/156 gruppi comuni NTS/combinato distinguono entrambi
gli scarti e il locale relativo resta invariato. Restano 91 gruppi insufficienti
e 23/80 timeout NTS. Confronto, ammissione e controllo locale sono ricalcolati
tramite il motore esistente; originali e risultati storici restano identici.
� una challenge software dei segnali GPS supportati, con BOOTTIME/NTS fidati,
non un modello RF completo n� una qualifica dei budget. P2 fisica e P3 restano
aperte: occorrono un confine temporale indipendente e dati benigni/challenge
verificabili, prima del sito; altre raccolte equivalenti non colmano il limite.

## Obiettivo

La direzione e sviluppare l'ecosistema descritto sopra, con avanzamenti
indipendenti. Il [piano PNT](PNT_SECURITY_PLAN.md) confronta osservazioni GNSS
locali ed esterne via Internet e produce diagnosi riproducibili di geometria
e tempo. Il primo caso e un ricevitore GPS fisso a coordinate note.
La [ricostruzione orbitale](SCIENTIFIC_ROADMAP.md) mantiene la domanda di
posizione/moto indipendente; la [ricerca RF](../ROADMAP.md) verifica previsioni
orbitali dichiarate. I risultati dei tre percorsi non si qualificano a vicenda.

La [roadmap operativa Android](PNT_SECURITY_PLAN.md#roadmap-operativa-dal-telefono-al-rapporto)
porta ora il telefono al centro del flusso: A1 raccoglie GNSS/NTS nella stessa
app senza Termux o controllo dal PC; A2 mostra stato e limiti; A3 esporta la
sessione e rende consultabile il rapporto del motore condiviso. A1 e implementata
nel raccoglitore 0.2; la versione 0.3 implementa A2 con callback/Raw effettivi,
satelliti distinti, età dell'ultimo callback, campi temporali mancanti o invalidi,
cambi del contatore di discontinuità e risultati NTS per endpoint. I fallimenti
cumulativi restano visibili; il confronto resta non valutato e i budget non
qualificati. La versione 0.4 implementa A3 con `android-session`: ZIP ->
rapporto PC -> **Open PC report**. Gli hash vengono confrontati con gli originali
privati; input mancanti, parziali, fallimenti e controlli non eseguiti restano
visibili. Senza budget il rapporto resta insufficiente; solo assunzioni esplicite
attivano il confronto e replay esistenti. L'app si affida al calcolo PC, senza
un nuovo motore, firma forense o upload. La qualifica temporale resta aperta.
La base GNSS della PR #196 conserva il suo formato; NTS ora gira nell'app,
mentre l'analisi resta sul PC. Primo obiettivo: nessun intervento tecnico
durante la raccolta. Qualifica temporale e beneficio
benigno/challenge restano necessari per P2; sito e deployment vengono dopo.

La [matrice del margine temporale nativo](../research/exploratory/PNT_NATIVE_TIME_BUDGET_ENVELOPE.md)
riusa la sessione A3 già esposta: ±100 ms di scarto software restano discordanti
per NTS nei 12/14 gruppi clock abbinati, nei casi ipotetici di associazione
1/10/25/50 ms. I due gruppi insufficienti e le cinque discordanze locali
dell'originale con 1 ms restano visibili. Con associazione ignota tutto resta
insufficiente. Nessun budget è scelto o qualificato; il margine di sviluppo
motiva un modello temporale indipendente, non altre ripetizioni della matrice.
Motore e app restano invariati; P2/P3 rimangono aperte.

La [decisione sul modello temporale Android](ANDROID_TIMING_MODEL.md) non trova
nelle API/HAL consultate un massimo indipendente per l'associazione del Galaxy;
monotonia del contatore e autenticazione NTS non qualificano gli altri budget.
Quella decisione ha motivato la valutazione empirica condizionale su sessioni separate,
con log originali e challenge software abbinati, riusando confronto e replay.
Gli allarmi sull'originale restano visibili e non diventano falsi allarmi
certificati. La decisione non ha adottato budget né chiuso P2/P3.

Il [riepilogo multi-sessione](../pnt/README.md#compare-multiple-android-sessions)
è ora disponibile nello stesso `time-sensitivity`: replay per sessione,
originali e scarti software, conteggi locale/rete/combinato su supporto comune
fisso, copertura propria e gruppi clock dichiarati. Sessioni vuote e NTS fallito
restano nel riepilogo; duplicati e profili numerici incompatibili non vengono
conteggiati insieme. I test automatici sono sintetici; la qualifica fisica
resta aperta. Nessun budget adottato nell'app.

La [prima valutazione su tre sessioni nuove](../research/exploratory/PNT_ANDROID_SESSION_EVALUATION.md)
è conclusa, con profilo e regole fissati prima della raccolta: sugli stessi
47/117 gruppi clock ammessi, ±100 ms producono discordanza esterna/combinata,
mentre il locale resta invariato; nessuna discordanza originale nei controlli
valutabili. Restano visibili 70 gruppi insufficienti e 16/60 slot NTS falliti.
Questo risolve la domanda condizionale in quel blocco, non qualifica i 25 ms
ipotetici o P2/P3. Il raccoglitore 0.4.2 separa ora i calendari dei due endpoint
NTS: un timeout non blocca l'altro server e i tentativi dello stesso endpoint
restano distanziati, senza recuperi compressi. Tutti gli slot restano nel file,
anche dopo arresto o errore; checkpoint e progressi sono serializzati. L'intake
controlla il nuovo protocollo per endpoint e conserva i controlli seriali sui
file storici, senza cambiare questa valutazione conclusa.

La [prova outdoor del raccoglitore 0.4.2](../research/exploratory/PNT_ANDROID_NTS_COVERAGE.md)
osserva l'isolamento dei timeout su una sessione reale: 13/20 scambi NTS
autenticati, sette timeout e 18/39 gruppi comuni. Gli scarti ±100 ms sono
discordanti per esterno/combinato su tutti i 18 gruppi; il locale resta invariato
e gli originali valutabili non mostrano discordanza. Restano 21 gruppi
insufficienti. Il 46,2% comune contro il precedente 40,2% non dimostra un guadagno
stabile; gli scambi autenticati scendono dal 73,3% storico al 65,0%. Non è un
confronto A/B. Hash e replay sono verificati, i 27 originali precedenti preservati;
input completi privati e riepilogo pubblico. Qualifica temporale e P2/P3 restano aperte.

La [prova di deriva graduale](../research/exploratory/PNT_ANDROID_TIME_DRIFT.md)
riusa queste quattro sessioni già esposte con ±5 ms/s e lo stesso profilo:
65/156 gruppi comuni, 91 insufficienti nel combinato e 23 timeout conservati.
Il locale distingue già la deriva sul proprio supporto; la rete separa alcune
epoche prima e altre dopo, con ricevute successive e un gruppo inconclusivo
per ciascun segno. Non è dimostrato un allarme operativo più rapido. Il comando
`time-sensitivity --drift-ppm` conserva conteggi e prime nuove discordanze
su supporto proprio/comune; i replay costanti precedenti restano identici.
La [disponibilità delle prove](../research/exploratory/PNT_ANDROID_TIME_AVAILABILITY.md)
è ora ricostruita con callback GNSS e completamento NTS: su supporto comune la
rete precede il locale in tre coppie sessione/segno, segue in tre e due sono
simultanee. Sul supporto proprio il locale precede nelle altre cinque coppie;
non sono prove indipendenti. Un allarme combinato diventa inconclusivo con
un'altra prova esterna e resta visibile. I conteggi finali e i vecchi replay
sono identici; quella modifica supera 783 test PNT.
Nessun budget qualificato, latenza live misurata o P2/P3 chiusa.

Il [monitor condizionale PC](../pnt/README.md#conditional-pc-session-monitor)
aggiunge `android-monitor` sui file nativi disponibili durante la sessione:
riusa intake, confronto e controllo locale/esterno esistenti, conserva ogni
snapshot osservato e le revisioni per record. Tentativi ancora attivi, input
parziali o mancanti e modifiche della storia non lasciano un vecchio esito
come risultato corrente. Misura lettura, elaborazione e pubblicazione del file
risultato sul contatore PC; non associa i contatori PC/telefono. I terminali
del formato ZIP chiuso restano obbligatori. Il raccoglitore **0.5.0** aggiunge
il [collegamento HTTPS privato](../pnt/android-collector/README.md#private-pc-connection):
configurazione esplicita e invio facoltativo delle copie native durante la raccolta
allo stesso monitor, senza cambiare il motore. La prova di connessione non avvia
GNSS né trasmette registrazioni. Credenziale e certificato dedicati proteggono
il trasporto; non attestano le misure. L'app conserva i fallimenti e mostra
ricevute di trasporto. La versione **0.6.0** restituisce gli esiti del monitor
esistente: conteggi locali/esterni/combinati, revisioni, insufficienze e motivi,
legati agli hash delle copie inviate. Un errore o una cancellazione rende il
risultato corrente indisponibile e conserva il precedente come storico;
una coppia chiusa confermata resta un risultato finale. I log privati conservano
le risposte e le durate richiesta/ricevuta/applicazione del testo sul telefono,
senza associare il contatore al PC. Latenza operatore e beneficio di sicurezza
restano da misurare; nessun nuovo motore o budget qualificato.

Prova ingegneristica 0.5.0 sul Galaxy S21 FE / Android 16: configurazione
importata e connessione HTTPS telefono -> PC riuscita sulla LAN Wi-Fi.
Nessuna nuova raccolta o trasmissione GNSS; i **34 file privati preesistenti**
conservano gli stessi hash. I test sintetici esercitano anche l'invio delle
copie al monitor e il rifiuto di credenziali, certificati, identità HTTPS,
sessioni miste e trasferimenti incompleti. Non è ancora una prova outdoor
del nuovo flusso né una misura di latenza fino all'operatore.

La [prima raccolta con trasferimento live alla finestra](../research/exploratory/PNT_ANDROID_LIVE_TRANSFER.md)
è conclusa: **43 callback / 1.082 righe Raw**, di cui 376 GPS normalizzate,
17 GPS con tempo di trasmissione irrisolto e 689 di altre costellazioni;
**9/20 scambi NTS autenticati**, con 11 timeout conservati. Tutti i **35 invii**
sono confermati, senza errori di trasporto; la coppia finale PC/telefono coincide
byte per byte e i 34 file preesistenti restano identici. Non sono stati forniti
budget: nessun confronto numerico, esito insufficiente esplicito. La prova
ha anche rilevato e corretto la chiusura PC che dipendeva erroneamente dai budget:
il ricevitore originale ha atteso il limite di durata; un replay separato dei
file finali conferma la correzione senza riscrivere quell'esito. Ricevute e tempi
di richiesta non misurano la latenza dell'allarme fino all'operatore. Il prossimo
incremento 0.6.0 porta quella consegna nell'app senza riscrivere questa prova.

La [prova 0.6.0 di consegna degli esiti alla finestra](../research/exploratory/PNT_ANDROID_LIVE_OUTCOMES.md)
chiude il percorso fino all'app: **37/37 risposte**, nessun errore di trasporto,
**37 applicazioni del testo alla UI**, file finali PC/telefono identici e tutti
i 37 file precedenti preservati. Conserva **49 callback / 1.419 Raw** e **11/20
scambi NTS autenticati**, con nove timeout. Ogni esito resta insufficiente perché
non sono forniti budget; la UI finale e la chiusura automatica PC sono verificate.
La mediana richiesta/ricevuta è 409,469 ms e ricevuta/applicazione testo 7,312 ms,
entro questa singola prova; non sono latenza operatore o beneficio RF.
I test sintetici verificano anche revisioni discordante -> inconclusivo e
indisponibilità con risultato storico. Il flusso software è ora completo fino
alla presentazione; il prossimo problema resta qualifica temporale e beneficio
benigno/challenge utile, non altre estensioni amministrative del monitor.

Verifica software: **805 test PNT passano**, cinque integrazioni restano
saltate come nel baseline. I confronti sui file completi delle quattro sessioni
reali già esposte sono identici ai rapporti precedenti; i replay storici con
scarti costanti e deriva restano invariati. Una consegna ricostruita e accelerata
di copie della sessione 0.4.2 produce tre aggiornamenti parziali e quello finale,
con circa 270–729 ms di lettura/elaborazione/pubblicazione sul PC in questa prova.
È una verifica ingegneristica sul PC, non una nuova raccolta o latenza live del
telefono; input e output completi restano privati. Il test sintetico conserva
anche il passaggio discordante -> inconclusivo con una nuova prova esterna.
Il costruttore condiviso della claim esclude ora una riga la cui epoca, anche
con il budget di associazione dichiarato, sia interamente successiva al proprio
callback completato: nuove ricevute NTS o terminali non possono renderla valida.
Riga e motivo restano nel rapporto; le altre righe rimangono utilizzabili.
Un callback ritardato o una sovrapposizione entro il budget non riducono né
spostano l'intervallo dell'epoca. Il controllo opera anche nel replay esistente.

Il [testimone temporale Internet autenticato](../research/exploratory/PNT_INTERNET_TIME_WITNESS.md)
aggiunge `python -m pnt time-probe`: NTS verso PTB, intervalli UTC senza assumere
ritardi simmetrici e confronto in sola lettura con il clock del PC. La prova
documentata ottiene 2/2 risposte autenticate, intervalli larghi 74,882 e 82,501 ms
e un clock locale in ritardo rispetto a entrambi. I budget di errore sono
assunzioni non calibrate; non e una prova di spoofing o una misura GNSS.
Questo apre il canale che le doppie differenze non osservano. Restano da
stabilire associazione con UTC GNSS co-acquisito, budget indipendente e beneficio
su casi benigni/challenge. P2 resta aperta; sito e pilot vengono dopo.

L'[adattatore UTC del ricevitore](../pnt/README.md#receiver-utc-and-nts-capture-association)
aggiunge `time-compare`: decodifica UBX-NAV-TIMEUTC e usa ricevute sul contatore
NTS con un intervallo esplicito fra epoca della soluzione e ricezione del
pacchetto. Riusa il confronto temporale esistente; tAcc resta un dato dichiarato
dal ricevitore, non un budget indipendente. Ogni misura e ogni testimone rimangono
nel rapporto, comprese associazioni mancanti, ritardi ignoti e fallimenti.
I test con UTC alterato di un secondo sono sintetici e non chiudono P2.
`time-capture` ora raccoglie un flusso UBX/TCP e sonde NTS nello stesso processo,
con un calendario esplicito e un solo contatore monotono. Conserva byte,
ricevute, errori, limiti raggiunti e tentativi interrotti; riusa il rapporto e
il replay esistenti. Il ritardo della soluzione resta un parametro indipendente:
se ignoto, i pacchetti vengono salvati senza produrre un confronto utilizzabile.
I test di acquisizione usano TCP locale reale con UTC/NTS sintetici, senza
strumenti. La review Codex della #188 non ha trovato problemi rilevanti.
La [qualifica con NTS reale e sorgente UTC virtuale](../research/exploratory/PNT_CONCURRENT_TIME_QUALIFICATION.md)
ottiene 4/4 scambi autenticati e 84 pacchetti ricevuti: solo 3/336 confronti
rientrano nella finestra ammessa, e anche la baseline del PC e discordante.
Tre pacchetti superano il ritardo assunto di 20 ms; tutti gli esiti restano
visibili senza cambiare i budget. L'interoperabilita e verificata; questa prova
storica conserva la sua copertura limitata e non dimostra beneficio su GNSS reale.
L'[estensione fra scambi NTS consecutivi](../research/exploratory/PNT_TEMPORAL_BRACKET_REPLAY.md)
aggiunge l'opzione `--bracket-span-ns`: stessa sorgente e contatore, limite
esplicito sull'intero intervallo e budget di deriva validi anche fra gli scambi.
Nel replay esplorativo degli stessi dati, la copertura passa da 3 a 45/84
pacchetti, equivalenti a 15 epoche virtuali nei tre casi software. I tre ritardi
fuori budget rimangono insufficienti; i 57 confronti fra scambi utilizzabili
sono discordanti, anche per la baseline. Nessun nuovo dato GNSS, guadagno di
rilevamento o falso allarme qualificato viene dichiarato. Gli esiti originali
e i confronti con singolo scambio restano conservati, senza nuovi sigilli.
Restano un flusso GNSS reale e limiti difendibili su ritardo e UTC, prima della
prova fisica benigno/challenge; l'ingresso TCP da solo non prova l'origine RF.
Nessuna vecchia epoca GNSS viene associata retroattivamente alle sonde NTS.

Il [percorso Android sullo stesso telefono](ANDROID_GNSS_TIME.md) aggiunge
`android-time-probe` in Termux con CLOCK_BOOTTIME e `android-time-compare` sui
campi clock di GNSS Logger. Riusa acquisizione NTS, intervalli e replay esistenti;
le dipendenze geometriche non servono per il confronto temporale. Associazione
a telefono/avvio, GPS-UTC esterno e budget restano espliciti; timestamp assenti o
associazione temporale ignota rimangono insufficienti. I test sono sintetici,
anche quando usano il campione Raw pubblico. La prima verifica sul Galaxy S21
FE SM-G990B, Android 16, risolve l'installazione con pin Android espliciti e
ottiene 204 test passati sul telefono e 20/20 scambi NTS autenticati. I 20
confronti con il clock del sistema Android restano discordanti sotto budget
non calibrati. La registrazione indoor non contiene misure Raw: l'intake
rifiuta il file, senza confronto GNSS. Una nuova raccolta esterna senza USB,
via Wi-Fi, ottiene 1.897 Raw, 479 GPS normalizzate e 13/20 NTS autenticati;
i sette timeout e le 1.418 righe di altre costellazioni restano contati.
Con l'assunzione di associazione temporale di 1 ms dichiarata prima dei valori,
183 righe GPS, corrispondenti a 32 delle 86 epoche clock distinte, sono
compatibili negli intervalli fra scambi NTS consecutivi dello stesso endpoint.
Nessuna riga ha supporto dentro un singolo scambio. Con associazione ignota il
rapporto resta insufficiente; il clock di sistema Android rimane discordante.
Timestamp e interoperabilita GNSS/NTS reali sono verificati su questo caso,
con replay esatto; qualifica indipendente dei budget e beneficio
benigno/challenge restano aperti. Nessuna autenticazione RF o convalida della
posizione e dichiarata; P2 resta aperta. Dettagli ed errori conservati sono
descritti nella guida Android; nessun acquisto di sensori.

Il [replay di sensibilita UTC](../pnt/README.md#receiver-utc-offset-sensitivity)
ora misura il limite del confronto su quella registrazione reale, spostando
solo l'UTC decodificato con budget e associazione invariati. Scarti software di
entrambi i segni di 1 e 10 ms restano indistinguibili nelle 32 epoche supportate;
50, 100 e 1.000 ms risultano discordanti. Le altre 54 epoche restano insufficienti;
con associazione ignota lo restano tutte le 86. La griglia e esplorativa su dati
gia esposti, senza simulazione RF o stima dei falsi allarmi. Il risultato
definisce cosa questa raccolta puo distinguere; il passo utile resta la qualifica
indipendente dei budget e una prova benigno/challenge, non altre soglie adattate.

Il [criterio di avanzamento](PNT_SECURITY_PLAN.md#traguardi-verificabili-e-uscita-dalle-prove-senza-manipolazione)
distingue il flusso software reale, già percorso, dal beneficio di sicurezza
ancora da dimostrare. Le raccolte senza manipolazione hanno uno scopo solo se
risolvono un limite nominato. Per il prossimo traguardo serve un confronto
abbinato baseline/challenge con controlli locali ragionevoli, non un'altra
compatibilità isolata; un esito negativo o non valutabile comporta una decisione
esplicita sul canale o sulla promessa del progetto.

Il [primo confronto abbinato locale/NTS](../research/exploratory/PNT_PHONE_PAIRED_TIME.md)
e ora eseguito come test software esplorativo sul log gia esposto. Scarti
costanti di ±100 ms sono discordanti per NTS in 145 righe/25 epoche che la
continuita locale lascia passare; i salti durante il log mostrano anche il
vantaggio del controllo locale, senza guadagno NTS sui piccoli scarti di 10 ms.
L'originale ha gia 51 discordanze locali/9 epoche sotto i budget assunti, delle
quali 38 righe/7 epoche abbinate. Sono mantenute nelle transizioni e non
eliminate con una nuova soglia. Il contributo informativo condizionale e
verificato, ma vantaggio a pari falsi allarmi e validazione RF restano aperti.
Il limite da risolvere e ora identificato nel clock relativo/associazione e
nei budget dell'originale; con associazione ignota tutti gli esiti restano
insufficienti. Nessuna nuova raccolta RF o conferma P3 e iniziata.

La [diagnosi dei clock Android](../research/exploratory/PNT_PHONE_CLOCK_DIAGNOSTICS.md)
ora scompone lo scarto originale nel replay esistente. La relazione fra
`TimeNanos` e contatore Android varia da -9,025255 a +3,283083 ms, mentre la
correzione FullBias/fine-bias varia al massimo di 235 ns. Il termine dominante
e identificato nei timestamp registrati, senza attribuire la causa fisica.
Il log non conserva l'incertezza di allineamento elapsed-realtime; il limite
indipendente di associazione di 1 ms resta non qualificato. Tutte le 51
discordanze/9 epoche, le esclusioni e i precedenti risultati sono invariati.
Il prossimo incremento utile riguarda i metadati di acquisizione sul telefono,
senza ricavare un nuovo budget dall'accordo osservato o ripetere la stessa
challenge. La diagnosi usa soltanto gli input originali.

Il [PNT Clock Collector Android](../pnt/android-collector/README.md) raccoglie
ora quei metadati nello stesso intake/replay. La [prova esterna sul telefono](../research/exploratory/PNT_PHONE_NATIVE_CLOCK_METADATA.md)
conserva 141 callback, 3.199 Raw e 13/20 NTS autenticati, con sette fallimenti.
L'incertezza nativa e disponibile in tutte le callback: circa **7 ms al 68%**,
piu ampia dell'assunzione di sviluppo di 1 ms, che rimane invariata e non
qualificata. Con quel budget, 316/1.463 righe GPS (30/140 epoche) hanno supporto
NTS compatibile; il controllo locale conserva 137 discordanze/13 epoche.
Con associazione ignota tutte le righe restano insufficienti. Quattro rapporti
si riproducono esattamente; gli originali e la prova indoor vuota restano
conservati. APK, test Java, lint e 656 test PNT verificati; CI Android
Linux/Windows aggiunta senza ridurre quella Python. Nessun campo dichiarato
o ritardo della callback diventa un budget indipendente; P2 resta aperta.

Il raccoglitore 0.2 aggiunge il primo incremento dell'app autonoma: GNSS e
NTS nello stesso processo/contatore, calendario esplicito, arresto e ZIP con
entrambi gli originali. Non servono Termux o PC durante la raccolta. TLS 1.3,
identita del server, ALPN e AES-SIV sono verificati anche con un server locale
Python indipendente dal client Java, compresi casi rifiutati e timeout.
La prima prova indoor sul Galaxy ottiene 10/20 scambi autenticati, dieci timeout
e zero Raw GNSS; entrambi i terminali e tutti i tentativi restano conservati.
E una verifica del trasporto, non una baseline GNSS o una nuova qualifica P2.
Il rapporto non assegna budget UTC/deriva o risoluzione del contatore: restano
ignoti e non autorizzano un confronto qualificato. Diagnosi live di qualita e
integrazione del rapporto Python sono i prossimi incrementi; gli esperimenti
e i budget precedenti restano invariati.

La [registrazione pubblica Yunnan del giorno d'attacco](../research/exploratory/PNT_YUNNAN_RECORDING_INTAKE.md)
e ora disponibile offline: due ore di messaggi originali, 7124 RAWX,
PVT e clock conservati. La qualifica trova salti della data GNSS, lacune,
associazioni temporali ambigue nei log e fase/Doppler scambiati nel campione.
Nessun timestamp nativo entra nella precedente griglia entro 1 ms.
Il [confronto alle epoche native](../research/exploratory/PNT_YUNNAN_NATIVE_NETWORK.md)
ora usa i timestamp originali nel motore condiviso, senza ritimare codici,
e abbina PVT/clock tramite iTOW. I riferimenti contemporanei JFNG/CUSV sono
acquisiti dal mirror pubblico ESA: 204/240 epoche sono valutabili sulle stesse
osservazioni e satelliti. Il combinato riduce il residuo in 91 casi e lo aumenta
in 113; peggiora la mediana nell'ora dopo i disturbi. Le grandi anomalie locali
restano visibili. Accesso ai dati e supporto software sono risolti, ma vantaggio
di rilevamento, falsi allarmi qualificati e tempo indipendente restano aperti.
Il prossimo passo fisico deve mostrare un'inconsistenza che il controllo locale
non vede; aggiungere filtri a posteriori a questo campione non lo dimostrerebbe.

L'intake [Android Raw](../pnt/README.md) aggiunge l'importazione GPS L1/L5 dai
log di telefoni, con clock a precisione nanosecondo, identificazione esplicita
del segnale e conservazione delle misure non utilizzabili. Il campione Pixel 6
pubblico contiene 11.406 misure GPS normalizzate e 76 tempi non risolti;
non copre gli attacchi dichiarati e non dimostra rilevamento o beneficio della
rete. `android-analyze` collega ora L1/C1C ai riferimenti RINEX C1C e al motore
geometrico esistente, con coordinate locali esplicite, selezione temporale
documentata e tutte le lacune conservate. I test fisici sono sintetici;
ionosfera e ritardi di codice restano nuisance non corretti. La dimostrazione
su dati reali con posizione e cronologia dell'evento documentate resta aperta.

La [CLI PNT riutilizzabile](../pnt/README.md) ora analizza registrazioni RINEX
di un sito fisso: controlli locali e abbinati alla rete, doppie differenze,
clock relativo, disaccordo fra riferimenti e lacune in un unico rapporto.
La [verifica software sui tre file gia esposti]
(../research/exploratory/PNT_FIXED_SITE_ANALYSIS.md) produce diagnostica su
tutte le 20 epoche richieste; il report storico ds7 resta identico dopo il
riuso dei calcoli. Non e ancora un rilevatore qualificato: P2 richiede ancora
la prova del beneficio e il tempo assoluto un testimone indipendente.

Il [confronto di sviluppo riutilizzabile]
(../research/exploratory/PNT_COMPARISON_BENCHMARK.md) aggiunge `python -m pnt compare`:
baseline, calibrazione e valutazione separate, stesso supporto locale/rete e
rampe software nelle pseudodistanze prima del fit. Nel corpus gia esposto il
combinato supera la soglia in 9/60 epoche originali, il locale in 6/60; non si
dimostra un vantaggio a pari falsi allarmi. Le rampe confermano la cancellazione
del clock comune e del disturbo condiviso, e la contaminazione da un riferimento
alterato. Tutte le 15 varianti e i campioni non valutabili restano nel report.
Sono risposte a perturbazioni software, non prestazioni su attacchi RF reali.

La [prova di trasferibilita su intervalli successivi]
(../research/exploratory/PNT_REFERENCE_TRANSFER.md) aggiunge `python -m pnt transfer`:
un solo coefficiente locale/rete imparato sul training e applicato senza
adattamenti a epoche successive, confrontato con nessuna correzione e
sottrazione unitaria. Due intervalli disgiunti e le tre rotazioni delle stazioni
producono sei confronti, ciascuno con 60 epoche di training e 120 di valutazione.
La sottrazione unitaria peggiora tutti e sei; il coefficiente imparato migliora
tre casi e peggiora tre, con riduzioni dell'errore quadratico medio fra
-1,00% (peggioramento) e +2,24%. Le classi di supporto e i peggioramenti per epoca restano
visibili. Non emerge un beneficio ripetibile sufficiente a promuovere questa
correzione a rilevatore; nessuna soglia del confronto precedente e modificata.
Si tratta di previsione di residui su dati gia esposti, senza etichette benigne,
non di conferma prospettica. Su questa topologia non proseguire con altre
varianti della stessa regressione per cercare un risultato positivo: la
prossima estensione deve motivare un diverso effetto fisico o una topologia
di riferimenti che lo osservi, prima di valutarne il beneficio P2.

La [prova con riferimenti vicini WegenerNet]
(../research/exploratory/PNT_CLOSE_REFERENCE_TRANSFER.md) riusa lo stesso metodo
su W181/W182/W183, distanti 4,6–9,9 km, nelle stesse finestre A/B. Il coefficiente
imparato riduce l'errore quadratico medio in 6/6 confronti, ma solo dello
0,372–2,287%; la sottrazione unitaria peggiora tutti e sei. Sono valutabili
717/720 righe richieste: l'ultima epoca omessa dal convertitore resta visibile.
Coordinate dichiarate prima del training, varianti preliminari, errori di
conversione e peggioramenti per epoca sono conservati con gli input originali.
E un piccolo effetto descrittivo, non un beneficio di sicurezza o una precisione
di posizione; P2 resta aperta. Non estendere queste regressioni per cercare
un guadagno maggiore: servono evidenze benigne/challenge abbinate o una diversa
osservabile fisica. Il risultato precedente resta invariato.

Il [confronto dei messaggi di navigazione]
(../research/exploratory/PNT_NAVIGATION_WITNESS.md) apre un meccanismo diverso:
`python -m pnt navigation` confronta la stessa issue GPS dichiarata localmente
con archivi esterni, mantenendo messaggi mancanti, discordanti e conflitti fra
fonti. Nel primo controllo software, una modifica comune di 0,954 microsecondi
dei clock satellitari sposta il clock stimato da codici TXAU reali di 285,905 m,
ma cambia i residui per satellite di meno di 1 mm. I campi alterati restano
discordanti rispetto all'archivio esterno. I messaggi locali sono varianti
**sintetiche** dell'archivio NOAA: questo dimostra un meccanismo e il codice,
non un beneficio su un attacco RF registrato o a pari falsi allarmi.
Il [confronto della registrazione JammerTest 2.1.1]
(../research/exploratory/PNT_NAVIGATION_JAMMERTEST_211.md) aggiunge l'adattatore
SFRBX GPS L1 C/A: 424 messaggi in 9.387 SFRBX multi-GNSS, due pacchetti
corrotti esclusi e conteggiati solo con recupero esplicito. Tre cicli completi
sono decodificabili senza riusare frammenti di altri cicli; 204 restano incompleti.
G17 e G21 concordano con il NAV NOAA dell'11 settembre 2024. G14 dichiara
invece il 1 ottobre e non trova la stessa issue nell'archivio del giorno: resta
evidenza insufficiente, non una discordanza fra campi della stessa issue.
La modalita UBX conserva l'intero file, anche i messaggi con `toc` fuori giorno;
la data dichiarata serve soltanto a risolvere l'era della settimana GPS.
La parita radio resta dichiarata dal ricevitore, non verificata indipendentemente.
L'episodio aveva gia anomalie locali evidenti: P2 non dimostra ancora beneficio
aggiuntivo a pari falsi allarmi. Il prossimo passo deve trovare un confronto
benigno/alterato abbinato che possa misurarlo, prima di moltiplicare analisi su
questo file. La concordanza dei messaggi non autentica distanze o tempo;
la provenienza indipendente delle fonti resta da qualificare.

Il [confronto abbinato OBS/NAV](../research/exploratory/PNT_NAVIGATION_COMPARISON.md)
aggiunge `python -m pnt navigation-compare`: soglie sui soli dati originali
di calibrazione, controlli locali sui residui e sul passo del clock, e
testimone esterno legato ai messaggi effettivamente usati. Su 120 epoche
successive della stazione NYA2, il bias comune sintetico nei messaggi NAV
lascia 7 superamenti locali come nell'originale, ma differisce dall'archivio
in tutte le epoche, incluse 113 senza superamenti locali. La deriva comune
ha 9 superamenti locali e 111 epoche discordanti senza superamenti; il
peggioramento resta visibile. Alterare invece solo i codici mantenendo il
NAV produce 74 superamenti locali e nessuna discordanza di messaggio:
la compatibilita NAV non convalida il segnale. Sono casi software su dati
gia esposti, con lo stesso archivio come origine delle varianti e testimone;
non un confronto benigno/attacco fisico, una fonte indipendente qualificata
o una misura dei falsi allarmi. P2 resta aperto, ma ora il confronto puo
essere applicato a un caso reale adeguato senza un nuovo esecutore o sigillo.

La [prova RF pubblica con ricevitore software]
(../research/exploratory/PNT_PUBLIC_RF_NAVIGATION.md) ha decodificato 100 secondi
di campioni GPS L1 senza nuovo hardware. La CLI ammette ora anche NAV RINEX 3
GPS, con gli stessi campi e criteri di confronto. Tutti i cinque messaggi
esportati da GNSS-SDR risultano discordanti con NOAA: il controllo dei bit
individua errori nell'esportazione del flag P e dell'URA, precisione degli
archivi e differenze nei codici L2 di tre satelliti. I risultati e i dieci
cicli completi, oltre ai cinque incompleti, restano visibili; non sono
rilevamenti di attacco. Prima della coppia benigno/attacco P2 serve un
confronto riutilizzabile che qualifichi queste rappresentazioni, conservando
variazioni reali di un bit e ambiguita. Non occorre acquistare sensori per
proseguire questo sviluppo; la concordanza NAV resta distinta dall'autenticita RF.

La [qualifica delle rappresentazioni LNAV]
(../research/exploratory/PNT_NAVIGATION_REPRESENTATION.md) aggiunge
`navigation --qualify-lnav`, conservando il confronto precedente. Ogni campo
deve ammettere un unico valore trasmissibile entro l'intervallo scritto;
nessuna correzione al bit piu vicino o precisione inferita. Sui dieci cicli
CTTC completi tutti i 270 campi locali sono risolvibili, ma le rappresentazioni
NOAA hanno 136 campi senza candidato, dieci zeri af2 ambigui e sei metadati L2
invalidi. Tutti i cicli restano non qualificati; le cinque discordanze native
restano invariate e non diventano attacchi. I test preservano cambiamenti di
un bit, conflitti e casi mancanti. La revisione V2 usa limiti razionali esatti
per la conversione angolare e rende espliciti URA/TGD indisponibili anche da
UBX, senza ammetterli nel confronto precedente. Il risultato V1 resta conservato;
la correzione non cambia gli esiti CTTC. Il prossimo prerequisito e un testimone
Internet che preservi i valori trasmessi o abbia limiti di conversione
documentati, prima del confronto benigno/attacco P2.

Il [testimone GFZ NavBit](../research/exploratory/PNT_GFZ_NAVIGATION_WITNESS.md)
colma quel limite di rappresentazione sul caso CTTC gia esposto: l'archivio
pubblico conserva le parole GPS trasmesse, senza passare da decimali NAV.
Tutti i 270 campi dei dieci cicli completi concordano; i cinque cicli locali
incompleti restano tali. Sono conservati cinque file giornalieri originali,
45 sottoframe con parita verificata e un replay offline. Il confronto con
NOAA resta non qualificato e quello con entrambe le fonti conserva dieci
conflitti; nessuna correzione dei risultati precedenti. GFZ e un singolo
fornitore aggregato, non una rete di testimoni indipendenti qualificati.
Resta da trovare la coppia benigno/attacco con NAV locale recuperabile e
copertura esterna contemporanea: autenticita RF e beneficio P2 non sono
dimostrati dalla concordanza dei messaggi.

Il [test su una registrazione d'attacco](../research/exploratory/PNT_GFZ_RECORDED_ATTACK.md)
applica GFZ a JammerTest 2.1.1: due cicli locali concordano su tutti i 54 campi,
anche G21 nella rampa secondo la cronologia provvisoria; G14 dichiara una issue
futura e resta senza testimone. Sono ancora tre cicli completi su 207, non una
misura del tasso di rilevamento. Il nuovo lettore NetCDF riutilizzabile conserva
tre issue GFZ incoerenti su 8.640 cicli e tutti gli esiti precedenti. La prova
conferma il limite del solo NAV: concordare durante un evento non autentica RF,
distanze o posizione. Il beneficio P2 resta aperto e va cercato con osservabili
geometriche/temporali e un controllo benigno difendibile, senza altre varianti
amministrative di questo episodio.

Il [primo ciclo esplorativo P0/P1]
(../research/exploratory/PNT_LOCAL_NETWORK_FEASIBILITY.md) confronta una
stazione fissa con altre sei su dati GPS gia esposti. Il prototipo mostra come
separare anomalie locali da anomalie condivise **nel modello ammesso**, ma non
dimostra un vantaggio di rilevamento a pari falsi allarmi ne identifica un
attacco. Quel ciclo non aveva una registrazione d'attacco locale abbinata a
riferimenti esterni contemporanei; manca ancora un clock indipendente. La rete sola
non verifica l'RF locale e la differenziazione non verifica il tempo assoluto.
Il passo P2 e un caso offline documentato con quelle misure abbinate, mantenendo
i controlli locali. Il [primo intake P2]
(../research/exploratory/PNT_JAMMERTEST_PAIRING.md) ha accoppiato 210
osservazioni GPS strutturalmente utilizzabili della vittima ferma a due stazioni esterne reali. Il registro
ufficiale JammerTest chiarisce che gli orari dei tre test sono CEST e li porta
nella finestra delle osservazioni GPST. Il CSV appiattito slitta alcune colonne
quando mancano misure: 12.012 righe GPS sono state escluse e non resta alcuna
coppia nei primi due test, una sola nel terzo. Il successivo
[recupero UBX](../research/exploratory/PNT_JAMMERTEST_RAWX.md) ha ricavato
317 coppie a tre ricevitori in 81 epoche, incluse 108 coppie nelle finestre
dei test, e ha osservato salti dell'ora interna nei due test GPS L1. L'ordine
dei pacchetti fornisce un tempo di acquisizione monotono provvisorio, non un
clock indipendente. Il [confronto esplorativo sui medesimi campioni]
(../research/exploratory/PNT_JAMMERTEST_CONTRAST.md) trova variazioni locali
molto maggiori di quelle esterne durante i test, ma la combinazione resta
simile al controllo locale: un vantaggio di rilevamento dato dalla rete non e
ancora dimostrato. Nessun tasso di rilevamento o falso allarme e misurato.
Il sito segue la prova fisica.

Il [secondo episodio stazionario P2]
(../research/exploratory/PNT_JAMMERTEST_211.md) aggiunge una rampa ufficiale
di 36 minuti dello stesso archivio. Il parser conserva due pacchetti UBX con
checksum errato come scarti espliciti e ricostruisce un intervallo RAWX mancante.
Si ottengono 231 coppie a tre ricevitori; nella rampa 154 coppie con supporto
pre-evento mostrano variazioni mediane di 0,71 m locali e 0,78 m combinate.
Il ricevitore presenta inoltre un salto del proprio tempo di circa 19 ore.
Neppure questo caso dimostra vantaggio di rilevamento della rete rispetto ai
controlli locali. P2 resta aperto: servono un controllo benigno abbinato e un
attacco in cui l'evidenza locale non sia già decisiva, oppure va limitata la
rivendicazione del prodotto al contesto indipendente dell'incidente. Ulteriori
varianti amministrative dello stesso confronto non sostituiscono quei dati.

La [verifica separata delle due stazioni]
(../research/exploratory/PNT_JAMMERTEST_211.md) evita che la mediana della rete
nasconda variazioni opposte: nella rampa 2.1.1 il disaccordo mediano sui 154
campioni supportati è 0,55 m, contro 0,42 m prima dell'evento. Il risultato
descrive contesto esterno per questo osservabile, non un'autenticazione del
segnale locale. Il confronto originario resta conservato e il nuovo output
versionato aggiunge il controllo di accordo, senza cambiare gli esiti chiusi.

Decisione P2: il risultato utilizzabile oggi è un **rapporto tecnico
riproducibile di contesto indipendente per un episodio offline**. Non
promuovere l'allarme a verifica del fix o
del timestamp e non dichiarare un beneficio di rilevamento della rete. La
prova successiva richiede nello stesso sito un periodo benigno e un attacco
meno evidente localmente, osservazioni grezze locali con qualità/clock/PVT,
due riferimenti contemporanei e una base temporale o verità indipendente.
Una [nuova qualifica TEXBAT/NOAA]
(../research/exploratory/PNT_TEXBAT_NOAA.md) ha trovato osservabili TEXBAT
gia elaborati e due stazioni fisicamente distinte con GPS C1 contemporaneo. Nel ds7
time-push, 110 coppie su dieci epoche mostrano una variazione mediana locale
di 168,86 m, contro 0,53 m nelle differenze fra satelliti: una modalita cieca
della sola geometria differenziale. Il confronto usa cleanStatic come
controfattuale esposto; non dimostra un allarme di rete, un clock indipendente
o un vantaggio a pari falsi allarmi. La combinazione completa richiesta da P2
resta dunque da dimostrare. [FGI-JSDR]
(https://www.maanmittauslaitos.fi/en/research/research/gnss-specialists/fgi-gnss-jamming-and-spoofing-dataset-repository-fgi-jsdr)
pubblica soprattutto RF da elaborare; il
[corpus di Kunming](https://pmc.ncbi.nlm.nih.gov/articles/PMC11220923/)
riporta osservabili ma anche forti distorsioni locali; i file completi di
[CG-SpoofGNSS](https://github.com/agilawood4/CG-SpoofGNSS) non risultano ancora
rilasciati. Il [confronto del clock TEXBAT/NOAA]
(../research/exploratory/PNT_TEXBAT_CLOCK_CONTEXT.md) usa le stesse 14 epoche
e un modello broadcast comune: il massimo pulito e 1,17 m sul solo ricevitore
e 1,23 m dopo la correzione di rete; durante il time-push ds7 entrambi i
canali arrivano a circa 312 m. Le due stazioni forniscono contesto stabile,
ma non un beneficio di rilevamento per questo attacco gia evidente localmente.
La posizione locale usata viene dal cleanStatic pubblicato, non da un rilievo
indipendente. Il passo ad alto valore e cercare un episodio con controllo
locale ambiguo e base fisica difendibile, non aggiungere altri sigilli o
varianti JammerTest.

La [qualifica mirata di una traiettoria simulata]
(../research/exploratory/PNT_P2_RECORDING_DECISION.md) mostra perché un'altra
registrazione dello stesso archivio non colma P2: nella finestra GPS 2.3.5
restano 33 coppie su 16 epoche, contro una sola coppia nella finestra Galileo
precedente. La pausa fra le due trasmissioni non è un controllo benigno
certificato; il CSV non identifica senza ambiguità i codici e il registro
secondario contraddice i nomi degli scenari. Il rapporto fissa i dati minimi da
ottenere per la prossima prova, senza introdurre nuovi sigilli o soglie.

L'[intake RINEX per sito fisso](../research/exploratory/PNT_FIXED_SITE_INTAKE.md)
riusa il parser e l'abbinamento esistenti: su tre stazioni pubbliche distinte
del giorno 255/2024 trova 28.515 righe satellite-epoca comuni in 2.880 epoche,
con 8–12 satelliti per epoca. È una verifica della disponibilità dei dati,
senza etichette d'attacco, verità locale indipendente o misura del beneficio
della rete. La registrazione decisiva descritta sopra resta da ottenere.

Il lavoro inverso resta una base scientifica riutilizzabile, con i limiti sotto
riportati. Questa variazione non chiude S2 e non avvia la vecchia campagna S3.

## Cosa abbiamo dimostrato

- G14 DOY246: una dimostrazione storica condizionale, errore esterno 31.017 m,
  raggio prospettico 5755.157 m, residuo del ricevitore escluso -0.846 m.
  Il singolo errore di 31 m non e una precisione generale garantita.
- G08 DOY249 e G12 DOY248: posizioni ricostruite, ma incertezza oltre il limite
  dichiarato; esiti conservati come `UNCERTAINTY_TOO_LARGE`.
- G12 DOY250 e G13 DOY247: dati insufficienti; nessuna posizione qualificata.
- Sorgenti, clock, bias, assetto dei riferimenti, coordinate e spostamenti
  delle stazioni sono stati confrontati con prodotti precisi e replay verificabili.
  Questi controlli migliorano la base fisica, non certificano l'incertezza totale.
- I recenti studi di maree e moto polare non spiegano i residui di riferimento
  ancora intorno a 0.9–1.0 m nelle due finestre esplorative di cinque minuti.
- Il nuovo confronto meteorologico conserva 72 campioni su nove stazioni e due
  giorni: differenze zenitali fino a 12.54 cm dal modello semplice, equivalenti
  fino a 70.02 cm a 10 gradi usando la medesima funzione di elevazione. E una
  sensibilita del modello. Il successivo replay RF con VMF3 completo misura
  miglioramenti dello 0.134%/0.838%, con tre stazioni peggiorate per giorno.

## Stato del verticale di ricostruzione orbitale

| Fase | Stato | Risultato necessario |
|---|---|---|
| S0: diagnosi | Consegnata | Cause e limiti degli eventi precedenti documentati |
| S1: cinematica sintetica | Consegnata | Posizione/moto con codice e variazione di distanza in simulazione |
| S2: misure vere | Aperta; avanzamento con criteri propri | Calibrazione fisica, continuita delle osservabili e incertezza difendibile |
| S3: conferma su nuovi dati | Non ancora avviata | Campioni nuovi, regole fissate prima dei dati, verifiche escluse |
| S4: prestazioni e prodotto | Da affrontare dopo S3 | Disponibilita, errori, incertezza e dominio d'uso misurati |

## Esito della fase reale su G12

La [prova sugli intervalli RF reali](../research/exploratory/REAL_TARGET_INTERVAL.md)
ha portato il codice e gli incrementi di fase di G12 nel solver esistente,
senza orbita del bersaglio nel fit. Il primo insieme di cinque stazioni fallisce
per geometria o fase assente (20/20 casi conservati). Una variante esplorativa
separata usa BOGT, con header GPS verificato: venti finestre complete, codice
accettato condizionalmente in 20/20, codice+fase in 5/20 e rigettato in 15/20.
Nei cinque casi ammessi la fase migliora le previsioni RF escluse, ma la
posizione rispetto all'oracolo storico migliora soltanto in 3/5 e peggiora in
2/5. L'RMS di posizione accoppiato e 49,88 m col solo codice e 55,41 m con
la fase; un caso di fase arriva a 120,68 m. L'oracolo e un confronto
retrospettivo, non un raggio d'incertezza.

**S2 rimane aperta per un motivo preciso:** gli incrementi di fase non
identificano il bias assoluto del codice specifico della stazione. La sua
ampiezza fisica e la covarianza completa non sono ancora vincolate; un metro
ipotetico di bias puo spostare la posizione fino a circa 70 m nel trasferimento
gia misurato. Una futura chiusura della ricostruzione indipendente richiede un
limite indipendente a quel modo o un'altra osservabile/geometria. Nel pivot
PNT si qualifica invece il budget del test di sicurezza specifico, senza
trasferire a esso una precisione orbitale non dimostrata. La campagna inversa
S3 resta subordinata a un inviluppo totale credibile con margine utile.

Il [controllo diretto di identificabilita](../research/exploratory/REAL_TARGET_BIAS_IDENTIFIABILITY.md)
conferma il limite sulla geometria G12 reale: aggiungendo quattro contrasti
liberi di bias per stazione, il rango numerico e 38/40 col codice in 20/20
archi e 39/40 nei cinque archi di fase ammessi. La fase recupera una direzione,
ma ne lascia una che accoppia bias e posizione. La risposta a +1 m omesso resta
circa 70–77 m; nessuna ampiezza fisica del bias e stata misurata.

La [roadmap scientifica](SCIENTIFIC_ROADMAP.md) resta il piano originale.
Il disegno di 24 tentativi contiene ancora parametri da fissare: non equivale
a una campagna gia pronta o validata. Nessuna percentuale di completamento
puo sostituire queste verifiche sperimentali.

## Consegne e passi residui del percorso inverso

Il riepilogo seguente conserva il percorso S2/S3. La prossima prova inversa
deve risolvere il limite di identificabilita sopra descritto; non dipende da
P2 PNT e non implica la prosecuzione automatica di ogni voce storica.

1. Collegamento meteorologico consegnato sulle due finestre esposte: griglie
   alle coordinate ammesse, 88 confronti numerici con la routine originale e
   616 calibrazioni riuscite. Il modello completo riduce i residui soltanto
   dello 0.134%/0.838%; tre stazioni peggiorano per ciascun giorno. Lo scarto
   del catalogo ALGO viene evitato usando le griglie, senza modificarne i dati.
2. Prima estensione temporale consegnata: un'ora G14, sette stazioni, 847
   calibrazioni qualificate. Stima delle correzioni nella prima mezz'ora e
   verifica nella seconda: RMS dei contrasti 0.974 -> 0.938 m con offset
   condivisi per satellite. Secondo arco 05:00–06:00 completato: altre 847
   calibrazioni valide, RMS 1.047 -> 1.003 m con stima recente (−4.15%) e
   1.015 m trasferendo le correzioni precedenti (−3.04%). Il modello direzionale
   trasferito peggiora tutte le stazioni; quello per coppia stazione/satellite
   non supporta nessun blocco completo del test. Verifica del 5 settembre
   consegnata: altre 847 calibrazioni, RMS 1.010 -> 0.931 m (−7.80%), tutte le
   stazioni migliorate; anche le cinque comuni migliorano (−5.77%). Cambiano
   due stazioni, riferimenti e bersaglio escluso: replica del metodo su un altro
   campione esposto, non effetto isolato del giorno né conferma indipendente.
   Confronto rapid/final CODE consegnato sugli stessi dati e collegamenti:
   RMS di base 1.010 -> 0.988 m (−2.17%), ma dopo correzione condivisa resta
   0.931 m in entrambi i casi. Anche trasferendo le correzioni rapid ai dati
   final si migliora: 0.935 m, −5.38%, tutte le stazioni. Il cambio di prodotti
   non risolve la struttura dominante; due prodotti CODE non sono una verita
   indipendente. Trasferimento alla settima stazione esclusa ora consegnato:
   RMS 0.953 m con entrambe le famiglie, miglioramento aggregato 5.64% rapid
   e 3.55% final, tutti i 3942 campioni supportati. Migliorano sei/cinque
   stazioni: AREQ peggiora in entrambi i casi, DRAO leggermente con i final.
   La correzione non va promossa come beneficio universale. I prodotti a monte
   possono ancora includere la stazione esclusa dalla stima locale.
3. Collegamento errori-posizione/moto consegnato su geometrie sintetiche:
   cinque casi validi e uno sotto la maschera, tutti conservati. Un modo comune
   per stazione di ampiezza ipotetica 1 m produce 11–166 m sulla posizione,
   pur essendo invisibile nei contrasti centrati. Non sono errori misurati o
   raggi al 95%; il budget reale e i suoi limiti restano invariati.
   Test con riferimenti esclusi consegnato: 22 rotazioni, 3942 percorsi valutati
   e 5452 assenze conservate. Ricalibrando senza il satellite in esame, RMS
   1.135 -> 1.132 m: beneficio della correzione condivisa soltanto 0.26%,
   con BOGT e BRAZ peggiorate. I contrasti fra stazioni migliorano dello 0.86%.
   Manteniamo quindi la versione senza correzione come base; nessuna riduzione
   del limite di errore o promozione della correzione in produzione.
   Collegamento fase reale consegnato sui due cohort esposti: 6299 intervalli
   valutati, sette/cinque stazioni utilizzabili; due esclusioni del 5 settembre
   conservate. La componente differenziale della fase e circa 0.19–0.24 mm/s,
   ma quella comune alla stazione resta circa 14 mm/s. Trasferendo questi errori
   nel modello a intervalli esistente, su traiettorie sintetiche e coordinate
   reali, la fase grezza viene rigettata in 12/12 finestre. Corretta con gli
   altri riferimenti, migliora la velocita in 9/12, ma peggiora la posizione
   iniziale in 8/12 e quella futura in 5/12. Un bias costante ipotetico di 1 m
   conserva fino a circa 70 m di risposta sulla posizione, quasi invariata.
   Questo e un risultato ibrido di sensibilita, non una nuova ricostruzione
   indipendente o una covarianza qualificata. L'integrazione successiva sul
   bersaglio reale e descritta sopra; resta da vincolare il bias assoluto.
   Nessuna riduzione del limite storico di 20 m sulla misura.
4. Congelare il metodo e provarlo su dati nuovi, conservando tutti gli esiti.
5. Riprendere API e sito quando i risultati stabiliscono cosa il servizio puo
   promettere e quando deve dichiarare che non sa determinare una posizione.

Studi: [sensibilita zenitale](../research/exploratory/ATMOSPHERE_ZENITH.md) e
[calibrazione RF con VMF3](../research/exploratory/VMF3_REFERENCE_CALIBRATION.md).
Ultimo studio: [fase reale e trasferimento al modello a intervalli](../research/exploratory/REAL_PHASE_INFORMATION.md).
Risultato piu recente: [G12 reale, fit RF e confronto retrospettivo](../research/exploratory/REAL_TARGET_INTERVAL.md).
Commit, push, CI e merge ordinario restano parte del workflow; deploy separato.

The one-hour replay entry point is `research.exploratory.hour_reference_checked`: it pins auxiliary bias/antenna inputs and revalidates the existing frame/loading chains before unchanged v2 calculation. Frozen v1/v2 evidence is preserved.
