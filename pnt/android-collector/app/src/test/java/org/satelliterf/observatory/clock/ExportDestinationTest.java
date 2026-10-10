package org.satelliterf.observatory.clock;

import org.junit.Test;
import static org.junit.Assert.*;

public final class ExportDestinationTest {
    @Test public void rejectsDirectPrivateFilesAndOtherSchemesEvenWithAReportedGrant() {
        for (String uri : new String[]{"file:///data/user/0/org.satelliterf.observatory.clock/files/session.txt",
                "file:///storage/emulated/0/Download/export.zip", "https://example.invalid/export.zip",
                "/data/user/0/private", "content:opaque", "content:///document/export.zip", "bad URI"}) {
            assertThrows(SecurityException.class, () -> ExportDestination.validate(uri, true));
        }
    }

    @Test public void providerAccessWithoutAnExplicitGrantCannotAuthorizeAnExport() {
        assertThrows(SecurityException.class, () -> ExportDestination.validate(
            "content://com.android.providers.downloads.documents/document/123", false));
    }

    @Test public void rejectsPrivatePathsAfterDecodingAndNormalizingTraversal() {
        for (String path : new String[]{"/data/user/0/private", "/document/../data/user/0/private",
                "/document/%2e%2e%2fdata/user/0/private", "/document/../../data/user/0/private"}) {
            assertThrows(SecurityException.class, () -> ExportDestination.validate("content://provider" + path, true));
        }
    }

    @Test public void preservesGrantedDocumentIdsAndDoesNotRewriteProviderPaths() {
        for (String uri : new String[]{"content://com.android.providers.downloads.documents/document/123",
                "content://com.android.externalstorage.documents/document/primary%3ADownload%2Fpnt.zip",
                "content://cloud.provider/document/folder%2Fexport.zip?account=1"}) {
            assertEquals(uri, ExportDestination.validate(uri, true).toString());
        }
    }
}
