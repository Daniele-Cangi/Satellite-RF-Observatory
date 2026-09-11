# S2 — Risultati del fit con covarianza congiunta

Studio sintetico del 10 settembre 2026. Nessun nuovo dato RF o stato orbitale
del bersaglio. Specifica in [S2_JOINT_FIT.md](../S2_JOINT_FIT.md), evidenza in
[joint_fit_study_v1.json](joint_fit_study_v1.json).

SHA-256 del report:
`4488a9ad4e8db5733199ca0253105ea47cfbb24f98bf2b63a02ee845bf73081f`.
Sono registrati ricetta e hash delle covarianze, seed, sorgenti, ambiente,
entrambi i fit nominali, tutte le sedici coppie rumorose e i due stress per
entrambi gli estimatori. Tutti i nove criteri di sviluppo passano;
`real_rf_qualified=false` rimane esplicito.

## Risultato principale

Ottimizzazione, covarianza locale e test dei residui ora usano la stessa
matrice di errore, incluse le correlazioni fra RF, calibrazioni e coordinate.
Le coordinate terrestri sono stimate come nuisance vincolate dalle misure
terrestri. Nessun prior orbitale del bersaglio viene aggiunto.

Nel problema linearizzato la distribuzione del costo dei residui è coerente
con i **143 gradi di libertà**. Eliminare le correlazioni fra i tre blocchi,
pur conservando le loro varianze e covarianze interne, cambia la distribuzione
del costo sotto lo stesso generatore. Questo è un miglioramento della
coerenza inferenziale; i sedici casi non dimostrano un miglioramento uniforme
della precisione né una calibrazione delle code all'1%.

## Confronto sullo stesso rumore dichiarato

| Quantità | Covarianza congiunta | Tre blocchi senza correlazioni incrociate |
|---|---:|---:|
| E[Q] esatto nel problema locale sotto il generatore | 143,000000 | 137,482828 |
| Var[Q] esatta nel problema locale sotto il generatore | 286,000000 | 274,012783 |
| Media Q nei 16 fit non lineari | 144,244655 | 137,114180 |
| Casi nominali accettati alla soglia p ≥ 0,01 | 16/16 | 16/16 |
| Mediana errore xyz al termine dell'arco | 645,059 m | 653,025 m |
| RMS errore xyz al termine dell'arco | 756,057 m | 752,906 m |

La distribuzione χ²₁₄₃ ha media 143 e varianza 286. La corrispondenza esatta
in tabella riguarda la linearizzazione gaussiana con covarianza nota, non
un teorema globale sul solver non lineare. La media di sedici fit è solo
diagnostica. Nessuna ampiezza di rumore è stata stimata o riscalata dai
residui per migliorare p-value o accettazione.

Nessuno dei sedici casi cambia esito nominale fra i due estimatori. Cambiano
tuttavia i p-value: per esempio, il caso di indice 5 passa da 0,55393 con
la covarianza congiunta a 0,91641 nell'ablazione, sugli stessi dati. Un costo
più basso con pesi diversi non prova un modello migliore.

Il fit senza rumore recupera la posizione entro il criterio di 1 cm.
Questo controllo numerico non è una precisione misurata su un satellite.

## Previsioni escluse e stress

Ogni fit congiunto accettato produce la previsione a +60 s e la sua
covarianza estesa prima della valutazione sintetica esclusa. Tutti i sedici
hash delle previsioni sono stati verificati. La covarianza mantiene le
correlazioni con clock, coordinate e rumore del holdout; il suo blocco dei
dati di fit deve coincidere esattamente con quello già usato dall'estimatore.

Nel nominale senza rumore estratto, il raggio locale gaussiano di posizione
a +60 s è **2183,608 m** sotto le nuove ipotesi di errore. Nei sedici casi
rumorosi l'errore futuro mediano è 747,595 m; tutte le posizioni future
rientrano nei rispettivi raggi locali. 16/16 non dimostra copertura al 95%,
né copertura dopo selezione per il superamento del test. La previsione
centrale non viene corretta usando misure o residui esclusi.

| Stress | Fit congiunto | Ablazione a blocchi |
|---|---|---|
| Salto di codice di 300 m su una stazione da metà arco | `MODEL_REJECTED`, p = 5,78642×10⁻⁴⁷ | `MODEL_REJECTED`, p = 9,54522×10⁻³⁴ |
| Forte jerk S2a [−5, 10, 3]×10⁻⁵ m/s³ | `MODEL_REJECTED`, p = 4,01747×10⁻²⁷ | `MODEL_REJECTED`, p = 7,70950×10⁻²⁷ |

Gli stress non producono previsioni escluse accettate. Il nuovo trattamento
non fa passare questi errori del modello aumentando le varianze.

## Verifiche e limiti aperti

**20 test nuovi e 172 test locali complessivi passano.** I nuovi controlli
coprono limite S2a con coordinate precise, momenti e covarianza locali,
risposta a perturbazioni confrontata con refit completi, correlazioni del
holdout, rifiuto di covarianze invalide o mutate, blocco delle misure target
dopo una calibrazione respinta, rifiuto degli stress e assenza di riscalamento
della covarianza dai residui. Le regressioni includono posizionamento,
esperimento G08, service, ricerca e archivio.

I sorgenti legati ai report S1, S2a corrente, S2b e al precedente bilancio
locale conservano i rispettivi hash. Gli estimatori storici non sono stati
modificati e i cinque eventi reali restano chiusi.

Le calibrazioni di questo studio sono dati gaussiani compressi assunti
ammessi; non sono una nuova qualifica del ponte RINEX o dei ricevitori.
Le correlazioni sono ipotesi sintetiche fissate, non stime empiriche di
errori fisici. Restano da qualificare la covarianza reale dalle fonti
non-target, i ricevitori/tempi e la propagazione; poi la calibrazione del
test non lineare con selezione e un inviluppo sistematico e di troncamento
completo. S2 resta aperto e non autorizza ancora una campagna S3.
