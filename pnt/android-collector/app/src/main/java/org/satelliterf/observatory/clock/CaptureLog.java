package org.satelliterf.observatory.clock;

import java.io.BufferedWriter;
import java.io.Closeable;
import java.io.IOException;
import java.io.Writer;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/** Append-only Raw CSV understood by the existing Python intake. No clock fitting. */
final class CaptureLog implements Closeable {
    // List.of requires Android API 30. Keep runtime initialization on API 29
    // without adding core-library desugaring to this platform-only collector.
    static final List<String> CLOCK_FIELDS = Collections.unmodifiableList(Arrays.asList(
        "TimeNanos", "LeapSecond", "TimeUncertaintyNanos", "FullBiasNanos",
        "BiasNanos", "BiasUncertaintyNanos", "DriftNanosPerSecond",
        "DriftUncertaintyNanosPerSecond", "HardwareClockDiscontinuityCount",
        "ChipsetElapsedRealtimeNanos", "ElapsedRealtimeUncertaintyNanos",
        "HasElapsedRealtimeNanos", "HasElapsedRealtimeUncertaintyNanos",
        "HasTimeUncertaintyNanos", "HasFullBiasNanos", "HasBiasNanos",
        "HasBiasUncertaintyNanos", "HasLeapSecond", "HasDriftNanosPerSecond",
        "HasDriftUncertaintyNanosPerSecond"));
    static final List<String> MEASUREMENT_FIELDS = Collections.unmodifiableList(Arrays.asList(
        "Svid", "ConstellationType", "TimeOffsetNanos", "State", "ReceivedSvTimeNanos",
        "ReceivedSvTimeUncertaintyNanos", "Cn0DbHz", "PseudorangeRateMetersPerSecond",
        "PseudorangeRateUncertaintyMetersPerSecond", "AccumulatedDeltaRangeState",
        "AccumulatedDeltaRangeMeters", "AccumulatedDeltaRangeUncertaintyMeters",
        "CarrierFrequencyHz", "CodeType", "SnrInDb", "AgcDb"));
    private final BufferedWriter writer;
    private final String captureId;
    private long events;
    private long rows;
    private boolean terminal;

    CaptureLog(Writer output, String id, Map<String, String> metadata) throws IOException {
        writer = new BufferedWriter(output);
        captureId = id;
        comment("Format", "pnt-android-clock-collector-v1");
        comment("CaptureId", id);
        for (Map.Entry<String, String> entry : metadata.entrySet()) {
            comment("Metadata", entry.getKey(), entry.getValue());
        }
        comment("UncertaintySemantics", "ElapsedRealtimeUncertaintyNanos: receiver estimate, 68% confidence; not a hard bound");
        comment("TimingSemantics", "callback entry and end of API reads; not RF arrival or file-write time");
        writer.write("# Raw,CaptureId,EventIndex,CallbackStartElapsedRealtimeNanos,CallbackReadEndElapsedRealtimeNanos");
        for (String field : CLOCK_FIELDS) writer.write("," + field);
        for (String field : MEASUREMENT_FIELDS) writer.write("," + field);
        writer.write("\n");
        writer.flush();
    }

    void event(long start, long readEnd, Map<String, String> clock,
               List<Map<String, String>> measurements) throws IOException {
        if (terminal) throw new IOException("capture already terminated");
        long index = ++events;
        // Keep clocks even for empty events; the Python intake retains comments.
        writer.write("# Event," + index + "," + start + "," + readEnd + "," + measurements.size());
        for (String field : CLOCK_FIELDS) writer.write("," + csv(clock.get(field)));
        writer.write("\n");
        for (Map<String, String> measurement : measurements) {
            writer.write("Raw," + csv(captureId) + "," + index + "," + start + "," + readEnd);
            for (String field : CLOCK_FIELDS) writer.write("," + csv(clock.get(field)));
            for (String field : MEASUREMENT_FIELDS) writer.write("," + csv(measurement.get(field)));
            writer.write("\n");
            rows++;
        }
        // Complete callbacks survive an orderly app stop. Process/storage failure
        // can still leave a partial event or no terminal; never claim completeness.
        writer.flush();
    }

    void comment(String... values) throws IOException {
        if (terminal) throw new IOException("capture already terminated");
        writer.write("# ");
        for (int i = 0; i < values.length; i++) {
            if (i != 0) writer.write(",");
            writer.write(csv(values[i]));
        }
        writer.write("\n");
        writer.flush();
    }

    void finish(String reason, long stopCounter) throws IOException {
        if (terminal) return;
        comment("Terminal", reason, Long.toString(stopCounter),
                Long.toString(events), Long.toString(rows));
        terminal = true;
    }

    long eventCount() { return events; }
    long rowCount() { return rows; }
    @Override public void close() throws IOException { writer.close(); }

    static String csv(String value) {
        if (value == null) return "";
        // One physical record per line, including error/device metadata.
        value = value.replace('\r', ' ').replace('\n', ' ');
        if (value.contains(",") || value.contains("\"")) {
            return "\"" + value.replace("\"", "\"\"") + "\"";
        }
        return value;
    }
}
