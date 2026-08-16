# Gate F2.3 — topologia causale del retune per-canale

Stato: **audit esclusivamente offline**. `NO_CAPABILITY_QUALIFIED` di Gate
F2.2 resta congelato: non è stato reinterpretato, non sono stati aperti
endpoint, directory, socket SND o nuove finestre RF, e non è stato acquisito
alcun campione.

La domanda è più stretta del contratto usato in F2.2: non chiede se due siti
indipendenti osservino lo stesso fenomeno, ma se la coordinata di una feature
sia invariante rispetto a un intervento NCO/DDC su un singolo canale. Il tipo
di root necessario deve quindi essere derivato da quel confine causale.

## 1. Audit delle tre topologie

| Configurazione | Causal cut | Cosa elimina | Cosa lascia aperto | Claim massimo | Indipendenza necessaria |
|---|---|---|---|---|---|
| A. due Kiwi fisicamente indipendenti | il DDC di un ricevitore viene perturbato mentre un secondo apparato resta fisso | una feature comune non può nascere soltanto a valle del canale del primo ricevitore; il secondo ramo segnala grandi cambiamenti temporali | propagazione HF, antenne, front-end e clock differenti; interferenza locale; identità della sorgente | upstream del DDC perturbato **e** osservata su un apparato indipendente; nessuna identità o localizzazione dell'emettitore | hardware + allineamento temporale |
| B. una Kiwi, due canali simultanei | fan-out dopo antenna/front-end/ADC/clock: un DDC fisso e un DDC retuned | differenze di propagazione e front-end; drift fra clock; fading temporale come unica spiegazione di A/B | spur/overload/intermodulazione upstream condivisi; coupling fra canali; errore di routing; software comune | upstream oppure channel-fixed downstream rispetto al DDC per-canale di quella Kiwi; non “RF esterna” | due rami di canale simultanei e controllabili, con receipt distinti |
| C. una Kiwi, un canale A1→B→A2 | lo stesso DDC cambia nel tempo; intervento e tempo restano confusi | A2 può mostrare reversibilità e recupero | fading, transienti, AGC, drift, perdita pacchetti e hysteresis durante B | risposta reversibile compatibile con il retune; nessuna localizzazione univoca rispetto al DDC | soltanto continuità e reversibilità temporale |

### A — witness e metadata

Servono continuità GNSS su entrambi gli stream, ledger del comando e witness
del retune sul ramo perturbato, stabilità sul ramo remoto, e lineage separato
di antenna/front-end/ADC. Le coordinate geografiche non sono necessarie per il
taglio DDC; diventano necessarie solo se si vuole affermare separazione di sito
o ragionare sul percorso di propagazione. L'identità indipendente dell'hardware
deve comunque essere provata in altro modo.

### B — witness e metadata

Servono due connection/channel role, due sequence range e receipt atomici,
event time GNSS, sample rate e overflow, ledger dei comandi per connessione,
centri richiesti, versione delle trasformazioni e hash degli artifact. Il ramo
reference non riceve comandi di frequenza dopo il tuning iniziale; deve restare
continuo e mantenere stabile target o witness attraverso A1/B/A2. Il ramo
perturbato deve mostrare, dopo il boundary del comando, un witness che segue la
previsione firmata e ritorna in A2. La geografia non ha alcun ruolo.

### C — witness e metadata

Servono command time, prime sample time post-comando, esclusione del settling,
continuità di sequenza/event time, overflow, centri e ritorno A2. Un witness
same-path deve restare rilevabile in tutti e tre i segmenti. Questi controlli
possono validare l'esecuzione ma non creano il ramo contemporaneo mancante.

## 2. Requisito di root derivato dall'ipotesi

`independent_hardware_roots` non è più una precondizione universale. Per questo
solo esperimento il requisito è `RootTopologyRequirement`:

