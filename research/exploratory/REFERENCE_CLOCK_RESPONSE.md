# Trasferimento degli errori di orologio dei riferimenti

Prova di sviluppo del 16 settembre 2026 su due eventi già esposti (G14 e G12).
Il runner `reference_clock_response.py` è stato salvato nel commit `2ac854f`
prima delle esecuzioni. Gli archivi e i loro verdetti restano invariati.

## Domanda e metodo

Quanto cambia la posizione se l'orologio trasmesso da un riferimento cambia
di una quantità nota, mantenendo le osservazioni reali identiche?

Per ogni riferimento osservato con navigazione disponibile, il runner applica
`af0 += delta / c` a tutti i suoi record, prima della propagazione. Prova
`delta = -1 m` e `+1 m` e aggiunge le due perturbazioni comuni a tutti i
riferimenti. Un metro è un'ampiezza inventata di sviluppo, non un errore
misurato, una deviazione standard o un limite fisico del prodotto.

Si ricalcolano tempi di emissione dei riferimenti, modelli delle misure,
calibrazioni dei ricevitori e soluzione inversa. I controlli originali restano
attivi. Stazioni, codici del bersaglio, finestra e pesi uguali di 20 m sono fissi.
Si includono anche i riferimenti osservati sotto la maschera di elevazione:
una perturbazione potrebbe modificare la selezione vicino alla soglia.

Per ogni coppia accettata si registra `(q_plus - q_minus) / (2 delta)` e
la componente pari `(q_plus + q_minus) / 2 - q_baseline`. La prima è una
risposta centrata a passo finito; la seconda misura l'asimmetria rispetto alla
baseline. Una piccola componente pari non dimostra convergenza della derivata
né esclude cambi di ramo. Le coppie respinte restano nel rapporto senza gain.

Gli assi terrestri e il tag u0 sono comuni; il tempo di emissione stimato può
cambiare con B. Queste differenze di stato non sono errori rispetto a una
posizione vera allo stesso istante. Il runner non legge orbite del bersaglio,
soluzioni storiche o valori del ricevitore escluso e non accede alla rete.

## Riproduzione

Usare destinazioni nuove esterne agli archivi originali:

```text
python -m research.exploratory.reference_clock_response experiments/positioning_g14_doy246_network NUOVO_G14.json
python -m research.exploratory.reference_clock_response research/exploratory/inputs/g12_doy248 NUOVO_G12.json
```

Ogni rapporto lega gli input e i sorgenti con SHA-256 e mantiene tutte le
varianti, incluse le eventuali reiezioni e gli errori tecnici.

## Risultati delle due esecuzioni

| Evento | Stime / varianti | Riferimento con risposta massima | Risposta xyz massima (m/m) | Risposta comune xyz (m/m) | Risposta comune B (m/m) |
|---|---:|---|---:|---:|---:|
| G14, 2026-09-03 | 45 / 45 | G20 | 4,134382 | 0,000044 | -0,999956 |
| G12, 2026-09-05 | 47 / 47 | G21 | 7,855346 | 0,000023 | -0,999980 |

Le baseline sono incluse nei conteggi. Nessuna variante respinta o modifica
dei riferimenti selezionati; durate circa 238 e 260 secondi, eseguendo i due
studi contemporaneamente sulla stessa macchina. I rapporti completi sono
[G14](results/g14_reference_clock_response_v1.json) e
[G12](results/g12_reference_clock_response_v1.json).

Le risposte successive sono G15 (3,052927 m/m) e G01 (2,927081 m/m) per G14;
G13 (7,066360 m/m) e G14 (4,948082 m/m) per G12. La classifica differisce
dalla precedente esclusione di un riferimento: qui l'ampiezza perturbata è
identica, mentre un'esclusione cambia insieme dati e calibrazione.

Il massimo termine pari xyz è 0,000572 m per G14 e 0,000002573 m per G12.
La risposta comune di posizione è piccola e non viene interpretata come
precisione fisica a livello micrometrico: comprende limiti numerici, e la
convergenza al variare del passo non è stata misurata. La risposta B prossima
a -1 mostra che questa perturbazione comune viene assorbita soprattutto dal
parametro temporale, mentre gli errori di singoli riferimenti possono spostare
la posizione di diversi metri. Il diverso massimo fra i due eventi non isola
la geometria: cambiano anche rete, epoca e riferimenti.

## Limite e seguito fisico

Questa prova quantifica il trasferimento di perturbazioni di orologio attraverso
la pipeline reale. Non quantifica ancora l'errore reale dei prodotti e non
perturba le loro coordinate orbitali. Non aggiorna l'incertezza storica, non
chiude G3/S2 e non autorizza una nuova conferma.

Il seguito è caratterizzare ampiezze e correlazioni degli errori dei prodotti
non bersaglio, con convenzioni temporali e di clock coerenti, e propagare
congiuntamente le componenti orbitali e temporali. Differenze tra prodotti
possono fornire evidenza di discrepanza, ma non sono automaticamente verità
indipendente o un limite al 95%. Le altre componenti differenziali del modello
restano aperte.
