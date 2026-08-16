# Gate F2.5 — primo e unico outcome live

Stato: **STOP**. È stata eseguita una sola sessione dal runtime congelato nel
commit locale `14000c285aa7a427c52befbadbd8631e8adc484a`. Non sono state
aperte nuove sorgenti, finestre o esecuzioni. Nessun push o PR.

## Outcome terminale

`QUALIFICATION_INCOMPLETE`

Il risultato è descrittivo, non fisico. Tutti i sei endpoint hanno restituito
`/status`, ma nessuno ha raggiunto il tentativo diretto dei due canali SND. La
policy di centro richiedeva il campo `bandwidth` nello status HTTP; quel campo
non era presente in nessuna delle sei risposte e `center_from_status()` ha
fermato ogni candidato prima di `_open_dual()`.

Di conseguenza non è autorizzato `NO_MULTI_CHANNEL_CAPABILITY`: i receipt
registrano esplicitamente `direct_reference_attempted = false` e
`direct_perturbed_attempted = false` per tutti i candidati.

## Bootstrap congelato prima della rete

- start: `2026-08-16T17:09:54.388256Z`;
- runtime commit: `14000c285aa7a427c52befbadbd8631e8adc484a`;
- bootstrap receipt hash:
  `5be2daad20566351ca7240ebd56ffa112da394cf4ca0c4a2abe329a8d0cec994`;
- candidate-set hash:
  `b5a4b7e133f10bcf019481e62ceae6c168aa8fd55aecb3601575e7b581c663d7`;
- retry budget: due complessivi, massimo uno per endpoint;
- center policy: `advertised-band-interior-endpoint-hash-v1`;
- `ext_api`: `DESCRIPTIVE_HINT_ONLY`;
- W/F: `OPTIONAL_AND_OUTSIDE_CAUSAL_PATH`;
- phase order: direct dual-SND, local IQ discovery, retune qualification,
  plan freeze, one confirmation.

La sessione è terminata a `2026-08-16T17:10:05.274510Z`, circa 10,9 secondi
dopo il bootstrap. Non è stato consumato alcun retry: la mancanza del campo
richiesto dalla policy congelata non apparteneva alle classi retryable e un
retry non avrebbe potuto cambiare la descrizione richiesta.

## Candidati

| Endpoint | Status hash | `ext_api` hint | Error hash | Dual-SND attempted |
|---|---|---:|---|---|
| `dl1bajkiwisdr.ddns.net:8074` | `fb353ac2…efd89` | 4 | `052a226e…bb8d7c` | no |
| `g0ghk.uk:8050` | `f334897d…75582` | 4 | `2a605244…83c4` | no |
| `hill.n8ga.org:8073` | `2c2143df…c282a` | 4 | `4cfe286b…9a4a6` | no |
| `kiwisdr2blair.ddns.net:8073` | `3de8e2d9…22af5e` | 3 | `41830bd7…e24268` | no |
| `kiwisdr.kfsdr.com:8074` | `23114924…a8c2` | 6 | `9adf90ca…3ce1b8` | no |
| `va6ok.ddns.net:8073` | `e3b9351f…1681ea` | 4 | `119474f1…01280a` | no |

Gli hint dimostrano che `ext_api` è stato letto e non usato come gate. Non
dimostrano slot SND liberi. Nessun endpoint è stato rifiutato in base al valore
di `ext_api`.

## Failure attribution

### Valutato

- accesso e parsing di sei documenti `/status`;
- hashing di ogni status prima della descrizione;
- presenza e parsing non-gating di `ext_api`;
- applicazione immutata della center policy congelata.

### Errore software/contrattuale

`center_from_status()` assumeva che `/status` contenesse `bandwidth`. Il codice
preesistente mostra invece che i percorsi Kiwi precedenti acquisivano
`bandwidth` dal messaggio WebSocket di handshake W/F, con un default locale di
30 MHz. Gate F2.5 ha eliminato correttamente W/F dal causal path, ma ha
trasferito accidentalmente una sua informazione di handshake dentro una
precondizione dello status HTTP.

Questa è una trasformazione/policy non materializzabile con i receipt live,
non evidenza che la banda del ricevitore sia sconosciuta in assoluto e non
evidenza contro la capability SND.

### Non valutato

Per ciascun endpoint sono `NOT_EVALUATED`:

- apertura del canale SND reference;
- tentativo e apertura del secondo canale SND perturbed;
- due IQ simultanei e channel ID distinti;
- event time, sequence, continuità, sample clock e overflow;
- STFT/PSD locale, target e witness;
- retune per-canale e isolamento del reference;
- plan freeze e confirmation A1/B/A2;
- entrambe le ipotesi sul boundary DDC.

## Artifact e persistenza

Sono presenti dodici hash: sei status e sei descrizioni dell'errore. Non
esistono SND/IQ artifact hash, segment receipt, intervention receipt,
measurement root o `plan_hash`.

Persistenza RF:

- IQ: zero;
- waterfall remota: zero richieste;
- STFT/PSD locale: zero;
- campioni o frame: zero;
- database/storage RF: assente.

## Claim autorizzati

- Il bootstrap è stato emesso dal commit congelato prima della rete.
- Tutti i sei endpoint hanno risposto a `/status` nella singola sessione.
- `ext_api` è rimasto un hint e W/F non è stata richiesta.
- La center policy non era materializzabile dai sei status ricevuti.
- Nessun canale SND è stato tentato; la capability multicanale resta
  indeterminata.
- Tutte le clausole fisiche downstream sono `NOT_EVALUATED`.
- Non sono stati acquisiti o persistiti dati RF.

## Claim non autorizzati

- I sei endpoint non supportano due canali.
- Uno o due slot SND erano o non erano disponibili.
- La banda fisica dei ricevitori è ignota o incompatibile.
- `ext_api` descrive correttamente la disponibilità corrente.
- La topologia same-Kiwi è inammissibile.
- Il retune per-canale non funziona.
- Una feature è upstream o downstream del DDC.
- Esiste un segnale RF esterno, una sorgente identificata o una causa fisica
  comune.

## SHOCK

Rimuovere W/F non è sufficiente se un'informazione ottenuta storicamente dal
suo handshake viene reintrodotta come requisito dello status. Il nuovo gate
era più sottile ma causalmente equivalente: la prova diretta dual-SND era
ancora subordinata alla conoscenza preliminare della banda.

Il prossimo cambiamento minimo, esclusivamente offline, dovrebbe eliminare la
necessità di conoscere la banda prima dell'apertura SND. Il centro iniziale
deve derivare da un'invariante già congelata e verificabile nel protocollo, o
essere negoziato/testimoniato dal medesimo handshake SND che costituisce la
capability. Non serve reintrodurre W/F, consultare nuovi endpoint o modificare
la domanda fisica.

Gate F2.5 outcome 1 si ferma qui. Il runtime non viene corretto o rilanciato in
questo passaggio.
