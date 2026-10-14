# Limitations

## UAV observability provider

The UAV validation uses released binary raster masks as the feature-view observability evidence. The public package reproduces the 396 observable and 84 not-observable bindings from these frozen masks, while the historical rasterization, coverage, and occlusion settings remain part of the upstream processing chain.

## Subpixel observability

The 2 mm feature group has a median projected scale of approximately 0.303 px. At this scale, mask-based observability depends partly on rasterization and coverage conventions, so it should be interpreted as provider-level observability rather than direct evidence of physical image-space resolvability.

## Materialized morphology

Feature family, length, curvature, and orientation describe the design-level centerline, while surface placement and materialization define the operational 3D geometry used downstream. Because these operations act on a discrete support representation, local morphology may differ from the original design-level centerline. Preservation of prescribed family morphology, curvature, and centerline shape lies outside the present validation gates.

## Internal consistency and reference construction

Geometric consistency evaluates station-level materialized boundary separation against prescribed width, while reference consistency evaluates the corresponding feature-level constructed metric reference. These gates therefore provide internal consistency evidence at two aggregation levels rather than independent external geometric or metrological validation.

## Neutral observability provider

The neutral example uses geometric station support as its observability provider, whereas the UAV branch uses frozen raster masks. Both instantiate the same provider interface and support the downstream workflow, while representing different application-specific visibility procedures.

## Neutral sampling coverage

All neutral features use the 101-station minimum. The released neutral example therefore represents the minimum-station configuration of the sampling rule; cases in which the 120 points/m criterion produces denser sampling remain outside this example.

## Public reproduction boundary

The public workflow begins from the released design catalog, materialized geometry, calibrated cameras, and feature-view visibility masks. Historical raw-image processing, support-surface reconstruction, UAV placement/materialization, and visibility-mask generation belong to the upstream processing chain.
