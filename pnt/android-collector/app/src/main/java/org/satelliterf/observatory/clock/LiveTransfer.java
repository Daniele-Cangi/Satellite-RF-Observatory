package org.satelliterf.observatory.clock;

import com.google.gson.Gson;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import java.util.function.LongSupplier;

/** Optional transport worker, never a scientific executor. No upload backlog or acquisition retry. */
final class LiveTransfer implements AutoCloseable {
    interface Source { byte[][] snapshot() throws Exception; }
    private final ScheduledExecutorService worker = Executors.newSingleThreadScheduledExecutor();
    private final PcConnection connection;
    private final Source source;
    private final String captureId;
    private final Path events;
    private final LongSupplier counter;
    private final Consumer<Update> listener;
    private final Object logLock = new Object();
    private volatile ScheduledFuture<?> periodic;
    private int acknowledged, failures, notificationIndex;
    private PcLiveResult current, historical;
    private long requestStarted, receiptReceived;
    private long highestUpdate;
    private volatile String lastDetail = "Waiting for first snapshot";
    private volatile boolean closed;
    private boolean finishing;

    LiveTransfer(PcConnection config, Source source, String captureId, Path directory,
                 LongSupplier counter, Consumer<Update> listener) throws IOException {
        this.connection = config.fresh();
        this.source = source;
        this.captureId = captureId;
        this.counter = counter;
        this.listener = listener;
        events = directory.resolve("pnt-transfer-" + captureId + ".jsonl");
        Files.createFile(events);
        periodic = worker.scheduleWithFixedDelay(this::send, 0, 1, TimeUnit.SECONDS);
    }
    private void send() {
        if (closed) return;
        long started = counter.getAsLong();
        String outcome, detail;
        boolean complete = false;
        PcLiveResult result = null;
        try {
            byte[][] snapshot = source.snapshot();
            if (closed) return;
            result = connection.send(captureId, snapshot[0], snapshot[1]);
            if (result.index < highestUpdate) throw new IOException("PC update index regressed");
            if (historical != null && result.index == highestUpdate && !result.receipt.getAsJsonObject("presentation")
                    .get("source_members").equals(historical.receipt.getAsJsonObject("presentation").get("source_members"))) {
                throw new IOException("PC reused an update index for different inputs");
            }
            outcome = "ACKNOWLEDGED";
            detail = "PC stored snapshot; update " + result.index;
            complete = result.complete;
        } catch (Exception error) {
            result = null;
            outcome = "UNAVAILABLE";
            detail = error.getClass().getSimpleName() + ": " + error.getMessage();
        }
        long received = counter.getAsLong();
        synchronized (this) {
            if (closed) return; // A cancelled request cannot restore a live result.
            requestStarted = started;
            receiptReceived = received;
            current = result;
            if (result != null) {
                acknowledged++;
                highestUpdate = result.index;
                historical = result;
            } else failures++;
            lastDetail = detail;
        }
        try {
            append(NtsCapture.map("kind", "REQUEST", "started_counter_ns", started,
                "finished_counter_ns", received, "counter_clock", "CLOCK_BOOTTIME",
                "outcome", outcome, "detail", detail, "pc_receipt", result == null ? null : result.receipt));
        } catch (IOException error) {
            synchronized (this) { current = null; lastDetail += "; transfer log storage failed; upload stopped"; }
            close();
        }
        // A complete pair is already the final upload. The receiver may now
        // exit; a queued finish() must not send it again and invent a failure.
        if (complete && !closed) close();
        else notifyListener();
    }
    private synchronized void notifyListener() {
        boolean finalResult = closed && current != null && current.complete;
        String text = "PC transport " + (closed ? "stopped: " : "active: ") + lastDetail
            + "\nAcknowledged: " + acknowledged + "; failures retained: " + failures;
        if (current != null && (!closed || finalResult)) {
            text += (finalResult ? "\nFINAL PC SNAPSHOT (not a live connection)\n" : "\nLATEST ACKNOWLEDGED PC SNAPSHOT\n") + current.text;
        } else {
            text += "\nCURRENT PC RESULT UNAVAILABLE; no current timing conclusion.";
            if (historical != null) text += "\nHISTORICAL ONLY — previous acknowledged snapshot\n" + historical.text;
        }
        listener.accept(new Update(++notificationIndex, text, requestStarted, receiptReceived));
    }

    private void append(Object value) throws IOException {
        byte[] bytes = (new Gson().toJson(value) + "\n").getBytes(StandardCharsets.UTF_8);
        synchronized (logLock) { Files.write(events, bytes, StandardOpenOption.APPEND); }
    }

    synchronized void displayFailed() {
        current = null;
        lastDetail = "UI evidence log storage failed; upload stopped";
        if (closed) notifyListener();
        else close();
    }

    final class Update {
        final int notification;
        final String text;
        final long started, received;
        private Update(int notification, String text, long started, long received) {
            this.notification = notification;
            this.text = text;
            this.started = started;
            this.received = received;
        }
        String timingText(long applied) {
            if (received == 0) return "\nNo completed PC request to time.";
            return "\nPhone request/snapshot -> receipt (ns): " + (received - started)
                + "\nReceipt -> UI text applied (ns): " + (applied - received)
                + "\nCLOCK_BOOTTIME durations; counters are not mapped to PC time."
                + "\nUI text applied is not frame presentation, operator observation or RF alert latency.";
        }
        void displayed(long applied) throws IOException {
            append(NtsCapture.map("kind", "UI_TEXT_APPLIED", "notification_index", notification,
                "request_started_counter_ns", started, "receipt_received_counter_ns", received,
                "text_applied_counter_ns", applied, "counter_clock", "CLOCK_BOOTTIME",
                "scope", "TEXT_ASSIGNMENT_ONLY; NOT_OPERATOR_OR_RF_ALERT_LATENCY"));
        }
    }
    synchronized void finish() {
        if (closed || finishing) return;
        finishing = true;
        periodic.cancel(false);
        worker.execute(() -> { try { send(); } finally { close(); } });
    }
    @Override public synchronized void close() {
        if (closed) return;
        closed = true;
        if (periodic != null) periodic.cancel(false);
        connection.cancel();
        worker.shutdown(); // Do not interrupt a pending evidence-log write.
        notifyListener();
    }
    boolean isClosed() { return closed; }
}
