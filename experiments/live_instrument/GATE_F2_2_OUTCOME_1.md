# Gate F2.2 — primo outcome multipath

Stato: **STOP dopo la singola esecuzione autorizzata**. Il runtime era
congelato nel commit locale
`549b62d90c7cea682389f1cc442949de070ddb3b`. Non è stata aperta una seconda
sessione e non viene progettato Gate G.

## Outcome terminale

`NO_CAPABILITY_QUALIFIED`

La sessione ha completato bootstrap e discovery, è entrata in qualification e
si è fermata prima di admission. Sono emersi sei candidati, ma zero
qualification sono state completate positivamente. Non esistono hardware root,
measurement root, coppie ammesse, plan hash, segment receipt o intervention
receipt.

Questo non è un risultato RF negativo. Nessuno stream IQ, waterfall o segmento
`A1/B/A2` è stato acquisito.

## Bootstrap congelato

- start: `2026-08-16T14:36:40.325843Z`;
- `bootstrap_plan_hash`:
  `522bcbed79db35bd3b5aa3db30a54c1463dbae76fff4bc6659e86bd0b26d266b`;
- runtime commit:
  `549b62d90c7cea682389f1cc442949de070ddb3b`;
- mother plan hash:
  `6f4b367d3b32cf6bfc362c14882f2e0822f33d3f0893b22df58a138f7caf5f9a`;
- discovery budget: 90 s;
- scheduling: `CONCURRENT_FROZEN_SET`;
- retry budget: massimo uno per transport path;
- session-affordance hash:
  `caf356e1824c59e5d00c934abbd91c7d4ab8d852c322ed7b4c1b3dd00992a890`;
- ranking: `gate-f2-lexicographic-falsification-v1`;
- qualification: `gate-f2.2-direct-stream-retune-v1`;
- frequenza: `gate-f2-targetless-waterfall-centers-v1`;
- transform: `gate-f2:c40ecb471dce:4eb733e6b614:1`.

Il receipt è stato emesso prima di qualsiasi connessione. Nessun path,
endpoint, provider, frequenza manuale, ranking o soglia è stato aggiunto dopo
il freeze.

## Bootstrap path

| Path | Origin | Inventory root | Transport | Risultato | Candidati |
|---|---|---|---|---|---:|
| A | `PROVIDER_LISTING` | `kiwisdr-public-registry` | `https://kiwisdr.com/.public/` | due `TRANSPORT_ERROR`, retry 0 e 1 | 0 |
| B | `LISTING_TRANSPORT_FALLBACK` | `kiwisdr-public-registry` | `https://kiwisdr.com/public/` | due `TRANSPORT_ERROR`, retry 0 e 1 | 0 |
| C | `SESSION_AFFORDANCE` | `session-affordance:tracked-receipts` | `session://frozen-prior-receipts` | `VALID_CANDIDATE_RESULT` | 6 |

I quattro errori A/B erano `URLError` con `WinError 10061` e non avevano una
risposta: `response_hash` è correttamente `null`. A e B sono due trasporti
dello stesso inventario e non valgono come root indipendenti.

Path C ha usato esclusivamente il set finito congelato prima della rete. Il
suo `DiscoveryReceipt` ha hash
`5368c5fae1e67e7d8c564c3546b1262849265f71e9709691b8f58e6208d6b4f4`,
TTL 600 s e scadenza `2026-08-16T14:46:40.571071Z`.

## Discovery e deduplicazione

Outcome di fase: `CANDIDATES_DISCOVERED`.

- candidati unici: 6;
- candidate-set hash dopo deduplicazione:
  `6adb13ad25b750a6c5241f1c1b4421540b5558aa624d2c65a000cdda4493e7e9`;
- origin di tutti i candidati: soltanto `SESSION_AFFORDANCE`;
- nessuna duplicazione fra i tre path, perché A e B non hanno restituito una
  risposta valida.

| Endpoint identity | Candidate receipt hash | Provenance |
|---|---|---|
| `dl1bajkiwisdr.ddns.net:8074` | `fcca0eb1eb0b057e7a96f866ef277e3b5eaa6b3dab660b72b9e38dc4ab5cb0fa` | receipt tracciati Hooksiel |
| `g0ghk.uk:8050` | `0a663e847380251e5822d6d06dc53429f815174b38739d09efdd795e72fd369c` | receipt tracciati Doncaster |
| `hill.n8ga.org:8073` | `390fc6edecfb3a83885e5c078715786b95da02557a2062d27fd86086346193e6` | Gate E congelato |
| `kiwisdr2blair.ddns.net:8073` | `ab546a23d4f61711bfe4ee9fb5e3ef738fa3e3ccee6195592f7ceae3ddd7ccbc` | Gate E congelato |
| `kiwisdr.kfsdr.com:8074` | `94550b851a2e716f93b6b7e192d36dfdc385a2bbb36251742d73b78dbc34f43a` | Gate E congelato |
| `va6ok.ddns.net:8073` | `9e7cc696062f1c3e3016b5247f564e7cc3ec446dbe8c2663b3bb8e6b998b1b4e` | Gate E congelato |