```text
intervention_boundary:
    FPGA per-channel RX NCO/DDC
shared_upstream_components:
    antenna, analogue front-end, ADC, ADC clock, GNSS timebase
independent_downstream_branches:
    reference_rx_channel, perturbed_rx_channel
fixed_reference_branch:
    reference_rx_channel
perturbed_branch:
    perturbed_rx_channel
claim_scope:
    upstream vs channel-fixed downstream del DDC; non origine esterna
simultaneous_required: true
independent_stream_receipts_required: true
geographic_location_required: false
hardware_independence_required: false
channel_independence_required: true
```

Non è un framework o una nuova ontologia delle sorgenti. È una descrizione
locale della topologia che rende informativo questo intervento.

## 3. Supporto multicanale verificato dal codice già congelato

L'audit usa soltanto evidenza già presente nella repository e i commit source
già congelati; non ha interrogato né scaricato nulla:

- Kiwi server `c40ecb471dced33689e335689f8ffd35a54f47fa`;
- kiwiclient `4eb733e6b6147f7fbeb97ced64cdac029b202d18`;
- `rx/rx_sound_cmd.cpp:67-79` e `151-175`;
- `rx/rx_sound.cpp:568-596` e `1082-1136`;
- decoder locale `_decode_iq_block()` e implementazione concorrente congelata
  `_capture_sequence_root()` / `capture_dual_sequence()`.

### Cosa è dimostrato

Una connessione SND è associata al canale RX selezionato. Il comando
`SET mod=iq ... freq=<kHz>` arriva a `rx_sound_set_freq()` e invia una phase
word a 48 bit, via `CmdSetRXFreq`, a quel canale FPGA. Il retune è quindi
per-canale e non cambia un LO hardware globale.

Due canali non viaggiano dentro lo stesso WebSocket: il vertical probe deve
mantenere due connessioni SND. Un singolo processo può farlo in concorrenza;
l'implementazione F2 congelata usa già due worker e due socket, anche se li
usava con endpoint differenti. Questo dimostra la forma del client, non la
disponibilità attuale di due slot sul medesimo endpoint.

Ogni payload SND rende osservabile un campo sequence e header temporali GNSS.
I receipt possono perciò essere distinti come `(connection/channel role,
sequence range, event-time range)`. Non segue che i counter o i clock siano
hardware indipendenti: il tempo GNSS e il sample clock hanno intenzionalmente
una root comune.

### Cosa non è dimostrato offline

`/status` e `ext_api` dovranno dimostrare nella futura qualification che vi
siano almeno due slot pubblici liberi. Password, limiti utente, preemption,
time limit, configurazione dei canali e busy state possono impedire la seconda
connessione. Una descrizione con `ext_api >= 2` non sostituisce l'apertura
riuscita di entrambi gli stream.

Il protocollo non restituisce un tune ACK. Per dimostrare che il reference non
è stato perturbato occorrono congiuntamente:

1. un connection/channel role congelato per il reference;
2. assenza di comandi di frequenza nel suo ledger;
3. sequence ed event-time continui;
4. stabilità della feature o di un witness nel reference durante A1/B/A2;
5. un effetto di retune osservabile soltanto nel ramo perturbato.

Il solo centro richiesto o riportato non dimostra che nuovi campioni siano
entrati dopo il comando.

## 4. Ipotesi e conseguenze congelabili

### `H_UPSTREAM_OF_CHANNEL_DDC`

- la coordinata absolute-RF della feature resta invariata;
- nel baseband del canale perturbato la feature si muove del delta firmato
  congelato;
- nel canale fisso la feature resta stabile.

“Upstream del DDC per-canale” include antenna, front-end, ADC, clock e FPGA a
monte del fan-out. Non è sinonimo di segnale RF esterno.

### `H_DOWNSTREAM_CHANNEL_FIXED`

- la feature resta nella stessa posizione baseband del canale perturbato;
- la coordinata RF ricostruita cambia con il tuning;
- nel canale fisso rimane stabile la feature, se condivisa, oppure rimane
  stabile il witness ortogonale same-path.

