# S2a — Prima verifica del modello fisico

**Report corrente:** `receiver_time_study_v2.json`. Il caso rumoroso termina
alla calibrazione respinta; nessun fit o previsione esclusa viene eseguito.
Il primo report è conservato come diagnostica di un difetto del runner,
corretto senza cambiare seme, dati o soglie. Vedere l'audit sotto.

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
| Rumore correlato, seme 20260910 | Calibrazione respinta, p = 0,00123 | Non stimata | Non prevista |
| Jerk non modellato | Respinto, p = 3,94 × 10⁻²⁷ | 111,269 m | +20,248 m |
| Salto non segnalato di 300 m su un codice | Respinto, p = 6,61 × 10⁻⁵⁵ | 1939,436 m | −17,043 m |

Gli errori dei casi respinti sono diagnostici, non predizioni accettate. Il
salto d'orologio mostra ancora che un residuo contenuto su un ricevitore escluso
può accompagnare un errore di posizione grande. Il controllo va effettuato
sull'insieme delle misure e del modello, non su un solo residuo favorevole.

Il caso rumoroso non produce una prestazione ammissibile. Anche in una
simulazione con modello noto, un controllo statistico può respingere una
realizzazione del rumore; il risultato non autorizza a cambiare seme o soglia.
Una sola replica non misura copertura o frequenza dei fallimenti.

Nel caso senza rumore, con le scale di incertezza dichiarate comunque presenti
nel fit, il raggio locale condizionale a +60 s è 1862,217 m; quello di velocità
a fine arco è 3,743 m/s. Non includono un inviluppo completo di errori sistematici.
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

Tutti i nove controlli dello studio aggiornato sono soddisfatti, compresa la
precedenza del rifiuto di calibrazione; non significa che tutti i casi siano
accettati. Ventuno nuovi test coprono
generatore indipendente, stima, clock, Doppler, quantizzazione RINEX, covarianze,
esclusione del bersaglio, tempi a cavallo di giorno/settimana e casi respinti.
La suite locale comprende 100 test superati, incluse le regressioni esistenti.
La CI della repository include già tutti i test di `research/kinematic/tests`.

I sorgenti del riferimento RF v1 e i risultati S0/S1 non sono modificati.
Le impronte dello studio S1 e del report S2a corrente coincidono con i file
locali; i sorgenti del primo report S2a restano nella storia Git.

Dati correnti: [receiver_time_study_v2.json](receiver_time_study_v2.json).
SHA-256 del report:

```text
f9d9303e563caabf5e004b2d4da505b2c77603adae186d3dad5225ae15c3d104
```

Il JSON conserva parametri, tutti i fit e le covarianze, tutte le predizioni,
gli esiti sfavorevoli, runtime e impronte. Il comando di riproduzione rifiuta
di sovrascrivere un report esistente. Non è una preregistrazione pubblica.

## Audit della correzione del runner

Nel [primo report](receiver_time_study_v1.json), la quinta calibrazione del
caso rumoroso ha p = 0,001233, sotto la soglia dichiarata di 0,01. Il runner
continuava e produceva un fit apparentemente accettato, con errore di circa
110 m a +60 s. Quel valore resta solo una diagnostica non ammissibile.

I sorgenti di quell'esecuzione sono nel commit `5f2a922`; il JSON originale
resta invariato, con impronta `99ff17dc…99a12`. I sorgenti RF v1 importati
possono avere terminatori diversi nel checkout Windows e nel blob Git, come
già documentato per S1. I nuovi sorgenti di ricerca conservano i byte in Git.

La seconda esecuzione corregge esclusivamente l'ordine di ammissione. Mantiene
gli stessi quattro casi, seme, rumori, soglie e budget; aggiunge un controllo
di regressione che impedisce fit e previsione dopo un rifiuto di calibrazione.
Non è una nuova conferma né una modifica del disegno per ottenere un successo.

## Prossima consegna S2b

Collegare l'importazione RINEX alla qualificazione delle convenzioni reali
dei ricevitori e alla produzione dei residui dei soli riferimenti. Completare
propagazione, correlazioni condivise e inviluppo dell'errore inverso prima di
ammettere una campagna. Il dettaglio operativo è in [S2_MODEL.md](../S2_MODEL.md).
S2a non autorizza acquisizioni S3 né riapertura degli eventi chiusi.
