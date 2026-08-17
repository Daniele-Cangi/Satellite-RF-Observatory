# Gate F2.5.11 — attribuzione offline del fallimento F2.5.10

Stato:

```text
FROZEN_FAILURE_BOUNDARY_ATTRIBUTED_CAUSE_UNRESOLVED
```

Questo Gate usa esclusivamente il receipt congelato di F2.5.10 e il codice che
lo produsse. Non apre connessioni, non acquisisce dati, non cambia predicate,
candidati, timeout, retry o outcome. Il documento F2.5.10 rimane immutato.

Artifact sorgente:

`session_receipts/gate-f2-5-10-20260817T093414.925168Z.jsonl`

SHA-256:

`cb8e63dd0dfcf8affebf98bc63cf9fbae640f426383a9badb2670a33632b1f1d`

## Correzione esatta del close 1005

Nel runtime congelato `_receive_data_frame()` rappresenta un close, prima
dell'analisi, come:

```text
b"CLOSE" + payload
```

e ne conserva SHA-256. Se il payload contiene meno di due byte, il recorder
scrive localmente `1005` nel transcript.

Tutti gli otto eventi terminali hanno artifact hash:

`f13a1ed0cf3c4197ec8f4301b169908f52e45cab428eb604f79aab4a4b10dee3`

che coincide esattamente con `SHA256(b"CLOSE")` e non con
`SHA256(b"CLOSE" + uint16_be(1005))`. Il payload era quindi vuoto. Il valore
`1005` non era uno status inviato dal peer: era il sentinel locale
`status-not-available` del receipt.

Questo non identifica chi, nel sistema remoto, decise il close né perché. Il
payload vuoto non contiene status o reason. L'espressione congelata “close
1005” va dunque letta come “close con payload vuoto, descritto localmente come
1005”, non come errore causale del server.

## Le due classi realmente osservate

| Classe | Rami | Attribuzione autorizzata |
|---|---:|---|
| `EXPLICIT_ATTEMPT_REJECTION` | 4 | Il server emise `badp` non-OK in quello specifico tentativo. |
| `POST_COMMAND_CAUSE_UNRESOLVED` | 8 | Allocation e invio locale di `mod_iq` precedettero un close a payload vuoto; nessun witness IQ qualificante entrò nel receipt. La causa non è attribuibile. |

La prima è un rifiuto di capability limitato al ramo e al tentativo. La seconda
resta `QUALIFICATION_ERROR`: non può essere promossa a
`CAPABILITY_REJECTED`.

## Attribuzione per candidato

| Endpoint | Reference | Perturbed | Claim massimo |
|---|---|---|---|
| `dl1bajkiwisdr.ddns.net:8074` | post-command, causa unresolved | post-command, causa unresolved | Due channel ID furono allocati; la usability IQ simultanea non fu determinata. |
| `g0ghk.uk:8050` | rifiuto esplicito `badp=1` | rifiuto esplicito `badp=1` | La coppia fu rifiutata in quel tentativo. |
| `hill.n8ga.org:8073` | post-command, causa unresolved | post-command, causa unresolved | Due channel ID furono allocati; la usability IQ simultanea non fu determinata. |
| `kiwisdr2blair.ddns.net:8073` | post-command, causa unresolved | rifiuto esplicito `badp=5` | La coppia non fu ammessa; la capability generale resta indeterminata. |
| `kiwisdr.kfsdr.com:8074` | post-command, causa unresolved | rifiuto esplicito `badp=5` | La coppia non fu ammessa; la capability generale resta indeterminata. |
| `va6ok.ddns.net:8073` | post-command, causa unresolved | post-command, causa unresolved | Due channel ID furono allocati; la usability IQ simultanea non fu determinata. |

## Confine causale degli otto rami unresolved

Il transcript prova questo ordine:

```text
WebSocket aperto
→ auth inviata
→ sample rate osservato
→ channel ID osservato
→ BADP_OK osservato
→ mod_iq inviato localmente
→ traffico inbound hashato
→ close con payload vuoto
```

Non contiene `IQ_FRAME_OBSERVED`. Il confine osservato è quindi:

```text
AFTER_LOCAL_MOD_IQ_SEND_BEFORE_QUALIFYING_EVENT_TIME_IQ
```

`MOD_IQ_SENT` dimostra un send locale riuscito, non l'applicazione remota del
comando. I frame inbound non terminali esistono — fra 16 e 17 per ramo chiuso
dopo aver sottratto il close — ma il receipt conserva soltanto i loro hash
individuali, il conteggio e il totale byte. Non conserva il tag `MSG`/`SND` per
ciascun hash.