Questo dimostra bootstrap da affordance effimere preautorizzate. Non dimostra
discovery autonoma dell'intera rete senza directory.

## Qualification

Tutti i sei endpoint hanno restituito un documento `/status`, quindi il
trasporto diretto descrittivo era raggiungibile nella sessione. Tutti sono
stati però classificati `CAPABILITY_REJECTED` prima dello stream probe: il
documento non conteneva una localizzazione hardware utilizzabile per verificare
l'indipendenza delle root.

| Endpoint identity | Status hash | Esito | Ragione |
|---|---|---|---|
| `dl1bajkiwisdr.ddns.net:8074` | `74761c10f84d7bd0f7e218dc2df55ecbc232090b96be472034661b0bfe4ea8e7` | rejected | hardware location unavailable |
| `g0ghk.uk:8050` | `d7898598e26d7f5a6cc7b9486c3d4103ee3918c9ca431bc85e7b4fb6d8d2ddc2` | rejected | hardware location unavailable |
| `hill.n8ga.org:8073` | `2a7212b79210d42871e93b337a4b20a9caadfaa90dc86c32da7c5827be1dcd21` | rejected | hardware location unavailable |
| `kiwisdr2blair.ddns.net:8073` | `7799121ee2c6d2641e792626c79d3d24af15aadba0178cd41ad5bc3089d97ed4` | rejected | hardware location unavailable |
| `kiwisdr.kfsdr.com:8074` | `7d5c9bf00cd96c8123bb0128fb710f9ac6e7a61eae94021d1408f3386187426b` | rejected | hardware location unavailable |
| `va6ok.ddns.net:8073` | `4907a6b37e0b80952b98eee9a5701b360671fc444b4952cf1c50a11f4edff3a1` | rejected | hardware location unavailable |

Non vi sono `QUALIFICATION_ERROR`: i sei rifiuti derivano da una precondizione
epistemica valutata. Tuttavia non autorizzano l'affermazione che i ricevitori
siano incapaci di misurare RF. Per ciascun candidato:

- `capability_offer_created = false`;
- `stream_capability = NOT_EVALUATED`;
- `event_time_semantics = NOT_EVALUATED`;
- `hardware_root = null`;
- nessun IQ stream è stato aperto;
- nessun candidato è diventato measurement root.

Il successo passato di Hooksiel, Doncaster o dei candidati Gate E non è stato
usato come prova di salute corrente.

## Admission

Admission non è stata raggiunta:

- coppie valutate: 0;
- hardware root qualificate: 0;
- causal cut valutati: 0;
- falsification power valutato: 0;
- plan freeze: assente (`plan_hash = null`).

La clausola `qualification_completed` è `UNSATISFIED`.
`capability_admitted` e `falsifiable_intervention_available` sono
`NOT_EVALUATED`. Tutte le 17 clausole dell'esperimento sono
`NOT_EVALUATED`.

## Experiment

Non eseguito. Non esistono:

- centro A o B;
- `Δf`;
- target o witness;
- acquisizioni waterfall/IQ;
- segmenti A1, B o A2;
- artifact RF;
- intervention receipt;
- risultato RF-frame o baseband-frame.

## Affermazioni autorizzate

- La sessione ha composto tre bootstrap path congelati mantenendone lineage e
  receipt separati.
- Le due superfici della directory ufficiale hanno fallito il trasporto in
  questa sessione.
- Un set preautorizzato di affordance ha prodotto sei candidati con TTL.
- I sei endpoint hanno risposto al probe descrittivo diretto.
- Nessuno ha soddisfatto la precondizione congelata per stabilire due hardware
  root indipendenti.
- Il runtime si è fermato correttamente in qualification senza promuovere
  endpoint raggiungibili a capability RF.

## Affermazioni non autorizzate

- Il fallimento della directory implica che non esistano ricevitori pubblici.
- Path C costituisce discovery autonoma o globale di Internet.
- Un candidate endpoint è una capability.
- Il documento `/status` prova stream, event time, continuità o integrità RF.
- I sei ricevitori sono fisicamente incapaci o offline.
- Non esiste una coppia Kiwi qualificabile in generale.
- Il retune è controllabile o fisicamente verificato.
- Una delle ipotesi RF-frame/baseband-frame è supportata o danneggiata.

## SHOCK

La directory centrale non è necessaria per entrare in discovery: affordance
finite e preautorizzate possono mantenere vivo il bootstrap quando entrambe le
surface del listing falliscono. Ma eliminare la directory non elimina la
qualification. In questa sessione il guadagno di reachability ha prodotto
candidati, non falsification power.

Gate F2.2 si ferma qui. Nessuna nuova rete, retry, finestra, sostituzione di
endpoint o reinterpretazione è autorizzata dopo questo outcome.
