# Flusso generale di verifica satellitare

Obiettivo richiesto il 12 settembre 2026: permettere una richiesta su satellite
e giorno, stabilire se le misure consentono una verifica e restituire posizione,
incertezza e controlli oppure il motivo preciso per cui non si può concludere.
Il flusso deve funzionare anche quando la verifica scientifica fallisce.

Questa priorità sostituisce la sospensione generale del lavoro sul servizio.
Il piano scientifico precedente e i suoi file restano immutati perché legati
alle prove già registrate. Nessun risultato storico viene riclassificato.

## Dominio iniziale e promessa

- Identità GPS G01–G32 dichiarata dai ricevitori; nessuna identificazione autonoma.
- Giorni storici completi dal 2022-11-27, con disponibilità da verificare sulle
  fonti. Primo intervallo strutturalmente idoneo, non un istante arbitrario.
- Profilo esistente `gps-code-network-v1`: sette stazioni da un insieme fisso
  di dieci candidati, GOLD esclusa dalla stima. Questo è il motore snapshot v1;
  la configurazione cinematica quattro-più-uno è ancora ricerca separata.
- Una posizione storica e un'incertezza condizionale all'evento. Nessuna
  promessa di posizione live, successo universale o copertura statistica generale.

La prima informazione fisica nuova da ottenere sarà la disponibilità e la
qualità predittiva su richieste fissate prima delle misure. I contratti software
qui consegnati non producono questa evidenza: rendono esplicito dove raccoglierla.

## Percorso di una richiesta

1. Validare satellite, giorno e profilo; rispondere subito ai casi non supportati.
2. Per eventi già conclusi, indirizzare all'archivio originale senza riesecuzione.
3. Preparare il piano completo: rete, osservabili, selezione, criteri e accessi
   precedenti. Congelare piano e versione prima della successiva acquisizione.
4. Verificare fonti e continuità con il selettore esistente. Un piano accettato
   non significa che i dati siano disponibili; disponibilità non è calibrazione.
5. Calibrare con soli riferimenti non bersaglio e stimare offline. Conservare
   gli arresti per dati, calibrazione, identificabilità e incertezza.
6. Congelare soluzione e previsione prima di leggere il ricevitore escluso e
   l'orbita di confronto. Non correggere una soluzione con la conferma.
7. Restituire un risultato leggibile con terminale originale, condizioni,
   epoca, frame, stazioni, incertezza, controlli ed evidenze scaricabili.

| Esito rivolto all'utente | Significato |
|---|---|
| Verificata nelle condizioni dichiarate | Tutti i criteri dell'evento sono passati |
| Inconcludente | Incertezza eccessiva o posizione non identificabile |
| Non verificabile con questi dati | Fonti, misure o calibrazione insufficienti |
| Non confermata | Il confronto escluso non soddisfa i criteri |
| Errore di esecuzione | Problema tecnico da diagnosticare; nessun verdetto fisico |

## Consegne ordinate

| Passo | Consegna | Verifica richiesta |
|---|---|---|
| G1 — Contratto locale | Ingresso minimo, piano esistente, capacità e risposta uniforme dai dossier sigillati | Richieste valide/non supportate, eventi archiviati, esiti positivi/negativi, integrità e nessun accesso RF |
| G2 — Esecuzione integrata | Collegare RequestStore al worker esistente, versione fissata, avanzamento, artefatti e ripresa controllata | Flusso completo offline con sorgenti simulate; nessun doppio tentativo dopo crash o lease scaduta |
| G3 — Validazione del dominio | Campione dichiarato in anticipo, distinto dai dati di sviluppo, e valutazione del trasferimento degli errori | Tutti i tentativi nel denominatore; disponibilità, errori, incertezze, controlli esclusi e tempi misurati |
| G4 — Accesso privato | API autenticata e interfaccia sullo stesso flusso verificato | Percorso utente completo, isolamento dei proprietari, quote e diagnosi degli errori |
| G5 — Servizio pubblicabile | Dominio qualificato e limiti documentati, gestione operativa e decisione di hosting | Evidenza a sostegno delle promesse, recupero verificato e autorizzazione al deployment |

G1 è la prima consegna implementata in `service/workflow.py` e `service/__main__.py`.
G2 collega ora `service/requests.py` e `positioning/jobs.py` attraverso
`service/worker.py`: invio locale, esecuzione di una richiesta, rinnovo del lease,
stato e risultato, blocco dei duplicati e riconciliazione dei risultati già
sigillati. I test usano sorgenti e risultati scientifici inventati; nessuna
nuova campagna è stata eseguita per questa consegna. L'operatore avvia il worker
su un checkout dedicato e pulito della versione dichiarata. HTTP, invio dal
browser e un worker continuamente in servizio restano da consegnare.

La perdita rilevata del lease arresta l'albero dei processi. Un arresto brutale
del supervisore può lasciare processi figli vivi: alla scadenza il registro
blocca ogni nuovo dispatch e richiede ispezione. Non è un sistema di isolamento
del sistema operativo. La riconciliazione adotta soltanto un risultato già
sigillato con ricevuta di uscita del processo; non riparte da stime o conferme
parziali e non rimette tentativi in coda.

G3 comprende il lavoro scientifico ancora aperto. Per la cinematica servono
continuità di fase, errori direzionali/atmosferici, trasferimento degli errori
dei riferimenti e correlazioni con il bersaglio. I residui di cinque minuti
del DOY240 non qualificano da soli il nuovo profilo. I sei termini aperti
devono portare a modelli e verifiche misurabili, non a ulteriori audit equivalenti.

Prima delle nuove acquisizioni dichiarare il campione concreto e gli accessi
pregressi. Le giornate di qualificazione già consumate restano tali. Nessuna
campagna viene avviata da questo documento o dalla preparazione di un piano.
La validazione deve includere anche indisponibilità e fallimenti senza cercare
un'altra finestra, rete o bersaglio dopo aver visto un esito sfavorevole.

## Criterio di avanzamento

Misurare quante richieste ricevono una risposta completa e quanto tale risposta
è sostenuta dai dati. Separare richieste supportate, fonti disponibili, stime
ottenute e verifiche superate. Non usare i cinque eventi eterogenei dell'archivio
come percentuale di successo del servizio. Il sito consumerà questi risultati
senza sostituire la posizione stimata con quella dell'orbita di confronto.
