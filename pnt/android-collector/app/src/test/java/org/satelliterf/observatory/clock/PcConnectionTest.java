package org.satelliterf.observatory.clock;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
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
                System::nanoTime, update -> { if (update.text.contains("failures retained: 1")) failure.countDown(); })) {
            assertTrue("Upload failure must be visible", failure.await(10, TimeUnit.SECONDS));
        }
        CountDownLatch acknowledged = new CountDownLatch(1);
        CountDownLatch completed = new CountDownLatch(1);
        try (LiveTransfer transfer = new LiveTransfer(connection, () -> new byte[][]{raw, nts}, id,
                Path.of(fixture.get("directory").getAsString()), System::nanoTime,
                update -> {
                    if (update.text.contains("Acknowledged: 1")) acknowledged.countDown();
                    if (update.text.contains("PC transport stopped:") && update.text.contains("Acknowledged: 1")) completed.countDown();
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

    @Test public void realEngineRevisionsFailuresAndDisplayTiming() throws Exception {
        String file = System.getenv("PNT_PC_CONNECTION_FIXTURE");
        assumeTrue(file != null);
        JsonObject fixture = JsonParser.parseString(new String(Files.readAllBytes(Path.of(file)), StandardCharsets.UTF_8)).getAsJsonObject();
        byte[] raw = Files.readAllBytes(Path.of(fixture.get("live_raw").getAsString()));
        byte[] first = Files.readAllBytes(Path.of(fixture.get("live_first").getAsString()));
        byte[] second = Files.readAllBytes(Path.of(fixture.get("live_second").getAsString()));
        AtomicInteger phase = new AtomicInteger();
        AtomicReference<String> last = new AtomicReference<>();
        CountDownLatch inconsistent = new CountDownLatch(1), revised = new CountDownLatch(1),
            unavailable = new CountDownLatch(1), malformed = new CountDownLatch(1);
        Path directory = Path.of(fixture.get("directory").getAsString()).resolve("live-phone");
        Files.createDirectory(directory);
        try (LiveTransfer transfer = new LiveTransfer(read(fixture.getAsJsonObject("live_config")), () -> {
            int stage = phase.get();
            if (stage == 2) throw new java.io.IOException("synthetic unavailable snapshot");
            if (stage == 3) return new byte[][]{"corrupt retained original\n".getBytes(StandardCharsets.UTF_8), "{}".getBytes(StandardCharsets.UTF_8)};
            return new byte[][]{raw, stage == 0 ? first : second};
        }, "synthetic-monitor", directory, System::nanoTime, update -> {
            last.set(update.text);
            String timing = update.timingText(System.nanoTime());
            if (update.accepted) assertTrue(timing.contains("request/snapshot -> receipt (ns)"));
            else {
                assertTrue(timing.contains("request/snapshot -> failure completion (ns)"));
                assertFalse(timing.contains("request/snapshot -> receipt"));
                assertFalse(timing.contains("Receipt -> UI text"));
            }
            try { update.displayed(System.nanoTime()); }
            catch (java.io.IOException error) { throw new AssertionError(error); }
            if (update.text.contains("LATEST ACKNOWLEDGED") && update.text.contains("combined (records, not independent trials): INCONSISTENT=1")) inconsistent.countDown();
            if (update.text.contains("Revised INCONSISTENT -> INCONCLUSIVE: 1")) revised.countDown();
            if (update.text.contains("CURRENT PC RESULT UNAVAILABLE") && update.text.contains("HISTORICAL ONLY")) unavailable.countDown();
            if (phase.get() == 3 && update.text.contains("LATEST ACKNOWLEDGED") && update.text.contains("no numerical comparison")) malformed.countDown();
        })) {
            assertTrue(inconsistent.await(10, TimeUnit.SECONDS));
            phase.set(1);
            assertTrue(revised.await(10, TimeUnit.SECONDS));
            phase.set(2);
            assertTrue(unavailable.await(10, TimeUnit.SECONDS));
            assertFalse(last.get().contains("LATEST ACKNOWLEDGED"));
            phase.set(3);
            assertTrue(malformed.await(10, TimeUnit.SECONDS));
        }
        assertTrue(last.get().contains("CURRENT PC RESULT UNAVAILABLE"));
        var lines = Files.readAllLines(directory.resolve("pnt-transfer-synthetic-monitor.jsonl"));
        boolean sawReceipt = false, sawApplied = false, sawFailure = false, sawFailedDisplay = false;
        for (String line : lines) {
            JsonObject event = JsonParser.parseString(line).getAsJsonObject();
            if (event.get("kind").getAsString().equals("UI_TEXT_APPLIED")) {
                assertTrue(event.get("text_applied_counter_ns").getAsLong() >= event.get("request_finished_counter_ns").getAsLong());
                if (event.get("request_outcome").getAsString().equals("ACKNOWLEDGED")) {
                    assertEquals(event.get("request_finished_counter_ns"), event.get("receipt_received_counter_ns"));
                } else {
                    assertEquals("UNAVAILABLE", event.get("request_outcome").getAsString());
                    assertFalse("A failed attempt has no accepted receipt counter", event.has("receipt_received_counter_ns"));
                    sawFailedDisplay = true;
                }
                sawApplied = true;
            } else if (event.get("outcome").getAsString().equals("UNAVAILABLE")) sawFailure = true;
            else {
                assertTrue(event.getAsJsonObject("pc_receipt").has("presentation"));
                sawReceipt = true;
            }
        }
        assertTrue(sawReceipt && sawApplied && sawFailure && sawFailedDisplay);
    }
}
