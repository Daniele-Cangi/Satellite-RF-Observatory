# Prima acquisizione GNSS e NTS con un telefono Android

Obiettivo: registrare il clock GNSS reale del telefono mentre lo stesso telefono
interroga un testimone UTC Internet autenticato. Non servono un ricevitore esterno,
root o un APK del progetto. Il risultato e una diagnostica temporale condizionale,
non un'autenticazione RF, una convalida della posizione o una prova di attacco.

## 1. Preparazione sul telefono

Installare [GNSS Logger di Google](https://developer.android.com/develop/sensors-and-location/sensors/gnss)
e [Termux da F-Droid](https://f-droid.org/en/packages/com.termux/).
La [guida ufficiale Termux](https://github.com/termux/termux-app#installation)
descrive installazione e compatibilita. E disponibile anche il
[fork ufficiale su Google Play](https://play.google.com/store/apps/details?id=com.termux),
verificato su Galaxy S21 FE (SM-G990B), Android 16, con Termux
`googleplay.2026.06.21` e Python 3.13.13. Se Android rifiuta un APK, usare un
canale ufficiale compatibile senza disattivare la verifica delle app. In Termux:

```sh
pkg update
pkg install python python-cryptography git
git clone https://github.com/Daniele-Cangi/Satellite-RF-Observatory.git
cd Satellite-RF-Observatory
python -m venv --system-site-packages .venv-time
. .venv-time/bin/activate
python -m pip install -r requirements-pnt-time.txt
python -m pnt android-time-probe --help
```

Il pacchetto Termux `python-cryptography` fornisce la libreria nativa; il venv
la riusa. I pin distinguono esplicitamente le piattaforme: Python con
`sys.platform == "android"` usa `cryptography==48.0.1` e `pyOpenSSL==26.2.0`,
una coppia supportata da [pyOpenSSL](https://www.pyopenssl.org/en/latest/changelog.html).
Gli altri runtime conservano `cryptography==50.0.2` e `pyOpenSSL==26.4.0`.
`service-identity==26.1.0` resta comune. Il tentativo con i soli pin desktop
sul telefono si e fermato nel backend Rust della compilazione di cryptography;
non ha prodotto un'acquisizione NTS. Se le versioni native installate non sono
compatibili con i pin del proprio runtime, conservare l'errore senza allentarli
o tentare un fallback automatico. Per questo percorso non
servono NumPy, SciPy, Hatanaka o le dipendenze del motore geometrico.

## 2. Una registrazione breve, sullo stesso telefono e avvio

1. All'aperto, con telefono fermo e connessione Internet, aprire GNSS Logger,
   concedere la posizione precisa e avviare la registrazione dei messaggi **Raw**.
2. Lasciare attiva la registrazione mentre in Termux si esegue il comando sotto.
   Tenere le app attive, per esempio in schermo diviso; non riavviare il telefono.
3. Dopo la fine delle sonde, fermare il logger ed esportare il file originale.
   Trasferire al PC quel file e `phone-nts.json`, mantenendo anche gli originali.

Il cavo non e necessario durante la raccolta: GNSS Logger e NTS girano sul
telefono, che puo usare il Wi-Fi. Per il controllo dal PC, Android 11+ offre
[debug wireless con abbinamento](https://developer.android.com/tools/adb#wireless-android11)
sulla stessa rete; una connessione USB iniziale puo preparare l'ambiente.
Verificare il collegamento wireless prima di scollegare il cavo; un cambio rete
puo disattivare il debug e cambiare IP/porta. Il PC controlla le app e recupera i
file, senza fornire il contatore alle sonde. Al termine fermare le app di raccolta
e i servizi temporanei e disattivare il debug wireless usato per la sessione.

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

### Metadati temporali aggiuntivi

Per raccogliere l'incertezza dell'epoca GNSS omessa dal log 3.1.1.3, usare
il [PNT Clock Collector](../pnt/android-collector/README.md) al posto di GNSS
Logger. Il piccolo APK registra `GnssClock` con i flag di disponibilita,
`ElapsedRealtimeUncertaintyNanos` e i contatori all'ingresso della callback e
dopo le letture API. Mantiene lo stesso formato Raw e percorso NTS/replay.
Tenere il raccoglitore visibile, anche in schermo diviso con Termux: quando
l'app viene nascosta chiude la sessione esplicitamente. Timestamp assenti,
callback vuote, errori e file parziali restano visibili. La confidenza Android
del 68% non diventa un limite indipendente; il ritardo della callback non
qualifica da solo l'associazione. Nessun budget o risultato storico cambia.

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

Per scomporre il clock originale senza modificare il confronto, aggiungere
`--android-clock-diagnostics` e `--local-counter-resolution-ns` a
`time-sensitivity`, anche con il solo `--offset-ns 0`. La
[diagnosi del telefono](../research/exploratory/PNT_PHONE_CLOCK_DIAGNOSTICS.md)
trova scarti di millisecondi fra clock hardware e contatore, con correzioni
di conversione al massimo di 235 ns. Le incertezze riportate restano metadati:
la diagnostica non calibra il budget di associazione, non cambia i verdetti
e non attribuisce il fenomeno a un attacco.

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
qualifica dei limiti e il beneficio benigno/challenge restano da verificare.
Riferimenti tecnici:
[GnssClock](https://developer.android.com/reference/android/location/GnssClock),
[SystemClock](https://developer.android.com/reference/android/os/SystemClock) e
[formato GNSS Logger](https://github.com/google/gps-measurement-tools/blob/master/LOGGING_FORMAT.md).

## Verifica sul dispositivo del 9 ottobre 2026

Sul Galaxy S21 FE sopra indicato, con GNSS Logger `v3.1.1.3`, i 204 test esistenti
di NTS, testimone temporale, Android Raw e clock Android passano sia in Termux
sia su Windows. Il primo trasferimento dei test mancava del rapporto storico
usato da un replay: 203 test passarono e uno falli per file assente. Trasferito
anche quell'input invariato, passano tutti; entrambi i log restano conservati.
Sul telefono `pip check` non rileva dipendenze incompatibili. Rimangono due
avvisi di deprecazione relativi al caricamento dei certificati del trust store.

La prova esplorativa all'interno usa il codice `8571827`, con i pin Android
espliciti sopra, e il comando di 10 round/3 s: **20/20 scambi NTS autenticati**,
10 per ciascun endpoint PTB, in circa 27,7 s. I 20 confronti con il **clock del
sistema Android** sono discordanti sotto i budget di sviluppo dichiarati:
separazione dagli intervalli fra 436,213 e 439,934 ms. Non sono confronti GNSS,
limiti calibrati o una diagnosi della causa.

Il file originale `gnss_log_2026_10_09_23_41_35.txt` contiene solo l'intestazione,
senza misure Raw o fix; Android registra zero eventi GNSS measurement per
l'app. `android-raw` termina con codice 2 e `no Android Raw measurements`,
senza rapporto numerico. La presenza di `ChipsetElapsedRealtimeNanos` nel nome
delle colonne non dimostra che il telefono ne fornisca valori utilizzabili.
Originali NTS/GNSS ed errori sono conservati localmente, non pubblicati come
corpus di qualifica. La ricezione indoor non e qualificata: serve una nuova
registrazione con cielo visibile, senza associare le nuove misure alle vecchie
sonde. Compatibilita effettiva dei timestamp e confronto GNSS/NTS restano aperti.

## Raccolta esterna via Wi-Fi del 10 ottobre 2026

Una nuova registrazione, sullo stesso dispositivo e codice, con telefono fermo
all'esterno secondo la dichiarazione dell'utente e senza USB, produce 1.897
righe Raw. Il canale GNSS/NTS reale e ora percorso: i valori clock necessari
sono presenti nelle righe GPS utilizzabili. Gli input restano privati sul
telefono e PC; questo resoconto non e un corpus pubblico di qualifica.

| Copertura conservata | Risultato |
|---|---|
| Intake GPS | 479 righe normalizzate, 86 epoche clock distinte |
| Altre costellazioni | 1.418 righe contate come non supportate |
| Sonde NTS, 10 round/3 s | 13/20 autenticate; 7 timeout conservati; durata 44,222 s |
| GPS nella finestra NTS con associazione assunta | 262 righe, 44 epoche; 217 righe fuori finestra restano insufficienti |
| Confronti dentro singoli scambi | 0/9.580 utilizzabili |
| Confronti fra tentativi consecutivi dello stesso endpoint | 183/8.622 `NOT_DISTINGUISHABLE`; 8.439 insufficienti |
| Righe GPS con supporto temporale | 183/479, corrispondenti a 32/86 epoche distinte |

Prima di esaminare i nuovi valori sono stati dichiarati gli stessi budget di
sviluppo: errore server 1 ms, deriva 100 ppm, errore UTC GNSS 1 ms e bracket
massimo 15 s. Il primo replay mantiene ignoto il limite di associazione fra
GNSS e CLOCK_BOOTTIME: tutti i confronti restano insufficienti, con uscita 2.
Un secondo replay separato usa l'assunzione esplicita di associazione di 1 ms,
gia dichiarata, e produce la copertura della tabella. Non e un limite misurato o
calibrato. Le 32 epoche distinte non sono 32 campioni statisticamente indipendenti.

I 183 intervalli utilizzabili sono larghi 40,548--58,437 ms: la compatibilita non
certifica l'accuratezza del clock, l'origine RF o una prestazione di rilevamento.
I 13 confronti con il clock del **sistema Android** rimangono
discordanti, separati dagli intervalli NTS di 361,543--432,124 ms; il clock GNSS
e una sorgente diversa. Nessuna soglia o finestra e stata adattata al risultato.
Entrambi i rapporti si riproducono esattamente con il replay esistente; gli
hash degli input originali coincidono con quelli dell'involucro CLI.
Restano da qualificare i budget e dimostrare il beneficio su benigno/challenge;
P2 e aperta e questa e una diagnostica esplorativa condizionale.

## Sensibilita agli scarti UTC software

Il replay esplorativo della stessa registrazione del 10 ottobre usa ora
`time-sensitivity`: sposta solo l'UTC decodificato del ricevitore, conservando
contatore, associazione, intervalli NTS, budget e fallimenti. Non modifica
`TimeNanos`, codici satellitari o pacchetti originali e non simula un attacco RF.
La griglia di sviluppo e stata scelta dopo aver esposto la baseline: zero e
gli scarti di entrambi i segni di 1, 10, 50, 100 e 1.000 ms. Non sono nuove
soglie di rilevamento o una conferma prospettica.

| Scarto aggiunto all'UTC | Righe compatibili | Righe discordanti | Epoche clock supportate |
|---|---:|---:|---:|
| 0 | 183 | 0 | 32 |
| -1 ms / +1 ms, ciascuno | 183 | 0 | 32 |
| -10 ms / +10 ms, ciascuno | 183 | 0 | 32 |
| -50 ms / +50 ms, ciascuno | 0 | 183 | 32 |
| -100 ms / +100 ms, ciascuno | 0 | 183 | 32 |
| -1 s / +1 s, ciascuno | 0 | 183 | 32 |

In ciascun caso **296/479 righe, 54/86 epoche**, restano insufficienti;
9.580/9.580 confronti con singolo scambio e 8.439/8.622 bracket restano
insufficienti. I sette timeout rimangono nel replay e non vengono aggirati.
I due endpoint PTB restano separati; appartengono alla stessa autorita e non
formano un quorum indipendente. Il replay con associazione ignota lascia
**479/479 righe e 86/86 epoche insufficienti per tutti gli scarti**, senza
un fallback verso l'assunzione di 1 ms.

Gli intervalli compatibili forniscono anche il limite esatto di questo caso:
ogni scarto aggiunto da **-15,809030 a +17,515728 ms**, estremi inclusi, resta
indistinguibile in tutti i 183 confronti utilizzabili. Uno scarto inferiore a
-34,704281 ms o superiore a +32,430833 ms e discordante in tutti. Fra questi
limiti l'esito dipende dal confronto specifico. Sono limiti condizionali su
questo input e questi budget, non accuratezza GNSS, sensibilita universale o
tassi di rilevamento. La precisione numerica degli estremi non calibra i budget.

Il [riepilogo aggregato](../research/exploratory/results/pnt_phone_time_sensitivity_v1.json)
conserva conteggi per scarto ed endpoint, epoche distinte, budget e hash degli
input e rapporti privati. Non pubblica fix o coordinate e non costituisce un
benchmark pubblico riproducibile senza quegli input. Gli originali e i due
nuovi rapporti completi restano nel fascicolo locale. Con i file conservati:

```console
python -m pnt time-sensitivity phone-time-outdoor-01-development-alignment.json --offset-ns -1000000000 --offset-ns -100000000 --offset-ns -50000000 --offset-ns -10000000 --offset-ns -1000000 --offset-ns 1000000 --offset-ns 10000000 --offset-ns 50000000 --offset-ns 100000000 --offset-ns 1000000000 --output phone-time-sensitivity-development-v1.json
```

Ripetere con `phone-time-outdoor-01-unknown-alignment.json` e un nuovo output
conserva tutti gli esiti insufficienti con uscita 2. La baseline di entrambi i
rapporti coincide con il replay originale, esclusi i metadati CLI delle sorgenti.
Il risultato orienta la prossima prova: qualificare indipendentemente
l'associazione temporale e gli altri budget, poi misurare ripetibilita, copertura
e beneficio benigno/challenge. Ripetere la stessa griglia non colmerebbe P2.

Il [confronto abbinato locale/NTS](../research/exploratory/PNT_PHONE_PAIRED_TIME.md)
ora distingue scarti costanti e salti introdotti durante il log. Lo scarto
costante di ±100 ms produce discordanza NTS in 145 righe/25 epoche che il
controllo locale relativo lascia passare. I piccoli salti mostrano invece
casi visibili solo localmente. L'originale ha gia 51 discordanze locali/9 epoche
sotto i budget assunti, di cui 38 righe/7 epoche abbinate: nessun tasso di falsi
allarmi o beneficio RF e qualificato. La nuova informazione non chiude P2.
