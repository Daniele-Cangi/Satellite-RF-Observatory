# Margine temporale della sessione Android nativa

La sessione della prova A3 conserva un contributo NTS sullo scarto software
costante di **±100 ms**, anche nei casi ipotetici con associazione GNSS/contatore
di 10, 25 e 50 ms. La domanda era se il meccanismo dipendesse necessariamente
dall'assunzione storica di 1 ms. Su questo campione la risposta è no; nessuno
dei nuovi budget è però qualificato o scelto per l'uso operativo. Con
associazione ignota il confronto resta interamente insufficiente.

## Metodo e input

Replay esplorativo del 10 ottobre 2026, su dati già esposti nella prova di
import/export A3; nessuna nuova acquisizione, manipolazione RF o conferma.
Il [riepilogo completo](results/pnt_native_time_budget_envelope_v1.json)
conserva configurazione, hash degli originali, copertura, tutti gli scenari,
conteggi per endpoint e transizioni. Il motore è `e576d51`, main dopo la PR #200;
le sorgenti e i risultati degli studi precedenti restano invariati.

La raccolta appartiene al Galaxy S21 FE SM-G990B, Android 16. Contiene 14
callback, 373 Raw, 145 righe GPS normalizzate e 228 righe di altre costellazioni.
NTS conserva 20 slot: dieci autenticati e dieci non eseguiti alla chiusura
`ACTIVITY_STOPPED`. Non sono dieci timeout né una raccolta completata secondo
il calendario. I due endpoint PTB condividono la stessa autorità.

Prima di eseguire la matrice sono stati scritti cinque casi: associazione
ignota, 1, 10, 25 e 50 ms; per ciascuno zero e ±100 ms. È una configurazione
ordinaria di sviluppo, non una preregistrazione o una qualifica prospettica.
100 ms riprende la challenge software dello
[studio abbinato](PNT_PHONE_PAIRED_TIME.md); non è un requisito di una banca,
rete 5G o navigazione, né una promessa commerciale. La griglia ampia serve
a verificare una dipendenza del metodo, non a cercare il primo budget che
renda compatibile l'originale.

Restano fissi i parametri di sviluppo non calibrati: errore UTC del server
e GNSS di 1 ms ciascuno, deriva 100 ppm, risoluzione del contatore 1 ns e
bracket massimo 15 s. GPS-UTC è 18 s, da TAI-UTC = 37 s meno 19 s;
la [tabella IERS aggiornata al bollettino 72](https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat)
copre il giorno della registrazione. La risoluzione non prova l'accuratezza.
Ogni caso ricrea il confronto dagli stessi originali con assunzioni esplicite;
la challenge modifica solo l'UTC decodificato, con budget e ammissione fissi
**entro quel caso**. Non simula una falsificazione coerente di tutte le misure
RF/Raw. Fra casi, l'associazione varia deliberatamente: è una nuova analisi
condizionale, non una correzione dei risultati storici.

In tutti i 14 callback è dichiarata un'incertezza di associazione di circa
7,001 ms. L'[API Android](https://developer.android.com/reference/android/location/GnssClock#getElapsedRealtimeUncertaintyNanos())
la descrive come stima con confidenza del 68%. Non è usata come limite,
moltiplicata per un fattore gaussiano o stimata dall'accordo con NTS.
Anche i ritardi delle callback non sono usati come limiti dell'epoca GNSS.

## Risultati e casi sfavorevoli

I gruppi nella tabella distinguono gli stessi metadati clock riportati dal
ricevitore, non campioni indipendenti: le 145 righe GPS condividono 14 gruppi.
Le transizioni e i conteggi per riga restano nel riepilogo. Non si calcolano
percentuali di rilevamento RF o falsi allarmi dal numero di satelliti.

