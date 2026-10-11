package org.satelliterf.observatory.clock;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.Test;
import static org.junit.Assert.*;

public class PcLiveResultTest {
    private static final byte[] RAW = {1, 2}, NTS = {3, 4};
    private JsonObject receipt() {
        JsonObject value = JsonParser.parseString("{\"capture_id\":\"test\",\"stored\":true,\"update_index\":1,"
            + "\"session_complete\":false,\"status\":\"CONDITIONAL_TIME_DIAGNOSTIC\",\"issues\":[],"
            + "\"issue_count\":0,\"issues_abbreviated\":false,\"presentation\":{\"calibrated\":false,"
            + "\"source_members\":[],\"record_count\":1,\"record_outcome_counts\":{"
            + "\"local\":{\"NOT_DISTINGUISHABLE\":1},\"external\":{\"INCONCLUSIVE\":1},\"combined\":{\"INCONCLUSIVE\":1}},"
            + "\"revision_transitions\":{\"local\":[],\"external\":[],\"combined\":[{\"previous\":\"INCONSISTENT\","
            + "\"current\":\"INCONCLUSIVE\",\"count\":1}]},\"revised_records\":1,"
            + "\"record_reasons\":{\"total\":0,\"preview\":[],\"abbreviated\":false},\"witness_status_counts\":{\"WITNESS_UNAVAILABLE\":2},"
            + "\"analysis_options\":{},\"analysis_options_abbreviated\":false,\"local_counter_resolution_ns\":1,"
            + "\"timing\":{\"counter_clock\":\"PC_MONOTONIC\",\"total_pc_processing_ns\":100},\"processor\":null}}")
            .getAsJsonObject();
        for (String name : new String[]{"clock", "nts"}) {
            byte[] bytes = name.equals("clock") ? RAW : NTS;
            JsonObject member = new JsonObject();
            member.addProperty("name", "pnt-" + name + "-test." + (name.equals("clock") ? "txt" : "json"));
            member.addProperty("size_bytes", bytes.length);
            member.addProperty("sha256", SessionReport.sha256(bytes));
            value.getAsJsonObject("presentation").getAsJsonArray("source_members").add(member);
        }
        return value;
    }
    @Test public void revisionsFailuresAndNoValidationClaimAreVisible() {
        PcLiveResult result = new PcLiveResult(receipt(), "test", RAW, NTS);
        assertTrue(result.text.contains("Revised INCONSISTENT -> INCONCLUSIVE: 1"));
        assertTrue(result.text.contains("WITNESS_UNAVAILABLE"));
        assertTrue(result.text.contains("not validation"));
        assertTrue(result.text.contains("partial, revisable"));
    }
    @Test public void wrongSnapshotAndUnsupportedClaimsAreRejected() {
        assertThrows(IllegalArgumentException.class, () -> new PcLiveResult(receipt(), "other", RAW, NTS));
        assertThrows(IllegalArgumentException.class, () -> new PcLiveResult(receipt(), "test", new byte[]{9, 8}, NTS));
        JsonObject unknown = receipt();
        unknown.addProperty("status", "ALLOW");
        assertThrows(IllegalArgumentException.class, () -> new PcLiveResult(unknown, "test", RAW, NTS));
        JsonObject qualified = receipt();
        qualified.getAsJsonObject("presentation").addProperty("calibrated", true);
        assertThrows(IllegalArgumentException.class, () -> new PcLiveResult(qualified, "test", RAW, NTS));
        JsonObject broken = receipt();
        broken.getAsJsonObject("presentation").getAsJsonObject("record_outcome_counts").getAsJsonObject("combined").addProperty("INCONCLUSIVE", 0);
        assertThrows(IllegalArgumentException.class, () -> new PcLiveResult(broken, "test", RAW, NTS));
        JsonObject cleared = receipt();
        cleared.addProperty("status", "INSUFFICIENT_EVIDENCE");
        // The global external status may be insufficient while the monitor
        // retains per-record local controls. Presentation adds no verdict rule.
        assertTrue(new PcLiveResult(cleared, "test", RAW, NTS).text.contains("Status: INSUFFICIENT_EVIDENCE"));
    }
}
