# Prodotti di riferimento ai tempi delle osservazioni

Prova esplorativa del 16 settembre 2026, eseguita con sorgenti registrati in
`bf4e315`. Collega la [conversione del codice](REFERENCE_CODE_BIAS.md) a orbite
e clock della medesima serie CODE rapid. Usa gli input esposti G14/G12 e produce
nuove calibrazioni e stime sperimentali, senza modificare gli eventi chiusi.

## Input coerenti per serie, giorno e modello

Dal [catalogo BKG IGSac della settimana 2434](https://igs.bkg.bund.de/root_ftp/IGSac/products/2434/)
sono stati acquisiti quattro file:

- `COD0OPSRAP_20262460000_01D_05M_ORB.SP3.gz`
- `COD0OPSRAP_20262460000_01D_30S_CLK.CLK.gz`
- `COD0OPSRAP_20262480000_01D_05M_ORB.SP3.gz`
- `COD0OPSRAP_20262480000_01D_30S_CLK.CLK.gz`

Gli SP3 dichiarano GPST, frame IGc20 e IGS20_2425; i CLK dichiarano GPST,
centro CODE, IGS20_2425 e bias CODE. I bias giornalieri già acquisiti appartengono
alla stessa serie e dichiarano C1W/C2W come riferimento dei clock GPS. Si
verificano queste convenzioni, le assegnazioni SVN e gli hash degli estratti.
Non si mescola il clock combinato IGS con un'orbita CODE per questa prova.

Le ricevute in `inputs/timed_reference_products/{g14,g12}/receipt.json`
conservano URL, dimensione e SHA256 dei gzip originali e degli estratti.
Sono mantenuti 289 nodi orbitali giornalieri, compresa la mezzanotte successiva;
i clock sono limitati alla finestra osservata con margine di 120 s per lato.
Gli estratti contengono complessivamente 12.427 posizioni dei riferimenti e
817 campioni di clock. Il bersaglio e tutti i clock dei ricevitori sono scartati
come testo prima della conversione numerica. Le coordinate delle stazioni nei
prodotti CLK non entrano nella calibrazione: si usano quelle ammesse originali.

Il prodotto CLK usa il formato 2.00 e riporta talvolta solo il bias, senza sigma.
Il parser supporta entrambi i casi; un sigma assente rimane `None`, non zero.
Il formato della famiglia RINEX clock e il significato dei campi sono descritti
nella [specifica IGS](https://files.igs.org/pub/data/format/rinex_clock304.txt).
La prima verifica del parser aveva rifiutato i record con un solo valore; il
supporto esplicito è stato aggiunto e testato prima delle esecuzioni scientifiche.

## Valutazione al tempo di emissione

Per ciascun codice IF del riferimento, dopo la conversione C1C→C1W, si risolve:

```text
offset = -corrected_IF_code/c - satellite_clock(t_tag + offset)
t_tx   = t_tag + offset
t_rx   = t_tag - receiver_clock/c
model  = |Rz(-OMEGA*(t_rx-t_tx))*antenna(t_tx) - station|
         - c*satellite_clock(t_tx) + troposphere
```

L'iterazione usa l'offset rispetto al tag per evitare la sottrazione di due
tempi assoluti grandi nel controllo della chiusura. Le posizioni SP3 sono
interpolate con nove nodi a passo 300 s, polinomio di grado otto in ascisse
centrate e scalate. La derivata dello stesso polinomio fornisce la velocità.
Il clock viene dal CLK a 30 s con interpolazione lineare, più la relatività
periodica `-2*r.v/c^2`. Non si usano i clock a basso campionamento dentro gli SP3.
La [guida IGS, §5.1.1 e §5.3.4](https://files.igs.org/pub/resource/pubs/UsingIGSProductsVer21_cor.pdf)
descrive riferimento al centro di massa, offset d'antenna e correzione periodica
richiesta per l'uso dei prodotti precisi.

Si applica il PCO IF radiale assumendo Z corporeo verso il centro terrestre.
Le componenti trasverse conservano l'intervallo yaw condizionale del precedente
modello. In questa prova l'escursione massima è 9,4 cm; non è un limite all'errore
totale d'antenna. Assetto reale, pitch/roll e risposta del codice restano aperti.

Nessuna estrapolazione: buchi nei clock, nodi orbitali assenti/segnalati o
mancata convergenza producono un fallimento esplicito. I clock non sono
interpolati attraverso record duplicati, che possono rappresentare discontinuità.
Le discontinuità non dichiarate nei dati restano un limite fisico del controllo.

## Quattro configurazioni, tutte conservate

Per ogni evento:

1. Broadcast con bias satellitari corretti, equivalente alla variante precedente.
2. Prodotti precisi: nove nodi orbitali e clock nativi a 30 s.
3. Controllo orbitale: sette nodi e clock a 30 s.
4. Controllo clock: nove nodi e clock diradati a 60 s.

Ogni configurazione ricalibra sette stazioni e ripete il fit inverso. Le tre
configurazioni precise mantengono i riferimenti della baseline broadcast; un
riferimento sotto maschera precisa è un fallimento, non viene sostituito.
Restano le soglie storiche su residui, sottoinsiemi, rango e verifica delle
coordinate a terra. I test dell'adattatore riproducono la calibrazione congelata
quando viene iniettato il modello broadcast originale.

Codici bersaglio, pesi uguali di 20 m, finestra e coordinate ammesse restano
fissi. Non vengono letti orbita/clock/bias del bersaglio o dati del ricevitore
escluso. `ESTIMATED` qui non significa nuova dimostrazione indipendente.

## Risultati

| Quantità | G14 | G12 |
|---|---:|---:|
| Casi stimati / eseguiti | 4 / 4 | 4 / 4 |
| Collegamenti valutati / osservati | 716 / 734 | 747 / 847 |
| Spostamento preciso rispetto a broadcast già corretto per bias | **3,374678 m** | **5,623492 m** |
| Variazione B rispetto alla stessa baseline | −3,598510 m | +4,739158 m |
| RMS calibrazione, baseline → preciso | 0,994680 → 0,954921 m | 1,039557 → 1,023831 m |
| Massimo offset del controllo delle coordinate a terra, baseline → preciso | 4,843906 → 4,203048 m | 4,786836 → 4,317306 m |
| Massimo residuo fit bersaglio, baseline → preciso | 0,450731 → 0,431844 m | 0,935784 → 0,954990 m |
| Spostamento fit: sette invece di nove nodi | 0,000109 m | 0,000051 m |
| Spostamento fit: clock a 60 invece di 30 s | 0,021831 m | 0,120575 m |

I 118 collegamenti esclusi dai set broadcast rimangono nel denominatore.
Tutte le 616 epoche di calibrazione degli otto casi superano i controlli;
non vengono eliminati casi falliti dopo l'esecuzione. La chiusura numerica
dell'equazione d'emissione è conservata per ogni collegamento: non misura la
precisione dei tempi reali né l'accuratezza della posizione.

Il controllo omette inoltre nodi nativi e li ricostruisce senza usarne il valore:

| Controllo | G14 | G12 |
|---|---:|---:|
| Nodi orbitali omessi, confrontati / previsti | 84 / 84 | 88 / 88 |
| Massimo scarto orbitale al nodo omesso | 1,234 mm | 1,748 mm |
| Clock nativi a 30 s omessi dalla griglia a 60 s | 147 / 147 | 154 / 154 |
| Massimo scarto clock al nodo omesso, equivalente distanza | 0,037393 m | 0,057696 m |

Questi confronti descrivono interpolazione, campionamento e numerica dei prodotti
usati. Non dimostrano convergenza dell'errore fisico e non definiscono covarianze
o limiti al 95%. Neppure la diminuzione del residuo di calibrazione dimostra
una posizione migliore: G12 aumenta leggermente il residuo del fit bersaglio,
e nessun confronto con l'oracolo è eseguito.

Rapporti: [G14](results/g14_reference_time_alignment_v1.json),
[G12](results/g12_reference_time_alignment_v1.json). Contengono tutte le varianti,
calibrazioni e soluzioni, i 1581 collegamenti osservati e i 473 controlli su nodi
omessi, con hash di input e sorgenti. Il replay completo usa tolleranze numeriche
per le stime nonlineari; i controlli dei nodi e dei tempi hanno verifiche separate.

## Stato e prossimo passo

La valutazione ai tempi osservati è consegnata nel modello sperimentale, con
prodotti abbinati e controllo della sensibilità temporale. Restano assetto reale
e risposta d'antenna del codice, frame/media delle stazioni, bias dei ricevitori
e covarianza fisica. Il catalogo CODE espone anche prodotti di assetto della
stessa serie: sono un seguito concreto per superare l'ipotesi di solo PCO radiale.
Il motore di produzione e il bilancio d'errore storico restano invariati; S2/G3
non sono chiusi e non viene avviata una nuova conferma o pubblicazione.

Riproduzione offline con output nuovo:

```text
python -m research.exploratory.reference_time_alignment experiments/positioning_g14_doy246_network research/exploratory/inputs/timed_reference_products/g14 research/exploratory/inputs/reference_biases/g14 research/exploratory/inputs/reference_antennas/g14 NUOVO_G14.json
python -m research.exploratory.reference_time_alignment research/exploratory/inputs/g12_doy248 research/exploratory/inputs/timed_reference_products/g12 research/exploratory/inputs/reference_biases/g12 research/exploratory/inputs/reference_antennas/g12 NUOVO_G12.json
python -m pytest research/exploratory/tests/test_reference_time_alignment.py -q
```