| Associazione ipotetica | Gruppi abbinati / totali | Originale: solo locale discordante | Originale: nessuno discordante | ±100 ms: solo NTS discordante | ±100 ms: entrambi discordanti |
|---|---:|---:|---:|---:|---:|
| Ignoto | 0 / 14 | 0 | 0 | 0 | 0 |
| 1 ms | 12 / 14 | 5 | 7 | 7 | 5 |
| 10 ms | 12 / 14 | 0 | 12 | 12 | 0 |
| 25 ms | 12 / 14 | 0 | 12 | 12 | 0 |
| 50 ms | 12 / 14 | 0 | 12 | 12 | 0 |

Con ciascun limite finito rimangono 19 righe/due gruppi insufficienti nel
confronto abbinato; le 126 righe/12 gruppi restanti hanno supporto. Con limite
ignoto sono insufficienti tutte le 145 righe/14 gruppi, anche dopo lo scarto.
Le categorie per gruppo possono sovrapporsi in altri dataset: non vanno
sommate come categorie esclusive. Su questo campione non si sovrappongono.

Il caso da 1 ms conserva **52 righe/cinque gruppi** localmente discordanti
nell'originale. Passano a discordanza di entrambi i canali dopo ±100 ms; non
sono nuovi allarmi locali prodotti dalla challenge. Gli scenari più larghi
rendono quelle righe compatibili, ma questo non dimostra che l'originale sia
benigno, che 10 ms sia corretto o che i falsi allarmi siano risolti.

Gli scarti costanti si cancellano nel controllo locale relativo; NTS aggiunge
informazione sull'origine UTC. L'inviluppo degli scarti ancora compatibili
con almeno un confronto esterno è conservato per ogni scenario nel JSON.
È l'inviluppo del campione, con budget ipotetici e righe escluse visibili;
non è una soglia garantita per altri telefoni o condizioni di rete.

## Decisione e riproduzione

Il margine osservato giustifica continuare a studiare errori dell'ordine di
100 ms senza imporre artificiosamente precisione sub-millisecondo. Non
giustifica adottare un budget da questa matrice. **P2/P3 restano aperte.**
Il limite da risolvere è un modello di associazione GNSS/CLOCK_BOOTTIME
difendibile indipendentemente dall'accordo di questo log, insieme agli altri
budget e alla verità di riferimento per baseline/challenge. La stima Android
al 68% da sola non specifica le code della distribuzione o un limite massimo.
Se quel modello non è disponibile, la promessa resta una diagnostica
condizionale: ripetere questa matrice o un'altra raccolta equivalente non
chiuderebbe la qualifica. Nessun budget viene promosso nell'app.

I dieci rapporti completi sessione/sensibilità e gli originali restano nel
fascicolo privato sul PC. Il riepilogo pubblico non è un corpus pubblico
integralmente riproducibile senza gli input privati. Sullo stesso ZIP,
con la configurazione del riepilogo, le API esistenti riproducono ciascun caso:

```python
import json
from pathlib import Path
from pnt.android_session import inspect_android_session
from pnt.time_sensitivity import assess_time_sensitivity

summary = json.loads(Path(
    "research/exploratory/results/pnt_native_time_budget_envelope_v1.json"
).read_text())
config = summary["configuration"]
for bound in config["alignment_cases_ns"]:
    options = config["fixed_options"] | {
        "epoch_alignment_error_ns": bound,
        "epoch_alignment_source": None if bound is None else
            "Hypothetical envelope case; not calibrated or fitted to this capture",
    }
    session = inspect_android_session("session.zip", analysis_options=options)
    sensitivity = assess_time_sensitivity(
        session["comparison"], [-100000000, 100000000],
        local_counter_resolution_ns=1,
    )
    assert sensitivity["baseline"] == session["comparison"]
    print(bound, [case["paired_pattern_counts"]
                  for case in sensitivity["offset_cases"]])
```

La verifica locale ha riprodotto esattamente tutti e cinque i confronti tramite
`compare_receiver_capture`, oltre al baseline di sensibilità, mantenendo
intake e testimone originali identici fra scenari e hash del ZIP invariato.
Non sono cambiati motore, criteri operativi, app, CI o risultati chiusi.
