# Modello temporale Android: decisione del 10 ottobre 2026

**Con le interfacce e le fonti consultate non è disponibile un limite massimo
indipendente per l'associazione GNSS/CLOCK_BOOTTIME del Galaxy S21 FE.**
La ricerca del contratto temporale non qualifica i budget storici né quelli
ipotetici della [matrice di sviluppo](../research/exploratory/PNT_NATIVE_TIME_BUDGET_ENVELOPE.md).
Il percorso disponibile resta una diagnostica condizionale. Questa è una
decisione sulle evidenze disponibili, non una dimostrazione di impossibilità
per ogni telefono o una verifica del firmware Samsung.

Il passo successivo è una **valutazione empirica separata dello stesso
rilevatore**, con log originali e challenge software abbinate. Può misurare
ripetibilità e allarmi nei casi osservati; non sostituisce una qualifica
metrologica o la validazione di attacchi RF. P2 forte e P3 restano aperte.
Nessuna nuova acquisizione o prova numerica è stata eseguita per questa decisione.

## Contratti disponibili e ciò che non stabiliscono

Fonti primarie consultate il 10 ottobre 2026:

| Componente | Contratto documentato | Conseguenza per il progetto |
|---|---|---|
| `GnssClock.getElapsedRealtimeNanos()` | Epoca sul tempo trascorso dall'avvio, disponibile solo con il relativo flag | Associazione nello stesso dominio del contatore; non un limite numerico di accuratezza |
| `getElapsedRealtimeUncertaintyNanos()` | Stima dell'allineamento al 68% di confidenza | I circa 7 ms registrati non sono un massimo, una copertura verificata sul Galaxy o una distribuzione delle code |
| HAL GNSS `ElapsedRealtime` | Timestamp dell'evento sincronizzato con `SystemClock`; incertezza stimata al 68% | Anche il contratto sottostante conserva la distinzione fra stima e limite; il requisito di sincronizzazione non assegna un massimo numerico |
| `SystemClock.elapsedRealtimeNanos()` | Contatore monotono dall'avvio, incluso il sonno profondo | Monotonia e unità in ns non qualificano risoluzione effettiva o deriva massima di 100 ppm |
| Server PTB | Riferimento UTC(PTB) derivato da orologi atomici indipendentemente dal GPS | Indipendenza utile dal canale RF locale; nessuna qualifica automatica del budget server di 1 ms del nostro report |
| NTS / NTP | Autenticazione dei messaggi; ritardo e dispersione verso il riferimento riportati dal server | Identità e integrità non dimostrano da sole accuratezza fisica o assenza di ritardo asimmetrico |

