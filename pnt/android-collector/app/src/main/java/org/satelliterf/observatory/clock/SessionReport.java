package org.satelliterf.observatory.clock;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.Strictness;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.charset.CodingErrorAction;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.StandardCopyOption;
import java.nio.file.AtomicMoveNotSupportedException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/** Phone presentation of a trusted PC report, bound to retained input bytes.
 * Never a second solver, independent replay, server signature or RF verdict.
 */
final class SessionReport {
    static final int MAX_BYTES = 32 * 1024 * 1024;
    final byte[] original;
    final String text;

    private SessionReport(byte[] original, String text) {
        this.original = original;
        this.text = text;
    }

    Path retain(Path directory) throws IOException {
        Path complete = directory.resolve("pnt-report-" + java.util.UUID.randomUUID() + ".json");
        Path pending = complete.resolveSibling(complete.getFileName() + ".pending");
        Files.write(pending, original, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        try { Files.move(pending, complete, StandardCopyOption.ATOMIC_MOVE); }
        catch (AtomicMoveNotSupportedException error) { Files.move(pending, complete); }
        return complete;
    }

    static Path latest(Path directory) throws IOException {
        Path latest = null;
        try (var files = Files.newDirectoryStream(directory, "pnt-report-*.json")) {
            for (Path file : files) {
                if (Files.isRegularFile(file) && (latest == null
                        || Files.getLastModifiedTime(file).compareTo(Files.getLastModifiedTime(latest)) > 0)) latest = file;
            }
        }
        return latest;
    }

    static SessionReport read(InputStream input, Path directory) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int count;
        while ((count = input.read(buffer)) != -1) {
            if (count > MAX_BYTES - output.size()) throw new IOException("PC report exceeds 32 MiB; no truncation");
            output.write(buffer, 0, count);
        }
        byte[] bytes = output.toByteArray();
        JsonObject report = new GsonBuilder().setStrictness(Strictness.STRICT).create().fromJson(
            StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString(), JsonObject.class);
        if (report == null || !"pnt-android-session-report-v1".equals(string(report, "schema"))) {
            throw new IllegalArgumentException("Unsupported PC session report");
        }
        String id = string(report, "capture_id");
        if (!id.matches("[a-zA-Z0-9-]{1,80}")) throw new IllegalArgumentException("Invalid session ID");
        JsonArray members = report.getAsJsonObject("sources").getAsJsonArray("members");
        if (members == null || members.size() < 1 || members.size() > 2) {
            throw new IllegalArgumentException("Report must identify Raw and optional NTS originals");
        }
        Set<String> names = new HashSet<>();
        String rawName = "pnt-clock-" + id + ".txt", ntsName = "pnt-nts-" + id + ".json";
        for (JsonElement item : members) {
            JsonObject member = item.getAsJsonObject();
            String name = string(member, "name");
            if ((!name.equals(rawName) && !name.equals(ntsName)) || !names.add(name)) {
                throw new IllegalArgumentException("Unexpected or duplicate original filename");
            }
            Path file = directory.resolve(name);
            String hash = string(member, "sha256");
            if (!hash.matches("[0-9a-f]{64}") || Files.size(file) != integer(member.get("size_bytes"))
                    || !hash.equals(sha256(file))) {
                throw new IllegalArgumentException("Report does not match retained original: " + name);
            }
        }
        if (!names.contains(rawName)) throw new IllegalArgumentException("Raw original is required");
        String status = string(report, "status");
        if (!status.equals("INSUFFICIENT_EVIDENCE") && !status.equals("CONDITIONAL_TIME_DIAGNOSTIC")) {
            throw new IllegalArgumentException("Unsupported timing status; no security verdict is accepted");
        }
        JsonElement comparison = report.get("comparison");
        boolean compared = comparison != null && !comparison.isJsonNull();
        if (compared) {
            JsonObject result = comparison.getAsJsonObject();
            if (!"pnt-gnss-time-comparison-v1".equals(string(result, "schema"))
                    || !status.equals(string(result, "status")) || !names.contains(ntsName)
                    || !id.equals(string(result.getAsJsonObject("receiver_capture"), "capture_id"))
                    || !id.equals(string(result.getAsJsonObject("witness_report"), "capture_id"))) {
                throw new IllegalArgumentException("Envelope differs from existing PNT comparison");
            }
        } else if (!status.equals("INSUFFICIENT_EVIDENCE")) {
            throw new IllegalArgumentException("No comparison supports the supplied timing status");
        }
        StringBuilder text = new StringBuilder("Imported PC report\nSession: ").append(id)
            .append("\nRetained original hashes match. PC arithmetic is not verified by this phone.")
            .append("\nStatus: ").append(status)
            .append("\nUncalibrated assumptions only; no GNSS authenticity or position decision.\n");
        JsonObject processor = report.getAsJsonObject("processor");
        if (processor == null) text.append("\nPC code provenance: unknown\n");
        else text.append("\nPC code: ").append(display(processor.get("source_revision")))
            .append("\nWorking tree modified: ").append(display(processor.get("working_tree_dirty"))).append('\n');
        JsonElement intake = report.get("intake");
        if (intake != null && !intake.isJsonNull()) {
            text.append("\nRaw intake accounting:\n");
            appendFields(text, intake.getAsJsonObject().getAsJsonObject("coverage").getAsJsonObject("status_counts"));
        } else text.append("\nRaw intake unavailable; see issues.\n");
        JsonElement witness = report.get("witness_report");
        if (witness != null && !witness.isJsonNull()) {
            if (!names.contains(ntsName) || !id.equals(string(witness.getAsJsonObject(), "capture_id"))) {
                throw new IllegalArgumentException("NTS source does not belong to the identified originals");
            }
            JsonArray attempts = witness.getAsJsonObject().getAsJsonArray("attempts");
            Map<String, Integer> totals = new LinkedHashMap<>();
            StringBuilder failures = new StringBuilder();
            for (int i = 0; i < attempts.size(); i++) {
                JsonObject attempt = attempts.get(i).getAsJsonObject();
                String state = string(attempt, "status");
                totals.put(state, totals.getOrDefault(state, 0) + 1);
                if (!state.equals("AUTHENTICATED_EXCHANGE")) {
                    failures.append("\n  Slot ").append(i + 1).append(": ").append(state)
                        .append(" / ").append(display(attempt.get("server")));
                    if (attempt.has("reason")) failures.append(" / ").append(display(attempt.get("reason")));
                    if (attempt.has("error")) failures.append(" / ").append(display(attempt.get("error")));
                }
            }
            text.append("\nNTS slots: ").append(attempts.size()).append("; ").append(totals)
                .append(failures).append('\n');
        } else text.append("\nNTS intake unavailable; see issues.\n");
        text.append("\nTerminals (including partials): ").append(display(report.get("terminals"))).append('\n');
        text.append("\nAnalysis assumptions (uncalibrated):\n");
        JsonElement options = report.get("analysis_options");
        if (options == null || options.isJsonNull()) text.append("Not supplied; no default budgets.\n");
        else appendFields(text, options.getAsJsonObject());
        if (compared) {
            text.append("\nExisting PNT comparison counts:\n");
            appendFields(text, comparison.getAsJsonObject().getAsJsonObject("coverage"));
        } else text.append("\nTiming comparison: NOT RUN\n");
        text.append("\nIssues:\n");
        JsonArray issues = report.getAsJsonArray("issues");
        for (JsonElement issue : issues) text.append("- ").append(display(issue)).append('\n');
        if (issues.size() == 0) text.append("None reported.\n");
        JsonArray formatNotes = report.getAsJsonArray("format_notes");
        if (formatNotes != null) for (JsonElement note : formatNotes) {
            text.append("\nFormat compatibility: ").append(display(note)).append('\n');
        }
        text.append("\nControls not performed: RF authenticity, position accuracy, spoofing attribution, ")
            .append("geometry, network benefit and independent budget qualification.\n");
        for (JsonElement limit : report.getAsJsonArray("limits")) text.append("- ").append(display(limit)).append('\n');
        return new SessionReport(bytes, text.toString());
    }

