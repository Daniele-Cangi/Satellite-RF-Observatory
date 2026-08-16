# Gate B — Checkpoint 3

Stato: **STOP dopo un failover SatNOGS e il primo confronto dual-Kiwi
assimilabile**. Nessuna nuova sorgente, TDoA, frontend, persistenza, database o
framework generico è stato aggiunto.

Il Checkpoint 2 corretto è conservato nel commit locale `b2a9dd8`; non è stato
eseguito alcun push o aperta alcuna PR.

## Semantica del contratto

Non esiste più uno stato globale `OBSERVABLE/DEGRADED`. Ogni
`DecisionContract` contiene clausole nominate e ogni `BeliefSnapshot` conserva
un esito separato per clausola: `SATISFIED`, `UNSATISFIED`, `UNRESOLVED` o
`UNOBSERVABLE`.

`measurement_age_s=77.638` significa 77.638 secondi. Nei JSON Lines il valore
rimane un numero con punto decimale. L'emettitore rifiuta NaN/Infinity e
normalizza gli scalari NumPy in primitive JSON. La factory runtime dello
snapshot impedisce a un receipt oltre il TTL calcolato da `event_end` di
soddisfare una clausola; un arrival recente non rinnova l'evidenza.

## Probe A — failover SatNOGS a clausole

Le waterfall non sono più fuse in una receipt a due root. Ogni artifact è una
evidence atomica con una sola measurement root. I due contratti sono distinti:

- `measurement_continuity`: almeno una root fresca con struttura RF ed event
  time;
- `measurement_corroboration`: almeno due root di stazione distinte,
  control-compatible e con finestra sovrapposta.

Entrambi hanno TTL 600 s. Il target del job rimane solo control context.

### Failover reale del 2026-08-15

| Offer | Measurement root | Event end UTC | Age iniziale | Struttura | Byte |
|---|---|---|---:|---:|---:|
| `satnogs:14784413` | `station:4829` | 23:37:06 | 98.890902 s | 0.071909 | 1,663,630 |
| `satnogs:14784268` | `station:34` | 23:36:02 | 162.890902 s | 0.042481 | 1,677,759 |

Il runtime ha scelto inizialmente `station:4829`, la root più fresca. Prima
della revoca:

- continuità: `SATISFIED` con `station:4829`;
- corroborazione: `SATISFIED` con `station:4829` e `station:34`.

La revoca di `satnogs:14784413` ha rimosso realmente `station:4829` dal grafo:

- continuità: `UNOBSERVABLE`;
- corroborazione: `UNOBSERVABLE`, perché rimane una sola root.

Il ranking non contiene ID di fallback. Ha rigettato l'offer revocata e scelto
`satnogs:14784268` perché aggiungeva una nuova root, ripristinava
`measurement_continuity`, aveva 437.109098 s di TTL residuo e dichiarava i
deficit dei transform (`unknown=0`, `partial=2`, `model_conditioned=1`,
`lossy=1`) e il valore/costo. La continuità è tornata `SATISFIED` su
`station:34`; la corroborazione non è stata falsamente ripristinata.

La sostituzione è causalmente reale — cambia la measurement root attiva — ma è
un hot failover su un artifact già acquisito per valutare la corroborazione;
non finge una nuova misura di rete dopo la revoca.

Avanzando il tempo logico a 23:47:07 UTC, oltre entrambi gli `event_end+TTL`,
continuità e corroborazione diventano ciascuna `UNOBSERVABLE` con zero root.
Gli stessi TLE sono stati propagati dal kernel puro; il contesto è emesso
separatamente come `MODEL_AVAILABLE` e non soddisfa alcuna clausola di misura.

## Probe B — scout targetless e confronto calibrato

Il piano è stato congelato prima dei campioni:

- center scout: 5, 10 e 15 MHz;
- 2.5 s per center, poi una sola capture calibrata di 8 s sul winner;
- 99 time shift e 99 frequency shift;
- `alpha=0.01`;
- STFT, forme delle regioni, regole GNSS/arrival e salience incluse nell'hash
  `d69c40dfdd761221b6b93ff65c4012d839d763f354cb110bd8a944a5880ea7d2`.

Lo scout simultaneo ha restituito:

| Center | Joint salience |
|---:|---:|
| 5 MHz | 2.500652 |
| 10 MHz | 0.739011 |
| 15 MHz | 0.872034 |

