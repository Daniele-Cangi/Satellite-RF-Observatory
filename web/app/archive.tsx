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
        <div className="status">
          <TriangleAlert size={17} aria-hidden="true" />
          {available
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
              <div className="success-line">
                <Check size={17} aria-hidden="true" /> Confronto orbitale entro
                il limite
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
                Soglia del piano: <strong>10 km</strong>. Superamento:{' '}
                <strong>{number(radius - event.thresholdM)} m</strong> (
                {number((radius / event.thresholdM - 1) * 100)}%).
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
              <strong>Il risultato e il suo limite, insieme.</strong> Il
              confronto è positivo, ma il criterio completo dell’esperimento non
              è superato. L’errore osservato non sostituisce l’incertezza
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
                <span className="pill">GOLD</span>
              </div>
              <p className="holdout-value">
                {event.heldoutM! > 0 ? '+' : ''}
                {number(event.heldoutM!)} <span>m</span>
              </p>
              <p className="small muted">
                Scarto fra misura e previsione, senza usare i codici di{' '}
                {event.target} ricevuti da GOLD nella stima.
              </p>
              <p className="success-line">
                <Check size={16} aria-hidden="true" />{' '}
                {event.heldoutConfirmed
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
                  <TableCell className="positive">Superato</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>GOLD ≤ 100 m e nella banda prevista</TableCell>
                  <TableCell>{number(Math.abs(event.heldoutM!))} m</TableCell>
                  <TableCell className="positive">Superato</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Incertezza prospettica ≤ 10 km</TableCell>
                  <TableCell>{number(radius / 1000, 3)} km</TableCell>
                  <TableCell className="warning">Non superato</TableCell>
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
            Le otto stazioni contengono osservazioni di G12, ma soltanto{' '}
            <strong>{event.supportAvailable} epoche consecutive</strong> sono
            comuni. Il piano ne richiedeva{' '}
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
            La regola non è stata accorciata dopo l’esito. Questo tentativo
            resta distinto da quello del 5 settembre.
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
            3 tentativi documentati
            <br />
            <span className="muted">
              Dati storici · nessuna posizione in tempo reale
            </span>
          </p>
        </div>
        <Tabs defaultValue={archive.events[0].id} className="event-tabs">
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
                  {event.errorM === null
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
