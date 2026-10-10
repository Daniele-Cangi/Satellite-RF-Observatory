package org.satelliterf.observatory.clock;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.Test;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.Assert.*;

public final class NtsCaptureTest {
    private NtsCapture.Listener listener(CountDownLatch done) {
        return new NtsCapture.Listener() {
            public void updated(int authenticated, int unavailable) {}
            public void finished(String error) { done.countDown(); }
        };
    }
    @Test public void retainedScheduleHasFailuresUnknownBudgetsAndNoRetry() throws Exception {
        Path path = Path.of("build", "synthetic-nts.json");
        Files.createDirectories(path.getParent());
        Files.deleteIfExists(path); // Test output only; production uses exclusive creation.
        AtomicLong counter = new AtomicLong(123456789012345L - 1000000000L);
        AtomicInteger calls = new AtomicInteger();
        CountDownLatch done = new CountDownLatch(1);
        NtsCapture capture = new NtsCapture(path, "synthetic-ci", "synthetic-collector.txt",
            Map.of("SourceRevision", "SYNTHETIC_ONLY"), List.of("synthetic-a", "synthetic-b"), 2, 1,
            () -> counter.addAndGet(100000000L), () -> new NtsCapture.Probe() {
                public Map<String, Object> probe(String server, int port, int timeout, int era) throws Exception {
                    int index = calls.getAndIncrement();
                    if (index == 1) throw new IOException("synthetic timeout");
                    return NtsCapture.map("authentication", NtsClient.AUTHENTICATION,
                        "server", server, "counter_clock", "CLOCK_BOOTTIME",
                        "send_monotonic_ns", counter.get(), "receive_monotonic_ns", counter.addAndGet(10000000L),
                        "server_receive_unix_ns", 1724971999254741002L,
                        "server_transmit_unix_ns", 1724971999254741002L,
                        "monotonic_resolution_ns", null);
                }
                public void close() {}
            }, listener(done));
        capture.start();
        assertTrue(done.await(5, TimeUnit.SECONDS));
        JsonObject report = JsonParser.parseString(new String(Files.readAllBytes(path), StandardCharsets.UTF_8)).getAsJsonObject();
        assertEquals(4, calls.get());
        assertEquals(4, report.getAsJsonArray("attempts").size());
        assertEquals(3, report.getAsJsonObject("terminal").get("authenticated_exchanges").getAsInt());
        assertEquals("WITNESS_UNAVAILABLE", report.getAsJsonArray("attempts").get(1).getAsJsonObject().get("status").getAsString());
        assertTrue(report.getAsJsonObject("assumptions").get("server_error_ns").isJsonNull());
        assertEquals("INSUFFICIENT_EVIDENCE", report.get("status").getAsString());
        assertEquals("synthetic-ci", report.getAsJsonArray("attempts").get(0).getAsJsonObject().getAsJsonObject("exchange").get("capture_id").getAsString());
        assertThrows(IOException.class, () -> new NtsCapture(path, "synthetic-ci", "file.txt", Map.of(),
            List.of("a"), 1, 1, counter::get, () -> null, listener(new CountDownLatch(1))));
    }
    @Test public void stopClosesPendingProbeAndRetainsEveryUnattemptedSlot() throws Exception {
        Path path = Files.createTempDirectory("pnt-cancel-test").resolve("nts.json");
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1), done = new CountDownLatch(1);
        AtomicInteger calls = new AtomicInteger();
        NtsCapture capture = new NtsCapture(path, "cancel", "gnss.txt", Map.of(), List.of("a", "b"), 2, 1,
            System::nanoTime, () -> new NtsCapture.Probe() {
                public Map<String, Object> probe(String server, int port, int timeout, int era) throws Exception {
                    calls.incrementAndGet(); entered.countDown(); release.await(); throw new IOException("cancelled");
                }
                public void close() { release.countDown(); }
            }, listener(done));
        capture.start();
        assertTrue(entered.await(5, TimeUnit.SECONDS));
        capture.cancel("ACTIVITY_STOPPED");
        assertTrue(done.await(5, TimeUnit.SECONDS));
        JsonObject report = JsonParser.parseString(new String(Files.readAllBytes(path), StandardCharsets.UTF_8)).getAsJsonObject();
        assertEquals(1, calls.get());
        assertEquals(4, report.getAsJsonArray("attempts").size());
        assertEquals("ACTIVITY_STOPPED", report.getAsJsonObject("terminal").get("reason").getAsString());
        assertEquals("CAPTURE_INTERRUPTED", report.getAsJsonArray("attempts").get(0).getAsJsonObject().get("reason").getAsString());
        assertEquals("NOT_ATTEMPTED", report.getAsJsonArray("attempts").get(1).getAsJsonObject().get("status").getAsString());
        assertTrue(report.getAsJsonObject("acquisition").get("interrupted").getAsBoolean());
    }
}
