package org.satelliterf.observatory.clock;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.junit.Assume.*;

public class PcConnectionTest {
    private PcConnection read(JsonObject config) throws Exception {
        return PcConnection.read(new ByteArrayInputStream(config.toString().getBytes(StandardCharsets.UTF_8)));
    }
    @Test public void addressesAndInputLimits() throws Exception {
        for (String address : new String[]{"127.0.0.1", "10.1.2.3", "192.168.1.2", "172.16.0.1", "172.31.255.255"}) {
            assertTrue(PcConnection.privateIpv4(address));
        }
        for (String address : new String[]{"0.0.0.0", "8.8.8.8", "localhost", "::1", "192.168.1.256", "127.00.0.1", "172.32.0.1"}) {
            assertFalse(PcConnection.privateIpv4(address));
        }
        assertThrows(java.io.IOException.class, () -> PcConnection.readLimited(new ByteArrayInputStream(new byte[11]), 10));
        assertEquals(10, PcConnection.readLimited(new ByteArrayInputStream(new byte[10]), 10).length);
    }
    @Test public void localHttpsAndExplicitTransfer() throws Exception {
        String file = System.getenv("PNT_PC_CONNECTION_FIXTURE");
        assumeTrue(file != null);
        JsonObject fixture = JsonParser.parseString(new String(Files.readAllBytes(Path.of(file)), StandardCharsets.UTF_8)).getAsJsonObject();
        JsonObject configs = fixture.getAsJsonObject("configs");
        for (String name : new String[]{"credential", "pin", "identity"}) {
            assertThrows("Invalid " + name + " must fail", Exception.class, () -> read(configs.getAsJsonObject(name)).health());
        }
        PcConnection connection = read(configs.getAsJsonObject("good"));
        assertTrue(connection.health().get("ready").getAsBoolean());
        JsonObject bad = configs.getAsJsonObject("good").deepCopy();
        bad.addProperty("url", "http://127.0.0.1:8443");
        assertThrows(Exception.class, () -> read(bad));
        bad.addProperty("url", "https://8.8.8.8:8443");
        assertThrows(Exception.class, () -> read(bad));
        String id = fixture.get("capture_id").getAsString();
        byte[] raw = Files.readAllBytes(Path.of(fixture.get("raw").getAsString()));
        byte[] nts = Files.readAllBytes(Path.of(fixture.get("nts").getAsString()));
        CountDownLatch failure = new CountDownLatch(1);
        try (LiveTransfer transfer = new LiveTransfer(read(configs.getAsJsonObject("credential")),
                () -> new byte[][]{raw, nts}, id + "-failed", Path.of(fixture.get("directory").getAsString()),
                System::nanoTime, text -> { if (text.contains("failures retained: 1")) failure.countDown(); })) {
            assertTrue("Upload failure must be visible", failure.await(10, TimeUnit.SECONDS));
        }
        CountDownLatch acknowledged = new CountDownLatch(1);
        CountDownLatch completed = new CountDownLatch(1);
        try (LiveTransfer transfer = new LiveTransfer(connection, () -> new byte[][]{raw, nts}, id,
                Path.of(fixture.get("directory").getAsString()), System::nanoTime,
                text -> {
                    if (text.contains("Acknowledged: 1")) acknowledged.countDown();
                    if (text.contains("PC transport stopped:") && text.contains("Acknowledged: 1")) completed.countDown();
                })) {
            assertTrue("Transport worker must acknowledge", acknowledged.await(10, TimeUnit.SECONDS));
            assertTrue("Complete receipt must stop upload before receiver exit", completed.await(10, TimeUnit.SECONDS));
            assertTrue(transfer.isClosed());
            transfer.finish(); // The later acquisition-completion callback is harmless.
            assertEquals(1, Files.readAllLines(Path.of(fixture.get("directory").getAsString())
                .resolve("pnt-transfer-" + id + ".jsonl")).size());
        }
        PcConnection cancelled = connection.fresh();
        cancelled.cancel();
        assertThrows(java.io.IOException.class, cancelled::health);
    }
}