È stato quindi scelto 5 MHz senza identità o target assegnato.

Una prima esecuzione con lo stesso plan hash aveva completato i calcoli ma non
ha prodotto un receipt: un `numpy.bool_` non era serializzabile dal JSONL. I
campioni non sono stati conservati e nessun esito è stato promosso. Dopo la
sola correzione dello strato di serializzazione, senza cambiare piano, soglie o
algoritmo, è stato eseguito un retry strumentale; quello seguente è il primo
confronto assimilabile.

### Audit temporale e continuità

| Proprietà | Hooksiel | Doncaster |
|---|---:|---:|
| event window UTC | 23:48:41.515106–23:48:49.750463 | 23:48:41.174207–23:48:49.708322 |
| campioni / blocchi | 98,816 / 193 | 102,400 / 200 |
| sequence gap / timestamp gap / dropped | 0 / 0 / 0 | 0 / 0 / 0 |
| GPS solution age massimo | 2 s | 2 s |
| ADC overflow | 0 | 0 |
| effective sample rate | 11,999.062573 Hz | 11,998.781374 Hz |
| sample-rate drift | +5.688663 ppm | -9.991851 ppm |
| cumulative timing drift | 0.000046848 s | 0.000085272 s |
| arrival latency median / p95 | 0.090175 / 0.176144 s | 0.105500 / 0.280166 s |

L'intersezione continua GNSS è 8.193216 s. Nessun gap è stato interpolato,
nessun time lag è stato ottimizzato e non è stata applicata alcuna correzione
TDoA o di propagazione.

### Regione e null model in-session

La regione targetless selezionata è:

- tempo: 23:48:47.035569–23:48:47.120910 UTC;
- frequenza: 4,995,887.109997–4,996,051.158748 Hz;
- 7 bin × 8 frame;
- joint score: 2.520066.

L'intera ricerca della regione è stata ripetuta per ogni shift del null:

- time-shift: `p=0.01`, 99 null;
- frequency-shift: `p=0.01`, 99 null;
- self-consistency even/odd: frequency IoU 1.0;
- offset relativo: -5.552 Hz;
- drift relativo nella regione: -120.569754 Hz/s;
- allineabile alla risoluzione del test: sì.

`p=0.01` è il minimo risolvibile con 99 null e uguaglia, non supera in senso
stretto, la soglia congelata. Il risultato significa che lo score osservato è
maggiore di tutti gli shift costruiti nella sessione; non è una probabilità
universale né una correzione per ogni possibile banda o modello di
propagazione.

Le clausole, dopo l'audit epistemico, sono:

- `measurement_availability = SATISFIED`;
- `shared_structure_beyond_null = SATISFIED`;
- `common_physical_cause = UNRESOLVED`.

Il terzo esito è intenzionale. Rifiutare questi null rende la similarità
distinguibile nel piano congelato, ma non identifica una causa. Multipath HF,
fading selettivo, polarizzazione, ritardo, Doppler, interferenza comune,
emettitori diversi e geometria ignota restano spiegazioni non risolte.

## Risposte alle quattro domande

1. **Una sorgente viene realmente sostituita perché ripristina una clausola
   persa?** Sì. Revocare `station:4829` rende la continuità `UNOBSERVABLE`; il
   ranking sceglie `station:34` e solo `measurement_continuity` torna
   `SATISFIED`. La corroborazione resta correttamente persa.
2. **Il runtime distingue disponibilità delle misure da supporto di
   un'ipotesi?** Sì. Nel ramo Kiwi la misura, il superamento del null e la causa
   comune sono tre clausole diverse. Nel ramo SatNOGS la misura scaduta non può
   essere sostituita da `MODEL_AVAILABLE`.
3. **La similarità dual-Kiwi supera un null model della stessa sessione?** Sì,
   al limite della risoluzione predefinita: `p_time=p_frequency=0.01` con 99
   shift per famiglia, self-consistency stabile e stream allineabili. Questo
   non risolve la causalità.
4. **Quale astrazione sopravvive in entrambi i rami?** Una valutazione per
   clausole sostenuta da receipt atomici, event time/TTL, transform ledger e
   lineage causale. Target, orbita, lease/failover e scout/null sono strumenti
   di ramo; non appartengono al nucleo condiviso.

Checkpoint 3 termina qui. Nessuna seconda regione, nuova soglia, nuova sorgente
o analisi TDoA viene avviata.
