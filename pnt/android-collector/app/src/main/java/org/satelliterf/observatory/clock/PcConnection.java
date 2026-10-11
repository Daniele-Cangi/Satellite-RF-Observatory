package org.satelliterf.observatory.clock;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.Strictness;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.Base64;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManagerFactory;
import javax.net.ssl.X509TrustManager;

/** Explicit private PC connection. Exact leaf trust plus normal HTTPS identity checks. */
final class PcConnection {
    static final int MAX_SNAPSHOT = 32 * 1024 * 1024;
    private static final com.google.gson.Gson JSON = new GsonBuilder().setStrictness(Strictness.STRICT).create();
    private static final ScheduledExecutorService DEADLINES = Executors.newSingleThreadScheduledExecutor(task -> {
        Thread thread = new Thread(task, "pnt-pc-request-deadline");
        thread.setDaemon(true);
        return thread;
    });
    final URI address;
    private final String token;
    private final SSLContext tls;
    private volatile HttpsURLConnection active;
    private volatile boolean cancelled;

    private PcConnection(URI address, String token, SSLContext tls) {
        this.address = address;
        this.token = token;
        this.tls = tls;
    }

    static PcConnection read(InputStream input) throws Exception {
        byte[] bytes = readLimited(input, 16384);
        JsonObject config = JSON.fromJson(new String(bytes, StandardCharsets.UTF_8), JsonObject.class);
        if (config == null || !"pnt-android-pc-connection-v1".equals(config.get("schema").getAsString())) {
            throw new IOException("Unsupported PC connection file");
        }
        URI address = URI.create(config.get("url").getAsString());
        if (!"https".equals(address.getScheme()) || !privateIpv4(address.getHost())
                || address.getPort() < 1 || address.getPort() > 65535 || address.getUserInfo() != null
                || address.getQuery() != null || address.getFragment() != null
                || !"".equals(address.getPath())) throw new IOException("Expected a private LAN HTTPS address and port");
        String token = config.get("token").getAsString();
        if (!token.matches("[0-9a-f]{64}")) throw new IOException("Invalid PC connection credential");
        byte[] der = Base64.getDecoder().decode(config.get("certificate_der").getAsString());
        X509Certificate cert = (X509Certificate) CertificateFactory.getInstance("X.509")
            .generateCertificate(new ByteArrayInputStream(der));
        cert.checkValidity();
        KeyStore store = KeyStore.getInstance(KeyStore.getDefaultType());
        store.load(null);
        store.setCertificateEntry("explicit-pc", cert);
        TrustManagerFactory factory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        factory.init(store);
        X509TrustManager standard = (X509TrustManager) factory.getTrustManagers()[0];
        X509TrustManager pinned = new X509TrustManager() {
            @Override public void checkServerTrusted(X509Certificate[] chain, String authType)
                    throws java.security.cert.CertificateException {
                if (chain.length == 0 || !MessageDigest.isEqual(cert.getEncoded(), chain[0].getEncoded())) {
                    throw new java.security.cert.CertificateException("PC certificate changed; explicit reconfiguration required");
                }
                chain[0].checkValidity();
                standard.checkServerTrusted(chain, authType);
            }
            @Override public void checkClientTrusted(X509Certificate[] chain, String authType)
                    throws java.security.cert.CertificateException { standard.checkClientTrusted(chain, authType); }
            @Override public X509Certificate[] getAcceptedIssuers() { return standard.getAcceptedIssuers(); }
        };
        SSLContext tls = SSLContext.getInstance("TLS");
        tls.init(null, new X509TrustManager[]{pinned}, null);
        return new PcConnection(address, token, tls);
    }

    static boolean privateIpv4(String value) {
        if (value == null || !value.matches("[0-9]{1,3}(\\.[0-9]{1,3}){3}")) return false;
        String[] pieces = value.split("\\.");
        int[] n = new int[4];
        for (int i = 0; i < 4; i++) {
            n[i] = Integer.parseInt(pieces[i]);
            if (n[i] > 255 || !Integer.toString(n[i]).equals(pieces[i])) return false;
        }
        return n[0] == 127 || n[0] == 10 || n[0] == 192 && n[1] == 168
            || n[0] == 172 && n[1] >= 16 && n[1] <= 31;
    }

    PcConnection fresh() { return new PcConnection(address, token, tls); }
    static byte[] readLimited(InputStream input, int limit) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int count;
        while ((count = input.read(buffer)) != -1) {
            if (count > limit-output.size()) throw new IOException("PC transport input exceeds size limit");
            output.write(buffer, 0, count);
        }
        return output.toByteArray();
    }
    JsonObject health() throws Exception {
        JsonObject result = request("/health", null, null, null);
        if (!result.get("ready").getAsBoolean()) throw new IOException("PC receiver is not ready");
        return result;
    }
    JsonObject send(String id, byte[] raw, byte[] nts) throws Exception {
        if (!id.matches("[a-zA-Z0-9-]{1,80}") || raw.length == 0 || nts.length == 0
                || raw.length > MAX_SNAPSHOT - nts.length) throw new IOException("Invalid or oversized native snapshot");
        JsonObject receipt = request("/snapshot", id, raw, nts);
        if (!id.equals(receipt.get("capture_id").getAsString()) || !receipt.get("stored").getAsBoolean()) {
            throw new IOException("PC did not acknowledge this capture");
        }
        return receipt;
    }
    private JsonObject request(String path, String id, byte[] raw, byte[] nts) throws Exception {
        if (cancelled) throw new IOException("PC transfer cancelled");
        HttpsURLConnection connection = (HttpsURLConnection) address.resolve(path).toURL().openConnection();
        connection.setSSLSocketFactory(tls.getSocketFactory());
        // Keep the platform HTTPS hostname verifier; never accept redirects or plain HTTP.
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(5000);
        connection.setRequestProperty("Authorization", "Bearer " + token);
        active = connection;
        // Also bound writes and trickling reads; ordinary per-read timeouts do not.
        var deadline = DEADLINES.schedule(connection::disconnect, 10, TimeUnit.SECONDS);
        try {
            if (cancelled) throw new IOException("PC transfer cancelled");
            if (raw != null) {
                connection.setRequestMethod("POST");
                connection.setDoOutput(true);
                connection.setFixedLengthStreamingMode(raw.length + nts.length);
                connection.setRequestProperty("Content-Type", "application/octet-stream");
                connection.setRequestProperty("X-PNT-Capture-Id", id);
                connection.setRequestProperty("X-PNT-Raw-Bytes", Integer.toString(raw.length));
                try (var output = connection.getOutputStream()) { output.write(raw); output.write(nts); }
            }
            if (connection.getResponseCode() != 200) throw new IOException("PC refused request: HTTP " + connection.getResponseCode());
            byte[] bytes;
            try (InputStream input = connection.getInputStream()) { bytes = readLimited(input, 65536); }
            JsonObject result = JSON.fromJson(new String(bytes, StandardCharsets.UTF_8), JsonObject.class);
            if (result == null || !"pnt-android-transfer-receipt-v1".equals(result.get("schema").getAsString())) {
                throw new IOException("Unsupported PC transport receipt");
            }
            return result;
        } finally { deadline.cancel(false); connection.disconnect(); active = null; }
    }
    void cancel() {
        cancelled = true;
        HttpsURLConnection connection = active;
        if (connection != null) connection.disconnect();
    }
}
