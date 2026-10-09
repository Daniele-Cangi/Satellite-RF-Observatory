# Confronto abbinato del clock locale e del riferimento Internet

Replay esplorativo del log Galaxy S21 FE del 10 ottobre 2026, gia esposto.
Misura quali scarti software del solo UTC decodificato separano due controlli
diversi. Non e una prova RF o una conferma prospettica; il log originale senza
manipolazione introdotta non e certificato benigno.

## Metodo e copertura

`time-sensitivity` riusa decoder, intervalli NTS e confronto esistenti. Il
controllo locale predice UTC dall'epoca iniziale del segmento e dal tempo
trascorso sul contatore del telefono. Propaga l'errore del primo clock e del
clock sotto esame, l'associazione delle epoche, la deriva e la quantizzazione.
Un'origine UTC ignota rimane un parametro locale: uno scarto costante comune
si cancella. Un salto successivo puo essere visibile senza Internet. Non si
riancora dopo una discordanza e non si usano tempi NTS nel controllo locale.
Entrambi usano le claim gia ammesse nella finestra della co-acquisizione;
le 217 righe fuori finestra non diventano storia locale. Il profilo costante
riguarda tutte le claim ammesse, senza reinterpretare le misure escluse o
modificare il log Raw. Non e un confronto con ogni possibile controllo locale.

I budget restano quelli di sviluppo: server e UTC GNSS 1 ms, associazione
GNSS/CLOCK_BOOTTIME 1 ms, deriva 100 ppm, bracket NTS massimo 15 s. La risoluzione
locale dichiarata di 1 ns coincide con quella conservata negli scambi del
collettore; la risoluzione non certifica l'accuratezza. I budget non sono
calibrati e la deriva locale e assunta sull'intero segmento. Il controllo
locale assoluto contro una sorgente UTC qualificata resta `NOT_EVALUATED`.

Si confrontano zero e entrambi i segni di 10 e 100 ms. La seconda famiglia
applica gli stessi scarti solo dalla meta dell'intervallo dei contatori ammessi:
`447980759069112` ns, scelto da metadati gia esposti. Questo criterio software
non e un istante d'attacco RF. Nessuna soglia, associazione o finestra viene
adattata agli esiti.

Restano 479 righe GPS e 86 epoche clock distinte. Il confronto NTS ammette 183
righe/32 epoche; tutte hanno anche un confronto locale. Le altre 296 righe/54
epoche rimangono insufficienti nel confronto abbinato. Sono conservati 13/20
scambi autenticati e sette timeout; i due endpoint PTB non sono due autorita
indipendenti. Righe ed epoche distinte non sono campioni indipendenti.

## Risultati

| Caso, ciascun segno dove indicato | Solo locale discordante | Solo NTS discordante | Entrambi discordanti | Nessuno discordante |
|---|---:|---:|---:|---:|
| Originale, zero | 38 | 0 | 0 | 145 |
| Scarto costante ±10 ms | 38 | 0 | 0 | 145 |
| Scarto costante ±100 ms | 0 | 145 | 38 | 0 |
| Salto -10 ms | 97 | 0 | 0 | 86 |
| Salto +10 ms | 79 | 0 | 0 | 104 |
| Salto ±100 ms | 32 | 0 | 65 | 86 |

La tabella usa tutte le 183 righe abbinate, con le altre 296 insufficienti in
ogni caso. Lo scarto costante coinvolge 262 righe ammesse/44 epoche; il salto
138 righe/22 epoche, delle quali 65 righe/11 epoche hanno supporto NTS.

Le 145 righe, **25 epoche**, che passano da nessuna discordanza a sola discordanza
NTS con ±100 ms mostrano il contributo del riferimento UTC esterno rispetto a
questo controllo relativo. Le altre 38 righe/7 epoche avevano gia una discordanza
locale: non sono nuovi rilevamenti locali della challenge. Con il salto ±100 ms,
59 righe/10 epoche passano da nessuna discordanza a discordanza di entrambi;
sei righe/un'epoca avevano gia il segnale locale. In questo caso NTS non
aggiunge una separazione dove la continuita locale lascia passare.

I salti di 10 ms conservano il limite opposto: NTS rimane compatibile, mentre
la continuita locale produce nuove discordanze in 59 righe/10 epoche per il
segno negativo e 47 righe/8 epoche per il positivo. Con +10 ms anche sei
discordanze originali/un'epoca diventano compatibili. Questa compensazione
accidentale rimane nel risultato e non viene usata per correggere il clock.

Sul totale locale, prima di qualsiasi challenge, **51 righe/9 epoche** sono
discordanti sotto i budget assunti; 38 righe/7 epoche appartengono alla copertura
abbinata. La separazione dagli intervalli locali e 0,340481--3,324667 ms. Non
sono falsi allarmi misurati o prove di attacco: manca la verita indipendente
necessaria a distinguere un limite del modello, dei budget o delle misure.
L'originale NTS resta compatibile. Non si allargano i budget per eliminare questi
casi. Con associazione ignota, tutti i 479 confronti abbinati restano insufficienti
per ogni scarto, senza fallback.

## Decisione e riproduzione

Il contributo informativo sullo scarto comune e dimostrato **nel test software
condizionale**; il confronto conserva anche il vantaggio del controllo locale
sui piccoli salti. Non e dimostrato beneficio RF o vantaggio a pari falsi allarmi.
P2 resta aperta. Il limite concreto da risolvere prima della prova piu forte e
ora la discordanza locale gia presente nell'originale, con qualifica indipendente
dell'associazione e dei budget. Ripetere gli stessi scarti o allargare una soglia
su questo log non risolve quel limite.

Il [riepilogo aggregato](results/pnt_phone_paired_time_v1.json) conserva conteggi
per endpoint, transizioni, epoche distinte e hash. I log con posizione e i
rapporti completi restano privati; non e un benchmark pubblico integralmente
riproducibile. Gli input originali e i rapporti storici non sono modificati.
Sul fascicolo locale, usare un output nuovo:

```console
python -m pnt time-sensitivity phone-time-outdoor-01-development-alignment.json --offset-ns -100000000 --offset-ns -10000000 --offset-ns 10000000 --offset-ns 100000000 --local-counter-resolution-ns 1 --output paired-constant.json
```

Per il salto aggiungere `--onset-monotonic-ns 447980759069112`. Ripetere sul
rapporto `phone-time-outdoor-01-unknown-alignment.json` conserva gli esiti
insufficienti e restituisce uscita 2. Le versioni locali `v2` aggiungono le
transizioni esplicite dai casi zero; le prime versioni `v1` senza queste
transizioni restano conservate. I tre rapporti finali e le loro baseline sono
riprodotti esattamente, e il replay storico senza le nuove opzioni e invariato.
