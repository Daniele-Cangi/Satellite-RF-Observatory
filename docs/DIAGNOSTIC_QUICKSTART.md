# Prima diagnostica riproducibile

Questa guida porta un nuovo utilizzatore dal checkout a un rapporto PC e,
se dispone di un telefono, alla raccolta e consultazione dei propri dati.
Il risultato e una diagnostica di ricerca: l'installazione riuscita non
qualifica tempo, posizione o rilevamento di spoofing.

## 1. Provare il rapporto senza telefono

Servono Git e Python 3.13. Da una cartella di lavoro:

```console
git clone https://github.com/Daniele-Cangi/Satellite-RF-Observatory.git
cd Satellite-RF-Observatory
git rev-parse HEAD
```

Conservare il commit stampato con i propri risultati. Per riprodurre un'altra
consegna, usare il suo commit prima di eseguire i comandi. Creare un ambiente
Python separato; il rapporto offline di una sessione Android usa soltanto la
libreria standard, senza dipendenze scientifiche o connessioni di rete.

**Windows / PowerShell:**

```powershell
python -m venv .venv-diagnostic
.\.venv-diagnostic\Scripts\python.exe -m pnt android-session pnt/examples/android-session-synthetic.zip --output demo-report.json
$LASTEXITCODE
```

**Linux:**

```sh
python3.13 -m venv .venv-diagnostic
.venv-diagnostic/bin/python -m pnt android-session pnt/examples/android-session-synthetic.zip --output demo-report.json
echo $?
```

L'esito atteso e **INSUFFICIENT_EVIDENCE**, con codice di uscita **2** e
`demo-report.json` scritto. Il messaggio "No usable timing comparison" significa
che il confronto non e eseguito: mancano budget indipendenti, intenzionalmente.
Un'uscita 2 senza rapporto puo invece indicare un errore di input/output:
leggere il messaggio, senza considerarla una diagnostica valida.

Aprire il JSON e verificare:

- `capture_id`: `synthetic-ci`; `comparison` e `analysis_options`: `null`;
- `intake.coverage.status_counts`: quattro righe Raw, tre GPS normalizzate e
  una di una costellazione non supportata;
- `witness_status_counts`: tre scambi sintetici etichettati come autenticati
  e un `WITNESS_UNAVAILABLE`, con il timeout conservato;
- `issues` e `checks_not_performed`: assunzioni mancanti e controlli non eseguiti;
- `sources` e `processor`: hash degli input e revisione del motore.

Tutti i valori sono inventati dai [test nativi](../pnt/examples/README.md),
compresa l'etichetta di autenticazione NTS. Il comando non interroga server e
non verifica pacchetti NTS reali. L'esempio dimostra il percorso software, non
una misura sul cielo o un risultato di sicurezza. Il suo rapporto resta sul PC:
l'app non ha gli originali privati di questa sessione sintetica da abbinare.

Gli output esistenti non sono sovrascritti. Per ripetere il comando usare un
nuovo nome di rapporto; conservare lo ZIP e il rapporto precedente.

## 2. Acquisire con un telefono Android

Servono Android 10+ con supporto alle misure GNSS, Internet e vista del cielo.
Il supporto effettivo si controlla con i callback e i campi ricevuti, non dal
solo modello o dalla versione di Android.

Per una prima installazione non serve costruire l'APK:

1. Aprire il [workflow Android clock collector](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/android-collector.yml).
   Scegliere una **esecuzione push su main completata con successo**, annotando
   il commit del run. I run di PR sono build di sviluppo del relativo ramo.
2. Scaricare l'artefatto `android-collector-ubuntu-latest` di quel run e aprire
   `outputs/apk/debug/app-debug.apk`. GitHub puo richiedere l'accesso; gli
   artefatti scadono. Se non disponibile, usare la [build locale](../pnt/android-collector/README.md#build-and-checks).
3. Trasferire l'APK sul telefono e installarlo. E un APK di sviluppo, non una
   pubblicazione Play Store. Annotare commit e versione scelti; i due sistemi
   CI possono usare chiavi debug diverse. Per aggiornare un'app gia installata
   mantenendo i dati serve la stessa chiave; esportare gli originali e seguire
   la guida di build, senza cancellare dati per aggirare l'errore di firma.
4. Abilitare Location, concedere posizione precisa e premere **Start GNSS + NTS**
   con l'app visibile e il telefono fermo. Non servono USB, Termux o controllo PC
   durante la raccolta. La sessione termina a calendario o con **Stop recording**.
5. Premere **Export last session** e salvare lo ZIP nel selettore documenti Android.
   Trasferirlo al PC, conservando gli originali. Una raccolta senza misure o con
   timeout resta un risultato da documentare, non va sostituita in silenzio.

Per riprodurre il motore associato alla build, ottenere il commit annotato con
`git fetch origin` e `git switch --detach COMMIT-DEL-RUN` in un checkout pulito.
Se quella versione non contiene questa guida/esempio, usare la guida per i
passaggi e il checkout scelto per analizzare i propri dati.

## 3. Analizzare e consultare la propria sessione

Dalla radice del repository, usando il Python dell'ambiente appena creato:

```powershell
.\.venv-diagnostic\Scripts\python.exe -m pnt android-session SESSIONE-ESPORTATA.zip --output phone-report.json
```

Su Linux usare `.venv-diagnostic/bin/python`. Sostituire il nome dello ZIP con
quello realmente esportato. Senza assunzioni esplicite l'esito resta
**INSUFFICIENT_EVIDENCE** (uscita 2): il rapporto conserva acquisizione, lacune,
fallimenti e controlli non eseguiti. Non equivale a un allarme o a un fix valido.

Copiare `phone-report.json` sullo **stesso telefono**, lasciando gli originali
nell'app, e premere **Open PC report**. L'app verifica nomi, dimensioni e hash
degli input prima di mostrarlo; si affida all'aritmetica PC. Un rapporto di
un'altra sessione, compreso quello sintetico, non puo essere importato come proprio.

Il flusso minimo e completo quando il rapporto corrisponde agli originali ed e
consultabile, anche se scientificamente insufficiente. Conservare ZIP, rapporto
e commit. Non disinstallare o cancellare i dati dell'app prima dell'esportazione.

Per un confronto numerico condizionale usare le
[opzioni esplicite e il replay esistente](../pnt/android-collector/README.md#zip-to-pc-report-to-phone).
Questa guida non propone valori temporali precompilati. Le sonde NTS Python
richiedono `requirements-pnt-time.txt`; il server HTTPS privato richiede le
proprie dipendenze; la geometria richiede `requirements-positioning.txt`.
Il [monitor LAN opzionale](../pnt/android-collector/README.md#private-pc-connection)
puo essere configurato dopo questo primo ciclo offline.

I prossimi requisiti fisici sono nel [piano PNT](PNT_SECURITY_PLAN.md)
e i risultati dei diversi verticali nello [stato del progetto](PROJECT_STATUS.md).
