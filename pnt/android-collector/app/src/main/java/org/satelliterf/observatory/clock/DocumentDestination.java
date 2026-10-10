package org.satelliterf.observatory.clock;

import java.net.URI;
import java.net.URISyntaxException;

/** Shared validation for explicit read/write access through the document picker. */
final class DocumentDestination {
    private DocumentDestination() {}

    static URI validate(String value, boolean explicitGrant, boolean documentUri) {
        final URI destination;
        try { destination = new URI(value); }
        catch (URISyntaxException error) { throw new SecurityException("Invalid export URI", error); }
        if (!"content".equals(destination.getScheme()) || destination.getAuthority() == null
                || destination.getRawPath() == null || destination.getRawPath().isEmpty()
                || destination.getRawPath().equals("/") || !explicitGrant || !documentUri) {
            throw new SecurityException("Document access requires a content document with an explicit URI grant");
        }
        // Android validates the DocumentsProvider envelope. Its document ID is opaque:
        // encoded slashes/dots are provider data, never a local filesystem path.
        return destination;
    }
}
