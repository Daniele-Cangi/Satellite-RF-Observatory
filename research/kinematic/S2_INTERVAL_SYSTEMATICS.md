# S2 — Bias sistematici e rilevabilità nel fit per intervalli

Il nuovo modulo `interval_systematics.py` trasporta perturbazioni deterministiche
attraverso il fit congelato per intervalli. Non cambia pesi, soglie o stime
precedenti e non aggiunge rumore per rendere accettabili i residui.

## Risposta locale e probabilità di rilevamento

Con J jacobiano dei dati, K guadagno del fit, C covarianza fissata e B matrice
delle perturbazioni dichiarate, le colonne di K B descrivono il bias dei
parametri per un coefficiente unitario. Il residuo medio sbiancato è
L⁻¹ (B − J K B), dove L Lᵀ = C. Il quadrato della norma di ogni colonna è
la non centralità lambda del costo residuo nel problema lineare gaussiano.

La probabilità di rifiuto è calcolata con la distribuzione chi-quadro non
centrale alla soglia originale p < 0,01. È una probabilità sotto ipotesi
gaussiane locali e con rumore di ampiezza dichiarata, non la frequenza empirica
dei dodici fit deterministici, né la potenza globale di tutti i gate.
Un bias completamente assorbito dai parametri ha lambda quasi nulla e resta
rilevabile solo al tasso nominale di falso rifiuto, anche se sposta la soluzione.

Le colonne sono trattate separatamente dalla covarianza casuale. Per
coefficienti simultanei in [-1,1], la somma dei moduli dà il limite esatto per
ciascuna componente affine; la somma delle norme dà un limite conservativo
per il vettore posizione o velocità. Non è un inviluppo non lineare o un
raggio totale al 95%. Le interazioni fra colonne nei residui sono conservate
nella matrice restituita; le probabilità tabulate riguardano una colonna
alla volta e non vanno sommate.

## Sei perturbazioni fissate

Le ampiezze sono esempi di sensibilità, non limiti qualificati fisicamente.
I ricevitori e le forme temporali sono fissati senza usare geometria target:

- Deriva di fase comune di 0,001 m/s, presente anche sul ricevitore escluso.
- Ritardo comune a codice/fase sul ricevitore 0: 0,1 (t/300)² m.
- Oscillazione di fase sul ricevitore 0: 0,02 sin(2 pi (t+300)/600) m.
- Errore di 0,001 m/s nella calibrazione compressa del drift del ricevitore 0.
- Ambiguità costante di fase di 5 m sul ricevitore 0, come controllo negativo.
- Offset comune di codice di 10 m, presente anche sul ricevitore escluso.

I tempi di fit sono da −300 a 0 secondi. Gli ultimi due estremi esclusi sono
30 e 60 secondi. I modi specifici del ricevitore 0 sono assenti sul ricevitore
escluso; i due modi comuni condividono lo stesso coefficiente. Le differenze
di fase e i blocchi incrociati restano quelli del precedente studio.

Una parabola o una sinusoide aggiunta al cammino non simula integralmente
troposfera, ionosfera, multipath o wind-up. Queste forme servono a quantificare
la sensibilità del solver a errori temporali semplici. Nessun dato RF reale
viene acquisito o qualificato.

## Confronto con refit e previsione

Per ciascun modo si conservano fit con segno positivo e negativo, senza
variare ampiezza o finestra. La risposta centrale non lineare è confrontata
con K B. Il controllo centrale cancella i termini pari: non certifica da
solo l'errore della linearizzazione per ogni singolo segno o combinazione.
Entrambi gli stati e gli esiti sono comunque conservati nel report.

Il trasporto sulla previsione usa la mappa dell'errore già implementata per
l'intervallo escluso. Il bias di misura esclusa entra con segno negativo;
condividere il coefficiente conserva cancellazioni che andrebbero perse
trattando fit e ricevitore escluso come errori sistematici indipendenti.
Si calcola la risposta della previsione solo quando entrambi i refit sono
accettati. Non si ricalibra il ricevitore escluso con i suoi valori target.

Il modulo rifiuta un fit non accettato prima di leggere le perturbazioni e
verifica l'hash della covarianza originale. Non cambia i fit o i report
storici. Risultati nel [report](results/S2_SYSTEMATICS_REPORT.md).

## Lavoro ancora necessario

Per passare da sensibilità a qualifica servono ampiezze e correlazioni
giustificate per ricevitori, riferimenti e propagazione, un modello delle
variazioni non rimosse e verifiche dei resti non lineari. I residui non
possono fornire da soli limiti agli errori che il modello assorbe.
La fase successiva dovrà costruire la calibrazione comune riferimento/target
e confrontare i suoi errori residui con queste sensibilità prima di S3.
