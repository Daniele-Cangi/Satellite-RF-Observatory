package org.satelliterf.observatory.clock;

import java.net.URI;
import java.net.URISyntaxException;

/** Validate a document-picker destination before any output is opened. */
final class ExportDestination {
    private ExportDestination() {}

    static URI validate(String value, boolean explicitWriteGrant, boolean documentUri) {
        final URI destination;
        try { destination = new URI(value); }
        catch (URISyntaxException error) { throw new SecurityException("Invalid export URI", error); }
        if (!"content".equals(destination.getScheme()) || destination.getAuthority() == null
                || destination.getRawPath() == null || destination.getRawPath().isEmpty()
                || destination.getRawPath().equals("/") || !explicitWriteGrant || !documentUri) {
            throw new SecurityException("Export requires a content document with an explicit write grant");
        }
        // Android validates the DocumentsProvider envelope. Its document ID is opaque:
        // encoded slashes/dots are provider data, never a local filesystem path.
        return destination;
    }
}
