package org.satelliterf.observatory.clock;

import org.conscrypt.Conscrypt;
import org.cryptomator.siv.SivMode;
import javax.crypto.spec.SecretKeySpec;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;
import java.io.ByteArrayOutputStream;
import java.io.Closeable;
import java.io.IOException;
import java.io.InputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.LongSupplier;

/** Single RFC 8915 exchange. Transport only: no UTC budget, clock adjustment or retry. */
final class NtsClient implements NtsCapture.Probe {
    static final String AUTHENTICATION = "NTS_TLS13_AES_SIV_256";
    private final LongSupplier counter;
    private final SSLSocketFactory testFactory;
    private final AtomicBoolean cancelled = new AtomicBoolean();
    private Closeable active;

    NtsClient(LongSupplier counter) { this(counter, null); }
    // An explicit trusted test CA is used by loopback tests; production uses system roots.
    NtsClient(LongSupplier counter, SSLSocketFactory testFactory) {
        this.counter = counter;
        this.testFactory = testFactory;
    }

    private synchronized void track(Closeable socket) throws IOException {
        if (cancelled.get()) { socket.close(); throw new IOException("CAPTURE_INTERRUPTED"); }
        active = socket;
    }
    private synchronized void untrack() { active = null; }
    private void check() throws IOException {
        if (cancelled.get()) throw new IOException("CAPTURE_INTERRUPTED");
    }
    @Override public synchronized void close() throws IOException {
        cancelled.set(true);
        if (active != null) active.close();
    }
    private int remaining(long deadline) throws IOException {
        check();
        long delta = deadline - counter.getAsLong();
        if (delta <= 0) throw new SocketTimeoutException("NTS stage deadline exceeded");
        return (int) Math.max(1, Math.min(Integer.MAX_VALUE, (delta + 999999L) / 1000000L));
    }

