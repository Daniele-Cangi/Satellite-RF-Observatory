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
        AtomicInteger bCalls = new AtomicInteger();
        List<String> notifications = new java.util.ArrayList<>();
        Map<String, Integer> completed = new java.util.HashMap<>();
        CountDownLatch done = new CountDownLatch(1);
        NtsCapture capture = new NtsCapture(path, "synthetic-ci", "pnt-clock-synthetic-ci.txt",
            Map.of("SourceRevision", "SYNTHETIC_ONLY"), List.of("synthetic-a", "synthetic-b"), 2, 1,
            () -> counter.addAndGet(100000000L), () -> new NtsCapture.Probe() {
                public Map<String, Object> probe(String server, int port, int timeout, int era) throws Exception {
                    calls.incrementAndGet();
                    if (server.equals("synthetic-b") && bCalls.getAndIncrement() == 0) throw new IOException("synthetic timeout");
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
                        int round = completed.getOrDefault(server, 0);
                        int endpoint = server.equals("synthetic-a") ? 0 : 1;
                        JsonObject attempt = saved.getAsJsonArray("attempts").get(round * 2 + endpoint).getAsJsonObject();
                        assertEquals(server, attempt.get("server").getAsString());
                        assertEquals(status, attempt.get("status").getAsString());
                        assertTrue(attempt.has("finished_monotonic_ns"));
                        completed.put(server, round + 1);
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
        assertEquals(3, java.util.Collections.frequency(notifications, "AUTHENTICATED_EXCHANGE:null"));
        assertTrue(notifications.contains("WITNESS_UNAVAILABLE:IOException: synthetic timeout"));
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
        CountDownLatch entered = new CountDownLatch(2), release = new CountDownLatch(1), done = new CountDownLatch(1);
        AtomicInteger calls = new AtomicInteger();
        AtomicInteger closed = new AtomicInteger();
        NtsCapture capture = new NtsCapture(path, "cancel", "gnss.txt", Map.of(), List.of("a", "b"), 2, 1,
            System::nanoTime, () -> new NtsCapture.Probe() {
                private final AtomicBoolean wasClosed = new AtomicBoolean();
                public Map<String, Object> probe(String server, int port, int timeout, int era) throws Exception {
                    calls.incrementAndGet(); entered.countDown(); release.await(); throw new IOException("cancelled");
                }
                public void close() {
                    if (wasClosed.compareAndSet(false, true)) closed.incrementAndGet();
                    release.countDown();
                }
            }, listener(done));
        capture.start();
        assertTrue(entered.await(5, TimeUnit.SECONDS));
        capture.cancel("ACTIVITY_STOPPED");
        assertTrue(done.await(5, TimeUnit.SECONDS));
        JsonObject report = JsonParser.parseString(new String(Files.readAllBytes(path), StandardCharsets.UTF_8)).getAsJsonObject();
        assertEquals(2, calls.get());
        assertEquals(2, closed.get());
        assertEquals(4, report.getAsJsonArray("attempts").size());
        assertEquals("ACTIVITY_STOPPED", report.getAsJsonObject("terminal").get("reason").getAsString());
        assertEquals("CAPTURE_INTERRUPTED", report.getAsJsonArray("attempts").get(0).getAsJsonObject().get("reason").getAsString());
        assertEquals("CAPTURE_INTERRUPTED", report.getAsJsonArray("attempts").get(1).getAsJsonObject().get("reason").getAsString());
        assertEquals("NOT_ATTEMPTED", report.getAsJsonArray("attempts").get(2).getAsJsonObject().get("status").getAsString());
        assertTrue(report.getAsJsonObject("acquisition").get("interrupted").getAsBoolean());
    }
    @Test public void socketStyleCancellationCannotInterruptTheFinalFileCheckpoint() throws Exception {
        Path path = Files.createTempDirectory("pnt-socket-cancel-test").resolve("nts.json");
        AtomicBoolean closed = new AtomicBoolean(), released = new AtomicBoolean(), interrupted = new AtomicBoolean();
        AtomicReference<String> storageError = new AtomicReference<>();
        CountDownLatch entered = new CountDownLatch(2), done = new CountDownLatch(1);
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
    @Test public void blockedEndpointDoesNotDelayAnotherOrCauseCatchUpBursts() throws Exception {
        Path path = Files.createTempDirectory("pnt-endpoint-spacing-test").resolve("nts.json");
        CountDownLatch slowEntered = new CountDownLatch(1), fastFinished = new CountDownLatch(1);
        CountDownLatch releaseSlow = new CountDownLatch(1), done = new CountDownLatch(1);
        AtomicInteger slowCalls = new AtomicInteger(), fastCalls = new AtomicInteger();
        List<Integer> progress = new java.util.ArrayList<>();
        AtomicReference<String> error = new AtomicReference<>();
        long interval = 20000000L;
        NtsCapture capture = new NtsCapture(path, "spacing", "gnss.txt", Map.of(), List.of("slow", "fast"),
            3, interval, System::nanoTime, () -> new NtsCapture.Probe() {
                public Map<String, Object> probe(String server, int port, int timeout, int era) throws Exception {
                    if (server.equals("slow")) {
                        if (slowCalls.incrementAndGet() == 1) {
                            slowEntered.countDown();
                            releaseSlow.await();
                        }
                        throw new IOException("synthetic timeout");
                    }
                    assertTrue(slowEntered.await(5, TimeUnit.SECONDS));
                    fastCalls.incrementAndGet();
                    return NtsCapture.map("authentication", NtsClient.AUTHENTICATION);
                }
                public void close() {}
            }, new NtsCapture.Listener() {
                public void updated(int authenticated, int unavailable) {
                    progress.add(authenticated + unavailable);
                    if (authenticated == 3) fastFinished.countDown();
                }
                public void finished(String failure) { error.set(failure); done.countDown(); }
            });
        capture.start();
        try {
            assertTrue(fastFinished.await(5, TimeUnit.SECONDS));
            assertEquals(1, slowCalls.get());
            assertEquals(3, fastCalls.get());
            assertFalse(capture.isFinished());
        } finally { releaseSlow.countDown(); }
        assertTrue(done.await(5, TimeUnit.SECONDS));
        assertNull(error.get());
        assertEquals(List.of(1, 2, 3, 4, 5, 6), progress);
        JsonObject report = JsonParser.parseString(new String(Files.readAllBytes(path), StandardCharsets.UTF_8)).getAsJsonObject();
        assertEquals("INDEPENDENT_ENDPOINTS_SPACED", report.getAsJsonObject("protocol").get("execution").getAsString());
        assertEquals("SCHEDULE_COMPLETED", report.getAsJsonObject("terminal").get("reason").getAsString());
        assertEquals(3, report.getAsJsonObject("terminal").get("unavailable_attempts").getAsInt());
        long previousStart = 0, previousEnd = 0;
        for (int round = 0; round < 3; round++) {
            JsonObject attempt = report.getAsJsonArray("attempts").get(round * 2).getAsJsonObject();
            long start = attempt.get("started_monotonic_ns").getAsLong();
            if (round > 0) assertTrue(start >= Math.max(previousEnd, previousStart + interval));
            previousStart = start;
            previousEnd = attempt.get("finished_monotonic_ns").getAsLong();
        }
        assertTrue(report.getAsJsonArray("attempts").get(5).getAsJsonObject().get("finished_monotonic_ns").getAsLong()
            < report.getAsJsonArray("attempts").get(0).getAsJsonObject().get("finished_monotonic_ns").getAsLong());
    }
    @Test public void collectorFailureClosesOtherEndpointBeforePublishingTerminal() throws Exception {
        Path path = Files.createTempDirectory("pnt-endpoint-failure-test").resolve("nts.json");
        CountDownLatch slowEntered = new CountDownLatch(1), releaseSlow = new CountDownLatch(1), done = new CountDownLatch(1);
        AtomicReference<String> fatal = new AtomicReference<>();
        AtomicBoolean slowClosed = new AtomicBoolean();
        NtsCapture capture = new NtsCapture(path, "failure", "gnss.txt", Map.of(), List.of("slow", "fast"),
            2, 60000000000L, System::nanoTime, () -> new NtsCapture.Probe() {
                private boolean slow;
                public Map<String, Object> probe(String server, int port, int timeout, int era) throws Exception {
                    if (server.equals("slow")) {
                        slow = true;
                        slowEntered.countDown();
                        releaseSlow.await();
                        throw new IOException("socket closed");
                    }
                    assertTrue(slowEntered.await(5, TimeUnit.SECONDS));
                    return NtsCapture.map("authentication", NtsClient.AUTHENTICATION);
                }
                public void close() {
                    if (slow) { slowClosed.set(true); releaseSlow.countDown(); }
                }
            }, new NtsCapture.Listener() {
                public void updated(int authenticated, int unavailable) { throw new IllegalStateException("synthetic collector failure"); }
                public void finished(String error) { fatal.set(error); done.countDown(); }
            });
        capture.start();
        assertTrue(done.await(5, TimeUnit.SECONDS));
        assertEquals("IllegalStateException", fatal.get());
        assertTrue(slowClosed.get());
        JsonObject report = JsonParser.parseString(new String(Files.readAllBytes(path), StandardCharsets.UTF_8)).getAsJsonObject();
        assertEquals("STORAGE_OR_COLLECTOR_FAILED", report.getAsJsonObject("terminal").get("reason").getAsString());
        assertEquals(1, report.getAsJsonObject("terminal").get("authenticated_exchanges").getAsInt());
        assertEquals(1, report.getAsJsonObject("terminal").get("unavailable_attempts").getAsInt());
        assertEquals("NOT_ATTEMPTED", report.getAsJsonArray("attempts").get(2).getAsJsonObject().get("status").getAsString());
        assertEquals("NOT_ATTEMPTED", report.getAsJsonArray("attempts").get(3).getAsJsonObject().get("status").getAsString());
    }
}