    private static String string(JsonObject object, String key) {
        JsonElement value = object.get(key);
        if (value == null || !value.isJsonPrimitive() || !value.getAsJsonPrimitive().isString()) {
            throw new IllegalArgumentException("Missing or invalid report field: " + key);
        }
        return value.getAsString();
    }

    private static long integer(JsonElement value) {
        if (value == null || !value.isJsonPrimitive() || !value.getAsJsonPrimitive().isNumber()
                || !value.getAsString().matches("[0-9]+")) throw new IllegalArgumentException("Invalid byte count");
        return Long.parseLong(value.getAsString());
    }

    static String sha256(Path path) throws IOException {
        try {
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            try (InputStream input = Files.newInputStream(path)) {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) != -1) hash.update(buffer, 0, count);
            }
            StringBuilder result = new StringBuilder();
            for (byte value : hash.digest()) result.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
            return result.toString();
        } catch (NoSuchAlgorithmException error) { throw new AssertionError(error); }
    }

    private static String display(JsonElement value) {
        String text = value == null || value.isJsonNull() ? "(not supplied)" :
            value.isJsonPrimitive() && value.getAsJsonPrimitive().isString() ? value.getAsString() : value.toString();
        return text.length() <= 1000 ? text : text.substring(0, 1000) + "… (full value retained in JSON)";
    }

    private static void appendFields(StringBuilder text, JsonObject object) {
        for (Map.Entry<String, JsonElement> field : object.entrySet()) {
            text.append("  ").append(field.getKey()).append(": ").append(display(field.getValue())).append('\n');
        }
    }
}
