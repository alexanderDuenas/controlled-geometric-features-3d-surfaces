
# v4.1 public-release cleanup

v4.1 is a release-structure cleanup of the audited v4 package. It does not
introduce new UAV scientific populations or change the frozen UAV validation
inputs.

Changes include:

- removal of accidental editor lock files;
- removal of redundant root-level quick-start/release-note documents;
- relocation of release and historical artifacts under `provenance/`;
- creation of `data/method_contract.json`;
- correction of README file-tree references;
- cleanup of public neutral-example terminology;
- correction of presentation-only text in `run_all.py`;
- regeneration of release inventories and SHA-256 hashes.

The operational UAV design remains:

```text
data/parameterization/feature_design_40.csv
```

Historical parameterization files moved under
`provenance/legacy_parameterization/` are not operational inputs to the public
validation.