### `H_UNRESOLVED`

Nessuna delle due previsioni di coordinata è supportata in modo univoco. Il
reference può validare l'intervento senza rendere risolvibile il target.

## 5. Vertical probe minimo futuro

Una sola Kiwi candidata deve superare, nell'ordine:

1. `endpoint_status_available`;
2. `multi_channel_slots_available` (almeno due slot simultanei);
3. `reference_stream_valid`;
4. `perturbed_stream_valid`;
5. `per_channel_retune_testimoniable`;
6. `admissible_causal_topology`;
7. target e witness contenuti nei passband richiesti per A e B.

La qualification deve mantenere distinti:

- `NO_MULTI_CHANNEL_CAPABILITY`: descrizione/slot o i due stream IQ non sono
  disponibili;
- `NO_ADMISSIBLE_CAUSAL_TOPOLOGY`: gli stream esistono, ma non si possono
  provare rami distinti, reference fisso o retune per-canale;
- `NO_FALSIFIABLE_INTERVENTION`: la topologia è valida, ma target e witness non
  permettono due previsioni distinguibili nel passband.

Solo dopo questi passaggi si congelano endpoint, due connection role, centro
A, delta firmato, orientamento, passband, feature, witness, durate, settling,
trasformazioni, tolleranze e outcome. La confirmation usa due stream IQ
simultanei: reference sempre fisso; perturbed A1/B/A2. Ogni artifact effimero è
hashato per stream e fase prima dell'analisi e della distruzione. Persistono
solo hash e receipt; RF, waterfall e campioni restano a persistenza zero.

Dopo il plan freeze: zero retry, zero nuova finestra, zero endpoint o frequenza
sostitutivi, zero modifica di prediction, trasformazioni o soglie. La stop
condition è il primo outcome terminale o un solo outcome di confirmation.

## 6. Outcome futuri

- `NO_MULTI_CHANNEL_CAPABILITY`
- `NO_ADMISSIBLE_CAUSAL_TOPOLOGY`
- `NO_FALSIFIABLE_INTERVENTION`
- `UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`
- `DOWNSTREAM_CHANNEL_FIXED_SUPPORTED`
- `AMBIGUOUS`
- `INTERVENTION_INVALID`
- `NOT_DETECTABLE`

`INTERVENTION_INVALID` precede ogni decisione fisica: command ledger non
pulito, reference perturbato, retune non instradato o witness del retune
assente. `NOT_DETECTABLE` indica invece un intervento valido ma receipt senza
continuità, allineamento, trasformazione/ADC puliti, detectability in A1/B/A2 o
ritorno A2. Un match unico autorizza uno dei due outcome `SUPPORTED`; due match
compatibili o nessun match producono `AMBIGUOUS`.

Nessuno di questi outcome autorizza identità del fenomeno, emitter location,
TDoA o origine RF esterna.

## 7. SHOCK

Il secondo hardware root non era richiesto dall'ipotesi di invarianza al DDC.
Anzi, introduceva front-end, clock e propagazioni differenti e ha impedito di
qualificare una topologia più pulita: stesso ADC e stesso istante, ma due rami
DDC controllati separatamente.

La conseguenza inattesa è doppia. La condivisione di ADC e clock rende il
confronto relativo eccezionalmente più netto: niente clock drift inter-ricevitore
e niente differenza di fading fra siti. Ma lo stesso vantaggio crea il limite
epistemico: uno spur coerente del clock, un artifact ADC, overload o
intermodulazione analogica è comune ai due canali e può seguire esattamente la
previsione “upstream del DDC”. Il probe può localizzare il lato del boundary,
non decidere se ciò che ha localizzato provenga dall'etere.

Gate F2.3 si ferma prima della rete. Non esiste ancora una capability
multicanale qualificata, un piano live congelato o un outcome RF.
