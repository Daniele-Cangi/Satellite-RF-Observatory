# Gate F2.5.21 — seal del verticale prospettico

## Outcome

```text
EXACT_PROSPECTIVE_INTERVENTION_READY_FOR_SEPARATE_AUTHORITY
```

Gate F2.5.21 non apre connessioni e non concede autorità live. Lega il
verticale Gate F2.5.20 al commit revisionato, al parent outcome realmente
qualificato, all'ambiente numerico e a una sola superficie pubblica booleana.

## Stato revisionato

- commit F2.5.20 revisionato:
  `92ef1e8500b6418f2ffe4c5232cbe010269b0178`;
- control-surface hash:
  `a823572e04063ff24e7030b2531dc2351c52e1efad2c260cb77589214018224d`;
- live-surface source hash:
  `fa4ab9e9dccd363b81f72998c89d3f986c1ed9506539d6a620a00822d443a315`;
- authority-envelope hash:
  `9299f8da2d66efb4d0b06a288b151110bb38c75a5254bf903af8ea03e66510d7`;
- causal allowlist: 22 file hash-bound, inclusi header e manifest del protocollo;
- ambiente: Python 3.13.5, NumPy 2.3.3, SciPy 1.17.1,
  websocket-client 1.8.0;
- retry pre-freeze: zero;
- retry post-freeze: zero;
- persistenza RF: zero.

Il live-surface hash copre anche le funzioni di assessment, default path,
connector binding, esecuzione revisionata e superficie pubblica. Cambiare il
solo wrapper d'autorità invalida quindi il seal anche se il verticale causale
restasse invariato.

## Unica superficie futura

```python
run_reviewed_once(*, live_authorised=False)
```

Il caller può cambiare soltanto `live_authorised`. Non può fornire endpoint,
frequenza, feature, delta, soglie, durate, connector, receipt path, retry,
discovery rule o evaluator.

Guard order:

1. autorità esplicita separata;
2. seal di commit, sorgenti, live surface e ambiente;
3. verifica hash del parent outcome F2.5.19;
4. apertura del receipt con authority envelope come primo evento;
5. un solo verticale prospettico.

## Massimo scope autorizzabile

Una futura singola chiamata può:

1. riqualificare due canali phase-aware sull'unico endpoint già selezionato;
2. acquisire una nuova discovery effimera;
3. selezionare target, witness e delta con le soglie invariate;
4. qualificare il retune usando il witness e non il target;
5. congelare predizioni e controlli;
6. eseguire un solo A1/B/A2 indipendente;
7. emettere il primo outcome terminale e fermarsi.

Non può aprire un secondo endpoint o una seconda finestra. Se una fase
pre-freeze non ammette la successiva, ogni fase downstream diventa
`NOT_EVALUATED`. Dopo il freeze qualunque failure diventa l'unico outcome,
senza rescue adattivo.

## Verifica offline

I test dimostrano default refusal prima di receipt e connector, identità di
commit/sorgenti/ambiente/live surface, primo evento d'autorità e un'esecuzione
sintetica che contatta esattamente reference e perturbed dell'unico endpoint.
Nessun test usa rete o persiste campioni.

Gate F2.5.21 si ferma prima della rete. L'autorità per una singola osservazione
deve essere esplicita e successiva al commit di questo seal.
