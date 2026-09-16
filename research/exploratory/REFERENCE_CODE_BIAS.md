# Bias del codice: conversione dei riferimenti e ricalibrazione

Esperimento di sviluppo del 16 settembre 2026, eseguito con sorgenti registrati
in `6e6180d`. Riutilizza gli input esposti G14/G12 senza cambiare eventi chiusi,
codici del bersaglio, pesi o soglie. Non legge orbite/bias del bersaglio, valori
del ricevitore escluso o precedenti soluzioni per inizializzare la stima.

## Differenza di convenzione affrontata

Il lettore storico forma `alpha*C1C + beta*C2W` e rifiuta i file che dichiarano
`SYS / DCBS APPLIED`. I prodotti CODE acquisiti dichiarano invece C1W/C2W come
osservabili di riferimento dei clock GPS. Si ricava una differenza satellitare
fra bias dei due codici L1, senza trasferire direttamente il datum dei clock CODE:

```text
DSB(C1W,C1C) = OSB(C1W) - OSB(C1C)                      [ns]
delta_IF = alpha * c * 1e-9 * DSB(C1W,C1C)              [m]
reference_IF_translated = reference_IF_original + delta_IF
```

Segno e trasformazione seguono il
[Bias-SINEX 1.00, §6.2–6.3](https://files.igs.org/pub/data/format/sinex_bias_100.pdf):
il DSB è la differenza dei bias e si aggiunge a C1C per ottenere l'equivalente
C1W. Un offset comune agli OSB si cancella nella differenza. Questo evita di
sottrarre OSB pseudo-assoluti CODE a misure modellate con clock di altra origine.
Il collegamento fra la famiglia CODE OSB e la differenza C1W−C1C è descritto
anche nel [rilascio CODE](https://lists.igs.org/pipermail/igsmail/2016/001221.html).

Si corregge soltanto la componente satellitare dei riferimenti: le risposte
dei ricevitori e il bias del bersaglio non sono stimati con questi prodotti.
I due codici L1 hanno la stessa frequenza; non si introduce una correzione
PCO interfrequenza per questa differenza.

## Prodotti e tracciabilità

Si usano due prodotti rapid giornalieri CODE dal centro dati BKG:

| Evento | Prodotto | Byte compressi | SHA256 compresso |
|---|---|---:|---|
| G14 | [COD0OPSRAP DOY246](https://igs.bkg.bund.de/root_ftp/IGSac/products/2434/COD0OPSRAP_20262460000_01D_01D_OSB.BIA.gz) | 70.427 | `43f6579aba99b29f79be9a8dff2cf3903e92d6541815ec4a8ea22102771fee41` |
| G12 | [COD0OPSRAP DOY248](https://igs.bkg.bund.de/root_ftp/IGSac/products/2434/COD0OPSRAP_20262480000_01D_01D_OSB.BIA.gz) | 70.690 | `9fd04562476de5beada8583fc7e32be4023eb231eec4aecd2c79637ee485d514` |

Entrambi dichiarano GPST, bias assoluti, `APC_MODEL IGS20_2425` e clock GPS
C1W/C2W. Il parser verifica queste convenzioni e, per ogni epoca, un solo record
valido per segnale e la corrispondenza SVN con l'ANTEX ammesso. L'intervallo è
inizio incluso/fine esclusa. Record sovrapposti, mancanti, non finiti, con unità
diverse o pendenza non supportata sono rifiutati; nessun valore mancante diventa
zero e nessun riferimento viene eliminato per far riuscire la prova.

Gli estratti in `inputs/reference_biases/` contengono solo C1C/C1W/C2W dei
riferimenti satellitari: 63 record per G14 e 66 per G12. Bersaglio, ricevitori,
altri sistemi e segnali sono esclusi come testo prima della conversione numerica.
Sono estratti dichiarati, non file completi: il conteggio nell'header originale
resta quello del prodotto sorgente, mentre la ricevuta specifica il conteggio
dell'estratto. Header utili e righe selezionate sono riproducibili byte per byte.

La ricerca iniziale nei percorsi generici IGS/MGEX e nel vecchio archivio AIUB
non ha prodotto i file richiesti (404 o timeout); il catalogo BKG IGSac della
settimana 2434 li espone. La prima decodifica ASCII dell'intero prodotto CODE
ha incontrato un carattere accentato nei commenti bibliografici: l'estrazione
usa Latin-1 senza perdita di byte, mentre le sole righe selezionate sono ASCII.
Non sono stati provati altri prodotti numerici per scegliere un risultato migliore.

## Prova eseguita

Per ogni evento si eseguono esattamente due casi: baseline e conversione
satellitare del codice. I bias giornalieri vengono verificati su tutti gli
11 tempi osservati e tutti i riferimenti (21/22), compresi quelli sotto maschera.
Per entrambe le varianti si ricalibrano le sette stazioni fit e si esegue il
medesimo fit inverso, con gli stessi codici bersaglio e pesi uguali di 20 m.
Restano attive le soglie originali e sono conservati eventuali fallimenti.

Questa è una prova isolata del bias sul modello broadcast esistente. Non
sostituisce le orbite/clock con gli SP3, non applica gli scarti della precedente
proiezione e non considera completa l'armonizzazione di tutti i prodotti.

## Risultati

| Quantità | G14 | G12 |
|---|---:|---:|
| Conversione IF per riferimento, minimo/massimo | −1,875 / +0,746 m | −1,822 / +0,728 m |
| Variazione clock ricevitori, minimo/massimo | −0,301 / −0,014 m | −0,012 / +0,258 m |
| RMS aggregato residui di calibrazione, prima → dopo | 1,281 → 0,995 m | 1,205 → 1,040 m |
| Massimo offset nel controllo delle coordinate a terra, prima → dopo | 6,706 → 4,844 m | 5,433 → 4,787 m |
| Spostamento della posizione stimata dalla baseline | **9,058 m** | **3,906 m** |
| Variazione del parametro B | −8,783 m | +3,457 m |
| Massimo residuo del fit bersaglio, prima → dopo | 0,433 → 0,451 m | 0,918 → 0,936 m |

Tutti e quattro i casi terminano `ESTIMATED`, con 77 epoche di calibrazione
per caso. Nei 154 confronti stazione-epoca non cambia alcuna selezione di
riferimenti. La variazione dei clock concorda con la media delle correzioni
ai codici entro 1,1 micrometri; lo scarto residuo riguarda la ricalibrazione
nonlineare e la numerica, non la precisione fisica dei clock.

La chiusura IF `alpha*OSB_C1W + beta*OSB_C2W` è entro 0,05 mm equivalenti,
compatibile con l'arrotondamento dei campi: è un controllo di convenzione,
non una misura della qualità del prodotto. Gli scarti standard riportati da
CODE, inclusi gli zeri, restano metadati; non diventano varianze indipendenti
né una covarianza dei DSB in assenza delle correlazioni.

Rapporti completi: [G14](results/g14_reference_code_bias_v1.json),
[G12](results/g12_reference_code_bias_v1.json). Contengono tutti i 473 abbinamenti
epoca-riferimento, le quattro calibrazioni/soluzioni, i 154 confronti e gli hash.
I 473 abbinamenti riusano bias giornalieri e non sono misure indipendenti.

La diminuzione dei residui dei riferimenti non dimostra un miglioramento della
posizione: i residui del bersaglio aumentano leggermente e non viene consultato
l'oracolo. Lo spostamento quantifica una dipendenza reale del risultato dalla
convenzione del codice, senza stabilire quanto fosse errata la baseline.

## Seguito e riproduzione

La conversione satellitare C1C→C1W è ora disponibile e verificata per questi
input. Restano integrazione coerente di orbite/clock ai tempi osservati,
datum fra prodotti, risposte dei ricevitori, assetto/frame/media e covarianza
fisica. I risultati non aggiornano le incertezze storiche, non abilitano S3/G3
e non entrano nel motore di produzione. Il prossimo lavoro può usare questa
conversione esplicita nel modello sperimentale con prodotti temporali adeguati.

```text
python -m research.exploratory.reference_code_bias experiments/positioning_g14_doy246_network research/exploratory/inputs/reference_biases/g14 research/exploratory/inputs/reference_antennas/g14 NUOVO_G14.json
python -m research.exploratory.reference_code_bias research/exploratory/inputs/g12_doy248 research/exploratory/inputs/reference_biases/g12 research/exploratory/inputs/reference_antennas/g12 NUOVO_G12.json
python -m pytest research/exploratory/tests/test_reference_code_bias.py -q
```
