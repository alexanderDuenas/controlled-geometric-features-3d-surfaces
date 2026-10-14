
# Limitations

## UAV observability provider

The method defines an observability-provider interface rather than one universal visibility algorithm. The UAV validation uses released binary raster masks.

The package reproduces the 396 observable and 84 not-observable bindings from those frozen masks, but it does not regenerate the historical rasterization, coverage and occlusion process. Historical provider parameters required to reproduce mask generation from raw imagery are not fully frozen in the public package.

## Subpixel observability

The 2 mm feature group has a median projected scale of approximately 0.303 px. At subpixel scales, mask-based observability can depend on rasterization and coverage conventions and must not be interpreted as physical feature resolvability.

## Materialized morphology

Feature family, length, curvature and orientation parameterize the design-level centerline. Surface placement and materialization define the operational 3D geometry used downstream.

Because these operations act on a discrete support representation, they may alter local design-level morphology. The present validation gates do not assess preservation of prescribed family morphology, curvature or centerline shape after materialization.

## Internal consistency versus independent validation

Geometric consistency checks station-level materialized boundary separation against prescribed width. Reference consistency aggregates those materialized widths to construct the feature-level metric reference.

These gates evaluate the same construction at different levels of aggregation. They should not be interpreted as independent validation of the original support surface or as an external metrological reference.

## Neutral observability provider

The neutral example uses a geometric station-support provider rather than the UAV raster-mask provider. It demonstrates the common provider interface and the remaining workflow, not equivalence of the two visibility procedures.

## Neutral sampling coverage

All neutral features use the 101-station minimum. The neutral example therefore does not exercise a case in which the 120 points/m rule produces more than 101 stations.

## Frozen-input scope

The public package reproduces reported validation from released frozen inputs. It does not rebuild the complete historical UAV workflow from raw photographs, regenerate the historical support surface, rerun UAV surface placement/materialization, or regenerate the original visibility masks.
