# Gate F2.5 — direct dual-SND causal path

Stato: **offline, nessuna osservazione eseguita**. Gate F2.4 e il suo outcome
restano immutati. Questo passaggio corregge il prossimo disegno sperimentale;
non reinterpretata retroattivamente la sessione già congelata.

## Confine causale minimo

La qualification futura segue questo ordine immutabile:

1. affordance e ordine dei sei candidati già congelati;
2. lettura descrittiva di `/status` e scelta del centro mediante una funzione
   deterministica dell'endpoint nell'interno della banda dichiarata;
3. tentativo diretto e concorrente di `SND reference` e `SND perturbed`;
4. due stream IQ simultanei con channel ID distinti, event time GNSS,
   continuità, sample rate compatibile e assenza di overflow;
5. STFT/PSD locale, soltanto in RAM, sui due artifact IQ già acquisiti;
6. selezione targetless di target, witness e delta senza usare
   l'orientamento dell'asse che il retune deve ancora rivelare;
7. qualification separata del retune A/B/A sul solo witness selezionato;
8. cancellazione del command ledger di qualification e plan freeze;
9. una sola confirmation A1/B/A2 sugli stessi due canali;
10. un outcome e stop, senza retry post-freeze.

Nessuna funzione W/F è chiamata da questo vertical probe. Una waterfall
potrebbe in futuro essere un diagnostico opzionale fuori dal causal path, ma
non può ammettere, respingere o bloccare la capability multicanale. La
waterfall analitica necessaria alla feature discovery è la PSD/STFT temporanea
costruita localmente dagli IQ e viene distrutta con essi.

## Audit di `ext_api`

`ext_api` è un campo dello status e descrive un'affordance dichiarata dal
server. I Gate precedenti avevano già stabilito che `ext_api >= 2` non
sostituisce l'apertura di due connessioni. Gate F2.4 ha mostrato anche il
problema inverso: usare il campo come gate colloca una descrizione non
verificata davanti alla prova fisica desiderata.

Gate F2.5 conserva perciò:

- presenza, valore parsato e hash del valore grezzo;
- `used_as_gate = false` in ogni receipt;
- nessuna inferenza da valori mancanti, nulli, negativi o malformati;
- verità operativa soltanto dal tentativo diretto di entrambe le allocazioni
  SND e dai loro campioni.

Un rifiuto esplicito del server (`busy`, public access rejected o equivalente)
dopo l'avvio di entrambe le allocazioni può rendere la coppia non disponibile
nella sessione. Timeout, decode, trasporto o descrizione restano invece
`QUALIFICATION_ERROR`: non diventano un rifiuto epistemico.

## Tre fasi che non possono collassare

| Fase | Domanda | Evidenza ammessa | Non autorizza |
|---|---|---|---|
| Direct dual-SND | Esistono ora due branch SND/IQ simultanei? | due tentativi, due allocazioni, IQ/event time/sequence | feature, retune o ipotesi DDC |
| Local IQ discovery | Gli IQ contengono target e witness distinti entro un envelope rilevabile? | hash IQ e STFT/PSD effimera locale | efficacia o isolamento del retune |
| Retune qualification | Il comando agisce sul solo branch perturbato e il witness trasla e ritorna? | command ledger P, ledger R vuoto, witness R stabile e P A/B/A | risultato sul target prospettico |

Il target non viene valutato durante la qualification del retune. Questa fase
usa soltanto il witness; altrimenti la futura prediction potrebbe essere
adattata al comportamento già visto del target.

## Semantica terminale pre-freeze

- `NO_MULTI_CHANNEL_CAPABILITY` è ammesso soltanto se, per ogni candidato
  eleggibile considerato nel risultato, entrambi i tentativi SND sono stati
  realmente avviati e nessuna coppia simultanea è stata ammessa.
- `QUALIFICATION_INCOMPLETE` copre timeout, trasporto, decode, description o
  transform error che lasciano irrisolta la capability. Un retry autorizzato
  sostituisce semanticamente il tentativo precedente dello stesso endpoint;
  il risultato usa l'ultimo receipt.
- `NO_ADMISSIBLE_CAUSAL_TOPOLOGY` richiede che due stream siano stati aperti,
  ma falliscano simultaneità, distinzione dei branch, integrità temporale o
  isolamento del retune.
- `NO_FALSIFIABLE_INTERVENTION` richiede una topologia dual-SND ammessa, ma
  nessun target/witness/delta rilevabile e congelabile.
- ogni fase downstream bloccata è materializzata come `NOT_EVALUATED`, non
  semplicemente omessa.

Dopo il freeze restano gli outcome di confine DDC già congelati:
`UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`,
`DOWNSTREAM_CHANNEL_FIXED_SUPPORTED`, `AMBIGUOUS`,
`INTERVENTION_INVALID` e `NOT_DETECTABLE`.

## Persistenza e receipt

Ogni body IQ viene hashato SHA-256 prima dell'analisi e della distruzione.
Attraversano il confine JSON soltanto hash, byte count, channel role/ID,
event-time range, sequence range, tuning dichiarato, gap/overflow e transform
ledger. Array IQ, frame STFT, PSD e waterfall locale non sono serializzabili
come receipt e hanno persistenza zero.

## Verifica offline

I test provano che:

- `ext_api = 0` non impedisce la chiamata diretta dual-SND;
- un timeout non diventa `NO_MULTI_CHANNEL_CAPABILITY`;
- il label `NO_MULTI_CHANNEL_CAPABILITY` richiede entrambi i tentativi;
- una coppia aperta ma temporalmente invalida è un fallimento topologico;
- il modulo non chiama `_capture_waterfall` né `_automatic_center`;
- discovery locale e plan freeze riusano esattamente gli hash dei due IQ;
- una selezione che cambia con l'orientamento non ancora rivelato è rifiutata;
- la qualification del retune dichiara `target_evaluated = false` e pulisce i
  comandi pre-freeze;
- tutte le fasi bloccate sono `NOT_EVALUATED`;
- nessun array RF può oltrepassare il boundary JSON.

## Claim massimo

Anche dopo un futuro outcome positivo, il claim massimo resta una posizione
della feature rispetto al boundary del DDC per-canale **dentro quel singolo
Kiwi**. La condivisione di antenna, front-end, ADC e clock rimane intenzionale:
riduce drift e differenze di propagazione, ma lascia aperte saturazione,
intermodulazione, spur e difetti common-mode upstream del channel split.

Gate F2.5 si ferma prima della rete. `run_once()` materializza la futura
sequenza, ma non viene invocato né testato contro endpoint live in questo Gate.