    @Override public Map<String, Object> probe(String server, int kePort, int timeoutMs, int era) throws Exception {
        if (server == null || !server.matches("[A-Za-z0-9.-]+") || kePort < 1 || kePort > 65535
                || timeoutMs < 1 || timeoutMs > 60000 || era < 0 || era > 1) {
            throw new IllegalArgumentException("Invalid explicit NTS endpoint, timeout or era");
        }
        check();
        long keDeadline = counter.getAsLong() + timeoutMs * 1000000L;
        SSLSocketFactory factory = testFactory;
        if (factory == null) {
            SSLContext context = SSLContext.getInstance("TLS", Conscrypt.newProvider());
            context.init(null, null, null); // Platform trust store; never an accept-all manager.
            factory = context.getSocketFactory();
        }
        InetAddress address = InetAddress.getAllByName(server)[0]; // Select once, no address fallback.
        remaining(keDeadline); // DNS is OS-managed; stop/deadline checked before connecting.
        KeParameters parameters = null;
        byte[] c2s = null, s2c = null;
        String certificateHash;
        InetAddress tcpPeer;
        try {
          try (Socket tcp = new Socket()) {
            track(tcp);
            tcp.connect(new InetSocketAddress(address, kePort), remaining(keDeadline));
            tcpPeer = tcp.getInetAddress();
            try (SSLSocket tls = (SSLSocket) factory.createSocket(tcp, server, kePort, true)) {
                track(tls);
                tls.setEnabledProtocols(new String[]{"TLSv1.3"});
                SSLParameters ssl = tls.getSSLParameters();
                ssl.setEndpointIdentificationAlgorithm("HTTPS");
                tls.setSSLParameters(ssl);
                Conscrypt.setHostname(tls, server);
                Conscrypt.setApplicationProtocols(tls, new String[]{"ntske/1"});
                tls.setSoTimeout(remaining(keDeadline));
                tls.startHandshake();
                if (!"TLSv1.3".equals(tls.getSession().getProtocol())
                        || !"ntske/1".equals(Conscrypt.getApplicationProtocol(tls))) {
                    throw new IOException("NTS-KE TLS 1.3 / ALPN required");
                }
                tls.getOutputStream().write(concat(record(1, new byte[2], true),
                    record(4, new byte[]{0, 15}, false), record(0, new byte[0], true)));
                ByteArrayOutputStream response = new ByteArrayOutputStream();
                InputStream input = tls.getInputStream();
                while (true) {
                    tls.setSoTimeout(remaining(keDeadline));
                    byte[] header = readFully(tls, input, 4, keDeadline);
                    int length = u16(header, 2);
                    if (response.size() + 4 + length > 65536) throw new IOException("NTS-KE exceeds 64 KiB");
                    tls.setSoTimeout(remaining(keDeadline));
                    byte[] body = readFully(tls, input, length, keDeadline);
                    response.write(header);
                    response.write(body);
                    if ((u16(header, 0) & 0x7fff) == 0) break;
                }
                parameters = parseKe(response.toByteArray());
                c2s = Conscrypt.exportKeyingMaterial(tls, "EXPORTER-network-time-security", new byte[]{0, 0, 0, 15, 0}, 32);
                s2c = Conscrypt.exportKeyingMaterial(tls, "EXPORTER-network-time-security", new byte[]{0, 0, 0, 15, 1}, 32);
                if (c2s == null || s2c == null) throw new IOException("NTS TLS exporter unavailable");
                certificateHash = sha256(tls.getSession().getPeerCertificates()[0].getEncoded());
            }
          } finally { untrack(); }
            check();
            boolean negotiated = parameters.host != null;
            long udpDeadline = counter.getAsLong() + timeoutMs * 1000000L;
            InetAddress udpAddress = negotiated ? InetAddress.getAllByName(parameters.host)[0] : tcpPeer;
            remaining(udpDeadline);
            Request request = request(parameters.cookie, c2s);
            long sent, received;
            byte[] packet;
            try (DatagramSocket udp = new DatagramSocket()) {
                track(udp);
                udp.connect(udpAddress, parameters.port);
                udp.setSoTimeout(remaining(udpDeadline));
                sent = counter.getAsLong();
                udp.send(new DatagramPacket(request.packet, request.packet.length));
                byte[] buffer = new byte[65536];
                DatagramPacket incoming = new DatagramPacket(buffer, buffer.length);
                udp.receive(incoming);
                received = counter.getAsLong(); // Timestamp before decoding/authentication/file I/O.
                check();
                packet = Arrays.copyOf(buffer, incoming.getLength());
            } finally { untrack(); }
            Map<String, Object> result = response(packet, s2c, request.uid, request.origin, era);
            result.put("server", server);
            result.put("ntp_host", negotiated ? parameters.host : tcpPeer.getHostAddress());
            result.put("ntp_port", parameters.port);
            result.put("peer_address", Arrays.asList(udpAddress.getHostAddress(), parameters.port));
            result.put("nts_ke_peer_address", Arrays.asList(tcpPeer.getHostAddress(), kePort));
            result.put("ntp_host_negotiated", negotiated);
            result.put("authentication", AUTHENTICATION);
            result.put("certificate_sha256", certificateHash);
            result.put("ntp_era", era);
            result.put("send_monotonic_ns", sent);
            result.put("receive_monotonic_ns", received);
            result.put("counter_clock", "CLOCK_BOOTTIME");
            result.put("monotonic_resolution_ns", null);
            result.put("counter_resolution_source", "Nanosecond API units; effective resolution not qualified");
            return result;
        } finally {
            if (c2s != null) Arrays.fill(c2s, (byte) 0);
            if (s2c != null) Arrays.fill(s2c, (byte) 0);
            if (parameters != null) Arrays.fill(parameters.cookie, (byte) 0);
        }
    }

