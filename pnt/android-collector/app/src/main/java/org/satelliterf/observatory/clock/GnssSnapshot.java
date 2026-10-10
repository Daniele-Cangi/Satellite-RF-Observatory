package org.satelliterf.observatory.clock;

import android.location.GnssClock;
import android.location.GnssMeasurement;
import java.util.LinkedHashMap;
import java.util.Map;

/** Serialize native values verbatim; absent optional values stay blank. */
final class GnssSnapshot {
    private GnssSnapshot() {}

    static Map<String, String> clock(GnssClock c) {
        Map<String, String> v = new LinkedHashMap<>();
        v.put("TimeNanos", Long.toString(c.getTimeNanos()));
        v.put("HardwareClockDiscontinuityCount", Integer.toString(c.getHardwareClockDiscontinuityCount()));
        optional(v, "LeapSecond", c.hasLeapSecond(), c.hasLeapSecond() ? c.getLeapSecond() : null);
        optional(v, "TimeUncertaintyNanos", c.hasTimeUncertaintyNanos(), c.hasTimeUncertaintyNanos() ? c.getTimeUncertaintyNanos() : null);
        optional(v, "FullBiasNanos", c.hasFullBiasNanos(), c.hasFullBiasNanos() ? c.getFullBiasNanos() : null);
        optional(v, "BiasNanos", c.hasBiasNanos(), c.hasBiasNanos() ? c.getBiasNanos() : null);
        optional(v, "BiasUncertaintyNanos", c.hasBiasUncertaintyNanos(), c.hasBiasUncertaintyNanos() ? c.getBiasUncertaintyNanos() : null);
        optional(v, "DriftNanosPerSecond", c.hasDriftNanosPerSecond(), c.hasDriftNanosPerSecond() ? c.getDriftNanosPerSecond() : null);
        optional(v, "DriftUncertaintyNanosPerSecond", c.hasDriftUncertaintyNanosPerSecond(), c.hasDriftUncertaintyNanosPerSecond() ? c.getDriftUncertaintyNanosPerSecond() : null);
        // Compatibility name used by GNSS Logger and pnt.android_time. This is
        // GnssClock's epoch, never a replacement with the callback counter.
        v.put("HasElapsedRealtimeNanos", Boolean.toString(c.hasElapsedRealtimeNanos()));
        v.put("ChipsetElapsedRealtimeNanos", c.hasElapsedRealtimeNanos() ? Long.toString(c.getElapsedRealtimeNanos()) : "");
        optional(v, "ElapsedRealtimeUncertaintyNanos", c.hasElapsedRealtimeUncertaintyNanos(),
            c.hasElapsedRealtimeUncertaintyNanos() ? c.getElapsedRealtimeUncertaintyNanos() : null);
        return v;
    }

    static Map<String, String> measurement(GnssMeasurement m) {
        Map<String, String> v = new LinkedHashMap<>();
        v.put("Svid", Integer.toString(m.getSvid()));
        v.put("ConstellationType", Integer.toString(m.getConstellationType()));
        v.put("TimeOffsetNanos", Double.toString(m.getTimeOffsetNanos()));
        v.put("State", Integer.toString(m.getState()));
        v.put("ReceivedSvTimeNanos", Long.toString(m.getReceivedSvTimeNanos()));
        v.put("ReceivedSvTimeUncertaintyNanos", Long.toString(m.getReceivedSvTimeUncertaintyNanos()));
        v.put("Cn0DbHz", Double.toString(m.getCn0DbHz()));
        v.put("PseudorangeRateMetersPerSecond", Double.toString(m.getPseudorangeRateMetersPerSecond()));
        v.put("PseudorangeRateUncertaintyMetersPerSecond", Double.toString(m.getPseudorangeRateUncertaintyMetersPerSecond()));
        v.put("AccumulatedDeltaRangeState", Integer.toString(m.getAccumulatedDeltaRangeState()));
        v.put("AccumulatedDeltaRangeMeters", Double.toString(m.getAccumulatedDeltaRangeMeters()));
        v.put("AccumulatedDeltaRangeUncertaintyMeters", Double.toString(m.getAccumulatedDeltaRangeUncertaintyMeters()));
        v.put("CodeType", m.getCodeType());
        v.put("CarrierFrequencyHz", m.hasCarrierFrequencyHz() ? Float.toString(m.getCarrierFrequencyHz()) : "");
        v.put("SnrInDb", m.hasSnrInDb() ? Double.toString(m.getSnrInDb()) : "");
        v.put("AgcDb", m.hasAutomaticGainControlLevelDb() ? Double.toString(m.getAutomaticGainControlLevelDb()) : "");
        return v;
    }

    private static void optional(Map<String, String> values, String field, boolean present, Number value) {
        values.put("Has" + field, Boolean.toString(present));
        values.put(field, present ? value.toString() : "");
    }
}
