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
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.locks.LockSupport;
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
        List<String> notifications = new java.util.ArrayList<>();
        CountDownLatch done = new CountDownLatch(1);
        NtsCapture capture = new NtsCapture(path, "synthetic-ci", "pnt-clock-synthetic-ci.txt",
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
            }, new NtsCapture.Listener() {
                public void attemptCompleted(String server, String status, String reason) {
                    // UI notifications must describe a completed, already-retained attempt.
                    try {
                        JsonObject saved = JsonParser.parseString(new String(Files.readAllBytes(path), StandardCharsets.UTF_8)).getAsJsonObject();
                        JsonObject attempt = saved.getAsJsonArray("attempts").get(notifications.size()).getAsJsonObject();
                        assertEquals(server, attempt.get("server").getAsString());
                        assertEquals(status, attempt.get("status").getAsString());
                        assertTrue(attempt.has("finished_monotonic_ns"));
                    } catch (IOException error) { throw new AssertionError(error); }
                    notifications.add(status + ":" + reason);
                }
                public void updated(int authenticated, int unavailable) {}
                public void finished(String error) { done.countDown(); }
            });
        capture.start();
        assertTrue(done.await(5, TimeUnit.SECONDS));
        JsonObject report = JsonParser.parseString(new String(Files.readAllBytes(path), StandardCharsets.UTF_8)).getAsJsonObject();
        assertEquals(4, calls.get());
        assertEquals(4, notifications.size());
        assertEquals("AUTHENTICATED_EXCHANGE:null", notifications.get(0));
        assertEquals("WITNESS_UNAVAILABLE:IOException: synthetic timeout", notifications.get(1));
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
    @Test public void socketStyleCancellationCannotInterruptTheFinalFileCheckpoint() throws Exception {
        Path path = Files.createTempDirectory("pnt-socket-cancel-test").resolve("nts.json");
        AtomicBoolean closed = new AtomicBoolean(), released = new AtomicBoolean(), interrupted = new AtomicBoolean();
        AtomicReference<String> storageError = new AtomicReference<>();
        CountDownLatch entered = new CountDownLatch(1), done = new CountDownLatch(1);
        NtsCapture capture = new NtsCapture(path, "socket-cancel", "gnss.txt", Map.of(),
            List.of("a", "b"), 2, 1, System::nanoTime, () -> new NtsCapture.Probe() {
                public Map<String, Object> probe(String server, int port, int timeout, int era) throws Exception {
                    entered.countDown();
                    while (!released.get()) LockSupport.parkNanos(500000);
                    // Native socket closure can throw without consuming an interrupt.
                    interrupted.set(Thread.currentThread().isInterrupted());
                    throw new IOException("socket closed");
                }
                public void close() { closed.set(true); }
            }, new NtsCapture.Listener() {
                public void updated(int authenticated, int unavailable) {}
                public void finished(String error) { storageError.set(error); done.countDown(); }
            });
        capture.start();
        assertTrue(entered.await(5, TimeUnit.SECONDS));
        capture.cancel("USER_STOPPED");
        assertTrue(closed.get());
        released.set(true);
        assertTrue(done.await(5, TimeUnit.SECONDS));
        assertFalse(interrupted.get());
        assertNull(storageError.get());
        JsonObject report = JsonParser.parseString(new String(Files.readAllBytes(path), StandardCharsets.UTF_8)).getAsJsonObject();
        assertEquals("FINISHED", report.getAsJsonObject("acquisition").get("state").getAsString());
        assertEquals("USER_STOPPED", report.getAsJsonObject("terminal").get("reason").getAsString());
        assertEquals(4, report.getAsJsonArray("attempts").size());
    }
    @Test public void cancelWakesScheduledWaitWithoutWaitingForTheNextRound() throws Exception {
        Path path = Files.createTempDirectory("pnt-schedule-cancel-test").resolve("nts.json");
        CountDownLatch firstRound = new CountDownLatch(1), done = new CountDownLatch(1);
        NtsCapture capture = new NtsCapture(path, "schedule-cancel", "gnss.txt", Map.of(),
            List.of("a", "b"), 2, 60000000000L, System::nanoTime, () -> new NtsCapture.Probe() {
                public Map<String, Object> probe(String server, int port, int timeout, int era) {
                    return NtsCapture.map("authentication", NtsClient.AUTHENTICATION);
                }
                public void close() {}
            }, new NtsCapture.Listener() {
                public void updated(int authenticated, int unavailable) {
                    if (authenticated == 2) firstRound.countDown();
                }
                public void finished(String error) { done.countDown(); }
            });
        capture.start();
        assertTrue(firstRound.await(5, TimeUnit.SECONDS));
        capture.cancel("USER_STOPPED");
        assertTrue(done.await(5, TimeUnit.SECONDS));
        JsonObject report = JsonParser.parseString(new String(Files.readAllBytes(path), StandardCharsets.UTF_8)).getAsJsonObject();
        assertEquals(2, report.getAsJsonObject("terminal").get("authenticated_exchanges").getAsInt());
        assertEquals("NOT_ATTEMPTED", report.getAsJsonArray("attempts").get(2).getAsJsonObject().get("status").getAsString());
    }
}
