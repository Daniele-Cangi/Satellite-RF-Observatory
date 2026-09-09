# S2a — Prima verifica del modello fisico

**Audit del primo report:** `receiver_time_study_v1.json` conserva un difetto
del runner: nel caso rumoroso la quinta calibrazione viene respinta, ma il
fit successivo viene comunque eseguito. Il suo esito accettato è soltanto
diagnostico e non costituisce un caso ammissibile. Gli otto controlli numerici
non verificavano la precedenza del rifiuto della calibrazione. Questa versione
viene conservata con i sorgenti per rendere riproducibile la correzione; il
prossimo report deve interrompere quel caso mantenendo seme e soglie invariati.

Esecuzione del 10 settembre 2026. Consegna di sviluppo sintetico: nessun nuovo
dato RF, nessuna orbita reale e nessuna conferma satellitare. S2 resta aperto;
sito, API, Docker e hosting restano sospesi.

## Che cosa è stato costruito

Il nuovo modello ricostruisce posizione, velocità, accelerazione e orologio
del trasmettitore usando tempi marcati dai ricevitori. Risolve separatamente
ricezione ed emissione, applica la rotazione terrestre durante il volo e
include la deriva degli orologi nella derivata delle osservazioni.

La calibrazione sintetica dei ricevitori usa soli residui etichettati come
riferimenti non bersaglio. Offset e derive entrano nel fit con covarianza,
insieme a rumore correlato nel tempo, tra stazioni e tra codice e variazione.
Un adattatore separato converte campi GPS C1C/C2W/D1C/D2W e conserva la
covarianza; campi mancanti e problemi di aggancio hanno esiti espliciti.

Equazioni, convenzioni, fonti e requisiti ancora aperti:
[S2_MODEL.md](../S2_MODEL.md). Questa è una validazione nel vuoto, non una
pipeline RINEX completa o un nuovo estimatore RF qualificato.

## Controllo fisico indipendente

Il generatore ruota separatamente trasmettitore e ricevitore in assi inerziali,
risolve la radice del tempo di volo e differenzia numericamente il codice.
Il modello verificato lavora in assi terrestri con derivata implicita.

| Controllo | Risultato |
|---|---:|
| Differenza massima fra i codici dei due calcoli | 1,12 × 10⁻⁸ m |
| Differenza massima fra le variazioni | 9,01 × 10⁻⁸ m/s |
| Errore massimo sul codice omettendo la rotazione | 34,782 m |
| Tempo di volo del segnale nella simulazione | 67,552–79,458 ms |

Le prime due differenze misurano accordo numerico fra implementazioni sotto
le stesse ipotesi fisiche; non sono precisioni ottenute su un satellite.
La prova senza rumore recupera la posizione a +60 s con errore 0,000128 m,
entro il criterio di sviluppo di 0,1 m, e la velocità entro 0,001 m/s.

## Tutti i quattro casi

Stesso arco di undici tempi da −300 a 0 s e stesse sette stazioni sintetiche.
Ottava stazione esclusa; predizioni a 0, +30 e +60 s improntate prima della
generazione della conferma. L'orologio della stazione esclusa è noto nella
simulazione. Nessun caso viene scartato dal report.

| Caso | Controllo residui | Errore di posizione a +60 s | Residuo codice escluso a +60 s |
|---|---|---:|---:|
| Senza rumore | Accettato condizionatamente | 0,000128 m | 0,000003 m |
| Rumore correlato, seme 20260910 | Accettato condizionatamente, p = 0,265 | 109,989 m | +3,404 m |
| Jerk non modellato | Respinto, p = 3,94 × 10⁻²⁷ | 111,269 m | +20,248 m |
| Salto non segnalato di 300 m su un codice | Respinto, p = 6,61 × 10⁻⁵⁵ | 1939,436 m | −17,043 m |

Gli errori dei casi respinti sono diagnostici, non predizioni accettate. Il
salto d'orologio mostra ancora che un residuo contenuto su un ricevitore escluso
può accompagnare un errore di posizione grande. Il controllo va effettuato
sull'insieme delle misure e del modello, non su un solo residuo favorevole.

Nel caso rumoroso il raggio locale condizionale di posizione al 95% a +60 s
è 1862,231 m; quello di velocità a fine arco è 3,743 m/s. Non includono un
inviluppo completo di errori sistematici. Una sola replica non misura copertura
e il suo errore di 110 m non è confrontabile come mediana con i 20 casi S1.
Il maggiore realismo del modello non implica da solo un guadagno di precisione.

## Limite che decide il prossimo lavoro

Per il jerk di stress dichiarato, includendo 0,1 s prima del primo campione
per coprire l'emissione, il resto di Taylor può raggiungere 521,434 m in
posizione e 5,213 m/s in velocità. Supera i budget di sviluppo di 20 m e
0,05 m/s: il modello quadratico non è automaticamente adeguato a cinque minuti.

Questo è un limite sulla rappresentazione Taylor, non sull'errore inverso del
fit. Non giustifica abbassare un'incertezza o cambiare arco dopo la conferma.
Prima di S3 servono una scelta preventiva dell'ordine/arco e la propagazione
del difetto di modello nell'incertezza della soluzione.

## Verifiche e provenienza

Tutti gli otto criteri dello studio sono soddisfatti. Venti nuovi test coprono
generatore indipendente, stima, clock, Doppler, quantizzazione RINEX, covarianze,
esclusione del bersaglio, tempi a cavallo di giorno/settimana e casi respinti.
La suite locale comprende 99 test superati, incluse le regressioni esistenti.
La CI della repository include già tutti i test di `research/kinematic/tests`.

I sorgenti v1 e i risultati S0/S1 non sono modificati. Le impronte dei sorgenti
registrate sia nello studio S1 sia in quello S2a coincidono con i file locali.

Dati: [receiver_time_study_v1.json](receiver_time_study_v1.json).
SHA-256 del report:

```text
99ff17dca9010b4eb3c9d4f61e42c13160a8a09cd05514e6514d3592df499a12
```

Il JSON conserva parametri, tutti i fit e le covarianze, tutte le predizioni,
gli esiti sfavorevoli, runtime e impronte. Il comando di riproduzione rifiuta
di sovrascrivere un report esistente. Non è una preregistrazione pubblica.

## Prossima consegna S2b

Collegare l'importazione RINEX alla qualificazione delle convenzioni reali
dei ricevitori e alla produzione dei residui dei soli riferimenti. Completare
propagazione, correlazioni condivise e inviluppo dell'errore inverso prima di
ammettere una campagna. Il dettaglio operativo è in [S2_MODEL.md](../S2_MODEL.md).
S2a non autorizza acquisizioni S3 né riapertura degli eventi chiusi.
