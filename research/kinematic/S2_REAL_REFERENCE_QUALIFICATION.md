# S2 — Primo tentativo di qualifica fisica reference-only

Il piano `real_reference_qualification_plan.json` ha congelato una sola giornata,
otto stazioni, l'esclusione di G14 prima della conversione numerica e una regola
di selezione basata esclusivamente su struttura e geometria dei satelliti di
riferimento. Il codice e il piano sono stati committati in `0af9ab6` prima del
primo accesso.

## Esito procedurale

L'esecuzione DOY252 si è fermata sul primo file, ALGO, prima di interpretare
qualunque misura. Il JSON prodotto contiene il terminale
`PHYSICAL_ERROR_ENVELOPE_NOT_SUPPORTED`, ma questo terminale **non è autorizzato
come conclusione fisica**. L'esito scientificamente valido dell'audit è:

```text
QUALIFICATION_EXECUTION_INVALID
```

Il parser riusato imponeva `MARKER TYPE == GEODETIC`. Questa condizione non era
nel piano congelato e non era necessaria a distinguere le clausole fisiche
dichiarate. Inoltre, il receipt completo della sorgente veniva aggiunto al
risultato soltanto dopo l'ammissione strutturale. L'eccezione ha quindi impedito
di conservare byte count e SHA-256 già calcolati in RAM.

Un errore descrittivo non può diventare un rifiuto epistemico. Non sappiamo se
il percorso di fase ALGO avrebbe superato o meno i limiti: nessun residuo di
codice o fase è stato calcolato, le altre sette stazioni e la navigazione non
sono state aperte.

## Confine di accesso

- Scaricato e decompresso in RAM soltanto il prodotto ALGO dichiarato.
- Nessun numero osservativo convertito.
- Nessun campo G14 ispezionato.
- Zero byte di payload persistiti.
- Nessun retry o secondo download: l'hash perduto non viene ricostruito
  riaprendo l'artifact.

Il [risultato grezzo](results/real_reference_qualification_study_v1.json) resta
immutato e il suo SHA-256 è
`9066fd05f474e1cbd2df0251c15b8330a6345c3e5de2fe29d5ad9313d44cff2a`.
L'[audit tipizzato](results/real_reference_qualification_execution_audit_v1.json)
separa l'errore di esecuzione da una decisione fisica.

## Riparazione consentita e passo successivo

Senza riaprire DOY252, il runner successivo deve:

1. conservare il receipt subito dopo la materializzazione e prima di ogni
   descrizione o ammissione;
2. trattare `MARKER TYPE` come metadata riportato, non come gate nascosto;
3. distinguere sempre `QUALIFICATION_EXECUTION_INVALID` da un envelope fisico
   non supportato;
4. congelare una data distinta prima di un nuovo accesso.

Non è stata prodotta alcuna nuova informazione sulla capacità fisica del
segnale C1C/C2W/L1C/L2W. S3, target e sito restano sospesi.
