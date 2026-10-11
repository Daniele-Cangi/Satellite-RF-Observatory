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
    private final Consumer<String> listener;
    private volatile ScheduledFuture<?> periodic;
    private int acknowledged, failures;
    private volatile String lastDetail = "Waiting for first snapshot";
    private volatile boolean closed;
    private boolean finishing;

    LiveTransfer(PcConnection config, Source source, String captureId, Path directory,
                 LongSupplier counter, Consumer<String> listener) throws IOException {
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
        try {
            byte[][] snapshot = source.snapshot();
            if (closed) return;
            var receipt = connection.send(captureId, snapshot[0], snapshot[1]);
            acknowledged++;
            outcome = "ACKNOWLEDGED";
            detail = "PC stored snapshot; update " + receipt.get("update_index").getAsInt()
                + "; intake issues " + receipt.getAsJsonArray("issues").size();
        } catch (Exception error) {
            failures++;
            outcome = "UNAVAILABLE";
            detail = error.getClass().getSimpleName() + ": " + error.getMessage();
        }
        try {
            String line = new Gson().toJson(NtsCapture.map("started_counter_ns", started,
                "finished_counter_ns", counter.getAsLong(), "counter_clock", "CLOCK_BOOTTIME",
                "outcome", outcome, "detail", detail)) + "\n";
            Files.write(events, line.getBytes(StandardCharsets.UTF_8), StandardOpenOption.APPEND);
        } catch (IOException error) {
            close();
            detail += "; transfer log storage failed; upload stopped";
        }
        lastDetail = detail;
        notifyListener();
    }
    private void notifyListener() {
        listener.accept("PC transport " + (closed ? "stopped: " : "active: ") + lastDetail
            + "\nAcknowledged: " + acknowledged + "; failures retained: " + failures
            + "\nThis is a transfer receipt, not a timing or security verdict.");
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
