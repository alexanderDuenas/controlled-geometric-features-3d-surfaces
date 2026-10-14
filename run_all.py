#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


def fail(msg):
    raise RuntimeError(msg)


def qvec_to_R(q):
    qw, qx, qy, qz = [float(v) for v in q]
    return np.array([
        [1-2*qy*qy-2*qz*qz, 2*qx*qy-2*qz*qw, 2*qx*qz+2*qy*qw],
        [2*qx*qy+2*qz*qw, 1-2*qx*qx-2*qz*qz, 2*qy*qz-2*qx*qw],
        [2*qx*qz-2*qy*qw, 2*qy*qz+2*qx*qw, 1-2*qx*qx-2*qy*qy],
    ], dtype=np.float64)


def project(X, K, qvec, tvec):
    R = qvec_to_R(qvec)
    t = np.asarray(tvec, dtype=np.float64)
    Xc = R @ np.asarray(X, dtype=np.float64) + t
    z = float(Xc[2])
    if not math.isfinite(z) or z <= 1e-9:
        return None
    uvw = K @ Xc
    if abs(float(uvw[2])) <= 1e-12:
        return None
    uv = uvw[:2] / uvw[2]
    if not np.all(np.isfinite(uv)):
        return None
    return uv, z


def inside(uv, width, height):
    return 0 <= float(uv[0]) < float(width) and 0 <= float(uv[1]) < float(height)


def read_bool(v):
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    return str(v).strip().lower() in {"true", "1", "yes"}


def norm_index(v):
    try:
        f = float(v)
        if f.is_integer():
            return str(int(f))
    except Exception:
        pass
    return str(v).strip()


print("=" * 78)
print("METHODSX LOCAL REPRODUCTION")
print("=" * 78)

# A. Observability from masks
vis_dir = DATA / "uav_validation" / "visibility"
manifest = pd.read_csv(vis_dir / "visibility_manifest_480.csv")
vis_rows = []
for _, r in manifest.iterrows():
    p = vis_dir / r["mask_file"]
    with Image.open(p) as im:
        arr = np.asarray(im)
    if arr.ndim == 2:
        n = int(np.count_nonzero(arr))
    else:
        n = int(np.count_nonzero(np.any(arr != 0, axis=2)))
    status = "observable" if n > 0 else "not_observable"
    vis_rows.append({
        "feature_id": str(r["feature_id"]),
        "image_name": str(r["image_name"]),
        "foreground_pixels": n,
        "observability_status": status,
        "manifest_match": n == int(r["foreground_pixels"]) and status == r["observability_status"],
    })
vis = pd.DataFrame(vis_rows)
obs_n = int((vis["observability_status"] == "observable").sum())
non_n = int((vis["observability_status"] == "not_observable").sum())
vis_mismatch = int((~vis["manifest_match"]).sum())
print("\n[GATE 5] View coverage")
print("bindings       =", len(vis))
print("observable     =", obs_n)
print("not observable =", non_n)
print("mismatches     =", vis_mismatch)
if len(vis) != 480 or obs_n != 396 or non_n != 84 or vis_mismatch != 0:
    fail("Visibility reproduction failed")
observable_keys = set(map(tuple, vis.loc[vis["observability_status"] == "observable", ["feature_id", "image_name"]].itertuples(index=False, name=None)))

# B. Structural geometry input
geom = pd.read_csv(DATA / "uav_validation" / "geometry" / "geometry_lcr_4530.csv")
if len(geom) != 4530 or geom["feature_id"].nunique() != 40:
    fail("Structural geometry population mismatch")
print("\n[B] Structural geometry")
print("features =", geom["feature_id"].nunique())
print("stations =", len(geom))
print("L/C/R point records =", len(geom) * 3)

# C. Frozen reference table
ref = pd.read_csv(DATA / "uav_validation" / "reference" / "reference_consistency_40.csv")
delta = pd.to_numeric(ref["delta_mm"], errors="raise")
if len(ref) != 40:
    fail("Reference population is not 40")
print("\n[C] Frozen reference table")
print("features =", len(ref))
print("median delta mm =", delta.median())
print("max abs delta mm =", delta.abs().max())

