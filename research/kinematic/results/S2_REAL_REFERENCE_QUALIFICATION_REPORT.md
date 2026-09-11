# S2 — Qualifica fisica reference-only DOY252

## Verdetto

```text
QUALIFICATION_EXECUTION_INVALID
```

Il terminale `PHYSICAL_ERROR_ENVELOPE_NOT_SUPPORTED` scritto dal primo runner
non autorizza un rifiuto della capability. Il controllo che lo ha generato era
una condizione descrittiva non dichiarata nel piano e si è verificato prima di
ogni valutazione dei residui.

| Clausa | Stato |
| --- | --- |
| Piano e implementazione congelati prima dell'accesso | `PASSED` |
| Sorgente ALGO materializzata in RAM | `COMPLETED_BUT_RECEIPT_NOT_RETAINED` |
| Header descritto | `DESCRIPTION_ERROR` |
| Identità/configurazione ricevitore | `NOT_EVALUATED` |
| Copertura temporale completa | `NOT_EVALUATED` |
| Finestra reference-only | `NOT_EVALUATED` |
| Continuità e LLI | `NOT_EVALUATED` |
| Residui di codice | `NOT_EVALUATED` |
| Residui di fase | `NOT_EVALUATED` |
| Envelope fisico | `NOT_EVALUATED` |

Il file ALGO è l'unico artifact contattato. Le altre sette sorgenti e la
navigazione non sono state aperte. Nessun valore osservativo e nessun campo del
target riservato G14 sono stati interpretati; non è persistito alcun payload.

## Causa

Il runner ha riutilizzato `_phase_header`, che richiede il valore letterale
`GEODETIC` per `MARKER TYPE`. Il piano congelato non conteneva questo requisito.
Il receipt era inoltre accodato dopo il controllo, quindi l'errore ha perso
l'evidenza descrittiva di byte count e SHA-256. Ricostruirla richiederebbe un
secondo accesso vietato dal piano.

La capability resta `UNRESOLVED`, non `REJECTED`. Il prossimo tentativo deve
usare un artifact distinto dopo una riparazione offline e un nuovo freeze.
