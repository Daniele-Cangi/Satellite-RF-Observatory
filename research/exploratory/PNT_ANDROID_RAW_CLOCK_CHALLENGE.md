# Challenge Android Raw: origine GPS e trasmissione spostate insieme

La rete NTS distingue uno scarto di **±100 ms** anche quando il clock GPS e il
tempo di trasmissione vengono modificati insieme, lasciando invariati gli
pseudorange del parser. Il controllo locale di continuità relativa rimane
invariato. È un risultato condizionale su dati esposti, **non una prova RF**.

## Domanda e metodo

La prova dell'11 ottobre 2026 riusa tutte le tre
[sessioni di valutazione](PNT_ANDROID_SESSION_EVALUATION.md) e la
[sessione 0.4.2](PNT_ANDROID_NTS_COVERAGE.md), senza nuove raccolte o selezione
per esito. Il [riepilogo pubblico](results/pnt_android_raw_clock_challenge_v1.json)
conserva digest, profilo, denominatori, casi insufficienti e verifiche. I file
originali e il replay completo restano nel fascicolo privato sul PC; senza
questi input non si possono riprodurre integralmente le osservazioni.

Il motore `7aebbb9edc9f32d1d00c63674ac3bba169ec5551` estende il comando esistente:

```console
python -m pnt time-sensitivity session-1-report.json session-2-report.json session-3-report.json coverage-report.json --android-raw-clock-offset-ns -100000000 --android-raw-clock-offset-ns 100000000 --local-counter-resolution-ns 1 --output raw-clock-summary.json
```

Per ciascuna riga GPS normalizzata, `FullBiasNanos -= offset` sposta la ricezione
GPS e `ReceivedSvTimeNanos = (ReceivedSvTimeNanos + offset) % GPS_WEEK_NS`
sposta la trasmissione. Il parser esistente verifica lo scarto del clock e
l'identico pseudorange. Il controllo zero conserva esattamente i campi originali.
BOOTTIME, timestamp di callback, NTS, fine bias, ADR, rate e budget non cambiano.
Righe non utilizzabili restano inalterate; le altre costellazioni restano negli
originali e nella copertura dell'intake, senza diventare parte della challenge.
Non si modella un ricevitore completo.

Si riusano l'adattatore UTC, il confronto NTS e il controllo locale. L'ammissione
e la segmentazione vengono ricalcolate dai claim derivati: nessun forcing dei
verdetti o fallback quando un claim diventa invalido. Il supporto comune è quello
del caso zero, senza selezione in base agli allarmi. I capture derivati conservati
si rigiocano con lo stesso motore; `original_source` identifica i byte acquisiti,
non un log sintetico prodotto dal telefono.

Il profilo rimane quello storico: associazione **25 ms**, UTC **1 ms**, errore
server **1 ms**, rate **100 ppm**, risoluzione dichiarata **1 ns**, bracket
massimo **15 s**. Sono assunzioni non qualificate, non valori calibrati o adottati
nell'app. I due scarti sono gli stessi delle prove precedenti, senza nuova
matrice di budget.

## Risultato

Tutte le **1.446 righe GPS**, per ciascun segno, conservano il loro pseudorange.
Il supporto comune comprende **560 righe e 65/156 gruppi clock**:

| Scarto GPS/trasmissione | Locale, gruppi comuni | NTS, gruppi comuni | Combinato, gruppi comuni |
|---|---:|---:|---:|
| Zero | 65 non distinguibili | 65 non distinguibili | 65 non distinguibili |
| −100 ms | 65 non distinguibili | 65 discordanti | 65 discordanti |
| +100 ms | 65 non distinguibili | 65 discordanti | 65 discordanti |

I denominatori comuni delle quattro sessioni sono rispettivamente **3/48,
18/31, 26/38, 18/39**. Il combinato conserva **91 gruppi / 886 righe insufficienti**.
I 80 slot NTS conservano 57 scambi autenticati e **23 timeout**. Nessun fallimento
viene rimosso. Sul supporto proprio, il locale valuta 152 gruppi, NTS 68 e il
combinato 65. Gli originali valutabili non mostrano discordanza, ma non sono
baseline benigne certificate e non stimano un tasso di falsi allarmi.

Gli esiti abbinati coincidono con quelli degli scarti applicati all'UTC già
decodificato, sotto il medesimo profilo. Il nuovo risultato è che l'effetto
sopravvive alla modifica dei campi Raw mantenendo il codice misurato invariato;
non è un aumento di prestazioni o copertura. Digest degli originali verificati,
replay dei derivati coincidente, precedenti rapporti costanti e di deriva
riprodotti senza modifiche. Il comando termina con codice 0. La suite PNT e
il controllo di provenienza passano con 869 test e sei verifiche native saltate;
i 20 test mirati finali passano separatamente. CI Linux/Windows invariata.

## Significato e limite successivo

Il canale Internet aggiunge un'origine temporale esterna che il solo controllo
locale relativo non possiede, purché BOOTTIME e NTS rimangano fidati e i budget
siano giustificati. Preservare gli pseudorange non preserva automaticamente la
geometria orbitale all'epoca spostata, i messaggi di navigazione o la coerenza
RF completa. Non è misurata latenza live; gli scambi NTS futuri possono servire
al confronto offline.

La prova non qualifica l'associazione GNSS/BOOTTIME, non copre un'app o sistema
operativo compromesso e non autentica RF o posizione. **P2 fisica e P3 restano
aperte.** Per avanzare oltre questa dimostrazione software servono un confine
temporale indipendente documentato e un caso benigno/challenge verificabile nel
modello di attacco scelto. Ripetere acquisizioni equivalenti o cambiare budget
per ottenere più gruppi non risolve questi limiti. Il sito segue la validazione.
