# Gate F2.5.15 — post-commit seal e authority surface

Stato:

```text
EXACT_AUTHORITY_SURFACE_READY_FOR_SEPARATE_AUTHORITY
```

Gate F2.5.15 è stato eseguito esclusivamente offline. Non ha aperto
connessioni, non ha creato finestre RF e non ha consumato alcuna autorità live.

## Oggetto della review

Il seal parte dal commit F2.5.14:

```text
d32dba647a9a49d8d980325567a0ae09f3a08c20
```

e vincola:

- le 17 sorgenti Python nel causal path effettivo;
- SHA-256 del testo canonico LF per ciascuna sorgente;
- presenza del commit revisionato nella lineage di `HEAD`;
- assenza di diff Git sulle causal source rispetto al commit revisionato;
- Python 3.13.5, NumPy 2.3.3, SciPy 1.17.1 e websocket-client 1.8.0;
- control-surface hash F2.5.14
  `9104f5ff98a5415a558112a38992d2d598b5f7c467c474198a080c96cf531bf0`;
- candidate set, ordine, center policy, due branch concorrenti, GPS age 30 s,
  tentativo unico, zero retry e zero persistenza già contenuti nell'envelope;
- working directory uguale alla repository root.

La normalizzazione LF è dichiarata: evita che un checkout CRLF Windows cambi
l'identità logica del source senza modificarne il contenuto Git. Non modifica
né normalizza RF o receipt di misura.

## Correzione rispetto al vecchio review set

L'audit transitivo ha aggiunto due sorgenti omesse dal vecchio F2.5.10:

- `kiwi_gate_f2_5_2.py`, che definisce la pair disposition usata dal receipt;
- `kiwi_gate_f2_5_6.py`, importata da F2.5.7 e quindi parte della semantica del
  wire contract.

Il seal include inoltre F2.5.12, F2.5.13 e F2.5.14. La lista non è presentata
come framework generale: è l'allowlist causale di questa sola esecuzione.

## Authority surface esatta

L'unico entry point pubblico di esecuzione è:

```python
run_reviewed_once(*, live_authorised: bool = False)
```

Il caller non può fornire:

- endpoint o ordine candidati;
- frequenza o center policy;
- soglie o GPS age;
- retry;
- receipt path;
- connector provider;
- modulo WebSocket;
- mirror sink;
- una seconda finestra.

L'ordine fail-closed è:

```text
explicit authority
→ post-commit seal
→ terminal receipt open
→ direct dual-SND connectors
```

Senza `live_authorised=True`, assessment, receipt e connector non vengono
nemmeno raggiunti. Con autorità esplicita ma seal non valido, l'esecuzione si
ferma ancora prima del receipt e della rete.

## Receipt della futura esecuzione

Il primo evento dovrà essere:

```text
gate_f2_5_15_authority_envelope_frozen
```

e conterrà:

- authority envelope e relativo hash;
- execution envelope con event time della sessione;
- control-surface hash verificato nuovamente;
- dichiarazione della separata autorità live.

Seguono soltanto i receipt atomici dei candidate pair, un outcome e il manifest
terminale. Un errore descrittivo del receipt non può cambiare la decisione
fisica. Nessun payload, IQ, sample, array, STFT o waterfall viene persistito.

## Cosa può fare la singola esecuzione

La futura chiamata può soltanto:

- attraversare i sei candidati nell'ordine congelato;
- aprire R e P contemporaneamente tramite due `create_connection` per ruolo;
- osservare il minimo SND/IQ readiness witness su entrambi;
- fermarsi al primo pair topologicamente ammissibile oppure a candidati
  esauriti;
- chiudere le connessioni;
- produrre un solo outcome terminale.

Non esegue feature discovery, retune, A1/B/A2 o inferenza upstream/downstream.
Questa è ancora qualification della capability, non il risultato fisico DDC.

## Outcome ammessi

```text
DUAL_SEMANTIC_PAIR_READY
NO_MULTI_CHANNEL_CAPABILITY
NO_ADMISSIBLE_CAUSAL_TOPOLOGY
QUALIFICATION_INCOMPLETE
```

`NO_MULTI_CHANNEL_CAPABILITY` resta autorizzato soltanto dopo due rifiuti
espliciti per ciascun candidato. Errori software, transport o readiness
producono `QUALIFICATION_INCOMPLETE`.

## SHOCK

L'autorità non deve autorizzare “il progetto” o “una prova Kiwi”. Deve
autorizzare una funzione con un solo bit controllabile, un commit preciso e un
control-surface hash. Tutte le altre dimensioni appartengono al receipt
revisionato, non al caller.

Gate F2.5.15 si ferma prima della rete. L'eventuale autorità successiva deve
riferirsi al commit che congela questo file e il modulo F2.5.15.
