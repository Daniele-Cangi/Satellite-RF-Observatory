# DRAO DOY232 materialization description error

**QUALIFICATION_DESCRIPTION_ERROR**

The one authorized transport attempt completed the file download and reached
full-file SHA-256 calculation. Receipt construction then failed because the
GET response did not expose `Content-Length` in the array form assumed by the
PowerShell expression. The attempted indexing raised `Cannot index into a
null array`.

This is not `QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED`: network transfer,
file creation and hashing had returned before the receipt expression failed.
It is also not a capability rejection. No artifact identity or physical
qualification clause obtained an admissible receipt, so every clause and the
physical decision remain `NOT_EVALUATED`.

## Preserved boundary

- transport attempts: 1;
- decompression attempts: 0;
- observation headers parsed: 0;
- observation values accessed: 0;
- primary locators, headers, bytes and values: 0;
- artifact payloads retained after cleanup: 0;
- retries after the failure: 0.

The computed digest and runtime byte count were local variables in the failed
process and were not emitted. They are recorded as unavailable, not replaced
with the HEAD length, ETag or an invented value.

The cleanup `finally` removed the exact file and empty quarantine directory.
A subsequent filesystem check confirmed that both are absent and the working
tree was clean.

## Retry boundary

The frozen contract permits no retry after complete-file hashing or decode.
Although one of the two nominal transport attempts remains, it cannot be used
under the present authority because hashing was reached. No repeat transfer
was made.

The next step is a change-of-abstraction review. It must decide whether a
content-blind, same-artifact receipt replay before any decode can be separated
from scientific retry. That rule cannot be changed inside this failed
execution.