# D. Projection over the 396 mask-observable bindings
camera_obj = json.loads((DATA / "uav_validation" / "cameras" / "cameras_12.json").read_text())
cams = camera_obj["cameras"]
if len(cams) != 12:
    fail("Expected 12 cameras")

geometry = {}
for fid, d in geom.groupby("feature_id", sort=True):
    rows = []
    for _, r in d.iterrows():
        rows.append({
            "station_index": r["station_index"],
            "center": np.array([r["center_x_m"], r["center_y_m"], r["center_z_m"]], dtype=np.float64),
            "left": np.array([r["left_x_m"], r["left_y_m"], r["left_z_m"]], dtype=np.float64),
            "right": np.array([r["right_x_m"], r["right_y_m"], r["right_z_m"]], dtype=np.float64),
        })
    rows.sort(key=lambda z: (0, float(z["station_index"])) if norm_index(z["station_index"]).replace(".", "", 1).isdigit() else (1, norm_index(z["station_index"])))
    geometry[str(fid)] = rows

station_rows = []
pair_rows = []
for feature_id, image_name in sorted(observable_keys):
    if feature_id not in geometry:
        fail(f"Missing geometry: {feature_id}")
    if image_name not in cams:
        fail(f"Missing camera: {image_name}")
    c = cams[image_name]
    K = np.asarray(c["K"], dtype=np.float64)
    qvec = c["qvec"]
    tvec = c["tvec"]
    width = int(c["width"])
    height = int(c["height"])
    widths = []
    front_n = 0
    valid_n = 0
    for st in geometry[feature_id]:
        pc = project(st["center"], K, qvec, tvec)
        pl = project(st["left"], K, qvec, tvec)
        pr = project(st["right"], K, qvec, tvec)
        all_front = pc is not None and pl is not None and pr is not None
        center_in = left_in = right_in = False
        valid = False
        width_px = np.nan
        vals = {
            "center_u_px": np.nan, "center_v_px": np.nan,
            "left_u_px": np.nan, "left_v_px": np.nan,
            "right_u_px": np.nan, "right_v_px": np.nan,
            "center_depth_camera": np.nan,
            "left_depth_camera": np.nan,
            "right_depth_camera": np.nan,
        }
        if all_front:
            front_n += 1
            (uvc, zc), (uvl, zl), (uvr, zr) = pc, pl, pr
            center_in = inside(uvc, width, height)
            left_in = inside(uvl, width, height)
            right_in = inside(uvr, width, height)
            wpx = float(np.linalg.norm(uvr - uvl))
            if math.isfinite(wpx) and wpx > 0:
                width_px = wpx
            valid = math.isfinite(width_px) and center_in and left_in and right_in
            if valid:
                valid_n += 1
                widths.append(width_px)
            vals.update({
                "center_u_px": float(uvc[0]), "center_v_px": float(uvc[1]),
                "left_u_px": float(uvl[0]), "left_v_px": float(uvl[1]),
                "right_u_px": float(uvr[0]), "right_v_px": float(uvr[1]),
                "center_depth_camera": float(zc),
                "left_depth_camera": float(zl),
                "right_depth_camera": float(zr),
            })
        station_rows.append({
            "feature_id": feature_id,
            "image_name": image_name,
            "image_id_colmap": int(c["image_id_colmap"]),
            "camera_id": int(c["camera_id"]),
            "station_index": st["station_index"],
            "all_three_in_front": bool(all_front),
            "center_inside_image": bool(center_in),
            "left_inside_image": bool(left_in),
            "right_inside_image": bool(right_in),
            "primary_station_valid": bool(valid),
            "projected_width_px": width_px,
            **vals,
        })
    if not widths:
        fail(f"Mask-observable binding has no valid projected stations: {feature_id}/{image_name}")
    arr = np.asarray(widths, dtype=float)
    pair_rows.append({
        "feature_id": feature_id,
        "image_name": image_name,
        "image_id_colmap": int(c["image_id_colmap"]),
        "camera_id": int(c["camera_id"]),
        "station_total_n": len(geometry[feature_id]),
        "station_all_three_front_n": front_n,
        "station_primary_valid_n": valid_n,
        "station_primary_valid_fraction": valid_n / len(geometry[feature_id]),
        "projected_width_px_median": float(np.median(arr)),
        "projected_width_px_p10": float(np.percentile(arr, 10)),
        "projected_width_px_p90": float(np.percentile(arr, 90)),
        "projected_width_px_min": float(arr.min()),
        "projected_width_px_max": float(arr.max()),
    })

