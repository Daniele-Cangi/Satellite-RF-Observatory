package org.satelliterf.observatory.clock;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import java.io.Closeable;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.LongSupplier;

/** One declared NTS schedule beside GNSS; checkpoints contain no session keys/cookies. */
final class NtsCapture {
    interface Probe extends Closeable {
        Map<String, Object> probe(String server, int port, int timeoutMs, int era) throws Exception;
    }
    interface Factory { Probe create(); }
    interface Listener {
        void updated(int authenticated, int unavailable);
        void finished(String error);
        default void attemptCompleted(String server, String status, String reason) {}
    }
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private final Path file;
    private final LongSupplier counter;
    private final Factory factory;
    private final Listener listener;
    private final long intervalNs;
    private final Map<String, Object> report = new LinkedHashMap<>();
    private final List<Map<String, Object>> attempts = new ArrayList<>();
    private final long started;
    private final Thread worker;
    private final List<Thread> endpoints = new ArrayList<>();
    // Report mutations, checkpoints, progress and active probes share this monitor.
    private final Map<Integer, Probe> active = new LinkedHashMap<>();
    private int authenticated, unavailable;
    private String fatal;
    private volatile String stopReason;
    private volatile boolean finished;

    NtsCapture(Path file, String captureId, String gnssFile, Map<String, String> metadata,
               List<String> servers, int rounds, long intervalNs, LongSupplier counter,
               Factory factory, Listener listener) throws IOException {
        if (servers.isEmpty() || servers.size() > 4 || rounds < 1 || rounds > 1000
                || intervalNs < 1 || intervalNs > 60000000000L) throw new IllegalArgumentException("Invalid NTS schedule");
        if (new java.util.HashSet<>(servers).size() != servers.size()) throw new IllegalArgumentException("Duplicate NTS endpoint");
        this.file = file;
        this.counter = counter;
        this.factory = factory;
        this.listener = listener;
        this.intervalNs = intervalNs;
        started = counter.getAsLong();
        report.put("schema", "pnt-internet-time-v1");
        report.put("regime", "EXPLORATORY_ANDROID_TIME_ACQUISITION");
        report.put("status", "INSUFFICIENT_EVIDENCE");
        report.put("reason", "Transport acquisition only; timing budgets and counter resolution are not qualified");
        report.put("capture_id", captureId);
        report.put("claim_source", "NO_HOST_WALL_CLOCK_CLAIM");
        report.put("capture_context", map("counter_clock", "CLOCK_BOOTTIME", "collector_source", metadata.get("SourceRevision"),
            "capture_id", captureId, "gnss_acquired_by_this_command", true, "gnss_file", gnssFile,
            "association", "SAME_APP_PROCESS_SESSION_NOT_HARDWARE_ATTESTATION", "metadata", metadata));
        report.put("assumptions", map("server_error_ns", null, "rate_error_ppm", null, "budget_source", null,
            "calibrated", false, "trusted_collector_and_monotonic_counter", true, "tls_calendar_bootstrap_required", true));
        report.put("protocol", map("timeout_s", 5.0, "ntp_era", 0, "automatic_retries", false,
            "endpoints", new ArrayList<>(servers), "planned_attempts", rounds * servers.size(), "interval_ns", intervalNs,
            "rounds", rounds, "interval_s", intervalNs / 1e9, "attempts_per_endpoint", rounds,
            "schedule", "ROUND_START_OFFSETS", "missed_schedule", "START_LATE_WITHOUT_REPLACEMENT",
            "execution", "INDEPENDENT_ENDPOINTS_SPACED"));
        for (int round = 0; round < rounds; round++) for (String server : servers) {
            attempts.add(map("server", server, "round_index", round,
                "scheduled_round_start_monotonic_ns", started + round * intervalNs,
                "status", "NOT_ATTEMPTED", "reason", "SCHEDULE_NOT_STARTED"));
        }
        report.put("attempts", attempts);
        report.put("acquisition", map("started_monotonic_ns", started, "ended_monotonic_ns", null,
            "interrupted", false, "state", "IN_PROGRESS"));
        Files.createFile(file); // A new capture can never overwrite an earlier session.
        save();
        for (int index = 0; index < servers.size(); index++) {
            final int endpoint = index;
            Thread thread = new Thread(() -> runEndpoint(endpoint, servers.size()), "pnt-nts-endpoint-" + index);
            thread.setDaemon(true);
            endpoints.add(thread);
        }
        worker = new Thread(this::run, "pnt-nts-capture");
        worker.setDaemon(true);
    }
    void start() { worker.start(); }
    boolean isFinished() { return finished; }
    synchronized void cancel(String reason) {
        if (finished || stopReason != null) return;
        stopReason = reason;
        for (Probe probe : active.values()) {
            try { probe.close(); } catch (IOException | RuntimeException ignored) { /* Worker retains interruption/failure. */ }
        }
        // An interrupt left pending by socket I/O also aborts Files.write().
        // Wake schedule waits without poisoning the final evidence checkpoint.
        notifyAll();
    }
    private synchronized void fail(Exception error) {
        if (fatal == null) fatal = error.getClass().getSimpleName();
        cancel("STORAGE_OR_COLLECTOR_FAILED");
    }
    private synchronized void awaitSchedule(long scheduled) throws InterruptedException {
        while (stopReason == null) {
            long delay = scheduled - counter.getAsLong();
            if (delay <= 0) return;
            wait(delay / 1000000L, (int) (delay % 1000000L));
        }
    }
    private void runEndpoint(int endpoint, int endpointCount) {
        long nextStart = started;
        try {
            for (int index = endpoint; index < attempts.size(); index += endpointCount) {
                Map<String, Object> attempt = attempts.get(index);
                synchronized (this) {
                    long scheduled = (Long) attempt.get("scheduled_round_start_monotonic_ns");
                    awaitSchedule(Math.max(scheduled, nextStart));
                    if (stopReason != null) return;
                    long attemptStart = counter.getAsLong();
                    // No catch-up burst after a late round; no retry or replacement slot.
                    nextStart = attemptStart + intervalNs;
                    attempt.put("status", "WITNESS_UNAVAILABLE");
                    attempt.put("reason", "ATTEMPT_IN_PROGRESS");
                    attempt.put("started_monotonic_ns", attemptStart);
                    save(); // Retain the attempted slot before opening the endpoint.
                }
                Probe probe = null;
                Map<String, Object> exchange = null;
                String reason = null, cleanupError = null;
                try {
                    probe = factory.create();
                    synchronized (this) {
                        if (stopReason != null) throw new IOException("CAPTURE_INTERRUPTED");
                        active.put(endpoint, probe);
                    }
                    exchange = probe.probe((String) attempt.get("server"), 4460, 5000, 0);
                } catch (Exception | LinkageError error) {
                    reason = stopReason != null ? "CAPTURE_INTERRUPTED" : error.getClass().getSimpleName()
                        + (error.getMessage() == null ? "" : ": " + error.getMessage());
                } finally {
                    if (probe != null) {
                        try { probe.close(); }
                        catch (IOException | RuntimeException error) { cleanupError = error.getClass().getSimpleName(); }
                    }
                }
                synchronized (this) {
                    active.remove(endpoint);
                    if (exchange != null) {
                        exchange.put("capture_id", report.get("capture_id"));
                        attempt.put("status", "AUTHENTICATED_EXCHANGE");
                        attempt.put("exchange", exchange);
                        attempt.remove("reason");
                        authenticated++;
                    } else {
                        attempt.put("reason", reason);
                        unavailable++;
                    }
                    if (cleanupError != null) attempt.put("cleanup_error", cleanupError);
                    attempt.put("finished_monotonic_ns", counter.getAsLong());
                    save();
                    listener.attemptCompleted((String) attempt.get("server"), (String) attempt.get("status"), (String) attempt.get("reason"));
                    listener.updated(authenticated, unavailable);
                }
            }
        } catch (InterruptedException error) {
            cancel("COLLECTOR_INTERRUPTED");
        } catch (IOException | RuntimeException error) {
            fail(error);
        }
    }
    private void run() {
        for (Thread endpoint : endpoints) endpoint.start();
        for (Thread endpoint : endpoints) {
            boolean joined = false;
            while (!joined) {
                try { endpoint.join(); joined = true; }
                catch (InterruptedException error) { cancel("COLLECTOR_INTERRUPTED"); }
            }
        }
        synchronized (this) {
            String reason = fatal != null ? "STORAGE_OR_COLLECTOR_FAILED" : stopReason != null ? stopReason : "SCHEDULE_COMPLETED";
            for (Map<String, Object> attempt : attempts) {
                if ("NOT_ATTEMPTED".equals(attempt.get("status"))) attempt.put("reason", reason);
            }
            long ended = counter.getAsLong();
            report.put("acquisition", map("started_monotonic_ns", started, "ended_monotonic_ns", ended,
                "interrupted", stopReason != null || fatal != null, "state", "FINISHED", "terminal_reason", reason));
            report.put("terminal", map("reason", reason, "counter_ns", ended,
                "authenticated_exchanges", authenticated, "unavailable_attempts", unavailable));
            try { save(); } catch (IOException | RuntimeException error) { fatal = error.getClass().getSimpleName(); }
            finished = true;
        }
        listener.finished(fatal);
    }
    private void save() throws IOException {
        Path pending = file.resolveSibling(file.getFileName() + ".pending");
        Files.write(pending, (JSON.toJson(report) + "\n").getBytes(StandardCharsets.UTF_8),
            StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE);
        try { Files.move(pending, file, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING); }
        catch (AtomicMoveNotSupportedException error) { Files.move(pending, file, StandardCopyOption.REPLACE_EXISTING); }
    }
    static Map<String, Object> map(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String) pairs[i], pairs[i + 1]);
        return result;
    }
}
