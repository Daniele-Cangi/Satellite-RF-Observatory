# S2 — Risultati del ponte RINEX codice/fase dei riferimenti

Il ponte completo legge file RINEX sintetici senza Doppler, stima il clock
dai soli codici e controlla gli incrementi di fase inutilizzati nella stima.
Nel caso dichiarato rileva anche uno slip di un ciclo non segnalato dai flag.
Tutti i nove casi sono conservati e i tredici criteri dello studio passano.
Questo risultato resta sintetico: `real_rf_qualified=false` in tutti i casi.

## Disegno e risultati

Quattro riferimenti GPS, dodici estremi ogni 30 secondi e undici intervalli
producono 48 codici IF e 44 rate medi di fase. Il generatore inerziale S2b
fornisce i dati inventati; la navigazione contiene solo riferimenti ammessi
al calcolo, mentre il target resta escluso prima della decodifica numerica.
La propagazione validata è in vuoto. La covarianza dichiarata include rumore
di codice e fase, correlazione fra i due e condivisione degli estremi.

| Caso conservato | Esito |
| --- | --- |
| Nominale senza Doppler | Modello accettato |
| Ambiguità costanti aggiunte | Modello accettato; le differenze le cancellano |
| Slip L1 di un ciclo non segnalato | Residui di fase respinti |
| Slip segnalato | Finestra respinta prima del fit del clock |
| Fase mancante | Finestra respinta prima del fit del clock |
| Reset del clock | RINEX respinto |
| Salto di 300 m sui codici di un riferimento | Codici respinti, controllo di fase non eseguito |
| Navigazione obsoleta | Modello non disponibile |
| Deriva comune di fase di 0,001 m/s | Modello accettato: limite di sensibilità conservato |

Nel nominale l'errore di offset del clock è −0,000203416 m e quello del
drift −0,00000127797 m/s. Il massimo residuo di fase è 0,0000195919 m/s.
Il test dei codici usa 46 gradi di libertà, quello della fase 44, con soglia
marginale p < 0,01. Le fasi non stimano parametri del clock.

Lo slip non segnalato porta il massimo residuo a 0,0161449 m/s e viene
respinto; i coefficienti del clock rimangono identici a quelli nominali.
Il p-value numerico è azzerato per underflow, non è una probabilità fisica
letteralmente nulla. La piccola deriva comune porta il residuo massimo a
0,00102620 m/s e resta compatibile con l'incertezza dichiarata. Il controllo
non costituisce quindi un rilevatore universale di slip o bias.

## Verifica e provenienza

Passano **25 nuovi test** e la regressione completa di **215 test**. Fra i
controlli: esclusione di target e dati futuri, arresto prima del fit su dati
inammissibili, assenza di riadattamento del clock alle fasi e propagazione
della covarianza rettangolare verificata con 60.000 estrazioni Monte Carlo.
I sorgenti registrati nei sei studi precedenti correnti e nel nuovo studio
corrispondono ai rispettivi hash; nessuna evidenza precedente è modificata.

Il [report JSON immutabile](phase_reference_bridge_study_v1.json) conserva
ipotesi, ambiente, matrici, tutti gli esiti e hash dei sorgenti.

```text
SHA256 report:
4d900b7b4b5b1083a7cf0598f015c35fb984f6cd6b6e8b38c1eabc2bb3ea79e7
SHA256 testo osservazioni sintetiche:
1d6d5db4870fd36a2d179e8138a40c62c56c860d85509da0584a948db4723bdf
SHA256 testo navigazione sintetica:
0e3f16d82d3c59ee8247d23ce3f32c7c1603c7cbce89febccba9256e65f06ce4
```

Per riprodurre, dalla radice della repository:

```text
python -m pytest research/kinematic/tests/test_phase_reference_bridge.py -q
python -m research.kinematic.phase_bridge_study NUOVO_REPORT.json
```

Il writer rifiuta sovrascritture. Gli hash delle fixture rappresentano il
testo UTF-8 generato con terminazioni LF.

## Confine della conclusione e prossimo passo

È dimostrata la catena sintetica file → clock dai codici → previsione sugli
stessi intervalli → controllo indipendente dall'uso della fase nel fit.
Non sono dimostrate indipendenza statistica dei due test, copertura globale,
qualifica di ricevitori reali o una nuova posizione target.

Il prossimo passo è un estimatore inverso dedicato agli intervalli, con
covarianza completa fra codici, incrementi e calibrazione. I vecchi fit a
rate istantanei restano immutati. Qualifica RF, termini fisici variabili e
inviluppo totale degli errori devono precedere S3; sito e acquisizioni
target restano sospesi. Dettagli nel
[documento del modello](../S2_PHASE_REFERENCE_BRIDGE.md).
