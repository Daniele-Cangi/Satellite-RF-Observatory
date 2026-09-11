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

## Esecuzione v2 su DOY253

Il receipt boundary corretto ha conservato identità complete per ALGO, BOGT e
DRAO. ALGO e BOGT hanno 2.880 epoche continue e identità ricevitore immutate.
La differenza fra `Geodetic` e il letterale maiuscolo imposto dal primo parser
conferma che il primo stop era descrittivo.

DRAO si è invece fermato su `WAVELENGTH FACT L1/2`. La specifica RINEX 2.11
definisce questo campo come trasformazione della lunghezza d'onda della fase,
con possibile override nel LLI. Poiché non appartiene al sottoinsieme RINEX 3
congelato e non era implementato nel transform ledger, accettarlo come metadata
avrebbe potuto alterare la coordinata fisica usata dal qualificatore.

| Clausa v2 | Stato |
| --- | --- |
| Receipt prima dell'ammissione | `PASSED` |
| ALGO: identità, giorno completo, continuità | `PASSED` |
| BOGT: identità, giorno completo, continuità | `PASSED` |
| DRAO: trasformazione fase interamente nota | `REJECTED` |
| Restanti cinque root | `NOT_EVALUATED` |
| Navigazione e selezione finestra | `NOT_EVALUATED` |
| Residui code/phase | `NOT_EVALUATED` |
| Envelope fisico completo | `NOT_SUPPORTED` |

Terminale congelato:

```text
PHYSICAL_ERROR_ENVELOPE_NOT_SUPPORTED
```

Il claim è limitato al set completo di otto root e al parser/ledger v2. Nessun
valore osservativo, residuo target, fit cinematico o orbit product target è
stato usato. Tutti i payload sono rimasti effimeri.
