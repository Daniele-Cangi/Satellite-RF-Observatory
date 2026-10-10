package org.satelliterf.observatory.clock;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.Test;
import org.conscrypt.Conscrypt;
import org.cryptomator.siv.SivMode;
import javax.crypto.spec.SecretKeySpec;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManagerFactory;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyStore;
import java.security.cert.CertificateFactory;
import java.util.Arrays;
import java.util.Map;
import static org.junit.Assert.*;

public final class NtsClientTest {
    static byte[] hex(String value) {
        byte[] result = new byte[value.length() / 2];
        for (int i = 0; i < result.length; i++) result[i] = (byte) Integer.parseInt(value.substring(2 * i, 2 * i + 2), 16);
        return result;
    }
    private JsonObject vectors() throws IOException {
        return JsonParser.parseString(new String(Files.readAllBytes(Path.of("..", "..", "tests", "fixtures", "android_collector", "nts-vectors.json")), StandardCharsets.UTF_8)).getAsJsonObject();
    }
    @Test public void independentPythonPacketsAuthenticateAndRejectEveryMutation() throws Exception {
        JsonObject data = vectors();
        for (var item : data.getAsJsonArray("responses")) {
            JsonObject test = item.getAsJsonObject();
            byte[] key = hex(test.has("key") ? test.get("key").getAsString() : data.get("key").getAsString());
            byte[] uid = hex(test.has("uid") ? test.get("uid").getAsString() : data.get("uid").getAsString());
            byte[] packet = hex(test.get("packet").getAsString());
            if (test.get("accepted").getAsBoolean()) {
                Map<String, Object> result = NtsClient.response(packet, key, uid, hex(data.get("origin").getAsString()), 0);
                assertEquals(1700000000000000000L, result.get("server_receive_unix_ns"));
                assertEquals(1700000001000000000L, result.get("server_transmit_unix_ns"));
            } else {
                assertThrows(test.get("name").getAsString(), IOException.class,
                    () -> NtsClient.response(packet, key, uid, hex(data.get("origin").getAsString()), 0));
            }
        }
    }
    @Test public void negotiationMatchesPythonAndPreservesOpaqueCookies() throws Exception {
        for (var item : vectors().getAsJsonArray("negotiations")) {
            JsonObject test = item.getAsJsonObject();
            byte[] bytes = hex(test.get("packet").getAsString());
            if (test.get("accepted").getAsBoolean()) {
                NtsClient.KeParameters result = NtsClient.parseKe(bytes);
                assertNull(result.host);
                assertEquals(123, result.port);
            } else assertThrows(test.get("name").getAsString(), IOException.class, () -> NtsClient.parseKe(bytes));
        }
        assertThrows(IOException.class, () -> NtsClient.parseKe(new byte[65537]));
    }
    @Test public void clientRequestHasFreshIdentifiersAndCorrectAuthenticatedPadding() throws Exception {
        byte[] key = hex(vectors().get("key").getAsString());
        for (int length : new int[]{0, 1, 13, 15, 16, 17}) {
            byte[] cookie = new byte[length];
            Arrays.fill(cookie, (byte) 0x81);
            NtsClient.Request request = NtsClient.request(cookie, key);
            var fields = NtsClient.fields(request.packet, 48);
            assertEquals(3, fields.size());
            assertEquals(0x0204, fields.get(1).kind);
            assertArrayEquals(cookie, Arrays.copyOf(fields.get(1).body, length));
            byte[] auth = fields.get(2).body;
            assertArrayEquals(new byte[0], new SivMode().decrypt(new SecretKeySpec(key, "AES"),
                Arrays.copyOfRange(auth, 20, auth.length), Arrays.copyOf(request.packet, fields.get(2).position),
                Arrays.copyOfRange(auth, 4, 20)));
            NtsClient.Request next = NtsClient.request(cookie, key);
            assertFalse(Arrays.equals(request.uid, next.uid));
            assertFalse(Arrays.equals(request.origin, next.origin));
        }
    }
    @Test public void timestampUsesExplicitEraAndLosslessFraction() throws Exception {
        byte[] stamp = ByteBuffer.allocate(8).putInt((int) 3908988800L).putInt(-1).array();
        assertEquals(1700000000999999999L, NtsClient.timestamp(stamp, 0, 0));
        assertEquals(4294967296000000000L, NtsClient.timestamp(stamp, 0, 1) - NtsClient.timestamp(stamp, 0, 0));
        assertThrows(IOException.class, () -> NtsClient.timestamp(new byte[8], 0, 0));
    }
    @Test public void realTlsLoopbackEnforcesIdentityAlpnAndTlsFloor() throws Exception {
        String config = System.getenv("PNT_NTS_LOOPBACK_CONFIG");
        org.junit.Assume.assumeNotNull(config);
        JsonObject data = JsonParser.parseString(new String(Files.readAllBytes(Path.of(config)), StandardCharsets.UTF_8)).getAsJsonObject();
        KeyStore store = KeyStore.getInstance(KeyStore.getDefaultType());
        store.load(null);
        try (InputStream ca = Files.newInputStream(Path.of(data.get("ca_file").getAsString()))) {
            int index = 0;
            for (var certificate : CertificateFactory.getInstance("X.509").generateCertificates(ca)) {
                store.setCertificateEntry("loopback-test-only-" + index++, certificate);
            }
        }
        TrustManagerFactory trust = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        trust.init(store);
        SSLContext context = SSLContext.getInstance("TLS", Conscrypt.newProvider());
        context.init(null, trust.getTrustManagers(), null);
        for (var item : data.getAsJsonArray("cases")) {
            JsonObject test = item.getAsJsonObject();
            try (NtsClient client = new NtsClient(System::nanoTime,
                    test.get("trusted").getAsBoolean() ? context.getSocketFactory() : null)) {
                int port = test.get("port").getAsInt();
                if (test.get("accepted").getAsBoolean()) {
                    Map<String, Object> result = client.probe("127.0.0.1", port, 2000, 0);
                    assertEquals(NtsClient.AUTHENTICATION, result.get("authentication"));
                    assertEquals(false, result.get("ntp_host_negotiated"));
                    assertEquals(1700000000000000000L, result.get("server_receive_unix_ns"));
                    assertNull(result.get("monotonic_resolution_ns"));
                } else assertThrows(test.get("name").getAsString(), IOException.class,
                    () -> client.probe("127.0.0.1", port, 1000, 0));
            }
        }
    }
}
