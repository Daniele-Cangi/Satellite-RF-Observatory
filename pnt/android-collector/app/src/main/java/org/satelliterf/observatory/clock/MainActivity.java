package org.satelliterf.observatory.clock;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.GnssMeasurementsEvent;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Bundle;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Foreground-only collector. Closing/hiding the app ends the current file. */
public final class MainActivity extends Activity {
    private static final int LOCATION_PERMISSION = 1;
    private static final int EXPORT_FILE = 2;
    private LocationManager locations;
    private CaptureLog log;
    private File latestFile;
    private TextView status;
    private Button startButton;
    private Button stopButton;
    private Button exportButton;
    private long missingEpochs;
    private long missingUncertainties;

    private final LocationListener locationListener = new LocationListener() {
        @Override public void onLocationChanged(Location ignored) {
            // Activate GPS without recording position, accuracy or a fix as truth.
        }
        @Override public void onProviderDisabled(String provider) {
            if (log != null) stop("GPS_PROVIDER_DISABLED");
        }
        @Override public void onProviderEnabled(String provider) {}
        @Override public void onStatusChanged(String provider, int value, Bundle extras) {}
    };

    private final GnssMeasurementsEvent.Callback callback = new GnssMeasurementsEvent.Callback() {
        @Override public void onGnssMeasurementsReceived(GnssMeasurementsEvent event) {
            long start = SystemClock.elapsedRealtimeNanos();
            if (log == null) return;
            try {
                Map<String, String> clock = GnssSnapshot.clock(event.getClock());
                List<Map<String, String>> rows = new ArrayList<>();
                for (var measurement : event.getMeasurements()) {
                    rows.add(GnssSnapshot.measurement(measurement));
                }
                long readEnd = SystemClock.elapsedRealtimeNanos();
                log.event(start, readEnd, clock, rows);
                if (!event.getClock().hasElapsedRealtimeNanos()) missingEpochs++;
                if (!event.getClock().hasElapsedRealtimeUncertaintyNanos()) missingUncertainties++;
                show("Recording\nCallbacks: " + log.eventCount() + "\nRaw rows: " + log.rowCount()
                    + "\nEpoch absent: " + missingEpochs + "\nAlignment uncertainty absent: " + missingUncertainties
                    + "\nKeep this app visible (split screen with Termux is supported).");
            } catch (IOException | RuntimeException error) {
                fail(error);
            }
        }
        @Override public void onStatusChanged(int value) {
            if (log == null) return;
            try {
                log.comment("GnssStatus", Long.toString(SystemClock.elapsedRealtimeNanos()), Integer.toString(value));
            } catch (IOException error) { fail(error); }
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        locations = (LocationManager) getSystemService(LOCATION_SERVICE);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (20 * getResources().getDisplayMetrics().density);
        layout.setPadding(padding, padding, padding, padding);
        status = new TextView(this);
        status.setTextSize(18);
        layout.addView(status);
        startButton = button(layout, "Start recording", v -> requestStart());
        stopButton = button(layout, "Stop recording", v -> stop("USER_STOPPED"));
        exportButton = button(layout, "Export last file", v -> export());
        ScrollView scroll = new ScrollView(this);
        scroll.addView(layout);
        setContentView(scroll);
        File[] previous = getFilesDir().listFiles((dir, name) -> name.startsWith("pnt-clock-") && name.endsWith(".txt"));
        if (previous != null) {
            for (File file : previous) {
                if (latestFile == null || file.lastModified() > latestFile.lastModified()) latestFile = file;
            }
        }
        show("PNT Clock Collector\nGNSS clocks and callback timing; no authenticity decision."
            + (latestFile == null ? "" : "\nPrevious file retained; completion not checked."));
        buttons();
        // Insets keep controls reachable on Android's edge-to-edge display.
        if (Build.VERSION.SDK_INT >= 30) {
            layout.setOnApplyWindowInsetsListener((view, insets) -> {
                var bars = insets.getInsets(android.view.WindowInsets.Type.systemBars());
                view.setPadding(padding + bars.left, padding + bars.top, padding + bars.right, padding + bars.bottom);
                return insets;
            });
        }
    }

    private Button button(LinearLayout layout, String label, View.OnClickListener action) {
        Button button = new Button(this);
        button.setText(label);
        button.setOnClickListener(action);
        layout.addView(button);
        return button;
    }

    private void requestStart() {
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.ACCESS_COARSE_LOCATION,
                Manifest.permission.ACCESS_FINE_LOCATION}, LOCATION_PERMISSION);
        } else { start(); }
    }

    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] grants) {
        super.onRequestPermissionsResult(request, permissions, grants);
        if (request != LOCATION_PERMISSION) return;
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) start();
        else show("Precise location permission is required for GNSS measurements. No recording started.");
    }

    private void start() {
        if (log != null) return;
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            show("Precise location permission is required. No recording started.");
            return;
        }
        try {
            if (!locations.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                show("Enable device Location/GPS before starting. No recording started.");
                return;
            }
            String id = UUID.randomUUID().toString();
            File file = new File(getFilesDir(), "pnt-clock-" + id + ".txt");
            Map<String, String> metadata = new LinkedHashMap<>();
            metadata.put("Version", BuildConfig.VERSION_NAME);
            metadata.put("SourceRevision", BuildConfig.SOURCE_REVISION);
            metadata.put("Device", Build.MANUFACTURER + " " + Build.MODEL);
            metadata.put("Sdk", Integer.toString(Build.VERSION.SDK_INT));
            metadata.put("BuildFingerprint", Build.FINGERPRINT);
            metadata.put("Counter", "SystemClock.elapsedRealtimeNanos / CLOCK_BOOTTIME");
            metadata.put("StartElapsedRealtimeNanos", Long.toString(SystemClock.elapsedRealtimeNanos()));
            OutputStream output = Files.newOutputStream(file.toPath(), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            latestFile = file;
            try {
                log = new CaptureLog(new OutputStreamWriter(output, StandardCharsets.UTF_8), id, metadata);
            } catch (IOException | RuntimeException error) {
                try { output.close(); } catch (IOException closing) { error.addSuppressed(closing); }
                throw error;
            }
            missingEpochs = missingUncertainties = 0;
            // Handler API avoids the Android R pre-QPR1 Executor callback issue.
            boolean registered = locations.registerGnssMeasurementsCallback(callback, new Handler(Looper.getMainLooper()));
            if (!registered) throw new IllegalStateException("GNSS callback registration rejected");
            locations.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000L, 0f, locationListener, Looper.getMainLooper());
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            show("Recording; waiting for GNSS callbacks. Keep the app visible.");
            buttons();
        } catch (IOException | RuntimeException error) { fail(error); }
    }

    private void fail(Exception error) {
        String message = error.getClass().getSimpleName() + ": " + error.getMessage();
        if (log != null) {
            try { log.comment("Error", Long.toString(SystemClock.elapsedRealtimeNanos()), message); }
            catch (IOException ignored) { /* Partial file remains; UI reports failure. */ }
        }
        String cleanupErrors = stop("FAILED");
        show("Capture failed: " + message + cleanupErrors + "\nOriginal/partial file retained. No automatic retry.");
    }

    private String stop(String reason) {
        CaptureLog closing = log;
        log = null; // Late queued callbacks cannot append to a closed file.
        String errors = "";
        try { locations.unregisterGnssMeasurementsCallback(callback); }
        catch (RuntimeException error) { errors += "\nUnregister failed: " + error; }
        try { locations.removeUpdates(locationListener); }
        catch (RuntimeException error) { errors += "\nGPS release failed: " + error; }
        if (closing != null) {
            if (!errors.isEmpty()) {
                try { closing.comment("CleanupError", errors); }
                catch (IOException error) { errors += "\nCleanup error write failed: " + error; }
            }
            try { closing.finish(reason, SystemClock.elapsedRealtimeNanos()); }
            catch (IOException error) { errors += "\nTerminal write failed: " + error; }
            try { closing.close(); }
            catch (IOException error) { errors += "\nFile close failed: " + error; }
            show(reason + "\nCallbacks: " + closing.eventCount() + "\nRaw rows: " + closing.rowCount() + errors);
        }
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        buttons();
        return errors;
    }

    @Override protected void onStop() {
        if (log != null) stop("ACTIVITY_STOPPED");
        super.onStop();
    }

    private void export() {
        if (log != null || latestFile == null) return;
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("text/plain");
        intent.putExtra(Intent.EXTRA_TITLE, latestFile.getName());
        startActivityForResult(intent, EXPORT_FILE);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != EXPORT_FILE || result != RESULT_OK || data == null || data.getData() == null) return;
        try (InputStream input = Files.newInputStream(latestFile.toPath());
             OutputStream output = getContentResolver().openOutputStream(data.getData(), "wt")) {
            if (output == null) throw new IOException("No export stream");
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            show("File exported. Private original retained.");
        } catch (IOException | RuntimeException error) { show("Export failed; original retained: " + error); }
    }

    private void buttons() {
        startButton.setEnabled(log == null);
        stopButton.setEnabled(log != null);
        exportButton.setEnabled(log == null && latestFile != null);
    }
    private void show(String text) {
        status.setText(text + (latestFile == null ? "" : "\nFile: " + latestFile.getName()));
    }
}
