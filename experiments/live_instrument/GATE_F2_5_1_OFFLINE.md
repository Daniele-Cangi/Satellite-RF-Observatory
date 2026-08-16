# Gate F2.5.1 — bootstrap diretto SND, esclusivamente offline

Stato: **PREPARATO E CONGELABILE; NESSUNA ESECUZIONE LIVE**.

Questo gate corregge un solo taglio causale emerso dal primo outcome F2.5. Il
runtime e l'outcome congelati di F2.5 restano immutati: il loro
`QUALIFICATION_INCOMPLETE` continua a descrivere correttamente una sessione in
cui nessun canale SND fu tentato.

## Correzione minima

F2.5 chiedeva a `/status` il campo `bandwidth` prima di poter scegliere la
coordinata del primo tentativo SND. I sei status live non materializzarono quel
campo. F2.5.1 sostituisce quella precondizione descrittiva con un'invariante
congelata e circoscritta alla famiglia Kiwi già selezionata:

- intervallo bootstrap: 0–30 MHz;
- intervallo interno di selezione: 7,5–22,5 MHz;
- coordinata deterministica derivata dall'identità dell'endpoint;
- ruolo: `QUALIFICATION_BOOTSTRAP_ONLY`;
- `status.bandwidth`: non richiesto e non usato;
- `ext_api`: `DESCRIPTIVE_HINT_ONLY`;
- W/F: `ABSENT_FROM_CAUSAL_PATH`.

La coordinata non è un target, non identifica un trasmettitore e non è la
feature dell'esperimento. Serve soltanto a formulare una richiesta SND interna
alla banda della famiglia già congelata. Il fatto che il client chieda quella
coordinata non dimostra che il server l'abbia accordata o abbia consegnato
campioni: apertura, sequence, timestamp e IQ devono ancora testimoniarlo.

## Base dell'invariante

L'invariante non pretende di descrivere ogni radio Internet. È limitata ai
candidati Kiwi e alla loro implementazione già congelati nel repository:

1. `CHECKPOINT_1.md` registra uno status Kiwi live 0–30 MHz e una acquisizione
   IQ riuscita a 10 MHz;
2. il client congelato in `kiwi_gate_f2.py` inizializza a 30 MHz la stessa
   famiglia di protocollo e sostituisce quel valore solo quando l'handshake
   W/F espone `bandwidth`;
3. `GATE_F2_5_OUTCOME_1.md` dimostra che trasferire quell'informazione in
   `/status` era una precondizione non materializzabile, non un rifiuto SND.

Questa è una politica bootstrap conservativa, non una misura live della banda.
Se il server rifiutasse il tuning o non producesse IQ valido, il receipt del
tentativo diretto descriverebbe quel fatto senza reinterpretare l'invariante.

## Percorso causale risultante

```text
affordance e candidati congelati
  -> status/accesso opzionale e descrittivo
  -> coordinata bootstrap indipendente dallo status
  -> tentativo simultaneo SND reference + perturbed
  -> ammissione della topologia dai due stream reali
  -> discovery STFT/PSD locale in RAM
  -> feature + witness
  -> qualification del retune per-canale
  -> plan freeze
  -> A1 / B / A2
  -> un outcome e stop
```

Topologia multicanale, feature discovery e qualification del retune restano
tre fasi distinte. Nessuna feature o soglia viene valutata prima che i due
stream siano ammessi. `NO_MULTI_CHANNEL_CAPABILITY` resta autorizzato soltanto
dopo un vero tentativo del secondo canale; timeout e errori software restano
`QUALIFICATION_INCOMPLETE`.

## Lineage e invarianti congelati

- runtime F2.5 padre:
  `14000c285aa7a427c52befbadbd8631e8adc484a`;
- outcome F2.5 padre:
  `dd713e993df40e35c23fadbf824e2df193b0aef7`;
- transform F2.5.1:
  `gate-f2.5.1-protocol-invariant-bootstrap-v1`;
- center policy:
  `kiwi-0-30mhz-interior-endpoint-hash-v2`;
- candidate set, ordine, retry budget, phase order e domanda fisica: invariati;
- retry post-freeze: zero;
- persistenza IQ, RF, waterfall o STFT: zero.

Il bootstrap receipt lega esplicitamente entrambi i commit padre, la policy,
l'invariante, il candidate-set hash e il transform ledger. Il runtime F2.5 è
riusato tramite due soli punti di iniezione locali: receipt bootstrap e
funzione di qualification diretta. Non è stato creato un framework generale.

## Verifica offline

I test dimostrano che:

- status senza `bandwidth`, malformato o con valori arbitrari non può impedire
  la chiamata fisica `_open_dual()`;
- nessun valore di `ext_api` può evitare il tentativo diretto;
- W/F e la vecchia automatic-center transform sono assenti dal modulo;
- l'implementazione F2.5 originale continua a riprodurre il proprio failure;
- un timeout dopo il tentativo resta errore di qualification;
- un rifiuto esplicito dopo entrambi i tentativi può sostenere
  `NO_MULTI_CHANNEL_CAPABILITY` per quel candidato;
- bootstrap e receipt attraversano la serializzazione JSON rigorosa.

Nessun test effettua rete. Nessuna nuova osservazione, connessione Kiwi o
acquisizione è stata eseguita in Gate F2.5.1. Il gate si ferma prima della
singola sessione live, che richiede autorizzazione separata.
