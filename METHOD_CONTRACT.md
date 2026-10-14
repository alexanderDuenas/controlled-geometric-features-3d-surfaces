
# MethodsX method contract

Contract ID: `methodsx_controlled_geometric_features_contract_v1`

The machine-readable contract is stored in:

```text
data/method_contract.json
```

## Observability interface

The public implementation separates **station projection validity** from **feature-view observability**.

A visibility provider supplies one observability status and associated evidence for each feature-view binding.

### UAV provider

The UAV validation uses released binary masks and the rule:

```text
foreground_pixels > 0  -> observable
foreground_pixels == 0 -> not_observable
```

The public package reproduces those frozen mask outputs. It does not regenerate the historical rasterization, coverage or occlusion process that created the masks.

### Neutral provider

The neutral reference example uses geometric station support. A binding is observable when it contains at least one primary-valid projected station.

The UAV and neutral providers instantiate the same observability interface but are intentionally **not** claimed to be equivalent visibility procedures.

## Station projection validity

For UAV station projection, `L`, `C` and `R` must all satisfy:

- positive camera depth;
- finite projected coordinates;
- projection inside the calibrated operational image domain.

The operational image domain is:

```text
0 <= u < width
0 <= v < height
```

with the public UAV cameras using `width = 6144` and `height = 4096`.

A finite-positive projected-width check is retained as an implementation guard. In the released UAV population it excludes zero rows; the 78 invalid projected station rows are rejected by image-domain bounds.

## Public interpretation boundary

The contract defines how provider output and station validity are consumed by the public method implementation. It does not specify enough information to regenerate the historical UAV visibility masks from raw imagery.