station_calc = pd.DataFrame(station_rows)
pair_calc = pd.DataFrame(pair_rows)
if len(pair_calc) != 396:
    fail(f"Expected 396 projected bindings, got {len(pair_calc)}")

# E. Station comparison
station_exp = pd.read_csv(DATA / "uav_validation" / "expected" / "projected_station_level_396.csv")
for d in (station_calc, station_exp):
    d["feature_id"] = d["feature_id"].astype(str)
    d["image_name"] = d["image_name"].astype(str)
    d["station_index"] = d["station_index"].map(norm_index)
sk = ["feature_id", "image_name", "station_index"]
sm = station_calc.merge(station_exp, on=sk, how="outer", suffixes=("_calc", "_exp"), indicator=True)
if (sm["_merge"] != "both").any():
    fail(f"Station key mismatch: {sm['_merge'].value_counts().to_dict()}")
bool_cols = ["all_three_in_front", "center_inside_image", "left_inside_image", "right_inside_image", "primary_station_valid"]
num_cols = [
    "projected_width_px", "center_u_px", "center_v_px", "left_u_px", "left_v_px",
    "right_u_px", "right_v_px", "center_depth_camera", "left_depth_camera", "right_depth_camera",
]
bool_bad = 0
for c in bool_cols:
    a = sm[f"{c}_calc"].map(read_bool)
    b = sm[f"{c}_exp"].map(read_bool)
    bool_bad += int((a != b).sum())
num_bad = 0
max_diff = {}
for c in num_cols:
    a = pd.to_numeric(sm[f"{c}_calc"], errors="coerce")
    b = pd.to_numeric(sm[f"{c}_exp"], errors="coerce")
    both_nan = a.isna() & b.isna()
    one_nan = a.isna() ^ b.isna()
    valid = ~(both_nan | one_nan)
    diff = (a - b).abs()
    max_diff[c] = float(diff[valid].max()) if valid.any() else 0.0
    bad = one_nan | (valid & ~np.isclose(a, b, rtol=1e-11, atol=1e-9))
    num_bad += int(bad.sum())
print("\n[D] Station-level reprojection")
print("station rows =", len(station_calc))
print("boolean mismatches =", bool_bad)
print("numeric mismatches =", num_bad)
print("max numeric differences =", max_diff)
if bool_bad or num_bad:
    fail("Station-level local reprojection does not match expected output")

# F. Pair comparison
pair_exp = pd.read_csv(DATA / "uav_validation" / "expected" / "projected_binding_level_396.csv")
pk = ["feature_id", "image_name"]
pm = pair_calc.merge(pair_exp, on=pk, how="outer", suffixes=("_calc", "_exp"), indicator=True)
if (pm["_merge"] != "both").any():
    fail(f"Pair key mismatch: {pm['_merge'].value_counts().to_dict()}")
pair_cols = [
    "station_total_n", "station_all_three_front_n", "station_primary_valid_n",
    "station_primary_valid_fraction", "projected_width_px_median", "projected_width_px_p10",
    "projected_width_px_p90", "projected_width_px_min", "projected_width_px_max",
]
pair_bad = 0
pair_max = {}
for c in pair_cols:
    a = pd.to_numeric(pm[f"{c}_calc"], errors="coerce")
    b = pd.to_numeric(pm[f"{c}_exp"], errors="coerce")
    diff = (a - b).abs()
    pair_max[c] = float(diff.max())
    pair_bad += int((~np.isclose(a, b, rtol=1e-11, atol=1e-9)).sum())
if pair_bad:
    fail(f"Pair-level mismatch count={pair_bad}; max={pair_max}")

# G. Projected scale summaries — additional characterization
x = pair_calc["projected_width_px_median"]
print("\n[E] Projected measurand scale")
print("bindings =", len(x))
print("median px =", x.median())
print("p10 px =", x.quantile(0.10))
print("p90 px =", x.quantile(0.90))
print("min px =", x.min())
print("max px =", x.max())

