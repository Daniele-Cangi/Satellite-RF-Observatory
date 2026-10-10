package org.satelliterf.observatory.clock;

import java.net.URI;
import java.net.URISyntaxException;

/** Validate a document-picker destination before any output is opened. */
final class ExportDestination {
    private ExportDestination() {}

    static URI validate(String value, boolean explicitWriteGrant) {
        final URI destination;
        try { destination = new URI(value); }
        catch (URISyntaxException error) { throw new SecurityException("Invalid export URI", error); }
        if (!"content".equals(destination.getScheme()) || destination.getAuthority() == null
                || destination.getPath() == null || !explicitWriteGrant) {
            throw new SecurityException("Export requires a content document with an explicit write grant");
        }
        // Decode and normalize before rejecting references to Android private storage.
        final String path;
        try { path = new URI(null, null, destination.getPath(), null).normalize().getPath(); }
        catch (URISyntaxException error) { throw new SecurityException("Invalid export path", error); }
        if (path.equals("/..") || path.startsWith("/../") || path.equals("/data") || path.startsWith("/data/")) {
            throw new SecurityException("Private export destination rejected");
        }
        return destination; // Preserve the provider's URI, including opaque document IDs.
    }
}
