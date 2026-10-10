package org.satelliterf.observatory.clock;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.GnssMeasurementsEvent;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.provider.DocumentsContract;
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
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Foreground-only collector. Closing/hiding the app ends the current file. */
public final class MainActivity extends Activity {
    private static final int LOCATION_PERMISSION = 1;
    private static final int EXPORT_FILE = 2;
    private static final int IMPORT_REPORT = 3;
    private static final List<String> NTS_SERVERS = Arrays.asList("ptbtime1.ptb.de", "ptbtime2.ptb.de");
    private static final int NTS_ROUNDS = 10;
    private LocationManager locations;
    private CaptureLog log;
    private File latestFile;
    private File latestNtsFile;
    private NtsCapture ntsCapture;
    private int ntsAuthenticated;
    private int ntsUnavailable;
    private String gnssTerminal;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private TextView status;
    private TextView details;
    private AcquisitionDiagnostics diagnostics;
    private long stoppedCounter;
    private Button startButton;
    private Button stopButton;
    private Button exportButton;
    private Button reportButton;
    private TextView reportDetails;
    private boolean reportLoading;
    private final Runnable refreshDiagnostics = new Runnable() {
        @Override public void run() {
            if (log == null) return;
            renderDiagnostics();
            ui.postDelayed(this, 1000L);
        }
    };

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
                diagnostics.gnss(start, clock, rows);
                renderDiagnostics();
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
        startButton = button(layout, "Start GNSS + NTS", v -> requestStart());
        stopButton = button(layout, "Stop recording", v -> stop("USER_STOPPED"));
        exportButton = button(layout, "Export last session", v -> export());
        reportButton = button(layout, "Open PC report", v -> importReport());
        details = new TextView(this);
        details.setTextSize(16);
        layout.addView(details);
        reportDetails = new TextView(this);
        reportDetails.setTextSize(16);
        layout.addView(reportDetails);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(layout);
        setContentView(scroll);
        File[] previous = getFilesDir().listFiles((dir, name) -> name.startsWith("pnt-clock-") && name.endsWith(".txt"));
        if (previous != null) {
            for (File file : previous) {
                if (latestFile == null || file.lastModified() > latestFile.lastModified()) latestFile = file;
            }
        }
        if (latestFile != null) {
            File nts = new File(getFilesDir(), latestFile.getName().replace("pnt-clock-", "pnt-nts-").replace(".txt", ".json"));
            if (nts.isFile()) latestNtsFile = nts;
        }
        show("PNT Clock Collector\nGNSS + authenticated Internet time; no authenticity decision."
            + (latestFile == null ? "" : "\nPrevious file retained; completion not checked."));
        buttons();
        File[] reports = getFilesDir().listFiles((dir, name) -> name.startsWith("pnt-report-") && name.endsWith(".json"));
        File lastReport = null;
        if (reports != null) for (File file : reports) {
            if (lastReport == null || file.lastModified() > lastReport.lastModified()) lastReport = file;
        }
        if (lastReport != null) loadReport(lastReport, null);
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
        if (busy()) return;
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
            metadata.put("BootCount", Integer.toString(Settings.Global.getInt(getContentResolver(), Settings.Global.BOOT_COUNT, -1)));
            OutputStream output = Files.newOutputStream(file.toPath(), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            latestFile = file;
            latestNtsFile = null;
            try {
                log = new CaptureLog(new OutputStreamWriter(output, StandardCharsets.UTF_8), id, metadata);
            } catch (IOException | RuntimeException error) {
                try { output.close(); } catch (IOException closing) { error.addSuppressed(closing); }
                throw error;
            }
            diagnostics = new AcquisitionDiagnostics(NTS_SERVERS, NTS_ROUNDS * NTS_SERVERS.size());
            stoppedCounter = 0;
            ntsAuthenticated = ntsUnavailable = 0;
            gnssTerminal = null;
            // Handler API avoids the Android R pre-QPR1 Executor callback issue.
            boolean registered = locations.registerGnssMeasurementsCallback(callback, new Handler(Looper.getMainLooper()));
            if (!registered) throw new IllegalStateException("GNSS callback registration rejected");
            locations.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000L, 0f, locationListener, Looper.getMainLooper());
            File ntsFile = new File(getFilesDir(), "pnt-nts-" + id + ".json");
            NtsCapture capture = new NtsCapture(ntsFile.toPath(), id, file.getName(), metadata,
                NTS_SERVERS, NTS_ROUNDS, 3000000000L,
                SystemClock::elapsedRealtimeNanos, () -> new NtsClient(SystemClock::elapsedRealtimeNanos),
                new NtsCapture.Listener() {
                    @Override public void attemptCompleted(String server, String state, String reason) {
                        ui.post(() -> {
                            if (latestFile != file) return;
                            diagnostics.ntsAttempt(server, state, reason);
                        });
                    }
                    @Override public void updated(int authenticated, int unavailable) {
                        ui.post(() -> {
                            if (latestFile != file) return;
                            ntsAuthenticated = authenticated;
                            ntsUnavailable = unavailable;
                            diagnostics.ntsProgress(authenticated, unavailable);
                            if (log != null) recordingStatus();
                            else renderDiagnostics();
                        });
                    }
                    @Override public void finished(String error) {
                        ui.post(() -> {
                            if (latestFile != file) return;
                            if (log != null) stop(error == null ? "SCHEDULE_COMPLETED" : "NTS_STORAGE_FAILED");
                            String gnss = gnssTerminal == null ? "" : gnssTerminal + "\n";
                            if (error != null) show(gnss + "NTS storage/collector failed: " + error + "\nOriginal/partial files retained.");
                            else show(gnss + "NTS authenticated: " + ntsAuthenticated + "/20"
                                + "\nUnavailable attempts: " + ntsUnavailable
                                + "\nNo timing precision or GNSS authenticity assessed. Export the session.");
                            renderDiagnostics();
                            buttons();
                        });
                    }
                });
            ntsCapture = capture;
            latestNtsFile = ntsFile;
            capture.start();
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            recordingStatus();
            ui.post(refreshDiagnostics);
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
        gnssTerminal = "Capture failed: " + message + cleanupErrors + "\nOriginal/partial file retained. No automatic retry.";
        show(gnssTerminal);
    }

    private String stop(String reason) {
        if (ntsCapture != null) ntsCapture.cancel(reason);
        CaptureLog closing = log;
        log = null; // Late queued callbacks cannot append to a closed file.
        ui.removeCallbacks(refreshDiagnostics);
        if (closing != null) stoppedCounter = SystemClock.elapsedRealtimeNanos();
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
            try { closing.finish(reason, stoppedCounter); }
            catch (IOException error) { errors += "\nTerminal write failed: " + error; }
            try { closing.close(); }
            catch (IOException error) { errors += "\nFile close failed: " + error; }
            gnssTerminal = reason + "\nCallbacks: " + closing.eventCount() + "\nRaw rows: " + closing.rowCount() + errors;
            show(gnssTerminal);
        }
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        renderDiagnostics();
        buttons();
        return errors;
    }

    @Override protected void onStop() {
        if (busy()) stop("ACTIVITY_STOPPED");
        super.onStop();
    }

    private void export() {
        if (busy() || latestFile == null) return;
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/zip");
        intent.putExtra(Intent.EXTRA_TITLE, latestFile.getName().replace("pnt-clock-", "pnt-session-").replace(".txt", ".zip"));
        startActivityForResult(intent, EXPORT_FILE);
    }

    private void importReport() {
        if (busy() || reportLoading) return;
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        startActivityForResult(intent, IMPORT_REPORT);
    }

    private void loadReport(File retained, Uri document) {
        reportLoading = true;
        buttons();
        new Thread(() -> {
            try (InputStream input = retained == null ? getContentResolver().openInputStream(document)
                    : Files.newInputStream(retained.toPath())) {
                if (input == null) throw new IOException("No report input stream");
                SessionReport report = SessionReport.read(input, getFilesDir().toPath());
                if (retained == null) {
                    File copy = new File(getFilesDir(), "pnt-report-" + UUID.randomUUID() + ".json");
                    Files.write(copy.toPath(), report.original, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
                }
                ui.post(() -> {
                    reportDetails.setText(report.text);
                    reportLoading = false;
                    buttons();
                });
            } catch (IOException | RuntimeException error) {
                ui.post(() -> {
                    show("PC report could not be opened: " + error + "\nOriginal recordings and earlier reports retained.");
                    reportLoading = false;
                    buttons();
                });
            }
        }, "pnt-report-import").start();
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if ((request != EXPORT_FILE && request != IMPORT_REPORT) || result != RESULT_OK
                || data == null || data.getData() == null) return;
        try {
            Uri requested = data.getData();
            boolean granted = checkUriPermission(requested, android.os.Process.myPid(), android.os.Process.myUid(),
                request == EXPORT_FILE ? Intent.FLAG_GRANT_WRITE_URI_PERMISSION : Intent.FLAG_GRANT_READ_URI_PERMISSION)
                == PackageManager.PERMISSION_GRANTED;
            String validated = DocumentDestination.validate(requested.toString(), granted,
                DocumentsContract.isDocumentUri(this, requested)).toString();
            if (!validated.equals(requested.toString())) {
                throw new SecurityException("Validated destination differs from the granted URI");
            }
            Uri destination = Uri.parse(validated);
            if (request == IMPORT_REPORT) {
                loadReport(null, destination);
                return;
            }
            try (OutputStream output = getContentResolver().openOutputStream(destination, "wt")) {
                if (output == null) throw new IOException("No export stream");
                try (ZipOutputStream zip = new ZipOutputStream(output)) {
                    for (File file : Arrays.asList(latestFile, latestNtsFile)) {
                        if (file == null) continue; // Legacy/partial sessions remain exportable.
                        zip.putNextEntry(new ZipEntry(file.getName()));
                        try (InputStream input = Files.newInputStream(file.toPath())) {
                            byte[] buffer = new byte[8192];
                            int count;
                            while ((count = input.read(buffer)) != -1) zip.write(buffer, 0, count);
                        }
                        zip.closeEntry();
                    }
                }
                show("Session exported. Private originals retained. Check both terminals before treating it as complete.");
            }
        } catch (IOException | RuntimeException error) { show("Document operation failed; originals retained: " + error); }
    }

    private void buttons() {
        startButton.setEnabled(!busy() && !reportLoading);
        stopButton.setEnabled(log != null);
        exportButton.setEnabled(!busy() && !reportLoading && latestFile != null);
        reportButton.setEnabled(!busy() && !reportLoading);
    }
    private boolean busy() { return log != null || (ntsCapture != null && !ntsCapture.isFinished()); }
    private void recordingStatus() {
        show("Recording GNSS + NTS; keep the app visible. No Termux or PC required."
            + "\nNTS authenticated: " + ntsAuthenticated + "/20; unavailable: " + ntsUnavailable
            + "\n10 rounds / 3 s; PTB endpoints share one authority. NTP era: 0.");
        renderDiagnostics();
    }
    private void renderDiagnostics() {
        if (diagnostics == null) return;
        details.setText(diagnostics.render(log == null ? stoppedCounter : SystemClock.elapsedRealtimeNanos(),
            log != null, ntsCapture != null && !ntsCapture.isFinished()));
    }
    private void show(String text) {
        status.setText(text + (latestFile == null ? "" : "\nFile: " + latestFile.getName()));
    }
}
