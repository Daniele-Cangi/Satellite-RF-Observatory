'use client';

import {
  ArrowDownToLine,
  ArrowUpRight,
  Check,
  Radio,
  ScanLine,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import archive from './results.json';
import Link from 'next/link';

type Event = (typeof archive.events)[number];
const number = (value: number, digits = 2) =>
  value.toLocaleString('it-IT', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
const date = (value: string) =>
  new Intl.DateTimeFormat('it-IT', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(value + 'T12:00:00Z'));
const utc = (value: string) =>
  value.slice(0, 10) + ' · ' + value.slice(11, 23) + ' UTC';

function EventPanel({ event }: { event: Event }) {
  const available = event.errorM !== null && event.radiusM !== null;
  const radius = event.radiusM ?? 0;
  const uncertaintyPass = available && radius <= event.thresholdM;
  const orbitPass = event.errorM !== null && event.errorM <= event.errorThresholdM;
  const holdoutPass = event.heldoutM !== null && event.heldoutConfirmed && Math.abs(event.heldoutM) <= event.heldoutThresholdM;
  return (
    <article
      className="event-panel"
      aria-label={`${event.target}, ${date(event.date)}`}
    >
      <div className="event-heading">
        <div>
          <p className="eyebrow">GPS · {date(event.date)}</p>
          <h2>
            {event.target}
            <span>
              {available ? 'Posizione ricostruita' : 'Dati non qualificati'}
            </span>
          </h2>
          <p className="muted">
            {available
              ? event.window + ' · evento storico'
              : 'Tentativo concluso prima del calcolo'}
          </p>
        </div>
        <div className={`status ${event.primaryPass ? 'passed' : ''}`}>
          {event.primaryPass ? <ShieldCheck size={17} aria-hidden="true" /> : <TriangleAlert size={17} aria-hidden="true" />}
          {event.primaryPass ? 'Criteri dell’evento soddisfatti' : available
            ? 'Soglia d’incertezza superata'
            : 'Copertura comune insufficiente'}
        </div>
      </div>
      {available ? (
        <>
          <div className="metrics">
            <section className="metric observed">
              <p className="eyebrow">
                <ScanLine size={17} aria-hidden="true" /> Confronto successivo
              </p>
              <h3>Errore di posizione osservato</h3>
              <p className="big-value">
                {number(event.errorM!)}
                <span>m</span>
              </p>
              <p>
                Scarto 3D rispetto all’orbita aperta <strong>dopo</strong> il
                congelamento della soluzione.
              </p>
              <div className={orbitPass ? 'success-line' : 'warning'}>
                {orbitPass ? <Check size={17} aria-hidden="true" /> : <TriangleAlert size={17} aria-hidden="true" />}
                {orbitPass ? 'Confronto orbitale entro il limite' : 'Confronto orbitale oltre il limite'}
              </div>
            </section>
            <section className="metric uncertainty">
              <p className="eyebrow">Dichiarata prima del confronto</p>
              <h3>Raggio d’incertezza</h3>
              <p className="radius-value">
                {number(radius / 1000, 3)}
                <span>km</span>
              </p>
              <p>
                Soglia del piano: <strong>{number(event.thresholdM / 1000, 0)} km</strong>.{' '}
                {uncertaintyPass ? 'Margine entro la soglia: ' : 'Superamento: '}
                <strong>{number(Math.abs(radius - event.thresholdM))} m</strong> (
                {number(Math.abs(radius / event.thresholdM - 1) * 100)}%).
              </p>
              <div className="ruler" aria-hidden="true">
                <div
                  className="ruler-fill"
                  style={{ width: `${Math.min((radius / 25000) * 100, 100)}%` }}
                />
                <div className="ruler-limit" />
              </div>
              <div className="ruler-labels">
                <span>0</span>
                <span>10 km · soglia</span>
                <span>25 km</span>
              </div>
            </section>
          </div>
          <div className="interpretation">
            <ShieldCheck size={22} aria-hidden="true" />
            <p>
              <strong>{event.primaryPass ? 'Un evento storico soddisfa tutti i criteri.' : 'Il risultato e il suo limite, insieme.'}</strong>{' '}
              {event.primaryPass ? 'Questo successo vale per il singolo evento e per le assunzioni dichiarate. ' : 'Il criterio completo dell’esperimento non è superato. '}
              L’errore osservato non sostituisce l’incertezza
              prospettica, che resta condizionata al modello dichiarato.
            </p>
          </div>
          <div className="detail-grid">
            <section className="surface">
              <div className="section-heading">
                <h3>Posizione all’emissione</h3>
                <span className="meta">ECEF · metri</span>
              </div>
              <div className="coordinates">
                {event.ecefM?.map((coordinate, index) => (
                  <div key={index}>
                    <span>{['X', 'Y', 'Z'][index]}</span>
                    <strong>{number(coordinate, 3)}</strong>
                  </div>
                ))}
              </div>
              <p className="small muted">
                Assi terrestri all’emissione. {number(event.emissionS!, 6)}{' '}
                secondi dalla mezzanotte GPST.
              </p>
            </section>
            <section className="surface">
              <div className="section-heading">
                <h3>Ricevitore escluso</h3>
                <span className="pill">{event.withheldStation.slice(0, 4)}</span>
              </div>
              <p className="holdout-value">
                {event.heldoutM! > 0 ? '+' : ''}
                {number(event.heldoutM!)} <span>m</span>
              </p>
              <p className="small muted">
                Scarto fra misura e previsione, senza usare i codici di{' '}
                {event.target} ricevuti da GOLD nella stima.
              </p>
              <p className={holdoutPass ? 'success-line' : 'warning'}>
                {holdoutPass ? <Check size={16} aria-hidden="true" /> : <TriangleAlert size={16} aria-hidden="true" />}{' '}
                {holdoutPass
                  ? 'Confermato entro la banda prevista'
                  : 'Non confermato'}
              </p>
            </section>
          </div>
          <section className="surface criteria">
            <div className="section-heading">
              <h3>Criteri del piano</h3>
              <span className="meta">Soglie conservate</span>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Controllo</TableHead>
                  <TableHead>Valore</TableHead>
                  <TableHead>Esito</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell>Errore 3D ≤ 10 km</TableCell>
                  <TableCell>{number(event.errorM!)} m</TableCell>
                  <TableCell className={orbitPass ? 'positive' : 'warning'}>{orbitPass ? 'Superato' : 'Non superato'}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>GOLD ≤ 100 m e nella banda prevista</TableCell>
                  <TableCell>{number(Math.abs(event.heldoutM!))} m</TableCell>
                  <TableCell className={holdoutPass ? 'positive' : 'warning'}>{holdoutPass ? 'Superato' : 'Non superato'}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Incertezza prospettica ≤ 10 km</TableCell>
                  <TableCell>{number(radius / 1000, 3)} km</TableCell>
                  <TableCell className={uncertaintyPass ? 'positive' : 'warning'}>{uncertaintyPass ? 'Superato' : 'Non superato'}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </section>
        </>
      ) : (
        <section className="no-position">
          <TriangleAlert size={32} aria-hidden="true" />
          <h3>Nessuna posizione stimata</h3>
          <p>
            Nella rete dichiarata per {event.target} sono disponibili{' '}
            <strong>{event.supportAvailable} epoche consecutive idonee comuni</strong>.
            {' '}Il piano ne richiedeva{' '}
            <strong>{event.supportRequired}</strong>.
          </p>
          <div className="absence-grid">
            <div>
              <strong>—</strong>
              <span>Posizione</span>
            </div>
            <div>
              <strong>—</strong>
              <span>Errore 3D</span>
            </div>
            <div>
              <strong>Non aperta</strong>
              <span>Orbita di confronto</span>
            </div>
          </div>
          <p className="small muted">
            Il tentativo è concluso. La rete e la regola non sono state cambiate
            dopo l’esito; nessuna posizione o conferma orbitale è stata calcolata.
          </p>
        </section>
      )}
      <section className="network">
        <h3>Rete di osservazione</h3>
        <div className="station-list">
          {event.fitStations.map((station) => (
            <span key={station}>
              <Radio size={14} aria-hidden="true" />
              {station.slice(0, 4)}
              <small>{station.slice(6)}</small>
            </span>
          ))}
          <span className="excluded">
            GOLD <small>verifica esclusa dal calcolo</small>
          </span>
        </div>
        {event.networkSelection && (
          <details className="audit">
            <summary>Selezione della rete: {event.networkSelection.candidateStations.length} candidate, {event.fitStations.length} selezionate</summary>
            <div className="audit-content">
              <p className="small muted">Prima finestra idonea e primo sottoinsieme previsto dal piano, senza usare l’orbita del bersaglio. GOLD resta esclusa dalla stima.</p>
              <ul className="network-decisions">
                {event.networkSelection.stations.map((station) => (
                  <li key={station.station}>
                    <strong>{station.station}</strong> · {station.station === event.withheldStation ? 'Ricevitore escluso' : event.fitStations.includes(station.station) ? 'Selezionata' : station.source_status === 'SOURCE_MISSING' ? 'File assente (HTTP 404)' : 'Non selezionata dal piano'}
                  </li>
                ))}
              </ul>
            </div>
          </details>
        )}
      </section>
      <section className="evidence">
        <div>
          <p className="eyebrow">Dati consultabili</p>
          <h3>Segui le evidenze</h3>
          <p className="muted">
            Ricevute originali, valori e provenienza. Il dossier contiene
            documenti JSON; le osservazioni RF complete sono disponibili nelle
            fonti.
          </p>
        </div>
        <div className="evidence-actions">
          <a className="button-primary" href={event.dossierUrl} download>
            <ArrowDownToLine size={17} aria-hidden="true" /> Scarica dossier
            JSON
          </a>
          <a
            className="button-link"
            href={event.sourceUrl}
            target="_blank"
            rel="noreferrer"
          >
            Esperimento su GitHub <ArrowUpRight size={17} aria-hidden="true" />
          </a>
        </div>
      </section>
      <details className="audit">
        <summary>Tempi, impronte e fonti</summary>
        <div className="audit-content">
          {event.freezeUtc && (
            <ol className="timeline">
              <li>
                <span>01 · Soluzione congelata</span>
                <time>{utc(event.freezeUtc)}</time>
              </li>
              <li>
                <span>02 · Ricevitore GOLD aperto</span>
                <time>{utc(event.heldoutUtc!)}</time>
              </li>
              <li>
                <span>03 · Orbita aperta</span>
                <time>{utc(event.oracleUtc!)}</time>
              </li>
            </ol>
          )}
          <p className="small muted">
            I tempi di questa sezione sono UTC; la data dell’evento e la
            finestra delle misure sono GPST.
          </p>
          <dl className="hashes">
            <dt>Stato operativo</dt>
            <dd>Concluso · {event.operationalStatus}</dd>
            <dt>Versione scientifica dell’archivio</dt>
            <dd>{event.sourceRevision}</dd>
            <dt>Esito scientifico originale</dt>
            <dd>{event.status}</dd>
            {event.solutionHash && (
              <>
                <dt>SHA-256 della soluzione</dt>
                <dd>{event.solutionHash}</dd>
              </>
            )}
            <dt>SHA-256 del dossier scaricabile</dt>
            <dd>{event.dossierHash}</dd>
          </dl>
          <div className="source-links">
            {event.sources.map((source) => (
              <a
                key={source.url}
                href={source.url}
                target="_blank"
                rel="noreferrer"
              >
                {source.label}
                <ArrowUpRight size={14} aria-hidden="true" />
              </a>
            ))}
          </div>
        </div>
      </details>
    </article>
  );
}

export default function Home() {
  return (
    <>
      <a className="skip-link" href="#archive">
        Vai alle verifiche
      </a>
      <header className="site-header">
        <Link
          className="brand"
          href="/"
          aria-label="Satellite RF Observatory, pagina iniziale"
        >
          <Radio size={24} aria-hidden="true" />
          <span>
            SATELLITE RF<small>OBSERVATORY</small>
          </span>
        </Link>
        <span className="archive-label">
          <span /> Archivio sperimentale
        </span>
        <a className="header-link" href="#method">
          Come leggere i risultati <ArrowUpRight size={15} aria-hidden="true" />
        </a>
      </header>
      <main id="archive">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Dalle osservazioni alla posizione</p>
            <h1>Verifiche di posizione</h1>
          </div>
          <p>
            {archive.events.length} tentativi documentati · {archive.events.filter((event) => event.primaryPass).length} con criteri soddisfatti
            <br />
            <span className="muted">
              Dati storici · nessuna posizione in tempo reale
            </span>
          </p>
        </div>
        <Tabs defaultValue="g14-2026-09-03" className="event-tabs">
          <TabsList aria-label="Scegli un esperimento" className="event-picker">
            {archive.events.map((event, index) => (
              <TabsTrigger
                className="event-choice"
                value={event.id}
                key={event.id}
              >
                <span className="choice-index">0{index + 1}</span>
                <span>
                  <strong>{event.target}</strong>
                  <small>{date(event.date)}</small>
                </span>
                <span className="choice-state">
                  {event.primaryPass ? 'Criteri soddisfatti' : event.errorM === null
                    ? 'Dati insufficienti'
                    : 'Posizione calcolata'}
                </span>
              </TabsTrigger>
            ))}
          </TabsList>
          {archive.events.map((event) => (
            <TabsContent value={event.id} key={event.id}>
              <EventPanel event={event} />
            </TabsContent>
          ))}
        </Tabs>
        <section id="method" className="method">
          <p className="eyebrow">Metodo e ambito</p>
          <h2>
            Prima il calcolo.
            <br />
            Poi il confronto.
          </h2>
          <div>
            <p>
              Le posizioni sono ricostruite da osservazioni RF pubbliche, con
              coordinate terrestri e riferimenti GPS diversi dal satellite
              bersaglio. La sua orbita entra soltanto nel confronto successivo.
            </p>
            <p>
              L’incertezza viene dichiarata prima di aprire le conferme. I
              risultati descrivono singoli eventi GPS: non dimostrano velocità,
              identificazione autonoma o affidabilità universale. L’orbita IGS
              può condividere osservazioni delle stazioni.
            </p>
          </div>
        </section>
      </main>
      <footer>
        <span>Satellite RF Observatory</span>
        <span>Posizioni, limiti, evidenze.</span>
        <a
          href="https://github.com/Daniele-Cangi/Satellite-RF-Observatory"
          target="_blank"
          rel="noreferrer"
        >
          Repository <ArrowUpRight size={14} aria-hidden="true" />
        </a>
      </footer>
    </>
  );
}