    static final class KeParameters {
        final String host;
        final int port;
        final byte[] cookie;
        KeParameters(String host, int port, byte[] cookie) { this.host = host; this.port = port; this.cookie = cookie; }
    }
    static KeParameters parseKe(byte[] bytes) throws IOException {
        if (bytes.length > 65536) throw new IOException("NTS-KE exceeds 64 KiB");
        Map<Integer, byte[]> seen = new LinkedHashMap<>();
        byte[] cookie = null;
        boolean ended = false;
        for (int pos = 0; pos < bytes.length;) {
            if (pos + 4 > bytes.length || ended) throw new IOException("Invalid NTS-KE framing");
            int rawKind = u16(bytes, pos), kind = rawKind & 0x7fff, length = u16(bytes, pos + 2);
            boolean critical = (rawKind & 0x8000) != 0;
            pos += 4;
            if (pos + length > bytes.length) throw new IOException("Truncated NTS-KE record");
            byte[] body = Arrays.copyOfRange(bytes, pos, pos + length);
            pos += length;
            if (kind == 2 || kind == 3) throw new IOException("NTS-KE error or warning");
            if (kind == 5) { if (cookie == null) cookie = body; }
            else if (kind == 0 || kind == 1 || kind == 4 || kind == 6 || kind == 7) {
                if (seen.put(kind, body) != null) throw new IOException("Duplicate NTS-KE negotiation record");
                if (kind == 0) {
                    if (!critical || body.length != 0) throw new IOException("Invalid NTS-KE end record");
                    ended = true;
                }
                if (kind == 1 && !critical) throw new IOException("Noncritical next-protocol record");
            } else if (critical) throw new IOException("Unknown critical NTS-KE record");
        }
        if (!ended || !Arrays.equals(seen.get(1), new byte[2])
                || !Arrays.equals(seen.get(4), new byte[]{0, 15}) || cookie == null) {
            throw new IOException("NTPv4 / AES-SIV-256 negotiation incomplete");
        }
        String host = null;
        if (seen.containsKey(6)) {
            for (byte b : seen.get(6)) if (b < 33 || b > 126) throw new IOException("Invalid negotiated NTP hostname");
            host = new String(seen.get(6), StandardCharsets.US_ASCII);
            if (host.isEmpty()) throw new IOException("Empty negotiated NTP hostname");
        }
        int port = 123;
        if (seen.containsKey(7)) {
            byte[] body = seen.get(7);
            if (body.length != 2 || (port = u16(body, 0)) == 0) throw new IOException("Invalid negotiated NTP port");
        }
        return new KeParameters(host, port, cookie);
    }

