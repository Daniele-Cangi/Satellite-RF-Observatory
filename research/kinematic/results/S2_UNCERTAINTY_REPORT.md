# S2 — Risultati della propagazione locale inversa

Studio del 10 settembre 2026, interamente sintetico. Nessun nuovo dato RF,
orbita del bersaglio, sito o deployment. Implementazione e limiti in
[S2_INVERSE_UNCERTAINTY.md](../S2_INVERSE_UNCERTAINTY.md).

Evidenza: [inverse_uncertainty_study_v1.json](inverse_uncertainty_study_v1.json).
SHA-256 del report:
`b01c555b150558147f19d8b51364f23c810e6957e319046933595fe3efcc6806`.
Sono registrati sorgenti, ambiente, ricetta/hash delle covarianze, sei
perturbazioni con entrambe le polarità, due moti cubici effettivi e tutti
gli undici criteri. Tutti i criteri passano, incluso il rifiuto atteso del
moto incompatibile. `real_rf_qualified=false` resta esplicito.

## Cosa cambia concretamente

Si può ora calcolare come errori delle misure, dei clock e delle coordinate
terrestri passano attraverso il fit fino a posizione, velocità e controllo
escluso. La covarianza completa conserva le correlazioni con il holdout.
Il modello distingue l'effetto del moto non rappresentato sul fit da quello
diretto sul futuro: il solo resto di Taylor futuro non misura entrambi.

Le calibrazioni sintetiche nominali, incluso il holdout, passano; nessun
rumore gaussiano viene estratto in questo studio. Le covarianze sono ipotesi
dichiarate, non precisioni misurate. I p-value nominali prossimi a uno non
sono una dimostrazione empirica del modello probabilistico.

## Incertezze locali a +60 secondi

| Ipotesi di ingresso | Raggio posizione locale 95% | Raggio velocità locale 95% | Semibanda codice escluso | Semibanda rate escluso |
|---|---:|---:|---:|---:|
| S2a, coordinate/clock escluso esatti e misura esclusa senza rumore | 1862,217 m | 3,744633 m/s | 21,247 m | 0,081016 m/s |
| Coordinate incerte e clock/misura esclusi incerti | 1863,852 m | 3,744648 m/s | 44,656 m | 0,127493 m/s |
| Inoltre, errori di clock condivisi fra fit e holdout | 1863,852 m | 3,744648 m/s | 44,656 m | 0,127493 m/s |
| Identiche varianze di clock, senza correlazioni | 2028,714 m | 4,823940 m/s | 46,419 m | 0,136732 m/s |

Le semibande sono marginali gaussiane al 95%, non simultanee. Il raggio
posizione è derivato dal massimo autovalore della covarianza locale.
Non include una copertura certificata della non linearità o di errori
fisici omessi. Il fit conserva i pesi e il test nominale S2a: le ipotesi
aggiuntive non ricalibrano quel test né autorizzano una conferma reale.

In questo modello affine di clock, l'errore comune viene quasi interamente
assorbito nel clock del satellite e si cancella nel confronto escluso.
La cancellazione è verificata separatamente anche con un offset comune
di 100 m. Questo non significa che qualsiasi errore condiviso si cancelli:
segno, correlazione, convenzioni temporali e modo fisico sono determinanti.

## Errori sistematici e moto non rappresentato

| Perturbazione dichiarata | Norma della risposta locale della posizione a +60 s |
|---|---:|
| Coordinata x della prima stazione: +2 m | 20,153108 m |
| Drift di riferimento condiviso: +0,02 m/s | 0,009332 m |
| Base temporale del solo arco di fit: +1 ms | 2,369341 m |
| Jerk costante ECEF x: +2×10⁻⁷ m/s³ | 0,530647 m |
| Jerk costante ECEF y: +2×10⁻⁷ m/s³ | 0,076396 m |
| Jerk costante ECEF z: +2×10⁻⁷ m/s³ | 0,108717 m |

Per questi sei modi, il limite della norma di posizione della scatola affine
è **23,247541 m**; quello della velocità è 0,011040 m/s. I limiti per codice
e rate esclusi sono 0,670737 m e 0,004683 m/s. Sono limiti della risposta
affine assunta, mantenuti separati dal bilancio gaussiano; non sono un
inviluppo totale del sistema non lineare né limiti per jerk arbitrario.

I dodici refit completi ai segni ± delle sei perturbazioni confermano le
derivate locali: massimo scarto di posizione 0,0000372 m, velocità
0,000000125 m/s, codice 0,00000838 m e rate 0,000000000493 m/s.
Sono controlli finiti in questa geometria, non un'analisi globale dei rami.

Un ulteriore caso usa direttamente il generatore cubico inerziale, con
jerk [2, 2, 2]×10⁻⁷ m/s³. Il resto di posizione a +60 s è appena
**0,012471 m**, mentre l'errore ricostruito è circa **0,648 m**: la deformazione
del fit sull'arco precedente domina. Il calcolo affine ne riproduce la
posizione entro 0,000257 m. Il test nominale accetta questo piccolo errore
di modello; residui piccoli non implicano assenza di errore di posizione.

Il secondo moto cubico conserva il jerk forte S2a [-5, 10, 3]×10⁻⁵ m/s³:
`MODEL_REJECTED`, p nominale 3,93776×10⁻²⁷. Lo studio si arresta prima di
produrre una previsione esclusa per quel caso. Non modifica il risultato S2a.

## Verifica e prossima frontiera

25 test nuovi verificano covarianza del fit recuperata nel caso base,
propagazione del clock/rumore escluso, correlazioni condivise e con la
misura futura, covarianze invalide, arresto su calibrazione/fit respinti,
limiti della scatola affine e confronti con refit e generatore indipendente.
Il runner registra separatamente gli undici criteri scientifici di sviluppo.
Gli hash dei sorgenti legati ai report S1, S2a corrente e S2b sono invariati.
La suite locale completa passa: **152 test**, comprendendo positioning,
regressione dell'esperimento G08, service, ricerca e archivio del sito.

Il passo successivo richiede un modello motivato degli errori fisici dei
ricevitori e dei riferimenti, e un fit/test coerente con la loro covarianza
congiunta. Restano aperti propagazione/antenne, comportamento reale del
Doppler, non linearità e troncamento generale. Questo blocco fornisce lo
strumento per misurarne l'impatto; non dichiara completato S2 e non apre S3.
