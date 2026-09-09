import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Satellite RF Observatory · Verifiche di posizione',
  icons: { icon: '/favicon.svg' },
  description:
    'Posizioni satellitari ricostruite da osservazioni RF pubbliche. Consulta errori osservati, incertezze prospettiche e dossier delle verifiche.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it">
      <body>{children}</body>
    </html>
  );
}
