# S2b — Importazione RINEX e controllo dei riferimenti

Esecuzione del 10 settembre 2026. È stato costruito e verificato il percorso
file RINEX → codici dei riferimenti → offset/deriva del ricevitore → Doppler
escluso dal fit. Nessun nuovo dato Internet o stato del bersaglio è stato
acquisito. Le fixture sono interamente inventate; S2 resta aperto.

## Consegna

- Importatore delimitato RINEX 3.04/3.05 GPS con continuazioni dell'header,
  epoca base GPST, finestra e riferimenti espliciti, controllo del predecessore.
- Esclusione testuale del bersaglio prima dei valori numerici nelle osservazioni
  e nella navigazione; rifiuto ulteriore ai confini di calibrazione/propagazione.
- Calibrazione del clock dai soli codici, con effemeridi broadcast dei riferimenti,
  tempi di emissione/ricezione distinti, rotazione e limite di validità del record.
- Verifica Doppler indipendente dal fit dei codici, con covarianza che conserva
  errori comuni e correlazioni tra codice, stima del clock e Doppler.

Formati supportati, equazioni, fonti e limiti sono descritti in
[S2B_REFERENCE_BRIDGE.md](../S2B_REFERENCE_BRIDGE.md).

## Misure nella simulazione

Quattro riferimenti circolari inventati, una stazione, undici epoche da −300 a
0 s, 44 coppie codice/rate ammesse. Il ricevitore ha offset 14000 m e deriva
0,73 m/s. Il generatore indipendente lavora in assi inerziali; il calibratore
interpreta record broadcast GPS e usa assi terrestri. I campi sono quantizzati
al formato RINEX F14.3.

| Controllo nominale | Risultato |
|---|---:|
| Errore dell'offset ricostruito | −0,000118 m |
| Errore della deriva ricostruita | −0,000000427 m/s |
| Residuo massimo del codice | 0,001826 m |
| Residuo massimo del Doppler non usato nel fit | 0,000365 m/s |

Sono errori di recupero di una costruzione sintetica quasi esatta, non precisioni
ottenute da un ricevitore reale. Le scale usate nel peso e nei controlli sono
assunzioni: 1 m per ciascun codice grezzo e 0,01 Hz per ciascun Doppler, prima
della combinazione duale. Non è stata stimata copertura statistica da questi
errori, né usata un'orbita del bersaglio.

## Tutti gli esiti

| Caso | Esito | Dove termina |
|---|---|---|
| Nominale quantizzato | `REFERENCE_MODEL_ACCEPTED` | Codici e Doppler coerenti nel modello sintetico |
| Doppler invertito su G01 | `REFERENCE_DOPPLER_REJECTED` | Codici invariati; nessun adattamento della deriva ai Doppler errati |
| Salto di 300 m sui codici G01 | `REFERENCE_CODE_REJECTED` | Prima del controllo Doppler |
| D2W mancante a un'epoca | `REFERENCE_WINDOW_REJECTED` | Prima della navigazione e del fit |
| Reset del ricevitore | `RINEX_REJECTED` | Nessuna ripresa automatica dell'arco |
| Limite di età del riferimento superato | `REFERENCE_MODEL_UNAVAILABLE` | Nessuna propagazione fuori validità |

Tutti gli undici controlli dello studio passano. Ciò include i rifiuti attesi:
non significa che tutti i sei casi siano utilizzabili. Il Doppler invertito
lascia identici i coefficienti dell'orologio ricavati dai codici: è il controllo
escluso a rivelare l'incompatibilità.

La sostituzione dei payload numerici del bersaglio con valori non validi lascia
identiche le impronte degli input ammessi e i coefficienti del clock. Il file
osservativo contiene inoltre un'epoca futura esclusa, che non viene decodificata.

## Test e provenienza

Ventisette nuovi test verificano il percorso completo, header e formati 3.04/3.05,
file osservativi misti, mancanti, tutti gli eventi 1–6, record fuori validità,
veleni sul bersaglio, arresto delle fasi e attraversamento di giorno/settimana
con frazioni di secondo. Le regressioni esistenti sono passate. Un controllo
con 60.000 simulazioni lineari verifica la propagazione della covarianza del
residuo Doppler, senza presumere indipendenza dal clock stimato.

Le impronte di tutti i sorgenti registrati nello studio S1, nel report S2a
corrente e nel nuovo report coincidono con i file locali. Il riferimento RF v1,
le precedenti simulazioni e i cinque eventi reali restano immutati.

Dati completi: [rinex_reference_study_v1.json](rinex_reference_study_v1.json).
SHA-256:

```text
d240bac2fc823ee0f7bd1b47564920accbe69e4958750923b1f0d5d875be7e34
```

Il JSON conserva tutti gli esiti, campioni ammessi, residui, covarianze, parametri,
impronte delle fixture, sorgenti e runtime. Non è un sigillo pubblico. Il writer
rifiuta la sovrascrittura e le fixture conservano i byte tramite `.gitattributes`.

## Decisione e prossimo blocco

Il collegamento RINEX–riferimenti è implementato e verificato su dati sintetici.
Ogni esito mantiene `real_rf_qualified=false`: un header leggibile e residui
coerenti non qualificano da soli un ricevitore o una campagna.

La prossima consegna deve quantificare come convenzioni e media del Doppler,
errori dei riferimenti, propagazione, antenne, coordinate terrestri e troncamento
si trasferiscono alla posizione del bersaglio e alle previsioni escluse.
Servono una qualifica dei ricevitori e un inviluppo dell'errore inverso prima
dei manifest definitivi S3. Sito, API, Docker e hosting restano sospesi.
