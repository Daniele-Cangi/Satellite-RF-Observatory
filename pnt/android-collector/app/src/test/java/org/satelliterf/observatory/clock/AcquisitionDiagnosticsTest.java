package org.satelliterf.observatory.clock;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.Test;
import static org.junit.Assert.*;

public final class AcquisitionDiagnosticsTest {
    private AcquisitionDiagnostics diagnostics() {
        return new AcquisitionDiagnostics(List.of("a", "b"), 4);
    }
    private Map<String, String> clock() {
        Map<String, String> clock = new LinkedHashMap<>(CaptureLogTest.clock(true));
        clock.put("HasFullBiasNanos", "true");
        clock.put("HasElapsedRealtimeUncertaintyNanos", "true");
        clock.put("ElapsedRealtimeUncertaintyNanos", "7001000.0");
        return clock;
    }

    @Test public void countsSignalsSeparatelyButDeduplicatesSatellitesAndRetainsEmptyCallbacks() {
        AcquisitionDiagnostics diagnostics = diagnostics();
        Map<String, String> otherSignal = new LinkedHashMap<>(CaptureLogTest.measurement());
        otherSignal.put("CarrierFrequencyHz", "1.17645E9");
        Map<String, String> otherConstellation = new LinkedHashMap<>(CaptureLogTest.measurement());
        otherConstellation.put("ConstellationType", "6");
        diagnostics.gnss(1, clock(), List.of(CaptureLogTest.measurement(), otherSignal, otherConstellation));
        String received = diagnostics.render(2, true, true);
        assertTrue(received.contains("3 rows / 2 satellites; GPS: 2 rows / 1 satellites"));
        diagnostics.gnss(3, clock(), List.of());
        String empty = diagnostics.render(4, true, true);
        assertTrue(empty.contains("latest callback has no Raw measurements"));
        assertTrue(empty.contains("Session callbacks: 2; empty: 1; Raw rows: 3"));
        assertTrue(empty.contains("Latest callback: 0 rows / 0 satellites"));
    }

    @Test public void optionalFlagsAndInvalidValuesCannotBecomeTimingEvidence() {
        AcquisitionDiagnostics diagnostics = diagnostics();
        Map<String, String> clock = clock();
        clock.put("HasElapsedRealtimeNanos", "false");
        clock.put("ChipsetElapsedRealtimeNanos", "0");
        clock.put("HasFullBiasNanos", "false");
        clock.put("HasElapsedRealtimeUncertaintyNanos", "false");
        clock.put("ElapsedRealtimeUncertaintyNanos", "0");
        diagnostics.gnss(1, clock, List.of());
        String text = diagnostics.render(2, true, true);
        assertTrue(text.contains("Native epoch: missing/invalid; FullBias: missing/invalid"));
        assertTrue(text.contains("Reported alignment uncertainty: missing/invalid"));
        assertTrue(text.contains("epoch / uncertainty / FullBias: 1 / 1 / 1"));
        for (String value : List.of("NaN", "Infinity", "-1", "bad")) {
            clock = clock();
            clock.put("ElapsedRealtimeUncertaintyNanos", value);
            diagnostics.gnss(3, clock, List.of());
            assertTrue(diagnostics.render(4, true, true).contains("Reported alignment uncertainty: missing/invalid"));
        }
        clock.put("ElapsedRealtimeUncertaintyNanos", "0");
        diagnostics.gnss(5, clock, List.of());
        text = diagnostics.render(6, true, true);
        assertTrue(text.contains("0.0 ns (68% receiver estimate, not a bound)"));
        assertTrue(text.contains("Timing comparison: NOT ASSESSED"));
        assertTrue(text.contains("Timing budgets and counter resolution: unqualified"));
    }

    @Test public void callbackAgeUsesIntegerDifferencesWithoutReplacingOrMutatingNativeEpoch() {
        AcquisitionDiagnostics diagnostics = diagnostics();
        Map<String, String> clock = clock();
        Map<String, String> original = Map.copyOf(clock);
        long callback = 9007199254741003L;
        diagnostics.gnss(callback, clock, List.of(CaptureLogTest.measurement()));
        assertTrue(diagnostics.render(callback + 50000000L, true, true).contains("Last callback age: 0.1 s"));
        assertTrue(diagnostics.render(callback + 1500000000L, false, false).contains("Last callback age at stop: 1.5 s"));
        assertTrue(diagnostics.render(callback - 1, true, true).contains("Last callback age: unavailable"));
        assertEquals(original, clock);
    }

    @Test public void countChangesIncludingDecreasesStayVisibleWithoutAttributingACause() {
        AcquisitionDiagnostics diagnostics = diagnostics();
        Map<String, String> clock = clock();
        diagnostics.gnss(1, clock, List.of());
        diagnostics.gnss(2, clock, List.of());
        clock.put("HardwareClockDiscontinuityCount", "8");
        diagnostics.gnss(3, clock, List.of());
        clock.remove("HardwareClockDiscontinuityCount");
        diagnostics.gnss(4, clock, List.of());
        assertTrue(diagnostics.render(4, true, true).contains("Clock discontinuity count: unavailable; observed changes: 1"));
        clock.put("HardwareClockDiscontinuityCount", "0");
        diagnostics.gnss(5, clock, List.of());
        assertTrue(diagnostics.render(6, true, true).contains("Clock discontinuity count: 0; observed changes: 2"));
    }

    @Test public void laterNtsSuccessCannotHideCumulativeFailuresOrCreateGnssEvidence() {
        AcquisitionDiagnostics diagnostics = diagnostics();
        diagnostics.ntsAttempt("a", "WITNESS_UNAVAILABLE", "IOException: synthetic timeout");
        diagnostics.ntsProgress(0, 1);
        assertTrue(diagnostics.render(1, true, true).contains("WITNESS_UNAVAILABLE — IOException: synthetic timeout"));
        diagnostics.ntsAttempt("a", "AUTHENTICATED_EXCHANGE", null);
        diagnostics.ntsProgress(1, 1);
        String text = diagnostics.render(2, false, false);
        assertTrue(text.contains("NTS authenticated: 1/4; unavailable: 1; not attempted: 2"));
        assertTrue(text.contains("a (latest completed): AUTHENTICATED_EXCHANGE"));
        assertTrue(text.contains("b (latest completed): none"));
        assertTrue(text.contains("no measurement callbacks received"));
        assertTrue(text.contains("Insufficient GNSS data: no Raw measurements collected"));
        assertTrue(text.contains("Timing comparison: NOT ASSESSED"));
    }
}
