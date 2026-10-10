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
    private volatile Probe active;
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
            "rounds", rounds, "interval_s", intervalNs / 1e9, "attempts_per_endpoint", rounds,
            "schedule", "ROUND_START_OFFSETS", "missed_schedule", "START_LATE_WITHOUT_REPLACEMENT"));
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
        worker = new Thread(this::run, "pnt-nts-capture");
        worker.setDaemon(true);
    }
    void start() { worker.start(); }
    boolean isFinished() { return finished; }
    synchronized void cancel(String reason) {
        if (finished || stopReason != null) return;
        stopReason = reason;
        Probe probe = active;
        if (probe != null) {
            try { probe.close(); } catch (IOException ignored) { /* Worker retains interruption/failure. */ }
        }
        worker.interrupt();
    }
    private void run() {
        int authenticated = 0, unavailable = 0;
        String fatal = null;
        try {
            for (Map<String, Object> attempt : attempts) {
                if (stopReason != null) { attempt.put("reason", "CAPTURE_INTERRUPTED"); continue; }
                long scheduled = (Long) attempt.get("scheduled_round_start_monotonic_ns");
                if (scheduled > counter.getAsLong()) {
                    long delay = scheduled - counter.getAsLong();
                    if (delay > 0) {
                        try { Thread.sleep(delay / 1000000L, (int) (delay % 1000000L)); }
                        catch (InterruptedException error) { attempt.put("reason", "CAPTURE_INTERRUPTED"); continue; }
                    }
                }
                if (stopReason != null) { attempt.put("reason", "CAPTURE_INTERRUPTED"); continue; }
                attempt.put("status", "WITNESS_UNAVAILABLE");
                attempt.put("reason", "ATTEMPT_IN_PROGRESS");
                attempt.put("started_monotonic_ns", counter.getAsLong());
                save(); // Retain the attempted slot before opening the endpoint.
                Probe probe = null;
                try {
                    probe = factory.create();
                    active = probe;
                    if (stopReason != null) { probe.close(); throw new IOException("CAPTURE_INTERRUPTED"); }
                    Map<String, Object> exchange = probe.probe((String) attempt.get("server"), 4460, 5000, 0);
                    exchange.put("capture_id", report.get("capture_id"));
                    attempt.put("status", "AUTHENTICATED_EXCHANGE");
                    attempt.put("exchange", exchange);
                    attempt.remove("reason");
                    authenticated++;
                } catch (Exception | LinkageError error) {
                    attempt.put("reason", stopReason != null ? "CAPTURE_INTERRUPTED" : error.getClass().getSimpleName()
                        + (error.getMessage() == null ? "" : ": " + error.getMessage()));
                    unavailable++;
                } finally {
                    active = null;
                    if (probe != null) {
                        try { probe.close(); }
                        catch (IOException error) { attempt.put("cleanup_error", error.getClass().getSimpleName()); }
                    }
                    attempt.put("finished_monotonic_ns", counter.getAsLong());
                }
                save();
                listener.updated(authenticated, unavailable);
            }
        } catch (IOException | RuntimeException error) {
            fatal = error.getClass().getSimpleName();
        } finally {
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
            listener.finished(fatal);
        }
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
