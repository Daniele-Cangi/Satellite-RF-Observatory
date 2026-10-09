# Prima acquisizione GNSS e NTS con un telefono Android

Obiettivo: registrare il clock GNSS reale del telefono mentre lo stesso telefono
interroga un testimone UTC Internet autenticato. Non servono un ricevitore esterno,
root o un APK del progetto. Il risultato e una diagnostica temporale condizionale,
non un'autenticazione RF, una convalida della posizione o una prova di attacco.

## 1. Preparazione sul telefono

Installare [GNSS Logger di Google](https://developer.android.com/develop/sensors-and-location/sensors/gnss)
e [Termux da F-Droid](https://f-droid.org/en/packages/com.termux/).
La [guida ufficiale Termux](https://github.com/termux/termux-app#installation)
descrive installazione e compatibilita. In Termux:

```sh
pkg update
pkg install python python-cryptography git
git clone --branch feat/android-gnss-time-capture https://github.com/Daniele-Cangi/Satellite-RF-Observatory.git
cd Satellite-RF-Observatory
python -m venv --system-site-packages .venv-time
. .venv-time/bin/activate
python -m pip install -r requirements-pnt-time.txt
python -m pnt android-time-probe --help
```

Il pacchetto Termux `python-cryptography` fornisce la libreria nativa; il venv
la riusa. I pin restano quelli del progetto: se le versioni installate non sono
compatibili, conservare l'errore senza allentare i pin. Per questo percorso non
servono NumPy, SciPy, Hatanaka o le dipendenze del motore geometrico. Dopo il merge
si puo clonare `main` al posto del branch indicato.

## 2. Una registrazione breve, sullo stesso telefono e avvio

1. All'aperto, con telefono fermo e connessione Internet, aprire GNSS Logger,
   concedere la posizione precisa e avviare la registrazione dei messaggi **Raw**.
2. Lasciare attiva la registrazione mentre in Termux si esegue il comando sotto.
   Tenere le app attive, per esempio in schermo diviso; non riavviare il telefono.
3. Dopo la fine delle sonde, fermare il logger ed esportare il file originale.
   Trasferire al PC quel file e `phone-nts.json`, mantenendo anche gli originali.

```sh
python -m pnt android-time-probe --server ptbtime1.ptb.de --server ptbtime2.ptb.de --collector-source "Samsung; GNSS Logger e Termux sullo stesso telefono e avvio" --rounds 10 --interval 3 --server-error-ns 1000000 --rate-error-ppm 100 --budget-source "Assunzioni di sviluppo non calibrate; non limiti certificati" --output phone-nts.json
```

Sono 20 tentativi dichiarati, senza sostituzione dei fallimenti o retry nascosti.
La durata puo superare i 30 secondi se la rete e lenta. Il calendario parte a
intervalli di 3 secondi; se una sonda ritarda, la successiva parte in ritardo.
Ctrl+C conserva i tentativi eseguiti e quelli non iniziati nel rapporto. Un arresto
forzato del processo da parte di Android puo invece impedire il salvataggio.
Un percorso di output gia esistente non viene sovrascritto.

Il JSON usa **CLOCK_BOOTTIME**, che include la sospensione, nello stesso dominio
di `elapsedRealtimeNanos` di Android. Un PC o `time-probe` ordinario non fornisce
questa associazione. La lettura del clock del sistema resta etichettata come
clock del telefono: GNSS Logger registra separatamente il clock GNSS. La
[implementazione AOSP](https://android.googlesource.com/platform/system/core/+/refs/heads/main/libutils/SystemClock.cpp)
esplicita il collegamento tra elapsed realtime e CLOCK_BOOTTIME.

## 3. Importazione e confronto sul PC

Per prima cosa importare il log, senza attribuirgli un esito scientifico:

```console
python -m pnt android-raw gnss_log.txt --output phone-raw.json
```

L'intestazione conserva modello, piattaforma e colonne; verificare in particolare
`ChipsetElapsedRealtimeNanos`. Il nome commerciale del telefono non garantisce
la disponibilita del campo. Servono anche `TimeNanos`, `FullBiasNanos`, `BiasNanos`
e `HardwareClockDiscontinuityCount` validi. Le righe GPS inutilizzabili restano
nel rapporto; le altre costellazioni restano contate nell'intake esistente.

Il primo replay puo mantenere **ignoto** il limite di associazione:

```console
python -m pnt android-time-compare phone-nts.json gnss_log.txt --association-source "Registrati sullo stesso telefono e avvio, durante la raccolta NTS" --gps-utc-offset-seconds 18 --time-scale-source "IERS Leap_Second.dat, bollettino C72, verificato per ottobre 2026" --utc-error-ns 1000000 --utc-error-source "Assunzione di sviluppo non calibrata" --bracket-span-ns 15000000000 --output phone-time-intake.json
```

L'assenza di `--epoch-alignment-error-ns` produce un rapporto con le righe e i
fallimenti conservati, stato `INSUFFICIENT_EVIDENCE` e codice di uscita 2. Per
esplorare il confronto, aggiungere un limite esplicito e la sua provenienza,
per esempio `--epoch-alignment-error-ns 1000000 --epoch-alignment-source
"Assunzione di sviluppo di 1 ms, non qualificata"`, usando un nuovo output.
Questi numeri di esempio non sono misure di accuratezza; il rapporto rimane
condizionale e non calibrato. Non sceglierli dall'accordo tra UTC GNSS e NTS.

## Significato del rapporto

Il clock comune e `TimeNanos - FullBiasNanos - BiasNanos`, riferito all'epoca del
clock GNSS. La conversione aggiunge l'epoca GPS Unix e sottrae il GPS-UTC
**fornito da una fonte esterna**. Il valore di esempio 18 s e quello vigente nel
periodo indicato, da [verificare alla data della registrazione](https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat).
Il campo `LeapSecond` del ricevitore non sostituisce questa fonte; non si
supportano intervalli che attraversano un secondo intercalare.

L'epoca di confronto e `ChipsetElapsedRealtimeNanos` piu/minus il limite esplicito
di associazione GNSS/contatore. Deve rientrare interamente nella finestra della
raccolta NTS. L'associazione a telefono e avvio e una dichiarazione del
collettore: GNSS Logger non fornisce un'identita di avvio autenticata.
Non associare vecchi log a nuove sonde copiando un ID.

`TimeOffsetNanos` appartiene alla singola misura satellitare: non sposta questo
clock comune. `utcTimeMillis`, l'ora di scrittura/ricezione del file e le
incertezze dichiarate dal ricevitore non diventano limiti indipendenti.
In particolare, le incertezze Android sono statistiche, non limiti deterministici.
La conversione di una frazione di nanosecondo conserva un margine di 1 ns.

Il confronto riusa gli intervalli NTS e il replay `time-compare`, senza un nuovo
sigillo o protocollo. Con `--bracket-span-ns` usa solo tentativi consecutivi dello
stesso endpoint, conservando i fallimenti; non mescola autorita. Piu righe Raw
possono ripetere lo stesso clock: **il numero di righe non e il numero di epoche
indipendenti**. Ogni riga resta visibile, senza fit o smoothing dei salti.

Un esito `NOT_DISTINGUISHABLE` significa sovrapposizione sotto i budget dichiarati;
`INCONSISTENT_WITH_WITNESS` significa discordanza sotto gli stessi budget, senza
attribuirne la causa a uno spoofer. I rapporti salvati richiedono fiducia nel
collettore; SHA-256 e autenticazione simmetrica NTS non costituiscono una firma
forense trasferibile del server.

I test usano trasporto sintetico e un campione Raw pubblico gia esposto. La
prima acquisizione su questo Samsung, la qualifica dei limiti e il beneficio
benigno/challenge restano da verificare. Riferimenti tecnici:
[GnssClock](https://developer.android.com/reference/android/location/GnssClock),
[SystemClock](https://developer.android.com/reference/android/os/SystemClock) e
[formato GNSS Logger](https://github.com/google/gps-measurement-tools/blob/master/LOGGING_FORMAT.md).
