package org.satelliterf.observatory.clock;

import org.junit.Test;
import static org.junit.Assert.*;

public final class DocumentDestinationTest {
    @Test public void rejectsDirectPrivateFilesAndOtherSchemesEvenWithAReportedGrant() {
        for (String uri : new String[]{"file:///data/user/0/org.satelliterf.observatory.clock/files/session.txt",
                "file:///storage/emulated/0/Download/export.zip", "https://example.invalid/export.zip",
                "/data/user/0/private", "content:opaque", "content:///document/export.zip", "bad URI"}) {
            assertThrows(SecurityException.class, () -> DocumentDestination.validate(uri, true, true));
        }
    }

    @Test public void providerAccessWithoutAnExplicitGrantCannotAuthorizeAnExport() {
        assertThrows(SecurityException.class, () -> DocumentDestination.validate(
            "content://com.android.providers.downloads.documents/document/123", false, true));
    }

    @Test public void rejectsProviderRootsAndNonDocumentsIncludingEncodedLeadingSlashes() {
        for (String uri : new String[]{"content://provider", "content://provider?key=value", "content://provider/",
                "content://provider/%2Fdata/user/0/private", "content://provider//data/user/0/private",
                "content://provider/data/user/0/private"}) {
            assertThrows(SecurityException.class, () -> DocumentDestination.validate(uri, true, false));
        }
        assertThrows(SecurityException.class, () -> DocumentDestination.validate("content://provider", true, true));
        assertThrows(SecurityException.class, () -> DocumentDestination.validate("content://provider/", true, true));
    }

    @Test public void preservesGrantedDocumentIdsAndDoesNotRewriteProviderPaths() {
        for (String uri : new String[]{"content://com.android.providers.downloads.documents/document/123",
                "content://com.android.externalstorage.documents/document/primary%3ADownload%2Fpnt.zip",
                "content://cloud.provider/document/folder%2Fexport.zip?account=1",
                "content://cloud/document/..%2Fdata%2Fexport.zip",
                "content://cloud/document/%2Fdata%2Fexport.zip",
                "content://cloud/tree/root%2Ffolder/document/..%2Fdata%2Fexport.zip"}) {
            assertEquals(uri, DocumentDestination.validate(uri, true, true).toString());
        }
    }
}
