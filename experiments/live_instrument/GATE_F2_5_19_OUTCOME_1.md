# Gate F2.5.19 — outcome live 1

Stato terminale:

```text
DUAL_SEMANTIC_PAIR_READY
```

L'unica autorità riferita al commit
`dc74bf5b98e463705485a351351b7913b74688bd` e all'authority envelope
`b89c09209e83797b06c9730e001fd85c3a04ae77719412655dd0f9c877bdd80a`
è stata consumata il 18 agosto 2026. Non è stato effettuato alcun retry e non
è autorizzata una seconda esecuzione di questa qualification.

## Artifact congelato

```text
path: experiments/live_instrument/session_receipts/gate-f2-5-19-20260818T102026.214534Z.jsonl
SHA-256: ab2ea016e60ca100d665310f520dbec022c206c3d42f1f92a7b55f5d0b684a47
prefix SHA-256: 4fa1e8aee9882d45cd6986c67e287f5be36ff9af470dae96a07b69cb8a80a15c
bytes: 186920
events: 3 + 1 terminal manifest
retention: COMPLETE
description errors: 0
raw RF persistence: ZERO
physical decision affected by receipt: false
```

Il JSON Lines rigoroso contiene soltanto envelope, stati di clausola, metadati,
contatori e hash pre-analisi. Non contiene IQ, campioni, waterfall o frame RF.

## Unico tentativo

Il primo candidato congelato, `dl1bajkiwisdr.ddns.net:8074`, è stato contattato
una sola volta con due WebSocket SND concorrenti, al centro deterministico
`16683606.560446203 Hz`. Il pair ha raggiunto `DUAL_READY`; la stop condition
ha quindi impedito qualunque contatto con gli altri cinque candidati.

| Clausola | Reference | Perturbed | Pair |
|---|---:|---:|---|
| semantic SND/IQ readiness | `SATISFIED` | `SATISFIED` | — |
| server channel | `1` | `0` | distinti: `SATISFIED` |
| connection object | distinto | distinto | `SATISFIED` |
| stream sequence | `2` | `2` | rami separati: `SATISFIED` |
| GPS solution age | `0 s` | `0 s` | — |
| event-time overlap | — | — | `0.024835 s`, `SATISFIED` |

Ogni ramo ha ricevuto 19 frame descrittivi MSG e due frame SND da 2068 byte.
Il primo SND, sequence 1, non aveva ancora il campo GPS-seconds e non è stato
ammesso. Il secondo, sequence 2, ha soddisfatto header SND, decode, modalità
IQ, GPS seconds, limite di età e readiness. Gli artifact hash dei due witness
ammessi sono distinti:

```text
reference: 99b8d6177ebd47ca7af4399e3913d5ddff8a8731f9a4f28a98e9d5c851157d22
perturbed: bafbeaa6c8bad50bd63ca2e77b551333bbf5ae907047bbca743b8102733fc7d0
```

## Controllo corretto osservato

Entrambi i rami hanno attraversato la stessa sequenza locale congelata:

```text
AUTH_EMITTED_LOCAL
REQUIRED_METADATA_OBSERVED
REQUIRED_SETUP_EMITTED_LOCAL
FIRST_SND_READY_OBSERVED
```

Il setup completo `CMD_FREQ | CMD_MODE | CMD_PASSBAND | CMD_AGC | CMD_AR_OK`
è stato emesso una sola volta per ramo dopo i metadati richiesti. I keepalive
pre-setup e post-setup osservati sono entrambi zero. Il protocollo non fornisce
un acknowledgement remoto esplicito del setup, quindi
`remote_setup_acknowledgement_clause` resta correttamente `NOT_EVALUATED`.
L'IQ successivo è un witness di output, non viene rinominato acknowledgement.

## Claim autorizzato

In questa sessione una singola Kiwi pubblica ha fornito due rami SND/IQ
simultanei, con connessioni, channel ID, sequenze, receipt atomici e witness
event-time separati. La topologia minima richiesta per un futuro intervento
DDC per-canale è quindi realmente disponibile senza due hardware root e senza
localizzazione geografica.

La condivisione di antenna, front-end, ADC e clock non invalida questo claim:
per la futura domanda DDC costituisce l'upstream comune che i due rami dovranno
controllare, mentre la separazione osservata inizia ai canali allocati.

## Claim non autorizzati

Questo outcome non dimostra che:

- il retune sia indipendente per canale o lasci stabile il ramo reference;
- esista già una feature target o un witness nel passband;
- la feature sia fisica, upstream o downstream del DDC;
- il centro usato contenga un segnale importante;
- una struttura sia invariabile in RF assoluta o in baseband;
- A1/B/A2 sia stato eseguito;
- un satellite, trasmettitore o fenomeno sia stato identificato;
- la correzione del controllo sia l'unica causa della differenza rispetto alle
  sessioni precedenti.

Discovery, qualification del retune e osservazione sono rimaste fuori dal
runtime per costruzione. La durata di overlap prova soltanto la simultaneità
minima dei due witness di readiness, non la continuità richiesta da un futuro
esperimento scientifico.

## SHOCK

Il secondo hardware root non era necessario per verificare l'intervento
NCO/DDC. Avrebbe anzi aggiunto propagazione, oscillatori, front-end e geografia
come confondenti. Una sola capability multicanale offre un causal cut più
pulito: upstream analogico e clock condivisi, rami digitali separati.

La conseguenza inattesa è duplice. Il clock condiviso rende più forte un
confronto di movimento relativo fra rami, ma impedisce anche di usare l'accordo
fra essi come prova di indipendenza strumentale: un artefatto comune dell'ADC o
del front-end può comparire in entrambi. Il futuro claim dovrà quindi restare
limitato alla posizione della feature rispetto al boundary DDC, non diventare
automaticamente un claim di origine RF esterna.

Gate F2.5.19 outcome 1 resta congelato. Il prossimo passaggio, se autorizzato,
deve essere un nuovo piano prospettico separato: discovery locale effimera,
qualification osservabile del retune, plan freeze e un solo A1/B/A2. Non può
riusare questa autorità né interpretare questi due frame come osservazione.