Riferimenti: [API GnssClock](https://developer.android.com/reference/android/location/GnssClock#getElapsedRealtimeUncertaintyNanos()),
[HAL GNSS 2.0, ramo Android 16](https://android.googlesource.com/platform/hardware/interfaces/+/refs/heads/android16-release/gnss/2.0/types.hal),
[HAL AIDL, ramo Android 16](https://android.googlesource.com/platform/hardware/interfaces/+/refs/heads/android16-release/gnss/aidl/android/hardware/gnss/ElapsedRealtime.aidl),
[API SystemClock](https://developer.android.com/reference/android/os/SystemClock),
[PTB: riferimento indipendente dal GPS](https://www.ptb.de/cms/ptb/fachabteilungen/abt9/gruppe-95/ref-952/zeitsynchronisation-technische-hinweise.html),
[RFC 5905, §§7.3 e 11.2](https://datatracker.ietf.org/doc/html/rfc5905),
[RFC 8915, §8.6](https://datatracker.ietf.org/doc/html/rfc8915#section-8.6).

La [CDD Android 16, §7.3.3](https://source.android.com/docs/compatibility/16/android-16-cdd#733_gps)
specifica prestazioni e disponibilità GNSS, ma non fornisce il massimo di
associazione cercato. Non trasferire al GNSS raccomandazioni della sezione
sui sensori generici. La compatibilità Android non è una calibrazione di
questo esemplare. Non sono stati ottenuti un contratto temporale specifico
Samsung né una misura hardware indipendente.

La `rootdisp` NTP e la `rootdelay` descrivono l'errore nel modello del server:
possono sostenere un'analisi che si affida esplicitamente a quel modello,
non diventano per il solo fatto di essere autenticate un nostro limite
indipendentemente verificato. Il [documento PTB sui sistemi di misura, §2.2](https://www.ptb.de/cms/fileadmin/internet/fachabteilungen/abteilung_8/8.5_metrologische_informationstechnik/8.51/PTB-8.51-MB09-ZS-EN-V09.pdf)
distingue l'uso di NTS dalla prova di accuratezza dell'orologio installato.
Non è una certificazione della nostra app; le sue prescrizioni non sono nuovi
requisiti di governance per questo repository.

## Perché l'accordo del log non basta

Sia `c` l'epoca riportata dal telefono, `delta` il suo errore di associazione
e `G` l'UTC GNSS. L'UTC del riferimento appartiene a un intervallo `W(c)`;
l'errore che vogliamo osservare è rispetto a `W(c + delta)`. Senza un vincolo
su `delta`, una discordanza può dipendere dall'associazione o dal clock GNSS.
L'accordo fra `G` e `W(c)` non distingue questi contributi e non calibra
indipendentemente `delta`. Questo è un limite di identificabilità del modello,
non una ragione per attribuire automaticamente la discordanza allo spoofing.

Non ricavare un massimo moltiplicando i 7 ms per un fattore gaussiano: il
contratto non dichiara una distribuzione gaussiana né una copertura empirica
delle code. Il ritardo fra epoca nativa e callback è una grandezza diversa;
non sostituisce l'epoca GNSS e non ne delimita indipendentemente l'errore.
Anche `BiasUncertaintyNanos` e gli altri errori stimati dal ricevitore restano
metadati, non una calibrazione indipendente del bersaglio sotto esame.

## Prossima consegna, senza un'altra matrice di budget

Il [riepilogo di più sessioni](../pnt/README.md#compare-multiple-android-sessions)
è implementato in `time-sensitivity`, riusando `android-session`, controllo
locale e replay. Richiede impostazioni numeriche compatibili ed esplicite:
risultato originale, alterazioni dell'UTC decodificato, confronto
locale/rete/combinato e denominatori comuni. Per la prossima valutazione usare
la challenge ±100 ms già descritta, senza una nuova matrice di budget. Conservare
ogni sessione, gruppo clock non valutabile e slot NTS fallito o non eseguito;
riportare anche la copertura propria di ciascun metodo. Un gruppo clock
non è automaticamente una prova indipendente.

Prima di aprire sessioni destinate alla valutazione, scegliere dal caso d'uso
un solo profilo di assunzioni e fissare selezione, regola di allarme e metriche.
I log già esposti sono sviluppo: non diventano dati esclusi cambiandone nome.
L'eventuale scelta ingegneristica di un nuovo profilo non qualifica i suoi
budget e non corregge gli esiti storici. Nessun profilo è adottato qui.
Qualunque calibrazione empirica usa solo sessioni di sviluppo dichiarate,
mai quelle di valutazione; non va presentata come qualifica indipendente
dell'associazione fisica GNSS/contatore.

Sui log originali misurare **allarmi senza alterazione introdotta**, disponibilità
e lacune. Chiamarli falsi allarmi su dati benigni verificati richiede la relativa
verità di riferimento. Sulle copie con ±100 ms misurare rilevazioni e mancate
rilevazioni della trasformazione nota; sono challenge software, non RF.
Riportare risultati per sessione e dipendenze fra epoche, senza dedurre una
prestazione di popolazione da poche sessioni correlate. Nessun ALLOW/BLOCK.

Questa consegna risponde a una domanda nuova: il vantaggio condizionale della
rete si ripete su sessioni separate senza nascondere gli allarmi sull'originale?
Se non si ripete, o richiede più allarmi degli stessi controlli locali, conservare
l'esito e rivalutare il canale; non cercare un budget vincente. Un risultato
positivo rimane circoscritto al test e alle assunzioni, e non chiude P2/P3.

Una garanzia fisica più forte richiede ancora un contratto del dispositivo
o una misura indipendente dell'associazione e del contatore nel dominio
dichiarato, oltre al riferimento per benigno/challenge. Quando queste evidenze
diventano disponibili, si riapre quella specifica qualifica. Nel frattempo
si sviluppa e misura il rilevatore condizionale, senza altre raccolte equivalenti
finalizzate soltanto a far concordare il clock.

La [valutazione successiva su tre nuove sessioni](../research/exploratory/PNT_ANDROID_SESSION_EVALUATION.md)
ha soddisfatto il criterio fissato prima della raccolta, con il solo profilo
ipotetico di 25 ms: il contributo esterno si ripete sui 47/117 gruppi clock
comuni, senza discordanze originali nei controlli valutabili. I 70 gruppi
insufficienti e i 16 timeout NTS restano visibili. Questa osservazione risolve
la domanda condizionale in quel blocco; i limiti fisici sopra restano aperti.
Il raccoglitore 0.4.2 separa i due endpoint NTS e conserva una distanza minima
fra gli avvii dello stesso endpoint, senza comprimere i tentativi dopo un ritardo.
Slot, fallimenti e cancellazioni restano verificabili nell'intake esistente;
la valutazione conclusa non cambia. La
[prova reale dell'11 ottobre](../research/exploratory/PNT_ANDROID_NTS_COVERAGE.md)
osserva l'isolamento dei timeout e 18/39 gruppi comuni con lo stesso profilo,
conservando 21 insufficienti e sette timeout su venti slot. Non dimostra un
guadagno stabile o qualifica i budget. La
[deriva software ±5 ms/s](../research/exploratory/PNT_ANDROID_TIME_DRIFT.md)
sui quattro rapporti già esposti è distinguibile anche dal locale. Le prime
epoche esterne possono precederlo, ma le ricevute NTS successive non dimostrano
una minore latenza live. La
[disponibilità ricostruita degli input](../research/exploratory/PNT_ANDROID_TIME_AVAILABILITY.md)
usa ora callback GNSS e completamenti NTS: anche questo risultato resta misto,
con un allarme combinato successivamente inconclusivo. Si conservano gli stessi
budget non qualificati e tutti gli esiti finali; la consegna effettiva del
risultato resta da misurare nel monitor condizionale di sessione.
