package org.satelliterf.observatory.clock;

import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** UI-only summaries of copied inputs; never an admission rule or timing bound. */
final class AcquisitionDiagnostics {
    private final int scheduledAttempts;
    private final Map<String, String> endpoints = new LinkedHashMap<>();
    private long callbacks, rawRows, emptyCallbacks, missingEpochs, missingUncertainties, missingBiases;
    private Long lastCallback;
    private int latestRows, gpsRows, satellites, gpsSatellites;
    private boolean hasEpoch, hasBias;
    private Double reportedUncertainty;
    private Integer discontinuity, previousDiscontinuity;
    private long discontinuityChanges;
    private int authenticated, unavailable;

    AcquisitionDiagnostics(List<String> servers, int scheduledAttempts) {
        this.scheduledAttempts = scheduledAttempts;
        for (String server : servers) endpoints.put(server, null);
    }

    void gnss(long callbackCounter, Map<String, String> clock, List<Map<String, String>> rows) {
        callbacks++;
        lastCallback = callbackCounter;
        latestRows = rows.size();
        rawRows += latestRows;
        if (rows.isEmpty()) emptyCallbacks++;
        Set<String> seen = new HashSet<>(), gpsSeen = new HashSet<>();
        gpsRows = 0;
        for (Map<String, String> row : rows) {
            String constellation = row.get("ConstellationType"), svid = row.get("Svid");
            if ("1".equals(constellation)) gpsRows++;
            if (constellation != null && svid != null) {
                String identity = constellation + ":" + svid;
                seen.add(identity);
                if ("1".equals(constellation)) gpsSeen.add(identity);
            }
        }
        satellites = seen.size();
        gpsSatellites = gpsSeen.size();
        Long epoch = "true".equals(clock.get("HasElapsedRealtimeNanos"))
            ? integer(clock.get("ChipsetElapsedRealtimeNanos")) : null;
        hasEpoch = epoch != null && epoch >= 0;
        hasBias = "true".equals(clock.get("HasFullBiasNanos")) && integer(clock.get("FullBiasNanos")) != null;
        reportedUncertainty = "true".equals(clock.get("HasElapsedRealtimeUncertaintyNanos"))
            ? nonnegativeFinite(clock.get("ElapsedRealtimeUncertaintyNanos")) : null;
        if (!hasEpoch) missingEpochs++;
        if (!hasBias) missingBiases++;
        if (reportedUncertainty == null) missingUncertainties++;
        Long count = integer(clock.get("HardwareClockDiscontinuityCount"));
        discontinuity = count != null && count >= Integer.MIN_VALUE && count <= Integer.MAX_VALUE ? count.intValue() : null;
        if (discontinuity != null) {
            if (previousDiscontinuity != null && !previousDiscontinuity.equals(discontinuity)) discontinuityChanges++;
            previousDiscontinuity = discontinuity;
        }
    }

    void ntsAttempt(String server, String state, String reason) {
        if (!endpoints.containsKey(server)) return;
        String detail = reason == null ? "" : " — " + reason.replace('\n', ' ').replace('\r', ' ');
        if (detail.length() > 160) detail = detail.substring(0, 160) + "… (full reason in NTS file)";
        endpoints.put(server, state + detail);
    }

    void ntsProgress(int authenticated, int unavailable) {
        this.authenticated = authenticated;
        this.unavailable = unavailable;
    }

    String render(long counter, boolean gnssRunning, boolean ntsRunning) {
        StringBuilder text = new StringBuilder("Acquisition diagnostics\nGNSS: ");
        if (lastCallback == null) text.append(gnssRunning ? "waiting for a measurement callback" : "no measurement callbacks received");
        else {
            text.append(latestRows == 0 ? "latest callback has no Raw measurements" : "Raw measurements received");
            if (!gnssRunning) text.append("; recording stopped");
            text.append("\nLast callback age").append(gnssRunning ? "" : " at stop").append(": ")
                .append(counter >= lastCallback ? String.format(Locale.ROOT, "%.1f s", (counter - lastCallback) / 1e9) : "unavailable");
        }
        text.append("\nSession callbacks: ").append(callbacks).append("; empty: ").append(emptyCallbacks)
            .append("; Raw rows: ").append(rawRows);
        if (lastCallback != null) {
            text.append("\nLatest callback: ").append(latestRows).append(" rows / ").append(satellites)
                .append(" satellites; GPS: ").append(gpsRows).append(" rows / ").append(gpsSatellites).append(" satellites")
                .append("\nNative epoch: ").append(hasEpoch ? "present" : "missing/invalid")
                .append("; FullBias: ").append(hasBias ? "present" : "missing/invalid")
                .append("\nReported alignment uncertainty: ").append(reportedUncertainty == null ? "missing/invalid" : reportedUncertainty + " ns (68% receiver estimate, not a bound)")
                .append("\nCallbacks missing/invalid epoch / uncertainty / FullBias: ")
                .append(missingEpochs).append(" / ").append(missingUncertainties).append(" / ").append(missingBiases)
                .append("\nClock discontinuity count: ").append(discontinuity == null ? "unavailable" : discontinuity)
                .append("; observed changes: ").append(discontinuityChanges);
        }
        text.append("\nNTS authenticated: ").append(authenticated).append("/").append(scheduledAttempts)
            .append("; unavailable: ").append(unavailable).append("; ").append(ntsRunning ? "pending" : "not attempted")
            .append(": ").append(scheduledAttempts - authenticated - unavailable);
        for (Map.Entry<String, String> endpoint : endpoints.entrySet()) {
            text.append("\n").append(endpoint.getKey()).append(" (latest completed): ")
                .append(endpoint.getValue() == null ? "none" : endpoint.getValue());
        }
        if (rawRows == 0) text.append("\nInsufficient GNSS data: no Raw measurements collected.");
        text.append("\nTiming comparison: NOT ASSESSED. Timing budgets and counter resolution: unqualified.")
            .append("\nReception, clock changes and NTS transport results do not establish GNSS authenticity.");
        return text.toString();
    }

    private static Long integer(String value) {
        try { return value == null ? null : Long.parseLong(value); }
        catch (NumberFormatException error) { return null; }
    }
    private static Double nonnegativeFinite(String value) {
        if (value == null) return null;
        try {
            double parsed = Double.parseDouble(value);
            return Double.isFinite(parsed) && parsed >= 0 ? parsed : null;
        } catch (NumberFormatException error) { return null; }
    }
}