    static final class Request {
        final byte[] packet, uid, origin;
        Request(byte[] packet, byte[] uid, byte[] origin) { this.packet = packet; this.uid = uid; this.origin = origin; }
    }
    static Request request(byte[] cookie, byte[] key) throws IOException {
        SecureRandom random = new SecureRandom();
        byte[] uid = new byte[32], origin = new byte[8], header = new byte[48], nonce = new byte[16];
        random.nextBytes(uid); random.nextBytes(origin); random.nextBytes(nonce);
        header[0] = 0x23;
        System.arraycopy(origin, 0, header, 40, 8);
        byte[] paddedCookie = Arrays.copyOf(cookie, Math.max(12, (cookie.length + 3) / 4 * 4));
        byte[] prefix = concat(header, extension(0x0104, uid), extension(0x0204, paddedCookie));
        byte[] ciphertext = new SivMode().encrypt(new SecretKeySpec(key, "AES"), new byte[0], prefix, nonce);
        byte[] body = concat(shorts(nonce.length, ciphertext.length), nonce, ciphertext);
        return new Request(concat(prefix, extension(0x0404, Arrays.copyOf(body, (body.length + 3) / 4 * 4))), uid, origin);
    }
    static final class Field {
        final int kind, position;
        final byte[] body;
        Field(int kind, int position, byte[] body) { this.kind = kind; this.position = position; this.body = body; }
    }
    static List<Field> fields(byte[] data, int start) throws IOException {
        List<Field> result = new ArrayList<>();
        for (int pos = start; pos < data.length;) {
            if (pos + 4 > data.length) throw new IOException("Truncated NTP extension");
            int kind = u16(data, pos), length = u16(data, pos + 2);
            if (length < 4 || length % 4 != 0 || pos + length > data.length) throw new IOException("Invalid NTP extension framing");
            result.add(new Field(kind, pos, Arrays.copyOfRange(data, pos + 4, pos + length)));
            pos += length;
        }
        return result;
    }
    static Map<String, Object> response(byte[] packet, byte[] key, byte[] uid, byte[] origin, int era) throws IOException {
        if (packet.length < 48) throw new IOException("Short NTP response");
        List<Field> fields = fields(packet, 48);
        Field auth = null;
        int identifiers = 0;
        for (Field field : fields) {
            if (field.kind == 0x0104) {
                if (!Arrays.equals(field.body, uid)) throw new IOException("Wrong request identifier");
                identifiers++;
            }
            if (field.kind == 0x0404) {
                if (auth != null) throw new IOException("Multiple NTS authenticators");
                auth = field;
            }
            if (field.kind == 0x0204 || field.kind == 0x0304) throw new IOException("Unencrypted server cookie or placeholder");
        }
        if (identifiers != 1 || auth == null || fields.get(fields.size() - 1) != auth) throw new IOException("Missing authentication or wrong identifier");
        byte[] body = auth.body;
        if (body.length < 4) throw new IOException("Short NTS authenticator");
        int nlen = u16(body, 0), clen = u16(body, 2), cstart = 4 + (nlen + 3) / 4 * 4, end = cstart + clen;
        if (nlen == 0 || clen < 16 || end > body.length || !zeros(body, 4 + nlen, cstart) || !zeros(body, end, body.length)) {
            throw new IOException("Invalid NTS authenticator lengths or padding");
        }
        byte[] plaintext;
        try {
            plaintext = new SivMode().decrypt(new SecretKeySpec(key, "AES"), Arrays.copyOfRange(body, cstart, end),
                Arrays.copyOf(packet, auth.position), Arrays.copyOfRange(body, 4, 4 + nlen));
        } catch (GeneralSecurityException error) { throw new IOException("NTS response authentication failed"); }
        int cookies = 0;
        for (Field field : fields(plaintext, 0)) {
            if (field.kind == 0x0204) cookies++;
            if (field.kind == 0x0104 || field.kind == 0x0304 || field.kind == 0x0404) throw new IOException("Invalid encrypted NTS field");
        }
        if (cookies != 1) throw new IOException("Missing or excessive replacement cookies");
        if (!Arrays.equals(Arrays.copyOfRange(packet, 24, 32), origin)) throw new IOException("Wrong NTP origin timestamp");
        if ((packet[0] & 255) != 0x24 || (packet[1] & 255) < 1 || (packet[1] & 255) > 15) throw new IOException("Unsupported NTP mode/version/leap or unsynchronized server");
        long receive = timestamp(packet, 32, era), transmit = timestamp(packet, 40, era);
        if (transmit < receive) throw new IOException("Server timestamps run backwards or cross era");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("server_receive_unix_ns", receive);
        result.put("server_transmit_unix_ns", transmit);
        result.put("stratum", packet[1] & 255);
        result.put("root_delay_raw", ByteBuffer.wrap(packet, 4, 4).getInt());
        result.put("root_dispersion_raw", Integer.toUnsignedLong(ByteBuffer.wrap(packet, 8, 4).getInt()));
        result.put("response_sha256", sha256(packet));
        return result;
    }
    static long timestamp(byte[] data, int pos, int era) throws IOException {
        long seconds = Integer.toUnsignedLong(ByteBuffer.wrap(data, pos, 4).getInt());
        long fraction = Integer.toUnsignedLong(ByteBuffer.wrap(data, pos + 4, 4).getInt());
        if (seconds == 0 && fraction == 0) throw new IOException("Missing server timestamp");
        return (era * 4294967296L + seconds - 2208988800L) * 1000000000L + fraction * 1000000000L / 4294967296L;
    }
    static String sha256(byte[] bytes) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder result = new StringBuilder();
            for (byte b : digest) result.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
            return result.toString();
        } catch (GeneralSecurityException error) { throw new IllegalStateException(error); }
    }
    static byte[] record(int kind, byte[] body, boolean critical) { return concat(shorts(kind | (critical ? 0x8000 : 0), body.length), body); }
    static byte[] extension(int kind, byte[] body) throws IOException {
        if (body.length % 4 != 0 || body.length + 4 > 65535) throw new IOException("Invalid extension length");
        return concat(shorts(kind, body.length + 4), body);
    }
    private static byte[] shorts(int a, int b) { return ByteBuffer.allocate(4).putShort((short) a).putShort((short) b).array(); }
    private static int u16(byte[] data, int offset) { return ((data[offset] & 255) << 8) | (data[offset + 1] & 255); }
    static byte[] concat(byte[]... arrays) {
        int length = 0;
        for (byte[] a : arrays) length = Math.addExact(length, a.length);
        ByteBuffer buffer = ByteBuffer.allocate(length);
        for (byte[] a : arrays) buffer.put(a);
        return buffer.array();
    }
    private static boolean zeros(byte[] data, int start, int end) {
        for (int i = start; i < end; i++) if (data[i] != 0) return false;
        return true;
    }
    private byte[] readFully(SSLSocket tls, InputStream input, int length, long deadline) throws IOException {
        byte[] data = new byte[length];
        for (int pos = 0; pos < length;) {
            tls.setSoTimeout(remaining(deadline));
            int read = input.read(data, pos, length - pos);
            if (read < 0) throw new IOException("NTS-KE closed before end record");
            pos += read;
        }
        return data;
    }
}