design = pd.read_csv(DATA / "parameterization" / "feature_design_40.csv")
feature_scale = (
    pair_calc.groupby("feature_id", as_index=False)["projected_width_px_median"]
    .median()
    .rename(columns={"projected_width_px_median": "feature_projected_scale_median_px"})
    .merge(design[["feature_id", "prescribed_width_mm"]], on="feature_id", how="left")
)
width_scale = (
    feature_scale.groupby("prescribed_width_mm", as_index=False)
    .agg(feature_n=("feature_id", "nunique"), projected_scale_median_px=("feature_projected_scale_median_px", "median"))
    .sort_values("prescribed_width_mm")
)
print("\nProjected scale by prescribed width:")
print(width_scale.to_string(index=False))


# H. Explicit manuscript validation gates beyond view coverage
#
# View coverage was already recomputed from masks in section A.
# Here we explicitly recompute geometric consistency, reference consistency
# and lineage completeness. Identity closure follows immediately afterward.

# Gate 2 — geometric consistency: materialized station width == prescribed width
L_xyz = geom[
    ["left_x_m", "left_y_m", "left_z_m"]
].to_numpy(dtype=float)

R_xyz = geom[
    ["right_x_m", "right_y_m", "right_z_m"]
].to_numpy(dtype=float)

geom_gate = geom[
    ["feature_id", "station_index"]
].copy()

geom_gate["materialized_width_mm"] = (
    np.linalg.norm(
        R_xyz - L_xyz,
        axis=1,
    )
    * 1000.0
)

geom_gate = geom_gate.merge(
    design[
        ["feature_id", "prescribed_width_mm"]
    ],
    on="feature_id",
    how="left",
    validate="many_to_one",
)

geom_gate["delta_mm"] = (
    geom_gate["materialized_width_mm"]
    - geom_gate["prescribed_width_mm"]
)

geometry_max_abs_delta_mm = float(
    geom_gate["delta_mm"]
    .abs()
    .max()
)

if geometry_max_abs_delta_mm > 1e-6:
    fail(
        "Geometric consistency failed: max abs delta = "
        f"{geometry_max_abs_delta_mm} mm"
    )

print("\n[GATE 2] Geometric consistency")
print(
    "max abs station width delta mm =",
    geometry_max_abs_delta_mm,
)
print("status = PASS")


# Gate 4 — recompute constructed metric reference from materialized geometry
ref_calc = (
    geom_gate.groupby(
        "feature_id",
        as_index=False,
    )["materialized_width_mm"]
    .median()
    .rename(
        columns={
            "materialized_width_mm":
            "constructed_metric_reference_mm"
        }
    )
    .merge(
        design[
            ["feature_id", "prescribed_width_mm"]
        ],
        on="feature_id",
        how="left",
        validate="one_to_one",
    )
)

ref_calc["delta_mm"] = (
    ref_calc["constructed_metric_reference_mm"]
    - ref_calc["prescribed_width_mm"]
)

ref_calc["abs_delta_mm"] = (
    ref_calc["delta_mm"]
    .abs()
)

ref_cmp = ref_calc.merge(
    ref,
    on="feature_id",
    how="outer",
    suffixes=("_calc", "_exp"),
    indicator=True,
)

if (ref_cmp["_merge"] != "both").any():
    fail(
        "Reference consistency feature-key mismatch."
    )

for col in [
    "prescribed_width_mm",
    "constructed_metric_reference_mm",
    "delta_mm",
    "abs_delta_mm",
]:
    a = pd.to_numeric(
        ref_cmp[f"{col}_calc"],
        errors="raise",
    )

    b = pd.to_numeric(
        ref_cmp[f"{col}_exp"],
        errors="raise",
    )

    if not np.allclose(
        a,
        b,
        rtol=1e-11,
        atol=1e-6,
    ):
        fail(
            "Reference consistency mismatch in "
            f"{col}"
        )

if float(
    ref_calc["abs_delta_mm"].max()
) > 1e-6:
    fail(
        "Reference consistency failed against prescribed width."
    )

ref_calc.to_csv(
    RESULTS
    / "reference_consistency_recomputed_40.csv",
    index=False,
)

