
# Controlled geometric features on 3D surfaces with constructed metric reference and auditable lineage

Reproducibility package accompanying the MethodsX manuscript **Controlled geometric features on 3D surfaces with constructed metric reference and auditable lineage**.

This repository provides the public validation package and an independent neutral reference implementation of the method. The UAV validation branch is reproduced from frozen packaged inputs; it is not a reconstruction of the complete historical UAV processing chain.

## Contents

- [1. Scope and reproducibility boundary](#1-scope-and-reproducibility-boundary)
- [2. Quick start](#2-quick-start)
- [3. Using the method on your own data](#3-using-the-method-on-your-own-data)
- [4. Reproducing the MethodsX validation](#4-reproducing-the-methodsx-validation)
- [5. Validation gates and expected results](#5-validation-gates-and-expected-results)
- [6. Citation, licensing and limitations](#6-citation-licensing-and-limitations)

## 1. Scope and reproducibility boundary

The UAV validation branch starts from four frozen packaged inputs:

- a 40-feature design catalog;
- materialized 3D station-level `L/C/R` geometry;
- 12 calibrated local camera models;
- 480 binary feature-view visibility masks.

From these inputs, the package recomputes the validation gates, feature-view observability, station-level projection and validity, binding-level projected-width summaries, and projected-scale characterization.

The package does **not** rerun historical raw-RGB ingestion, support-surface reconstruction, UAV surface placement/materialization, visibility-mask generation/rasterization, or absolute georeferencing. The 396 observable and 84 not-observable feature-view bindings are reproduced from the frozen masks; the historical rasterization, coverage and occlusion parameters used to generate those masks are not reconstructed from raw imagery.

Feature-view observability and station-level projection validity are intentionally separate. For the UAV configuration:

```text
foreground_pixels > 0  -> observable
foreground_pixels == 0 -> not_observable
```

Station validity is evaluated inside observable bindings. A station is primary-valid only when the projected `L/C/R` points have positive camera depth and fall inside the operational image domain:

```text
0 <= u < 6144
0 <= v < 4096
```

Historical UAV acquisition filenames are not distributed. Public camera labels are `View_01` through `View_12`. Raw RGB photographs, EXIF records, GPS coordinates, latitude/longitude, EPSG site coordinates and absolute site geolocation are not included.

For the method interface and reproduction boundary, see [`METHOD_CONTRACT.md`](METHOD_CONTRACT.md), [`data/method_contract.json`](data/method_contract.json) and [`REPRODUCIBILITY_SCOPE.md`](REPRODUCIBILITY_SCOPE.md).

## 2. Quick start

Python 3.8 or newer is recommended. Dependencies are listed in:

```text
environment/requirements.txt
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r environment/requirements.txt
python run_all.py
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r environment\requirements.txt
python run_all.py
```

A successful run ends with:

```text
VALIDATION GATES
identity preservation  = PASS
geometric consistency  = PASS
lineage completeness   = PASS
reference consistency  = PASS
view coverage          = PASS

VERDICT = PASS_METHODSX_LOCAL_REPRODUCTION
```

Generated outputs are written to `results/`. That directory is intentionally excluded from the distributed release because frozen expected outputs are already provided under `data/uav_validation/expected/`.

## 3. Using the method on your own data

The reusable entry point is the independent neutral reference implementation:

```text
src/reproduce_neutral_example.py
```

Run it from the repository root:

```bash
python src/reproduce_neutral_example.py
```

The neutral example is not a numerical replica of the UAV validation case. It provides an independent implementation of the method on a neutral support configuration.

The machine-readable method contract is:

```text
data/method_contract.json
```

When adapting the method to another application, preserve these distinctions:

- a **feature ID** remains persistent across the workflow;
- the **prescribed width** is a design-level parameter;
- the **materialized width** is defined by station-level `L/R` geometry;
- the **projected width** is an image-space quantity associated with a feature-view binding;
- the **feature-view visibility provider** is application-specific and remains separate from station-level projection validity;
- the **constructed metric reference** is derived from materialized geometry and is not an independent external metrological reference.

Legacy identifiers retained inside the neutral implementation are mapped in [`TERMINOLOGY.md`](TERMINOLOGY.md).

## 4. Reproducing the MethodsX validation

Run:

```bash
python run_all.py
```

The verifier performs the five manuscript validation gates and also recomputes station-level camera projection and projected-scale summaries. The latter are reproduction checks or additional characterization; they are **not** additional validation gates.

The main public inputs are organized as:

```text
data/
├── method_contract.json
├── parameterization/
│   └── feature_design_40.csv
└── uav_validation/
    ├── cameras/
    │   └── cameras_12.json
    ├── expected/
    ├── geometry/
    │   └── geometry_lcr_4530.csv
    ├── reference/
    │   └── reference_consistency_40.csv
    └── visibility/
        ├── visibility_manifest_480.csv
        └── masks/
```

Other release components are:

```text
environment/                 dependency specification
provenance/                  release and historical provenance
src/                         neutral reference implementation
MANIFEST_SHA256.txt          release integrity hashes
PACKAGE_CONTENTS.csv         release file inventory and hashes
```

## 5. Validation gates and expected results

The five gates are internal validation of the packaged method execution. They do not constitute independent validation of the original surface reconstruction or of the historical UAV mask-generation procedure.

| Gate | What the public verifier checks | Interpretive boundary |
| --- | --- | --- |
| Identity preservation | Persistent feature IDs close across design, materialized geometry, reference, visibility and expected projection populations. | Identity integrity, not geometric accuracy. |
| Geometric consistency | Station-level materialized separation `||R-L||_2` agrees with prescribed width. | Internal materialization-consistency check; not an independent surface-accuracy test. |
| Lineage completeness | Each feature closes from design through materialized geometry, reference population, 12 feature-view bindings and observable projected outputs. | Audits lineage completeness, not physical visibility truth. |
| Reference consistency | The feature-level constructed metric reference derived from materialized station widths agrees with prescribed width and the frozen expected reference table. | Derived from the same materialized geometry; not an external metrological reference. |
| View coverage | All 480 frozen feature-view masks are reread and their observable/not-observable states are reproduced. | Reproduces frozen provider outputs; does not regenerate the historical masks. |

Expected public-validation populations are:

| Quantity | Expected value |
| --- | ---: |
| Controlled geometric features | 40 |
| Materialized stations | 4,530 |
| `L/C/R` point records | 13,590 |
| Camera views | 12 |
| Feature-view bindings | 480 |
| Observable bindings | 396 |
| Not-observable bindings | 84 |
| Projected station rows | 45,024 |
| Primary-valid projected stations | 44,946 |

Projected measurand scale is reported separately as additional characterization. It is not a sixth validation gate.

## 6. Citation, licensing and limitations

### Citation

When using this package, cite the associated MethodsX article and the archived repository DOI once available. Repository citation metadata should be kept consistent with the final article metadata.

### Licensing

The package uses a dual-license structure:

- source code: MIT License, copyright holder `Alex Salazar et al.`;
- data, documentation and non-code scientific artifacts: CC BY 4.0, rights holder `SENAI Institute of Innovation in Embedded Systems, Florianópolis, Brazil`.

See [`LICENSE.md`](LICENSE.md), [`LICENSE-CODE.txt`](LICENSE-CODE.txt) and [`LICENSE-DATA.md`](LICENSE-DATA.md).

### Limitations

- The UAV branch reproduces validation from frozen materialized geometry, calibrated cameras and feature-view visibility masks; it does not regenerate the complete historical UAV processing chain.
- The 396/84 observability population is exactly reproducible from the packaged masks, but the historical rasterization, coverage and occlusion parameters used to generate those masks are not fully frozen.
- Surface placement and materialization on a discrete support representation may alter local design-level morphology. The validation gates do not assess preservation of prescribed family morphology, curvature or centerline shape after materialization.
- Geometric consistency and reference consistency assess the same construction at station and feature-aggregation levels, respectively; they are not independent external geometric or metrological validation.
- At small projected scales, mask-based observability should not be interpreted as physical image-space resolvability.

See [`LIMITATIONS.md`](LIMITATIONS.md) for the complete limitation statement.