## Audit del predicate di readiness

Per un frame taggato `SND`, il runtime avrebbe eseguito:

```text
frame hash pre-analisi
→ decode header SND
→ verifica stereo IQ
→ decode samples temporanei
→ ricostruzione event time dai secondi GPS
→ gps_timestamp_available
→ gps_solution_age_s <= 30
→ IQ_FRAME_OBSERVED
```

Un errore di decode avrebbe terminato il ramo con quel tipo di errore, non con
`_ObservedWebSocketClose`. Ma il receipt non dice se un frame `SND` raggiunse
il decoder. Se lo raggiunse senza sollevare errori, non dice se fu escluso per
GPS seconds uguale a zero o solution age oltre 30 secondi. Queste possibilità
sono osservazionalmente equivalenti nel receipt conservato:

- nessun `SND` prima del close;
- uno o più `SND` decodificati, ma senza timestamp GPS ammesso;
- uno o più `SND` decodificati, ma oltre il limite di GPS solution age.

Non è quindi possibile scegliere fra esse. La grandezza del traffico inbound
non sostituisce il tag né l'esito delle clausole del predicate.

## Causal cut chiusi e ancora aperti

Chiusi dal receipt:

- il collegamento WebSocket fu aperto;
- arrivarono campi server sufficienti per osservare rate, allocation e
  `BADP_OK` nei rami unresolved;
- il comando `mod_iq` fu inviato localmente dopo quei witness;
- arrivarono frame poi hashati;
- il terminale era un close con payload vuoto;
- nessun evento superò il predicate completo di readiness.

Ancora aperti:

- tag di ciascun frame inbound hashato;
- presenza e numero di frame `SND`;
- GPS-seconds presence e solution age per eventuali `SND` scartati;
- applicazione remota del comando DDC;
- componente remota che originò il close;
- motivo software, policy, carico, protocollo, trasporto o hardware del close.

## Claim autorizzati

- Quattro rami ricevettero un rifiuto esplicito limitato al tentativo.
- Otto rami attraversarono il control path fino al send locale di `mod_iq`.
- Quegli otto rami terminarono con un close a payload vuoto prima di un witness
  IQ qualificante.
- Il `1005` registrato è un sentinel locale, non uno status remoto.
- Il receipt non permette di attribuire la causa del mancato ingresso nella
  readiness.
- Nessuna ipotesi DDC fu valutata.

## Claim non autorizzati

- Non arrivò alcun frame `SND`, byte IQ o campione.
- Arrivarono certamente frame `SND` scartati dal GPS predicate.
- GPS assente o stale causò il risultato.
- Il peer rifiutò o applicò il retune.
- Una particolare implementazione client/server, policy, frequenza o timeout
  causò il close.
- Gli endpoint unresolved non possiedono due stream IQ simultanei.
- Un rerun o una modifica del runtime risolverebbe la qualification.

## Cambiamento minimo che un futuro receipt richiederebbe

Non serve conservare RF. Prima di distruggere ogni frame, un eventuale futuro
receipt dovrebbe materializzare soltanto metadati categorici atomici:

```text
frame tag observed
→ SND decode accepted / typed decode failure
→ IQ-mode clause
→ GPS-seconds-present clause
→ GPS-age-within-limit clause
→ readiness admitted / not admitted
```

Ogni stato dovrebbe portare l'artifact hash pre-analisi già esistente. Questo
separerebbe `NO_SND_OBSERVED` da `SND_NOT_ADMISSIBLE` senza persistere payload,
sample, IQ, waterfall o feature. Non risolverebbe l'assenza di un ack remoto
per `mod_iq`, che deve restare una clausola distinta e non inventata.

Questo è un requisito concettuale emerso dal postmortem, non una modifica al
runtime congelato e non autorizza una nuova sessione.

## SHOCK

Hashare ogni artifact prima dell'analisi protegge integrità e provenienza, ma
non garantisce attribuibilità causale. Distruggendo insieme al payload anche la
classe del frame e l'esito di ogni clausola del predicate, il receipt ha
preservato “quali byte” in forma crittografica ma ha perso “quale trasformazione
li ha esclusi”.

La primitive sopravvissuta non è quindi “hashare tutto”. È:

```text
artifact hash + transizione semantica per clausola
```

Gate F2.5.11 si ferma qui. Non è autorizzato alcun rerun.