print("\n[GATE 4] Reference consistency")
print(
    "max abs reference delta mm =",
    float(
        ref_calc["abs_delta_mm"]
        .max()
    ),
)
print("status = PASS")


# Gate 3 — feature-level lineage closure
lineage_rows = []

for fid in sorted(
    set(
        design["feature_id"]
        .astype(str)
    )
):
    design_n = int(
        (
            design["feature_id"]
            .astype(str)
            == fid
        ).sum()
    )

    station_n = int(
        (
            geom["feature_id"]
            .astype(str)
            == fid
        ).sum()
    )

    reference_n = int(
        (
            ref["feature_id"]
            .astype(str)
            == fid
        ).sum()
    )

    binding_n = int(
        (
            manifest["feature_id"]
            .astype(str)
            == fid
        ).sum()
    )

    observable_n = int(
        (
            (
                vis["feature_id"]
                .astype(str)
                == fid
            )
            &
            (
                vis["observability_status"]
                == "observable"
            )
        ).sum()
    )

    expected_binding_n = int(
        (
            pair_exp["feature_id"]
            .astype(str)
            == fid
        ).sum()
    )

    expected_station_n = int(
        (
            station_exp["feature_id"]
            .astype(str)
            == fid
        ).sum()
    )

    complete = (
        design_n == 1
        and
        station_n > 0
        and
        reference_n == 1
        and
        binding_n == 12
        and
        expected_binding_n
        == observable_n
        and
        expected_station_n > 0
    )

    lineage_rows.append(
        {
            "feature_id": fid,
            "design_row_n": design_n,
            "materialized_station_n": station_n,
            "reference_row_n": reference_n,
            "feature_view_binding_n": binding_n,
            "observable_binding_n": observable_n,
            "expected_projected_binding_n":
            expected_binding_n,
            "expected_projected_station_row_n":
            expected_station_n,
            "lineage_complete": bool(
                complete
            ),
        }
    )

lineage = pd.DataFrame(
    lineage_rows
)

if not bool(
    lineage["lineage_complete"]
    .all()
):
    fail(
        "Lineage completeness failed."
    )

lineage.to_csv(
    RESULTS
    / "lineage_closure_40.csv",
    index=False,
)

print("\n[GATE 3] Lineage completeness")
print(
    "complete lineages =",
    int(
        lineage["lineage_complete"]
        .sum()
    ),
    "/",
    len(lineage),
)
print("status = PASS")


# H. Persistent identity closure
ids_design = set(design["feature_id"].astype(str))
ids_geom = set(geom["feature_id"].astype(str))
ids_ref = set(ref["feature_id"].astype(str))
ids_vis = set(vis["feature_id"].astype(str))
ids_station_exp = set(station_exp["feature_id"].astype(str))
ids_pair_exp = set(pair_exp["feature_id"].astype(str))

if not (
    len(ids_design) == 40
    and
    ids_design
    == ids_geom
    == ids_ref
    == ids_vis
    == ids_station_exp
    == ids_pair_exp
):
    fail(
        "Persistent feature identity sets do not match"
    )

print("\n[GATE 1] Identity preservation")
print("persistent feature IDs =", len(ids_design))
print("status = PASS")

station_calc.to_csv(RESULTS / "projected_station_level_recomputed.csv", index=False)
pair_calc.to_csv(RESULTS / "projected_binding_level_recomputed.csv", index=False)
width_scale.to_csv(RESULTS / "projected_scale_by_width_recomputed.csv", index=False)
vis.to_csv(RESULTS / "visibility_recomputed.csv", index=False)

print("\n" + "=" * 78)
print("VALIDATION GATES")
print("=" * 78)
print("identity preservation  = PASS")
print("geometric consistency  = PASS")
print("lineage completeness   = PASS")
print("reference consistency  = PASS")
print("view coverage          = PASS")

print("\nADDITIONAL REPRODUCTION/CHARACTERIZATION")
print("station reprojection             = PASS")
print("binding projected scale summary  = PASS")

print("\n" + "=" * 78)
print("FINAL VERDICT")
print("=" * 78)
print()
print("VERDICT = PASS_METHODSX_LOCAL_REPRODUCTION")
