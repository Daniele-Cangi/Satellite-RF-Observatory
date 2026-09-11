# Prima consegna scientifica: diagnosi e cinematica sintetica

10 settembre 2026. Progetto: `docs/SCIENTIFIC_ROADMAP.md`, dichiarato nel commit
`0965c86`. Sono stati eseguiti S0 e il protocollo nominale/stress di S1.
Non sono state acquisite osservazioni RF nuove o aperte nuove orbite bersaglio.
La versione reale v1 e i cinque esperimenti conclusi sono conservati.

## S0 — Limite geometrico nelle soluzioni già rivelate

L'esportatore verifica le ricevute disponibili; la diagnosi legge le covarianze
congelate senza eseguire di nuovo il risolutore.

| Evento | Assi locali a 1 sigma, metri | Rapporto asse maggiore/minore | Allineamento asse debole/direzione geocentrica |
|---|---|---|---|
| G12, 5 settembre | 52,51; 175,59; 1998,81 | 38,06 | 0,99929 |
| G14, 3 settembre | 66,59; 107,74; 1070,06 | 16,07 | 0,99670 |

L'allineamento è il valore assoluto del prodotto scalare di due versori: uno
indica allineamento completo. In entrambi i casi l'asse meno vincolato è quasi
radiale. Questo suggerisce di studiare l'informazione aggiunta dal movimento;
non attribuisce da solo il problema a una singola fonte di errore.

Per G14 restano 2991,96 m di estensione statistica e 2489,14 m di spostamento
massimo nei bias campionati, con margine 1,05: raggio condizionale 5755,16 m.
Non sono errori reali osservati. G08 non ha una covarianza completa nel set di
ricevute consultato e resta senza questa decomposizione; gli altri due tentativi
non hanno una posizione. Nessun dato mancante è stato ricostruito o inventato.

## S1 — Vantaggio nominale della nuova osservabile ideale

20 repliche accoppiate, rumore codice 20 m e rumore del tasso di pseudodistanza
0,05 m/s, entrambi indipendenti e dichiarati nella simulazione. Le due varianti
usano gli stessi codici e lo stesso modello quadratico a 11 parametri. Le sette
stazioni del fit e l'ottava esclusa sono sintetiche.

| Metrica | Solo codice | Codice e variazione |
|---|---:|---:|
| Fit nominali finiti | 20/20 | 20/20 |
| Controllo residui nominale accettato | 20/20 | 20/20 |
| Errore mediano di posizione a +60 s | 606,67 m | 228,26 m |
| Raggio locale mediano 95% di posizione a +60 s | 2264,96 m | 1054,35 m |
| Raggio locale mediano 95% di velocità a fine fit | 9,78 m/s | 2,26 m/s |

Il rapporto degli errori mediani a +60 s è 2,66; quello dei raggi locali di
velocità è 4,33. Queste sono prestazioni della simulazione e non del software
su misure GPS reali. L'incertezza locale usa rumori noti e non contiene un
inviluppo di errori sistematici paragonabile a quello di G14.

Entrambe le varianti recuperano il caso senza rumore entro 0,1 m e 0,001 m/s,
con margine ampio. Tutti i criteri nominali dichiarati sono soddisfatti. La
prova non misura copertura statistica generale né confronta direttamente il
prototipo con l'intera pipeline RF v1.

## Le prove sfavorevoli e ciò che insegnano

| Caso | Solo codice | Codice e variazione | Implicazione |
|---|---|---|---|
| Rete concentrata | Ambigua; errore diagnostico +60 s circa 377 km | Ambigua; circa 247 km | Aggiungere una misura non risolve ogni geometria |
| Moto lineare su verità accelerata | Modello respinto | Modello respinto | L'accelerazione non può essere ignorata su questo arco |
| Jerk non modellato | Residui nominali accettati | Modello respinto | La misura più precisa rivela un errore di modello nascosto al solo codice |
| Bias persistenti per stazione | Residui nominali accettati | Residui nominali accettati | Il controllo residui non certifica l'assenza di bias |

Le previsioni dei casi respinti o ambigui sono diagnostiche, non risultati
accettati. Nella rete concentrata anche un residuo piccolo sulla stazione
esclusa può accompagnare un grande errore di posizione: la geometria della
verifica conta quanto il suo residuo. Il caso con bias è una singola perturbazione
di sviluppo, insufficiente a dimostrare robustezza o copertura degli intervalli.

## Decisione e confine del risultato

La direzione codice più variazione merita S2. Il passo necessario è un modello
delle osservazioni completo: tempo di volo, emissione/ricezione, Terra rotante,
deriva degli orologi, Doppler RINEX, correlazioni e limite degli errori di
troncamento. Il caso con jerk impedisce di assumere che una cinematica quadratica
sia automaticamente sufficiente alla precisione delle nuove misure.

I sette test del prototipo coprono anche Jacobiano analitico, relazione fra
codice e sua derivata, separazione della deriva di orologio, previsione su
tempo/ricevitore esclusi e rifiuto di ricevitori coincidenti. Sono controlli
software/sintetici; non sostituiscono S3 e una nuova conferma satellitare.

Dati completi: `frozen_diagnosis.json` e `synthetic_study_v1.json` in questa
cartella. Il secondo conserva tutti i 50 fit, i parametri, i semi, gli esiti,
le previsioni e le impronte dei sorgenti utilizzati.
