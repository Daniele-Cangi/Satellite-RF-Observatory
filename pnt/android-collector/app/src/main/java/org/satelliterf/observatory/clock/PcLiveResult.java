package org.satelliterf.observatory.clock;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import java.util.Arrays;
import java.util.HashSet;
import static org.satelliterf.observatory.clock.SessionReport.integer;
import static org.satelliterf.observatory.clock.SessionReport.string;

/** Bounded presentation of the existing PC monitor. No solver or RF verdict. */
final class PcLiveResult {
    private static final String[] METHODS = {"local", "external", "combined"};
    private static final java.util.Set<String> OUTCOMES = new HashSet<>(Arrays.asList(
        "NOT_DISTINGUISHABLE", "INCONSISTENT", "INCONCLUSIVE", "INSUFFICIENT_EVIDENCE"));
    final JsonObject receipt;
    final long index;
    final boolean complete;
    final String text;

    PcLiveResult(JsonObject value, String id, byte[] raw, byte[] nts) {
        if (!id.equals(string(value, "capture_id")) || !bool(value, "stored")) {
            throw new IllegalArgumentException("PC did not acknowledge this capture");
        }
        index = integer(value.get("update_index"));
        if (index < 1) throw new IllegalArgumentException("Missing PC update index");
        complete = bool(value, "session_complete");
        String status = string(value, "status");
        if (!status.equals("INSUFFICIENT_EVIDENCE") && !status.equals("CONDITIONAL_TIME_DIAGNOSTIC")) {
            throw new IllegalArgumentException("Unsupported PC diagnostic status");
        }
        JsonObject view = value.getAsJsonObject("presentation");
        if (bool(view, "calibrated")) throw new IllegalArgumentException("Unsupported calibration claim");
        var members = view.getAsJsonArray("source_members");
        if (members.size() != 2) throw new IllegalArgumentException("Expected both uploaded sources");
        var names = new HashSet<String>();
        for (JsonElement item : members) {
            JsonObject member = item.getAsJsonObject();
            String name = string(member, "name");
            byte[] bytes;
            if (name.equals("pnt-clock-" + id + ".txt")) bytes = raw;
            else if (name.equals("pnt-nts-" + id + ".json")) bytes = nts;
            else throw new IllegalArgumentException("Unexpected uploaded source");
            if (!names.add(name) || integer(member.get("size_bytes")) != bytes.length
                    || !SessionReport.sha256(bytes).equals(string(member, "sha256"))) {
                throw new IllegalArgumentException("PC result differs from uploaded snapshot");
            }
        }
        long records = integer(view.get("record_count"));
        long issues = integer(value.get("issue_count"));
        StringBuilder output = new StringBuilder("PC update ").append(index)
            .append(complete ? " — native session closed" : " — partial, revisable snapshot")
            .append("\nStatus: ").append(status).append("\nSession: ").append(id)
            .append("\nUploaded snapshot hashes match; PC arithmetic is trusted.")
            .append("\nUncalibrated assumptions; no RF authenticity or ALLOW/BLOCK decision.\n");
        for (String method : METHODS) {
            JsonObject counts = view.getAsJsonObject("record_outcome_counts").getAsJsonObject(method);
            long total = 0;
            for (var entry : counts.entrySet()) {
                if (!OUTCOMES.contains(entry.getKey())) throw new IllegalArgumentException("Unknown timing outcome");
                total = Math.addExact(total, integer(entry.getValue()));
            }
            if (total != records) {
                throw new IllegalArgumentException("Inconsistent PC outcome accounting");
            }
            output.append('\n').append(method).append(" (records, not independent trials): ");
            if (records == 0) output.append("INSUFFICIENT_EVIDENCE; no numerical comparison");
            else for (String outcome : new String[]{"INCONSISTENT", "INCONCLUSIVE", "INSUFFICIENT_EVIDENCE", "NOT_DISTINGUISHABLE"}) {
                output.append(outcome).append('=').append(counts.has(outcome) ? integer(counts.get(outcome)) : 0).append("; ");
            }
            for (JsonElement item : view.getAsJsonObject("revision_transitions").getAsJsonArray(method)) {
                JsonObject change = item.getAsJsonObject();
                String old = string(change, "previous"), current = string(change, "current");
                if (!OUTCOMES.contains(old) || !OUTCOMES.contains(current)) throw new IllegalArgumentException("Unknown revision");
                output.append("\n  Revised ").append(old).append(" -> ").append(current)
                    .append(": ").append(integer(change.get("count")));
            }
        }
        output.append("\nRevised records in this update: ").append(integer(view.get("revised_records")))
            .append("\nIntake issues: ").append(issues);
        for (JsonElement issue : value.getAsJsonArray("issues")) output.append("\n- ").append(issue.getAsString());
        if (bool(value, "issues_abbreviated")) output.append("\nIssue preview abbreviated; full reasons retained on PC.");
        JsonObject reasons = view.getAsJsonObject("record_reasons");
        output.append("\nRecords with reasons: ").append(integer(reasons.get("total")));
        for (JsonElement reason : reasons.getAsJsonArray("preview")) output.append("\n- ").append(reason.getAsString());
        if (bool(reasons, "abbreviated")) output.append("\nReason preview abbreviated; full reasons retained on PC.");
        output.append("\nNTS slot states: ").append(view.get("witness_status_counts"))
            .append("\nDeclared analysis options: ").append(view.get("analysis_options"))
            .append("\nLocal counter resolution assumption (ns): ").append(integer(view.get("local_counter_resolution_ns")));
        if (bool(view, "analysis_options_abbreviated")) output.append("\nSource descriptions abbreviated; full values retained on PC.");
        JsonObject timing = view.getAsJsonObject("timing");
        if (!"PC_MONOTONIC".equals(string(timing, "counter_clock"))) throw new IllegalArgumentException("Unexpected PC timing counter");
        output.append("\nPC processing/publication (ns, PC_MONOTONIC): ").append(integer(timing.get("total_pc_processing_ns")))
            .append("\nPC code provenance: ").append(view.get("processor"))
            .append("\nNOT_DISTINGUISHABLE means no separation under these assumptions; it is not validation.")
            .append("\nFull records, inputs and revisions retained in the PC monitor.");
        receipt = value.deepCopy();
        text = output.toString();
    }

    private static boolean bool(JsonObject value, String key) {
        JsonElement field = value.get(key);
        if (field == null || !field.isJsonPrimitive() || !field.getAsJsonPrimitive().isBoolean()) {
            throw new IllegalArgumentException("Invalid boolean field: " + key);
        }
        return field.getAsBoolean();
    }
}
