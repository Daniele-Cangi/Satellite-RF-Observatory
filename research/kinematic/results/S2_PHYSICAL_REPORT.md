# S2 — Audit delle fonti e diagnostica della velocità media da fase

Evidenza del 10 settembre 2026: [physical_source_study_v1.json](physical_source_study_v1.json).
SHA-256: `7f90957d7b668b03a7fa106b56d209c3a4af0f1fdbda1e13b2a3f8e0a05ab317`.
Specifica, fonti tecniche e limiti: [S2_PHYSICAL_SOURCES.md](../S2_PHYSICAL_SOURCES.md).

Il risultato utile dell'audit è un limite concreto della sorgente: la rete
storica G14 non dispone dei Doppler dichiarati su abbastanza stazioni per
alimentare direttamente il fit cinematico attuale, né sul holdout GOLD.
L'audit non ricalcola G14 e non modifica il suo successo storico code-only.

## Cosa dichiarano realmente gli header archiviati

Fonte immutata: `experiments/positioning_g14_doy246_network/structure.json`.
Sono esaminate soltanto le strutture degli header già disponibili; nessuna
nuova osservazione target, calibrazione numerica o orbita è stata acquisita.

| Stazione | Ricevitore | Firmware | D1C/D2W richiesti dichiarati | Campi per alternativa di fase |
|---|---|---|---|---|
| ALGO | SEPT POLARX5 | 5.3.2 | Sì | Sì |
| AMC4 | Header indisponibile | — | Non verificabile | Non verificabile |
| AREQ | SEPT POLARX5 | 5.7.0 | No | Sì |
| BOGT | JAVAD TRE_3 DELTA | 4.6.00 | No | Sì |
| BRAZ | LEICA GR50 | 4.83/7.900 | No | Sì |
| DRAO | SEPT POLARX5 | 5.2.0 | Sì | Sì |
| MKEA | SEPT POLARX5 | 5.7.0 | No | Sì |
| PIE1 | SEPT POLARX5TR | 5.7.0 | No | Sì |
| STJO | SEPT POLARX5 | 5.3.2 | Sì | Sì |
| YELL | SEPT POLARX5 | 5.5.0 | Sì | Sì |
| GOLD, holdout storico | JAVAD TRE_G3TH DELTA | 4.2.03 | No | Sì |

Sono **4 dichiarazioni Doppler, 10 candidati strutturali di fase e 1 header
indisponibile**, su undici voci conservate. La presenza dei campi non prova
completezza, lock continuo o qualità delle misure. La differenza fra stazioni
con lo stesso modello di ricevitore mostra inoltre perché la sola famiglia
hardware non determina ciò che il file effettivamente fornisce.

## Alternativa implementata e controllata

Il nuovo adapter usa solo riferimenti non-target e restituisce incrementi
ionosphere-free di fase divisi per la durata dell'intervallo. Conserva gli
estremi, la matrice di trasformazione e la covarianza fra tutti gli intervalli.
Non effettua una sostituzione nel vecchio importatore Doppler o nel fit.
Non importa ancora file RINEX reali di fase end-to-end.

La prova inventata usa quattro riferimenti circolari, un generatore inerziale
indipendente, dodici estremi da −330 a 0 s, fasi arrotondate a 0,001 cicli,
ambiguità costanti e ionosfera dispersiva al primo ordine. Non contiene una
traiettoria target. Tutti gli otto criteri di sviluppo passano.

| Controllo | Risultato |
|---|---:|
| Massimo scarto della media di fase dal cammino indipendente | 0,0000183143 m/s |
| Massima differenza media su 30 s / rate istantaneo alla fine | **1,530522 m/s** |
| Correlazione fra intervalli adiacenti con fasi IID | **−0,5** |
| Sigma del rate dal solo sigma inventato di 0,01 cicli | 0,000289510 m/s |
| Massimo sigma del rate dalla sensibilità neutra dichiarata | 0,000476608 m/s |

Il piccolo errore del primo controllo è accuratezza numerica del generatore
e della conversione; non è precisione di un ricevitore reale. Il confronto
da 1,53 m/s mostra che usare questi incrementi come Doppler istantanei
sarebbe un errore del modello temporale. Anche assegnarli al punto medio
non è esatto per una traiettoria generica, come verifica il test cubico.

Il contributo atmosferico usa una base dichiarata 1/sin(e), elevazioni
inventate crescenti e sigma zenitali 0,05 m / 0,0001 m/s. La propagazione
dalla covarianza delle fasi grezze coincide con quella della base di ritardo
neutro differenziata. Non è un modello meteorologico qualificato né una
nuova correzione nei solver storici; dimostra come conservare l'errore
condiviso fra riferimenti ed epoche.

## Stress conservati, compreso il limite negativo

| Caso | Esito dell'adapter |
|---|---|
| Slip segnalato dal flag L1C | Intero arco respinto |
| Estremo di fase mancante | Intero arco respinto |
| Flag di reset del clock | Intero arco respinto |
| Salto di un ciclo L1C non segnalato | **Non rilevato dai flag**, variazione del rate 0,016148 m/s |

L'ultimo caso resta `REFERENCE_PHASE_RATE_AVAILABLE`, con
`real_rf_qualified=false`. Il software non confonde «campi disponibili»
con «continuità provata». Servono un controllo indipendente dei riferimenti
e ulteriori criteri di continuità; non si può trasferire direttamente questa
disponibilità in un risultato scientifico accettato.

## Consegna e passaggio successivo

18 nuovi test verificano header, ambiguità costanti, anticorrelazione,
trasporto atmosferico, esclusione target/futuro prima dei valori, input
malformati, discontinuità e distinzione fra rate medio e istantaneo.
La suite locale completa passa: **190 test**, incluse le regressioni di
posizionamento, esperimento G08, service, ricerca e archivio web.
Gli hash dei sorgenti associati alle evidenze S1, S2a, S2b, bilancio locale
e fit congiunto sono invariati. Nessun evento chiuso viene rivalutato.

Il passo seguente è collegare l'osservabile medio al **ponte dei riferimenti**,
con importer di fase e controlli di continuità prima della stima target.
La covarianza fisica di clock/riferimenti, antenne, coordinate e propagazione
resta da qualificare; sono elencate le evidenze mancanti nella specifica.
Non c'è ancora una nuova qualifica RF, un inviluppo totale o una campagna S3.
