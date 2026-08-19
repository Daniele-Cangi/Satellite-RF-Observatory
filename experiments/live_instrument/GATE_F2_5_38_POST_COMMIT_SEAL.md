# Gate F2.5.38 — corrected-vertical post-commit seal

Gate F2.5.38 sigilla il successore F2.5.37 senza aprire connessioni e senza
consumare authority. L'unica superficie live-capable è default-refusing:

```python
run_reviewed_once(*, live_authorised: bool = False)
```

Con il valore predefinito solleva prima di assessment, creazione del receipt o
accesso al connector.

## Lineage revisionata

```text
F2.5.37 commit:
  897a7f14bbf323bce1cf40009b93168c1c5d7676

F2.5.37 source:
  1747833281b13525113ecd358446ba1cd828a34aa7eba3f22854d5f7de195d8b

F2.5.37 plan:
  a400327530a1d1db0949197d65fbaed9b09723a4cd4f7608d7ebdef426520d78

continuity evaluator surface:
  cec12d24da7e4710d705d510085e49fd77b2b96189684c9e06b89fabc5e1e515

temporary installation scope:
  4c06a83f0e5c5cd417d45e46dd0d2279bd91efb34c48e976f6ed6d4cdb1bc366

corrected integration surface:
  a1fdfb2a626edc0c13b6c7f304cb243677a762fed9e451dab790be2183c474fd

reviewed F2.5.33 connector source:
  a69f25b9a98482b84dc8c3b404984fe72c5b555a45f28efd27c5d0ae15e27917

live surface:
  196c8bcf1f709f6116bb83599e856196c39683d189a14877fa408338b5720508

authority envelope:
  e2a1ee4e835f32960a00986fbfbe514feb838af6026419d8e958cface127f91d
```

L'assessment richiede che il commit sia un ancestor, che il file F2.5.37 non
differisca dal commit, che il frozen receipt F2.5.36 continui a sostenere
l'attribuzione e che tutti gli hash sopra corrispondano.

## Execution envelope congelato

Il seal fissa:

- endpoint `dl1bajkiwisdr.ddns.net:8074`;
- due connessioni SND simultanee sulla stessa Kiwi;
- rami DDC reference fisso e perturbed distinti;
- identico ordine A1→B→A2;
- una sola regola F2.5.27 per qualification iniziale e full-session;
- il piano F2.5.32 e tutte le soglie RF invariate;
- decisione discovery prima del sibling scalar audit non autoritativo;
- connector F2.5.33 e ownership/zeroization già revisionati;
- waterfall assente dal causal path ed `ext_api` solo descrittivo;
- zero retry pre-freeze e post-freeze;
- una sola outcome window e stop al primo terminale;
- path receipt predefinito non sovrascrivibile dal caller;
- receipt JSONL rigoroso con decisioni, scalari e hash soltanto;
- zero persistenza RF.

Il caller non può cambiare endpoint, frequenza, timing, soglia, feature,
normalizzazione, trasformazione, retry, receipt path o connector.

## Guard order

```text
explicit authority
  → post-commit seal
  → authority envelope come primo receipt
  → due connector SND fissati
  → un solo corrected F2.5.37 outcome
  → terminal manifest
```

Un fallimento parziale del connector chiude il peer già aperto e terminalizza
il receipt. L'owner corretto distrugge IQ e ripristina l'evaluator congelato
anche su eccezione.

## Verifica offline

I test sintetici stabiliscono che:

- il default refusal precede ogni side effect;
- ogni mismatch di source, plan, continuity function, installation scope,
  integration, connector, ambiente, live surface o envelope fallisce chiuso;
- l'authority envelope è il primo evento e viene emesso un solo outcome;
- un transcript con un timestamp iniziale nullo per ramo supera la continuity
  corretta senza cambiare discovery, audit o soglie;
- il fixture fisico preesistente può produrre il proprio outcome sintetico;
- il receipt non contiene IQ, campioni, waterfall, STFT o numeri non finiti;
- cleanup, terminal manifest e zero RF persistence restano obbligatori.

Il risultato sintetico non è un outcome live e non supporta alcun claim sul
fenomeno osservato in F2.5.36.

## Stato

```text
assessment: CORRECTED_VERTICAL_READY_FOR_SEPARATE_AUTHORITY
live execution authorized: false
authority consumed: false
network activity: zero
raw RF persistence: ZERO
```

Gate F2.5.38 si ferma qui. Il prossimo passo è una decisione dell'utente:
mantenere il runner sigillato e inutilizzato oppure autorizzare una singola
esecuzione esatta. Un'eventuale authority successiva avrebbe zero retry,
nessun cambio di dimensione e stop dopo il primo outcome.
