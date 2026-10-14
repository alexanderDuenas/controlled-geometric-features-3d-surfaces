
# Provenance

This directory contains release and historical provenance material that is not
required as an operational input to `run_all.py`.

## Release provenance

- `PUBLIC_RELEASE_TRANSFORM.md` documents the public-release transformation
  applied before the v4 release.
- `MASK_PROVENANCE_AND_LICENSE_NOTE.md` records the provenance and licensing
  boundary of the released UAV visibility masks.
- `v4_build_self_test.txt`, when present, records the earlier v4 build test.
- `source_hashes.csv`, when present, retains historical source hashes.
- `neutral_local_test.json`, when present, records an earlier neutral-example
  local test.

## Legacy parameterization provenance

`legacy_parameterization/` contains historical parameterization artifacts that
are retained only for provenance. They are not operational inputs to the public
MethodsX validation and should not be interpreted as the final 40-feature
design population.

The operational design population is:

```text
data/parameterization/feature_design_40.csv
```
