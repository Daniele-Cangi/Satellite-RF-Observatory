# Gate B — primo outcome prospettico Kiwi

Stato: **STOP dopo la prima finestra di confirmation**. Checkpoint 3 è
congelato nel commit locale `90d345b`. Nessun push o PR.

## Audit della selezione di banda

Il null max-stat di Checkpoint 3 ripeteva l'intera ricerca della regione
tempo-frequenza dentro la capture finale a 5 MHz. Non ripeteva però la scelta
precedente fra i center 5, 10 e 15 MHz.

Scout e confronto CP3 erano acquisizioni distinte, quindi i p-value finali non
riutilizzavano gli stessi campioni usati per scegliere il center; restavano
comunque inferenze condizionate alla banda selezionata. L'esperimento
prospettico elimina questo grado di libertà: center e intervallo RF sono stati
fissati e hashati prima della nuova finestra.

Limiti conservati:

- il discovery scout conteneva soltanto tre center predefiniti;
- `p=0.01` era la risoluzione minima di 99 shift per famiglia;
- una ricorrenza indipendente non avrebbe identificato un trasmettitore o una
  causa fisica comune.

## Separazione prospettica

### 1. Discovery congelata

- commit: `90d345b`;
- discovery record hash:
  `ec6a9ae6f77b9e5fc2a1d750c335849921fa91fd4e7b76fd8454e0855a12e0b5`;
- center scelto: 5,000,000 Hz;
- banda: 4,995,887.109997–4,996,051.158748 Hz;
- regione CP3: 0.085341 s;
- fine dell'evidence discovery: 2026-08-15T23:48:49.708322Z.

### 2. Model reveal

Il modello è stato rivelato alle 2026-08-16T00:31:54.923086Z con plan hash
`d8cb716633d9f021339dd6349c612f5fb1efa7ca84f99594baafb57ac1fbf362`.

Stato alto: entrambe le stazioni almeno a 2.0 per 3 frame. Stato basso:
entrambe al massimo a 0.5 per 3 frame. Ordine richiesto:
`positive → subsequent_negative`, entro 2 s.

Controlli fissati prima dei campioni:

- bande della stessa larghezza a offset -1,500, -750, +750 e +1,500 Hz;
- stream destro spostato di -192, -128, -64, +64, +128 e +192 frame, senza
  wrap;
- lo score della coppia target deve superare ogni controllo.

### 3. Prediction

Registrata alle 2026-08-16T00:31:54.923171Z:

> Nella successiva finestra indipendente la banda congelata mostrerà almeno
> una transizione low→high simultanea, seguita da high→low, e la coppia
> supererà tutti i controlli wrong-frequency e wrong-time.

### 4. Confirmation indipendente

Finestra comune GNSS:
2026-08-16T00:31:57.824769Z–2026-08-16T00:32:09.849784Z. Inizia dopo discovery,
model reveal e prediction registration. Measurement age all'assimilazione:
0.199132 s.

Outcome:

| Clausola | Esito |
|---|---|
| `measurement_availability` | `SATISFIED` |
| `positive_transition` | `UNSATISFIED` — non osservata |
| `negative_transition` | `UNSATISFIED` — nessun onset da cui ritornare |
| `prospective_confirmation` | `UNSATISFIED` — predizione non confermata |
| `common_physical_cause` | `UNRESOLVED` |

Target pair score: 0.0. Tutte le quattro bande di controllo e tutti i sei
time-shift hanno score 0.0. Questo non è un pareggio utile: senza la coppia di
transizioni richiesta, la regola prospettica fallisce prima del confronto di
superiorità.

Il JSONL live aveva inizialmente etichettato le tre clausole di predizione come
`UNRESOLVED`. L'audit successivo le corregge in `UNSATISFIED`: la finestra era
osservabile e la predizione dichiarava esplicitamente che le transizioni
sarebbero comparse. Solo `common_physical_cause` resta `UNRESOLVED`. Nessun dato
o criterio numerico è stato modificato.

## Interpretazione

Il risultato CP3 non si è ripetuto nella prima finestra futura sotto il modello
rivelato. Questo falsifica la specifica predizione di ricorrenza per questa
finestra, banda, coppia di ricevitori e soglie; non prova che il fenomeno RF non
esista e non modifica retroattivamente il risultato esplorativo CP3.

Nessuna soglia, controllo o banda viene cambiata. Non viene aperta una seconda
finestra. Nessun TDoA, nuova sorgente, database o persistenza è introdotto.
