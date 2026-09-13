# Esperimenti di sviluppo su dati reali

Le prove in questa cartella possono riutilizzare dati già esposti e modificare
ipotesi durante lo sviluppo. Non sono nuove conferme indipendenti. Gli eventi
originali restano immutati e ogni variante, inclusi i fallimenti, è conservata.

## Sensibilità ai riferimenti: G14, 3 settembre 2026

Abbiamo riutilizzato soltanto le osservazioni già ammesse e la navigazione
senza bersaglio di `experiments/positioning_g14_doy246_network`. Nessun download,
accesso all'orbita, lettura della soluzione storica o nuova valutazione GOLD.

Il confronto mantiene fissi sette ricevitori, gli undici endpoint 03:55–04:00
GPST e i codici del bersaglio. Calibra prima con tutti i riferimenti ammessi,
poi esclude a turno ciascuno dei 21 riferimenti effettivamente usati, in tutte
le stazioni. Il solver cerca autonomamente i rami senza usare la soluzione
storica come inizializzazione. Si mantengono i controlli di calibrazione e
interpolazione esistenti e pesi uguali di 20 m per isolare l'effetto della
calibrazione: non si ricalcola l'incertezza completa dell'evento originale.

**22 stime ottenute su 22 casi: baseline più 21 esclusioni.** Nessuna variante
respinta o errore software in questa esecuzione, durata totale circa 72 s.
Spostamento rispetto alla baseline, escludendo la baseline dalle statistiche:

- Minimo: **0,340 m** (senza G07).
- Mediana: **2,762 m**.
- Massimo: **11,057 m** (senza G15).

| Riferimento escluso | Spostamento della stima |
| --- | ---: |
| G15 | 11,057 m |
| G02 | 9,434 m |
| G13 | 5,542 m |
| G19 | 5,305 m |
| G01 | 5,181 m |

Nel caso G15 la massima variazione della calibrazione fra le stazioni e gli
endpoint è circa 0,391 m, mentre lo spostamento xyz raggiunge 11,057 m.
Il confronto misura direttamente l'amplificazione nel fit di questa variazione
di calibrazione. Non identifica G15 come errato e non suggerisce di escluderlo
per migliorare l'accuratezza, che qui non è stata misurata.

Le coordinate sono confrontate negli stessi assi terrestri al tag comune u0.
Anche il parametro B cambia (10,854 m senza G15), quindi cambia leggermente
l'istante di emissione stimato: il JSON riporta questa differenza. Non è un
confronto con la verità a un istante fisico fissato. Non si interpreta la
dispersione fra esclusioni come raggio al 95%, né come limite agli errori
comuni a tutti i riferimenti. È un singolo evento già esposto e scelto perché
disponeva di dati completi riutilizzabili, non un campione rappresentativo GPS.

La [registrazione completa](results/g14_reference_sensitivity_v1.json) contiene
tutte le varianti, le identità dei riferimenti e la calibrazione per ogni
stazione/epoca, gli spostamenti, i rami del fit, i tempi e gli hash degli input
e dei sorgenti. I fallimenti di future esecuzioni restano righe esplicite, con
spostamento nullo nel senso JSON (`null`), mai sostituito da zero metri.

Per riprodurre in un nuovo file di sviluppo, senza modificare l'archivio:

```text
python -m research.exploratory.reference_sensitivity experiments/positioning_g14_doy246_network NUOVO_OUTPUT.json
```

Il prossimo confronto utile è la stessa prova su un altro evento già esposto,
per vedere se la sensibilità cambia con geometria e calibrazione. Non occorre
una nuova campagna di conferma per fare questo sviluppo; servirà invece un
campione nuovo quando il metodo sarà abbastanza stabile da valutarne le
prestazioni fuori dai dati usati per migliorarlo.
