# Esperimenti di sviluppo su dati reali

Il [confronto dei prodotti reali](REFERENCE_PRODUCT_DISCREPANCY.md) aggiunge
4128 coppie satellite-epoca broadcast/IGS rapido, senza conversione numerica
degli stati del bersaglio. Conserva scarti orbitali, clock grezzi e centrati,
componente comune e covarianza descrittiva; non fornisce ancora un budget
d'errore qualificato.

Il [trasferimento degli errori di orologio](REFERENCE_CLOCK_RESPONSE.md) è ora
misurato con perturbazioni controllate sui due eventi: 92 varianti complessive,
incluse due baseline, senza accesso all'orbita bersaglio. Risposte massime
4,13 m/m (G14) e 7,86 m/m (G12); le ampiezze reali degli errori dei prodotti
restano da qualificare.

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

Il confronto è stato esteso a G12, come descritto sotto. Non occorre una nuova
campagna di conferma per fare questo sviluppo; servirà invece un campione nuovo
quando il metodo sarà abbastanza stabile da valutarne le prestazioni fuori
dai dati usati per migliorarlo.

## Secondo evento reale: G12, 5 settembre 2026

Eseguito lo stesso runner, senza modifiche, sui dati originali dell'evento
G12 DOY248. Gli input sono stati recuperati dal runtime locale e confrontati
con gli hash della ricevuta già pubblicata in
`experiments/positioning_g12_doy248/admission_receipt.json`: entrambi coincidono.
La copia in [inputs/g12_doy248](inputs/g12_doy248) rende il confronto riproducibile
anche senza quel runtime. L'archivio storico non è stato modificato.

Sette ricevitori (ALGO, DRAO, STJO, YELL, BOGT, BRAZ, AREQ), undici endpoint
10:30–10:35 GPST, stessi pesi e controlli del primo confronto. Esclusi a turno
tutti i 22 riferimenti effettivamente usati: **23 stime su 23 casi**, baseline
inclusa, nessuna variante respinta, circa **79,5 secondi**. Nessun nuovo download,
accesso all'orbita o lettura della soluzione storica. L'esito storico di G12
resta `UNCERTAINTY_TOO_LARGE`: qui non abbiamo ricalcolato quel criterio.

| Evento già esposto | Esclusioni con stima / provate | Minimo | Mediana | Massimo | Esclusione con maggior effetto |
| --- | ---: | ---: | ---: | ---: | --- |
| G14, 3 settembre | 21 / 21 | 0,340 m | 2,762 m | 11,057 m | G15 |
| G12, 5 settembre | 22 / 22 | 0,312 m | 3,915 m | 26,505 m | G11 |

Le statistiche escludono le baseline, che per costruzione hanno spostamento
zero. Il massimo G12 è circa 2,4 volte quello G14. Senza G11 le correzioni
di calibrazione cambiano al massimo di **0,338 m**, ma la stima xyz cambia di
**26,505 m**, insieme a una variazione di B di **26,040 m**. Le successive
esclusioni per effetto sono G18 (12,460 m), G15 (11,830 m), G19 (8,649 m) e
G04 (5,535 m). Nessuna di queste classifiche dimostra che un riferimento sia
errato o che eliminarlo migliori l'accuratezza.

Il risultato di sviluppo è che la sensibilità non è una costante del servizio:
questi due eventi hanno reti, riferimenti, orari e geometrie differenti.
Il confronto non isola causalmente uno di questi fattori, non misura errori
comuni a tutti i riferimenti e non produce una distribuzione di accuratezza
GPS. Restano due eventi scelti perché i dati erano già disponibili.

La [registrazione G12 completa](results/g12_reference_sensitivity_v1.json)
conserva tutte le varianti e le diagnostiche per stazione/epoca. Riproduzione:

```text
python -m research.exploratory.reference_sensitivity research/exploratory/inputs/g12_doy248 NUOVO_OUTPUT.json
```

Il prossimo passo utile è rendere questa sensibilità una diagnostica per
richiesta, separata dall'esito di conferma: mostrare quali esclusioni cambiano
di più la stima e quante fanno fallire la calibrazione. Per attribuire la
variazione alla geometria occorre invece un confronto che tenga fisse le
perturbazioni di calibrazione, evitando di dedurlo dal solo massimo osservato.
