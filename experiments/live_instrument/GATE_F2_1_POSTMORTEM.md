# Gate F2.1 — phase semantics e discovery offline

Stato: **STOP prima della rete**. Gate F2 outcome 1 resta immutato nel commit
`fbda0bf`; questo documento lo annota senza riscriverne receipt, outcome o
interpretazioni storiche. Nessuna connessione Kiwi, acquisizione RF o sequenza
`A→B→A` è stata eseguita in Gate F2.1.

## Annotazione del primo outcome

| Campo | Valore congelato o corretto |
|---|---|
| Outcome registrato | `NO_CAPABILITY_ADMITTED` |
| Fase realmente raggiunta | `DISCOVERY` |
| Discovery path validi | 0 |
| Candidati scoperti | 0 |
| Qualification completate positivamente | 0 |
| Capability ammesse | 0 |
| Interpretazione corretta | `DISCOVERY_PATH_FAILED` |

Il runtime aveva aperto la fase discovery, ma i due tentativi consentiti sullo
stesso transport path non avevano prodotto una risposta inventory valida. Il
primo receipt storico non viene rinominato retroattivamente. Gate F2.1 registra
che `NO_CAPABILITY_ADMITTED` era una classificazione di fase troppo avanzata.

Non è autorizzata alcuna conclusione sulla disponibilità globale dei Kiwi,
sulla capacità RF di un endpoint, sulla propagazione, sulle soglie, sulla
presenza di feature o sulla falsificabilità dell'intervento. Nessun endpoint
era arrivato a qualification.

## Semantica delle fasi

Il percorso futuro è esplicito e strettamente ordinato:

`BOOTSTRAP → DISCOVERY → QUALIFICATION → ADMISSION → PLAN FREEZE → EXPERIMENT`

Gli outcome pre-freeze hanno ora domini disgiunti:

| Outcome | Condizione necessaria | Fase terminale |
|---|---|---|
| `DISCOVERY_PATH_FAILED` | `successful_discovery_paths == 0` | `DISCOVERY` |
| `NO_CAPABILITY_DISCOVERED` | almeno un discovery path valido, zero candidati | `DISCOVERY` |
| `NO_CAPABILITY_QUALIFIED` | candidati > 0, qualification positive = 0 | `QUALIFICATION` |
| `NO_CAPABILITY_ADMITTED` | qualification positive > 0, capability ammesse = 0 | `ADMISSION` |
| `NO_FALSIFIABLE_EXPERIMENT_AVAILABLE` | capability ammesse > 0, nessun contrasto congelabile | `ADMISSION` |

Il codice rifiuta combinazioni incoerenti. In particolare,
`NO_CAPABILITY_ADMITTED` non può più descrivere un errore di trasporto o una
discovery vuota. Le clausole aggregate `qualification_completed`,
`capability_admitted` e `falsifiable_intervention_available` sono
`NOT_EVALUATED` finché la fase precedente non è completata. Tutte le 17
clausole della confirmation restano `NOT_EVALUATED` finché non esiste un plan
freeze.

## DiscoveryReceipt atomico

Ogni singolo tentativo di transport path produce un receipt in RAM con:

- `provider`, `inventory_root`, `transport_route`, `access_mode`;
- `started_at`, `completed_at`, `retry_index`, `expires_at`;
- `response_status`, `candidate_count`;
- `response_hash` soltanto quando esiste una risposta;
- `error_class` e `error_detail` soltanto per un errore.

Gli stati sono `TRANSPORT_ERROR`, `PROTOCOL_ERROR`, `DESCRIPTION_ERROR`,
`VALID_EMPTY_RESULT` e `VALID_CANDIDATE_RESULT`. Un errore di discovery non
produce `CapabilityRejected`: non esiste ancora una capability da rifiutare.
Un transport error non può contenere un response hash inventato; un risultato
valido deve invece hashare la risposta prima del parsing.

La response, gli endpoint candidati e i receipt restano effimeri e soggetti a
TTL. Il codice dell'adapter può sopravvivere, ma non vengono scritti cataloghi,
reputazioni, inventari, endpoint o stato globale Kiwi.

## Causal lineage

Gate F2.1 distingue quattro identità:

1. `inventory_root`: l'insieme causale che origina l'inventario;
2. `listing_transport`: la route usata per leggere quell'inventario;
3. `endpoint_identity`: l'indirizzo candidato descritto dal listing;
4. `hardware_root`: l'hardware stabilito soltanto dal probe diretto.

Due pagine o route derivate dal registro ufficiale Kiwi aggiungono resilienza
di trasporto, non una seconda inventory root. Un endpoint elencato non è una
measurement root. Lo diventa soltanto dopo un probe diretto riuscito che
stabilisca endpoint e hardware root; la mera presenza nel listing non conta
come conferma della capability.

## Bootstrap leciti considerati

Questa è una progettazione offline, non una lista di adapter già autorizzati.
Ogni path futuro deve avere termini e modalità d'uso registrati prima del
bootstrap; il fatto che una pagina sia pubblica non autorizza automaticamente
lo scraping.

