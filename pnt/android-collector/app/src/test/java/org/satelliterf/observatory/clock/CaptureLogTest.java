package org.satelliterf.observatory.clock;

import org.junit.Test;
import java.io.IOException;
import java.io.StringWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import static org.junit.Assert.*;

public final class CaptureLogTest {
    static Map<String, String> clock(boolean elapsed) {
        Map<String, String> clock = new LinkedHashMap<>();
        clock.put("TimeNanos", "9007199254741003");
        clock.put("FullBiasNanos", "-1400000000000000000");
        clock.put("BiasNanos", "0.25");
        clock.put("HardwareClockDiscontinuityCount", "7");
        clock.put("HasElapsedRealtimeNanos", Boolean.toString(elapsed));
        if (elapsed) clock.put("ChipsetElapsedRealtimeNanos", "123456789012345");
        clock.put("HasElapsedRealtimeUncertaintyNanos", "false");
        return clock;
    }

    static Map<String, String> measurement() {
        return Map.of("Svid", "1", "ConstellationType", "1", "TimeOffsetNanos", "0.0",
            "State", "9", "ReceivedSvTimeNanos", "20000000000", "CodeType", "C",
            "CarrierFrequencyHz", "1.57542E9");
    }

    @Test public void preservesLargeIntegersMissingMetadataAndEveryEvent() throws Exception {
        StringWriter output = new StringWriter();
        CaptureLog log = new CaptureLog(output, "synthetic", Map.of("SourceRevision", "UNSPECIFIED"));
        log.event(123456790012346L, 123456790012401L, clock(true), List.of(measurement(), measurement()));
        log.event(123456791012346L, 123456791012401L, clock(false), List.of());
        log.finish("USER_STOPPED", 123456792012345L);
        log.close();
        String text = output.toString();
        assertTrue(text.contains("9007199254741003")); // Would round if converted to double.
        assertTrue(text.contains("-1400000000000000000"));
        assertTrue(text.contains("# Event,2,123456791012346,123456791012401,0,"));
        assertTrue(text.contains("# Terminal,USER_STOPPED,123456792012345,2,2"));
        assertEquals(2, text.lines().filter(line -> line.startsWith("Raw,")).count());
        assertEquals(2, log.eventCount());
        assertEquals(2, log.rowCount());
    }

    @Test public void terminalIsUniqueAndCannotBeAppended() throws Exception {
        StringWriter output = new StringWriter();
        CaptureLog log = new CaptureLog(output, "synthetic", Map.of());
        log.finish("ACTIVITY_STOPPED", 1L);
        log.finish("USER_STOPPED", 2L);
        assertEquals(1, output.toString().lines().filter(line -> line.startsWith("# Terminal,")).count());
        assertThrows(IOException.class, () -> log.event(3L, 4L, clock(true), List.of(measurement())));
        assertThrows(IOException.class, () -> log.comment("Error", "late"));
    }

    @Test public void failureDoesNotCreateASuccessTerminalOrRetry() throws Exception {
        class FailingWriter extends Writer {
            boolean broken;
            int attempts;
            @Override public void write(char[] value, int offset, int count) throws IOException {
                attempts++;
                if (broken) throw new IOException("storage unavailable");
            }
            @Override public void flush() {}
            @Override public void close() {}
        }
        FailingWriter output = new FailingWriter();
        CaptureLog log = new CaptureLog(output, "synthetic", Map.of());
        int before = output.attempts;
        output.broken = true;
        assertThrows(IOException.class, () -> log.event(1, 2, clock(true), List.of(measurement())));
        assertEquals(before + 1, output.attempts);
    }

    @Test public void metadataCannotInjectAnotherPhysicalRecord() {
        assertEquals("\"device,\"\"name\"\" next\"", CaptureLog.csv("device,\"name\"\nnext"));
        assertEquals("", CaptureLog.csv(null));
    }

    @Test public void generateSyntheticIntakeFixture() throws Exception {
        Path path = Path.of("build", "synthetic-collector.txt");
        Files.createDirectories(path.getParent());
        try (CaptureLog log = new CaptureLog(Files.newBufferedWriter(path, StandardCharsets.UTF_8),
                "synthetic-ci", Map.of("Evidence", "SYNTHETIC_ONLY"))) {
            log.event(123456790012346L, 123456790012401L, clock(true), List.of(measurement(), measurement()));
            log.event(123456791012346L, 123456791012401L, clock(false), List.of(measurement()));
            Map<String, String> other = new LinkedHashMap<>(measurement());
            other.put("ConstellationType", "6");
            log.event(123456792012346L, 123456792012401L, clock(true), List.of(other));
            log.event(123456793012346L, 123456793012401L, clock(false), List.of());
            log.finish("USER_STOPPED", 123456794012345L);
        }
        assertTrue(Files.exists(path));
    }
}
