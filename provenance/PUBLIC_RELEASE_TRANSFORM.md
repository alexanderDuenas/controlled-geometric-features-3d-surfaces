# Public release transformation from v3 to v4

The transformation changes public identifiers and release organization, not the
scientific validation populations.

Changes:

- generated `results/` were removed from the distribution;
- acquisition filenames were replaced by `View_01` ... `View_12`;
- 480 mask filenames were renamed consistently;
- public operational image bounds are recorded as 6144 x 4096 px;
- the five manuscript validation gates are explicitly recomputed;
- station reprojection/projected scale are separated from validation gates;
- the frozen-input boundary of the UAV configuration is documented;
- package hashes and release indices are regenerated.

No raw RGB, EXIF, GPS, latitude/longitude or absolute site coordinates are
introduced.

The mapping from public view labels back to historical acquisition filenames is
intentionally not distributed.
