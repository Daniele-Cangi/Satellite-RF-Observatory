# Previously revealed G08 regression data

These small excerpts derive from the public BKG observations, reference-only
broadcast file and G08-only IGS oracle already opened in the closed DOY249 run.
They are engineering fixtures, not new or unexposed confirmation data.

- `g08_admitted.json`: eleven epochs of non-G08 calibration measurements at six
  stations and target IF codes at only the five fit stations.
- `g08_reference_only.rnx.gz`: the originally admitted non-G08 navigation file.
- `gold_g08_excerpt.rnx.gz`: header and first eleven epochs of GOLD, gzip RINEX
  rather than a full daily Hatanaka product.
- `gold_header.json`: original header interpretation for the GOLD excerpt.
- `g08_oracle_excerpt.sp3`: first nine G08 positions from the already revealed
  IGS rapid product; abbreviated test header. It is not an official full SP3.

Original observation pattern:
`https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/249/{station}_R_20262490000_01D_30S_MO.crx.gz`

Original oracle:
`https://igs.bkg.bund.de/root_ftp/IGS/products/2435/IGS0OPSRAP_20262490000_01D_15M_ORB.SP3.gz`

The regression preserves the original result as `UNCERTAINTY_TOO_LARGE`.