| Bootstrap | Diversità | Stabilità e freschezza | Accesso e condizioni | Endpoint diretti |
|---|---|---|---|---|
| Listing ufficiale Kiwi, route raw già usata da F2 | inventory root centrale; un solo transport HTTPS | inventario live ma senza garanzia di disponibilità; TTL 600 s | accesso pubblico osservato, ma l'automazione va limitata alla route documentata e alle condizioni del provider | sì, se la risposta è valida |
| Vista ufficiale umana/map della medesima registry | solo fallback di transport, **non** root indipendente | può avere rendering/cache diversi dalla route raw | non viene scrapata automaticamente; può produrre un affordance di sessione soltanto tramite uso umano autorizzato | sì, se l'utente fornisce esplicitamente il link risultante |
| Affordance di sessione fornita da utente od operatore | nessuna directory; inventory root è la dichiarazione di sessione con provenance | stabile soltanto fino al TTL dichiarato | endpoint e autorizzazione al probe sono forniti esplicitamente; il runtime non amplia l'insieme | sì, ma sono solo candidati fino al probe diretto |
| API di un indice terzo con licenza machine-readable | potenziale seconda inventory root | dipende da SLA, timestamp e policy dell'indice | ammissibile solo dopo aver congelato API, termini e attribution | potenzialmente sì |

Offline non è stata verificata una seconda inventory root pubblica con API e
condizioni programmatiche sufficienti. Il quarto path resta quindi escluso dal
piano eseguibile; non viene inventato un provider. La vista ufficiale umana
non viene promossa ad API. Oggi non risultano due discovery provider
programmatici e causalmente indipendenti già qualificati.

## Strategia futura da revisionare

La strategia è congelata concettualmente, ma nessun adapter multipath viene
ancora implementato:

- massimo tre transport path, elencati e hashati durante `BOOTSTRAP` prima di
  ogni rete;
- set iniziale consentito: affordance di sessione già fornite e route ufficiale
  raw; un terzo slot resta assente finché un provider programmatico lecito non
  viene documentato **prima** dell'esecuzione;
- avvio concorrente dei path congelati, così un ordine di risposta non diventa
  ranking implicito;
- budget discovery complessivo: 90 s;
- timeout per tentativo: 8 s;
- massimo un retry per transport path, sulla stessa route e soltanto per
  trasporto, protocollo, descrizione o software;
- nessuna nuova source, route o affordance dopo aver osservato i risultati;
- deduplicazione effimera per endpoint identity, senza fondere inventory roots;
- arresto immediato con `DISCOVERY_PATH_FAILED` se tutti i path falliscono;
- `NO_CAPABILITY_DISCOVERED` se almeno un path è valido ma l'unione effimera è
  vuota;
- `CANDIDATES_DISCOVERED` se esiste almeno un candidato valido; soltanto allora
  si può entrare in qualification.

I tre soli outcome della fase sono quindi:

`DISCOVERY_PATH_FAILED | NO_CAPABILITY_DISCOVERED | CANDIDATES_DISCOVERED`.

Il piano non obbliga Gate F a trovare candidati. Una response scade, i
candidate receipt scadono con essa e l'insieme in RAM viene distrutto alla fine
della sessione.

## SHOCK — eliminare la directory centrale

Sì, la directory centrale può cessare di essere una primitiva, ma non può
essere sostituita con scansione o memoria storica.

### Alternativa 1 — provider multipli

Due o più inventory provider realmente indipendenti, ciascuno con API e termini
programmatici espliciti, emettono receipt atomici con TTL. I listing vengono
uniti soltanto in RAM e le root restano separate. Route multiple dello stesso
registro aumentano availability, non indipendenza. Questa alternativa non è
implementabile oggi perché offline non è stato qualificato un secondo provider
lecito.

### Alternativa 2 — affordance-first

Il bootstrap accetta inviti effimeri forniti nella sessione da utente od
operatore: endpoint diretto, provenance, permesso al probe, scadenza e limiti.
L'invito non è una capability affidabile e non è una measurement root. Un probe
diretto, limitato all'insieme esplicitamente fornito, può trasformarlo in
candidato qualificabile. Senza inviti si termina; non si cercano host vicini,
non si enumerano seriali, non si scansionano porte e non si consulta un
database storico.

Una variante push può usare beacon/inviti time-limited pubblicati
volontariamente dagli operatori verso la sessione. Anche qui il runtime riceve
affordance; non esplora Internet.

Queste alternative sono proposte per revisione e non sono implementate in Gate
F2.1.

## Verifica e stop

I test offline coprono receipt e stati numerici/temporali, invarianti degli
outcome, gating delle clausole, lineage e il caso storico simulato: due errori
di trasporto producono `DISCOVERY_PATH_FAILED`, mai
`CAPABILITY_REJECTED`. Nessun test apre la rete.

Gate F2.1 si ferma qui, prima della discovery multipath e prima di qualunque
nuova acquisizione.
