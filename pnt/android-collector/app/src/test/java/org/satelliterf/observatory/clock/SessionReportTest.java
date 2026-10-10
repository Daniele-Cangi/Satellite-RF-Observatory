package org.satelliterf.observatory.clock;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.Assume;
import org.junit.Test;
import static org.junit.Assert.*;

public final class SessionReportTest {
    private JsonObject report(Path directory) throws Exception {
        Files.write(directory.resolve("pnt-clock-test-id.txt"), new byte[]{1, 2, 3});
        JsonObject root = new JsonObject();
        root.addProperty("schema", "pnt-android-session-report-v1");
        root.addProperty("capture_id", "test-id");
        root.addProperty("status", "INSUFFICIENT_EVIDENCE");
        root.add("comparison", null);
        root.add("intake", null);
        root.add("witness_report", null);
        root.add("analysis_options", null);
        JsonObject sources = new JsonObject(), member = new JsonObject();
        member.addProperty("name", "pnt-clock-test-id.txt");
        member.addProperty("sha256", SessionReport.sha256(directory.resolve("pnt-clock-test-id.txt")));
        member.addProperty("size_bytes", 3);
        JsonArray members = new JsonArray(); members.add(member);
        sources.add("members", members); root.add("sources", sources);
        JsonArray issues = new JsonArray(); issues.add("No GNSS measurements; NTS original missing");
        root.add("issues", issues);
        JsonArray limits = new JsonArray(); limits.add("No timing budgets qualified");
        root.add("limits", limits);
        return root;
    }

    private SessionReport read(JsonObject root, Path directory) throws Exception {
        return SessionReport.read(new ByteArrayInputStream(root.toString().getBytes(StandardCharsets.UTF_8)), directory);
    }

    @Test public void insufficientReportDisplaysFailuresAndLimitsAndRetainsExactJson() throws Exception {
        Path dir = Files.createTempDirectory("report-test");
        JsonObject root = report(dir);
        SessionReport loaded = read(root, dir);
        assertArrayEquals(root.toString().getBytes(StandardCharsets.UTF_8), loaded.original);
        assertTrue(loaded.text.contains("INSUFFICIENT_EVIDENCE"));
        assertTrue(loaded.text.contains("Timing comparison: NOT RUN"));
        assertTrue(loaded.text.contains("No GNSS measurements"));
        assertTrue(loaded.text.contains("arithmetic is not verified"));
        assertTrue(loaded.text.contains("independent budget qualification"));
    }

    @Test public void wrongSessionOrChangedOriginalCannotBeImported() throws Exception {
        Path dir = Files.createTempDirectory("report-test");
        JsonObject root = report(dir);
        root.addProperty("capture_id", "different-id");
        assertThrows(IllegalArgumentException.class, () -> read(root, dir));
        root.addProperty("capture_id", "test-id");
        Files.write(dir.resolve("pnt-clock-test-id.txt"), new byte[]{1, 2, 4});
        assertThrows(IllegalArgumentException.class, () -> read(root, dir));
    }

    @Test public void pathTraversalDuplicateMembersAndUnsupportedVerdictsAreRejected() throws Exception {
        Path dir = Files.createTempDirectory("report-test");
        JsonObject root = report(dir);
        JsonArray members = root.getAsJsonObject("sources").getAsJsonArray("members");
        JsonObject member = members.get(0).getAsJsonObject();
        member.addProperty("name", "../pnt-clock-test-id.txt");
        assertThrows(IllegalArgumentException.class, () -> read(root, dir));
        member.addProperty("name", "pnt-clock-test-id.txt");
        members.add(member.deepCopy());
        assertThrows(IllegalArgumentException.class, () -> read(root, dir));
        members.remove(1);
        root.addProperty("status", "ALLOW");
        assertThrows(IllegalArgumentException.class, () -> read(root, dir));
        root.addProperty("status", "CONDITIONAL_TIME_DIAGNOSTIC");
        assertThrows(IllegalArgumentException.class, () -> read(root, dir));
    }

    @Test public void malformedAndOversizedJsonCannotBeSilentlyTruncated() throws Exception {
        Path dir = Files.createTempDirectory("report-test");
        assertThrows(RuntimeException.class, () -> SessionReport.read(
            new ByteArrayInputStream("{unquoted: true}".getBytes(StandardCharsets.UTF_8)), dir));
        InputStream oversized = new InputStream() {
            int remaining = SessionReport.MAX_BYTES + 1;
            public int read() { if (remaining == 0) return -1; remaining--; return ' '; }
            public int read(byte[] data, int offset, int length) {
                if (remaining == 0) return -1;
                int count = Math.min(length, remaining);
                java.util.Arrays.fill(data, offset, offset + count, (byte) ' ');
                remaining -= count;
                return count;
            }
        };
        assertThrows(java.io.IOException.class, () -> SessionReport.read(oversized, dir));
    }

    @Test public void pythonGeneratedReportRoundtrip() throws Exception {
        String file = System.getenv("PNT_SESSION_REPORT_FIXTURE");
        Assume.assumeTrue(file != null);
        Path path = Path.of(file);
        try (InputStream input = Files.newInputStream(path)) {
            SessionReport loaded = SessionReport.read(input, path.getParent());
            assertArrayEquals(Files.readAllBytes(path), loaded.original);
            assertTrue(loaded.text.contains("Existing PNT comparison counts"));
            assertTrue(loaded.text.contains("synthetic timeout"));
            assertTrue(loaded.text.contains("CONDITIONAL_TIME_DIAGNOSTIC"));
            assertTrue(loaded.text.contains("RF authenticity"));
        }
    }

    @Test public void interruptedCacheWriteCannotShadowThePreviousCompleteReport() throws Exception {
        Path dir = Files.createTempDirectory("report-cache-test");
        SessionReport loaded = read(report(dir), dir);
        Path complete = loaded.retain(dir);
        Files.write(dir.resolve("pnt-report-interrupted.json.pending"), new byte[]{'{', 'x'});
        assertEquals(complete, SessionReport.latest(dir));
        try (InputStream input = Files.newInputStream(SessionReport.latest(dir))) {
            assertArrayEquals(loaded.original, SessionReport.read(input, dir).original);
        }
        Path another = loaded.retain(dir);
        assertNotEquals(complete, another);
        assertArrayEquals(loaded.original, Files.readAllBytes(complete));
        assertArrayEquals(loaded.original, Files.readAllBytes(another));
    }
}
