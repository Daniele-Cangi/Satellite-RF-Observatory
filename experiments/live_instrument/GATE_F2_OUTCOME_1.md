# Gate F2 — primo outcome sotto intervento controllato

Stato: **STOP dopo la singola esecuzione autorizzata**. Il runtime era già
congelato nel commit locale `b6e3525`. Non è stata aperta una seconda
esecuzione e non verrà costruito Gate G da questo outcome.

## Outcome

`NO_CAPABILITY_ADMITTED`

Alle `2026-08-16T13:37:09.218289Z` la discovery effimera della directory Kiwi
non ha completato il primo confine di ammissione. La prima connessione ha
prodotto `URLError` con `WinError 10061`; il solo retry pre-freeze autorizzato
per la chiave `directory` ha incontrato lo stesso errore. Il processo si è
fermato con exit code 0 dopo aver emesso il receipt finale.

Questo è un outcome di ammissione, non un risultato RF negativo. Non sono
stati scelti endpoint, frequenza, target o witness; nessuna CapabilityOffer è
stata qualificata o ammessa e nessuna sequenza `A→B→A` è stata acquisita.

## Deciso prima dell'esecuzione

- Metodo madre, ordine di ammissione, budget e retry policy.
- TTL della CapabilityOffer: 600 s.
- Massimo due retry pre-freeze complessivi e al massimo uno per candidato.
- Zero retry, cambio endpoint, cambio frequenza o modifica delle soglie dopo
  un eventuale plan freeze.
- Una sola confirmation indipendente e arresto al primo outcome.
- Le tre ipotesi congelate: frame RF, frame baseband e altro/non risolto.
- Il punto causale dell'intervento: NCO/DDC per canale nel FPGA, dopo ADC e
  prima di FIR, AGC e stream IQ.

Nessun piano specifico è stato congelato: `plan_hash` è `null`.

## Osservato

- L'audit del protocollo e il piano madre sono stati serializzati prima della
  discovery.
- La directory pubblica configurata era
  `https://kiwisdr.com/.public/`.
- Il primo tentativo ha fallito per rifiuto della connessione.
- Il runtime ha consumato l'unico retry consentito per quella chiave.
- Anche il secondo tentativo ha fallito prima che potesse esistere una
  descrizione di capability.

Non esistono artifact RF di questa esecuzione. Il receipt contiene quindi
correttamente `artifact_hashes: []`, `segment_receipts: []`,
`intervention_receipts: []` e nessuna measurement root. Non vi erano dati RF
da conservare o distruggere.

## Clausole

Tutte le 17 clausole prospettiche sono `NOT_EVALUATED`, tra cui indipendenza
hardware, validità dell'event time, continuità delle due root, orientamento
dell'asse, completezza del transform ledger, detectability di target e
witness, applicazione dell'intervento e i tre confronti `A1/B/A2`.

La semantica è intenzionale: nessuna clausola è falsa o `NOT_DETECTED`, perché
nessuna capability è entrata nell'esperimento. Non esiste una misura dalla
quale derivare `NOT_DETECTABLE`.

## Derivato dal transform ledger

Nessuna classificazione fisica è stata derivata. Il ledger si arresta alla
trasformazione descrittiva `qualification: stopped`; conserva soltanto come
model root la revisione auditata del server Kiwi
`c40ecb471dced33689e335689f8ffd35a54f47fa`.

In particolare, l'assenza di acknowledgement del comando di tuning resta una
limitazione nota del piano, ma non ha influito su questo outcome: nessun
intervento è stato inviato.

## Affermazioni autorizzate

- La discovery non ha prodotto capability descrivibili entro il retry budget
  congelato di questa singola sessione.
- Nessuna capability è stata ammessa e nessun esperimento falsificabile è
  entrato in confirmation.
- Il runtime ha distinto il fallimento di discovery da un'assenza fisica.
- `H_OTHER_OR_UNRESOLVED` resta l'unica etichetta possibile, nel senso preciso
  che le ipotesi di frame non sono state valutate.

## Affermazioni non autorizzate

- Non esisteva alcun Kiwi pubblico operativo.
- Una feature RF era presente o assente.
- Le ipotesi RF-frame o baseband-frame sono supportate o danneggiate.
- Due ricevitori osservavano lo stesso fenomeno o lo stesso emettitore.
- Il fallimento dipendeva dalla propagazione, dal sensore o dalle soglie.
- Un secondo tentativo in un altro momento avrebbe avuto lo stesso outcome.

## Astrazioni e SHOCK

Sopravvivono il receipt atomico, il confine descrittivo rigoroso e la capacità
di terminare senza fabbricare evidenza. Event time, causal lineage e transform
ledger restano necessari come clausole progettate, ma non sono stati esercitati
da misure reali in questa esecuzione.

Il planner centrale rimane eliminabile: non ha selezionato un esperimento e il
risultato corretto è stato prodotto dal confine di ammissione. Lo SHOCK è che
la terminazione senza esperimento è un risultato epistemico utile solo se non
viene rinominata come osservazione negativa.

Gate F2 si ferma qui. Non viene effettuata una seconda discovery, non viene
aperta una nuova finestra e non viene progettato Gate G.
