#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone neutral reference implementation for the MethodsX method.

Builds from zero:
mildly nonplanar triangulated height field -> 40 controlled geometric features -> placement -> parametric
centerlines -> nearest surface vertex binding -> duplicate collapse + densify ->
explicit L/C/R geometry -> persistent identity -> 12 synthetic pinhole cameras ->
projection/visibility -> projected measurand scale -> constructed metric reference ->
validation gates + hashes.

Scientific boundary: this is a PUBLIC NEUTRAL reference implementation of the
method, not a numerical replica of the UAV validation case. Internal legacy
identifiers are documented in TERMINOLOGY.md.
"""
from __future__ import annotations
import os
import csv, hashlib, json, math, shutil, sys, traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT = Path(os.environ.get("METHODSX_NEUTRAL_ROOT", str(Path(__file__).resolve().parents[1] / "results" / "neutral_work")))
OUT = ROOT / 'stage_METHODSX_PUBLIC_NEUTRAL_EXAMPLE_v3'

FAMILIES = ['straight','arc','sinusoidal','zigzag']
WIDTHS_MM = [2.0,5.0,10.0,20.0,50.0]
REPLICATES = [1,2]
SURFACE_W, SURFACE_H = 1.60, 1.00
SURFACE_NX, SURFACE_NY = 241, 151
# Deterministic mild non-planarity. Peak-to-peak relief is intentionally small
# relative to the 1.60 m x 1.00 m support surface.
SURFACE_WAVE_A1_M = 0.0060
SURFACE_WAVE_A2_M = 0.0020
SURFACE_WAVE_PHASE_RAD = 0.35
PROBE_LENGTH_M = 0.18
SAMPLE_DENSITY_PER_M = 120.0
MIN_SAMPLE_N = 101
ARC_SAG_RATIO = 0.20
SIN_AMP_RATIO, SIN_CYCLES = 0.10, 1.25
ZIG_AMP_RATIO, ZIG_CYCLES = 0.10, 2.0
IMAGE_W, IMAGE_H = 1600, 1200
FX = FY = 1450.0
CX, CY = IMAGE_W/2.0, IMAGE_H/2.0
CAMERA_N = 12
EPS = 1e-12


def p(*a): print(*a, flush=True)
def now(): return datetime.now(timezone.utc).isoformat()
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024), b''): h.update(b)
    return h.hexdigest()
def write_json(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
def write_csv(path,rows):
    fields=[]; seen=set()
    for r in rows:
        for k in r:
            if k not in seen: seen.add(k); fields.append(k)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def med(vals):
    a=np.asarray(list(vals),dtype=float)
    return float(np.median(a)) if a.size else float('nan')
def quant(vals,q):
    a=np.asarray(list(vals),dtype=float)
    return float(np.quantile(a,q,interpolation="linear")) if a.size else float('nan')


def odd_n(length):
    n=max(MIN_SAMPLE_N,int(math.ceil(length*SAMPLE_DENSITY_PER_M)))
    return n if n%2 else n+1


def surface_z(x,y):
    """
    Deterministic, smooth and mildly nonplanar height field.

    The relief is intentionally small: a few millimetres over a metre-scale
    support. This satisfies the MethodsX neutral-example requirement without
    introducing scene-specific structure.
    """
    return (
        SURFACE_WAVE_A1_M
        * np.sin(2.0*math.pi*x/SURFACE_W)
        * np.cos(2.0*math.pi*y/SURFACE_H)
        +
        SURFACE_WAVE_A2_M
        * np.sin(4.0*math.pi*x/SURFACE_W + SURFACE_WAVE_PHASE_RAD)
        * np.sin(2.0*math.pi*y/SURFACE_H)
    )


def surface_gradient(x,y):
    """Analytic dz/dx and dz/dy for the neutral height field."""
    dzdx = (
        SURFACE_WAVE_A1_M
        * (2.0*math.pi/SURFACE_W)
        * np.cos(2.0*math.pi*x/SURFACE_W)
        * np.cos(2.0*math.pi*y/SURFACE_H)
        +
        SURFACE_WAVE_A2_M
        * (4.0*math.pi/SURFACE_W)
        * np.cos(4.0*math.pi*x/SURFACE_W + SURFACE_WAVE_PHASE_RAD)
        * np.sin(2.0*math.pi*y/SURFACE_H)
    )
    dzdy = (
        -SURFACE_WAVE_A1_M
        * (2.0*math.pi/SURFACE_H)
        * np.sin(2.0*math.pi*x/SURFACE_W)
        * np.sin(2.0*math.pi*y/SURFACE_H)
        +
        SURFACE_WAVE_A2_M
        * (2.0*math.pi/SURFACE_H)
        * np.sin(4.0*math.pi*x/SURFACE_W + SURFACE_WAVE_PHASE_RAD)
        * np.cos(2.0*math.pi*y/SURFACE_H)
    )
    return float(dzdx), float(dzdy)


def surface_normal(x,y):
    dzdx,dzdy=surface_gradient(x,y)
    n=np.array([-dzdx,-dzdy,1.0],dtype=float)
    return n/np.linalg.norm(n)


def build_surface():
    xs=np.linspace(-SURFACE_W/2,SURFACE_W/2,SURFACE_NX)
    ys=np.linspace(-SURFACE_H/2,SURFACE_H/2,SURFACE_NY)
    vertices=np.array([[x,y,float(surface_z(x,y))] for y in ys for x in xs],dtype=float)
    faces=[]
    vid=lambda ix,iy: iy*SURFACE_NX+ix
    for iy in range(SURFACE_NY-1):
        for ix in range(SURFACE_NX-1):
            a,b,c,d=vid(ix,iy),vid(ix+1,iy),vid(ix,iy+1),vid(ix+1,iy+1)
            faces += [(a,b,c),(b,d,c)]
    return xs,ys,vertices,faces


def nearest_vertex(point,xs,ys):
    x,y,_=point
    ix=int(np.clip(np.rint((x+SURFACE_W/2)/SURFACE_W*(SURFACE_NX-1)),0,SURFACE_NX-1))
    iy=int(np.clip(np.rint((y+SURFACE_H/2)/SURFACE_H*(SURFACE_NY-1)),0,SURFACE_NY-1))
    xx=float(xs[ix]); yy=float(ys[iy]); zz=float(surface_z(xx,yy))
    return iy*SURFACE_NX+ix, np.array([xx,yy,zz],dtype=float)


def design():
    xs=np.linspace(-0.64,0.64,8); ys=np.linspace(-0.34,0.34,5)
    centers=[(iy,ix,float(x),float(y)) for iy,y in enumerate(ys) for ix,x in enumerate(xs)]
    combos=[(f,w,r) for f in FAMILIES for w in WIDTHS_MM for r in REPLICATES]
    orient={'straight':0.0,'arc':25.0,'sinusoidal':-20.0,'zigzag':45.0}
    rows=[]
    for i,((fam,w,rep),(iy,ix,x,y)) in enumerate(zip(combos,centers),1):
        rows.append({'feature_id':f'P{i:03d}','family':fam,'prescribed_width_mm':w,'parameterization_level':rep,
                     'probe_length_m':PROBE_LENGTH_M,'sample_density_per_m':SAMPLE_DENSITY_PER_M,
                     'minimum_sample_n':MIN_SAMPLE_N,'orientation_deg':orient[fam]+12.0*(rep-1),
                     'placement_row_index':iy,'placement_col_index':ix,
                     'center_x_m':x,'center_y_m':y,'center_z_m':0.0})
    return rows


def tri_wave(x): return 2.0/math.pi*np.arcsin(np.sin(x))
def curve(fam,L,n):
    u=np.linspace(-L/2,L/2,n)
    if fam=='straight': v=np.zeros_like(u)
    elif fam=='arc':
        half=L/2; sag=ARC_SAG_RATIO*L; v=sag*(1-(u/half)**2)
    elif fam=='sinusoidal':
        v=SIN_AMP_RATIO*L*np.sin(2*math.pi*SIN_CYCLES*(u/L+0.5))
    elif fam=='zigzag':
        v=ZIG_AMP_RATIO*L*tri_wave(2*math.pi*ZIG_CYCLES*(u/L+0.5))
    else: raise ValueError(fam)
    return u,v


def parametric_centerlines(specs):
    rows=[]
    for s in specs:
        n=odd_n(s['probe_length_m']); u,v=curve(s['family'],s['probe_length_m'],n)
        th=math.radians(s['orientation_deg']); c,sn=math.cos(th),math.sin(th)
        xr,yr=c*u-sn*v, sn*u+c*v
        for j in range(n):
            rows.append({'feature_id':s['feature_id'],'family':s['family'],'prescribed_width_mm':s['prescribed_width_mm'],
                         'parameterization_level':s['parameterization_level'],'sample_index':j,'sample_n':n,
                         'local_u_m':float(u[j]),'local_v_m':float(v[j]),
                         'x_m':s['center_x_m']+float(xr[j]),'y_m':s['center_y_m']+float(yr[j]),'z_m':0.0})
    return rows


def surface_bind(rows,xs,ys):
    out=[]
    for r in rows:
        vid,xyz=nearest_vertex(np.array([r['x_m'],r['y_m'],r['z_m']],dtype=float),xs,ys)
        out.append({**r,'surface_vertex_id':int(vid),'surface_x_m':float(xyz[0]),'surface_y_m':float(xyz[1]),'surface_z_m':float(xyz[2])})
    return out


def collapse(xyz):
    keep=[0]
    for i in range(1,len(xyz)):
        if np.linalg.norm(xyz[i]-xyz[keep[-1]])>EPS: keep.append(i)
    return xyz[np.asarray(keep,dtype=int)]
def cumlen(xyz):
    if len(xyz)<2: return np.zeros(len(xyz))
    return np.r_[0.0,np.cumsum(np.linalg.norm(np.diff(xyz,axis=0),axis=1))]
def densify(xyz,n):
    """
    Deterministic vertex-preserving densification.

    Guarantees:
    - every unique source polyline vertex is retained;
    - both endpoints are retained exactly;
    - output contains exactly n points;
    - inserted points lie strictly inside original segments;
    - polyline path length is preserved to floating-point precision.

    This matches the intended MethodsX repair semantics better than uniform
    arc-length resampling, which can skip corners and shorten the chordal path.
    """
    xyz=np.asarray(xyz,dtype=float)
    m=len(xyz)
    if m<2: raise RuntimeError('degenerate centerline')
    if n<m: raise RuntimeError(f'target sample_n {n} smaller than unique vertex_n {m}')

    seg=np.linalg.norm(np.diff(xyz,axis=0),axis=1)
    if np.any(seg<=EPS):
        raise RuntimeError('densify received zero-length segment after duplicate collapse')

    if n==m:
        return xyz.copy()

    extra=n-m
    total=float(seg.sum())
    raw=extra*(seg/total)
    interior=np.floor(raw).astype(int)
    remainder=int(extra-int(interior.sum()))

    # Largest-remainder allocation; stable tie-break by segment index.
    frac=raw-interior
    order=sorted(range(len(seg)),key=lambda i:(-float(frac[i]),i))
    for i in order[:remainder]:
        interior[i]+=1

    points=[xyz[0].copy()]
    for i in range(m-1):
        k=int(interior[i])
        for j in range(1,k+1):
            a=j/(k+1.0)
            points.append((1.0-a)*xyz[i]+a*xyz[i+1])
        points.append(xyz[i+1].copy())

    out=np.asarray(points,dtype=float)
    if len(out)!=n:
        raise RuntimeError(f'vertex-preserving densify produced {len(out)} points, expected {n}')
    return out


def repair(rows):
    by=defaultdict(list)
    for r in rows: by[r['feature_id']].append(r)
    out=[]; summary=[]
    for pid in sorted(by):
        g=sorted(by[pid],key=lambda x:int(x['sample_index']))
        src=np.array([[r['surface_x_m'],r['surface_y_m'],r['surface_z_m']] for r in g],dtype=float)
        uq=collapse(src); rep=densify(uq,len(src)); base=g[0]
        for j,xyz in enumerate(rep):
            out.append({'feature_id':pid,'family':base['family'],'prescribed_width_mm':base['prescribed_width_mm'],
                        'parameterization_level':base['parameterization_level'],'sample_index':j,'sample_n':len(src),
                        'x_m':float(xyz[0]),'y_m':float(xyz[1]),'z_m':float(xyz[2])})
        summary.append({'feature_id':pid,'source_sample_n':len(src),'unique_vertex_n_after_collapse':len(uq),
                        'collapsed_duplicate_n':len(src)-len(uq),'source_unique_path_length_m':float(cumlen(uq)[-1]),
                        'repaired_path_length_m':float(cumlen(rep)[-1]),
                        'path_length_abs_delta_m':abs(float(cumlen(rep)[-1]-cumlen(uq)[-1])),
                        'endpoint_start_delta_m':float(np.linalg.norm(rep[0]-uq[0])),
                        'endpoint_end_delta_m':float(np.linalg.norm(rep[-1]-uq[-1]))})
    return out,summary


def norm_rows(v):
    n=np.linalg.norm(v,axis=1,keepdims=True); n[n<=EPS]=1.0; return v/n

def materialize(rows):
    """
    Materialize L/C/R using the local tangent frame of the nonplanar surface.

    The lateral direction is n x t, where n is the analytic local surface
    normal and t is the repaired 3D centerline tangent. L/R are tangent-plane
    offsets from C. We do not claim that L/R are themselves exact mesh vertices.
    """
    by=defaultdict(list)
    for r in rows: by[r['feature_id']].append(r)
    out=[]
    for pid in sorted(by):
        g=sorted(by[pid],key=lambda x:int(x['sample_index']))
        C=np.array([[r['x_m'],r['y_m'],r['z_m']] for r in g],dtype=float)
        T=np.empty_like(C)
        T[0]=C[1]-C[0]
        T[-1]=C[-1]-C[-2]
        T[1:-1]=C[2:]-C[:-2]
        T=norm_rows(T)

        N=np.array([surface_normal(float(x),float(y)) for x,y,_ in C],dtype=float)
        lat=norm_rows(np.cross(N,T))
        w=float(g[0]['prescribed_width_mm'])/1000.0
        L=C-0.5*w*lat
        R=C+0.5*w*lat

        for j in range(len(C)):
            common={
                'feature_id':pid,
                'family':g[0]['family'],
                'prescribed_width_mm':g[0]['prescribed_width_mm'],
                'parameterization_level':g[0]['parameterization_level'],
                'sample_index':j,
                'surface_normal_x':float(N[j,0]),
                'surface_normal_y':float(N[j,1]),
                'surface_normal_z':float(N[j,2]),
            }
            for role,xyz in [('left_border',L[j]),('centerline',C[j]),('right_border',R[j])]:
                out.append({**common,'point_type':role,'x_m':float(xyz[0]),'y_m':float(xyz[1]),'z_m':float(xyz[2])})
    return out


def normalize(v):
    n=float(np.linalg.norm(v))
    if n<=EPS: raise RuntimeError('zero vector')
    return v/n
def look_at(center,target=np.zeros(3)):
    f=normalize(target-center); up=np.array([0.,1.,0.])
    if abs(float(np.dot(f,up)))>.95: up=np.array([1.,0.,0.])
    right=normalize(np.cross(f,up)); up2=normalize(np.cross(right,f)); R=np.stack([right,up2,f]); t=-R@center
    return R,t

def cameras():
    rows=[]
    for i in range(CAMERA_N):
        a=2*math.pi*i/CAMERA_N; c=np.array([0.55*math.cos(a),0.32*math.sin(a),1.20+0.08*math.sin(2*a)])
        R,t=look_at(c)
        r={'view_id':f'V{i+1:02d}','image_name':f'synthetic_view_{i+1:02d}.png','width_px':IMAGE_W,'height_px':IMAGE_H,
           'fx_px':FX,'fy_px':FY,'cx_px':CX,'cy_px':CY,'camera_center_x_m':float(c[0]),'camera_center_y_m':float(c[1]),'camera_center_z_m':float(c[2])}
        for rr in range(3):
            for cc in range(3): r[f'r{rr}{cc}']=float(R[rr,cc])
        for k in range(3): r[f't{k}']=float(t[k])
        rows.append(r)
    return rows

def project(xyz,cam):
    R=np.array([[cam['r00'],cam['r01'],cam['r02']],[cam['r10'],cam['r11'],cam['r12']],[cam['r20'],cam['r21'],cam['r22']]],dtype=float)
    t=np.array([cam['t0'],cam['t1'],cam['t2']],dtype=float); x,y,z=R@xyz+t
    if z<=EPS: return False,False,float('nan'),float('nan'),float(z)
    u=cam['fx_px']*x/z+cam['cx_px']; v=cam['cy_px']-cam['fy_px']*y/z
    inside=0<=u<cam['width_px'] and 0<=v<cam['height_px']
    return True,bool(inside),float(u),float(v),float(z)


def triplets(geometry):
    d={}
    for r in geometry:
        key=(r['feature_id'],int(r['sample_index'])); d.setdefault(key,{'family':r['family'],'prescribed_width_mm':r['prescribed_width_mm'],'parameterization_level':r['parameterization_level']})
        xyz=np.array([r['x_m'],r['y_m'],r['z_m']],dtype=float)
        if r['point_type']=='left_border': d[key]['L']=xyz
        elif r['point_type']=='centerline': d[key]['C']=xyz
        elif r['point_type']=='right_border': d[key]['R']=xyz
    return d


def project_all(geometry,cams):
    tr=triplets(geometry); stations=[]
    for cam in cams:
        for (pid,sidx),data in sorted(tr.items()):
            P={role:project(data[role],cam) for role in ('L','C','R')}
            valid=all(P[x][0] for x in P) and all(P[x][1] for x in P)
            wpx=float('nan')
            if valid:
                du=P['R'][2]-P['L'][2]; dv=P['R'][3]-P['L'][3]; wpx=math.hypot(du,dv)
            stations.append({'feature_id':pid,'family':data['family'],'prescribed_width_mm':data['prescribed_width_mm'],'parameterization_level':data['parameterization_level'],
                             'view_id':cam['view_id'],'image_name':cam['image_name'],'sample_index':sidx,
                             'all_three_in_front':int(all(P[x][0] for x in P)),'all_three_inside_image':int(all(P[x][1] for x in P)),
                             'primary_station_valid':int(valid),'projected_width_px':wpx,
                             'center_u_px':P['C'][2],'center_v_px':P['C'][3],'left_u_px':P['L'][2],'left_v_px':P['L'][3],
                             'right_u_px':P['R'][2],'right_v_px':P['R'][3],'center_depth_m':P['C'][4]})
    by=defaultdict(list)
    for r in stations: by[(r['feature_id'],r['view_id'])].append(r)
    pairs=[]; bindings=[]
    for (pid,vid),g in sorted(by.items()):
        valid=[r for r in g if r['primary_station_valid']==1 and math.isfinite(float(r['projected_width_px']))]
        vals=[float(r['projected_width_px']) for r in valid]; first=g[0]; visible=bool(vals); idx=int(vid[1:])
        cls='not_observable' if not visible else 'observable'
        bindings.append({'feature_id':pid,'view_id':vid,'image_name':first['image_name'],'observability_status':cls})
        pairs.append({'feature_id':pid,'family':first['family'],'prescribed_width_mm':first['prescribed_width_mm'],'parameterization_level':first['parameterization_level'],
                      'view_id':vid,'image_name':first['image_name'],'station_total_n':len(g),'primary_valid_station_n':len(valid),
                      'primary_valid_station_fraction':len(valid)/len(g),'projected_width_px_median':med(vals),'projected_width_px_p10':quant(vals,.1),
                      'projected_width_px_p90':quant(vals,.9),'projected_width_px_min':min(vals) if vals else float('nan'),
                      'projected_width_px_max':max(vals) if vals else float('nan'),
                      'projected_width_primary_definition':'median_projected_width_px_over_primary_valid_stations','observability_status':cls})
    byi=defaultdict(list)
    for r in pairs:
        v=float(r['projected_width_px_median'])
        if math.isfinite(v): byi[r['feature_id']].append(r)
    identities=[]
    for pid,g in sorted(byi.items()):
        vals=[float(r['projected_width_px_median']) for r in g]; f=g[0]
        identities.append({'feature_id':pid,'family':f['family'],'prescribed_width_mm':f['prescribed_width_mm'],'parameterization_level':f['parameterization_level'],
                           'projected_pair_valid_n':len(vals),'projected_width_px_identity_median':med(vals),
                           'projected_width_px_identity_p10':quant(vals,.1),'projected_width_px_identity_p90':quant(vals,.9),
                           'projected_width_px_identity_min':min(vals),'projected_width_px_identity_max':max(vals)})
    return stations,pairs,identities,bindings


def references(geometry):
    tr=triplets(geometry); by=defaultdict(list)
    for (pid,sidx),d in sorted(tr.items()): by[pid].append((sidx,1000.0*float(np.linalg.norm(d['R']-d['L'])),d))
    out=[]
    for pid,g in sorted(by.items()):
        vals=[x[1] for x in g]; d=g[0][2]; ref=med(vals); nominal=float(d['prescribed_width_mm'])
        out.append({'feature_id':pid,'family':d['family'],'parameterization_level':d['parameterization_level'],'prescribed_width_mm':nominal,'station_n':len(vals),
                    'constructed_metric_reference_mm':ref,'reference_definition':'median_s(1000*||R_s-L_s||_2)',
                    'materialized_minus_prescribed_mm':ref-nominal})
    return out


def validate(specs,repaired,repair_summary,geometry,cams,pairs,identities,bindings,refs,surface_vertices):
    family=Counter(r['family'] for r in specs); widths=Counter(float(r['prescribed_width_mm']) for r in specs)
    cells=Counter((r['family'],float(r['prescribed_width_mm'])) for r in specs); roles=Counter(r['point_type'] for r in geometry)
    bindpairs={(r['feature_id'],r['view_id']) for r in bindings}; bcounts=Counter(r['observability_status'] for r in bindings)
    max_ref=max(abs(float(r['materialized_minus_prescribed_mm'])) for r in refs)
    max_path=max(float(r['path_length_abs_delta_m']) for r in repair_summary); max_end=max(max(float(r['endpoint_start_delta_m']),float(r['endpoint_end_delta_m'])) for r in repair_summary)
    surface_z_min=float(np.min(surface_vertices[:,2]))
    surface_z_max=float(np.max(surface_vertices[:,2]))
    surface_z_range=surface_z_max-surface_z_min
    raw=[
        ('surface_is_mildly_nonplanar',surface_z_range>=0.005,{'z_min_m':surface_z_min,'z_max_m':surface_z_max,'z_range_m':surface_z_range}),
        ('feature_identity_n_eq_40',len({r['feature_id'] for r in specs})==40,len({r['feature_id'] for r in specs})),
        ('family_counts_10_each',all(family[f]==10 for f in FAMILIES),dict(family)),
        ('width_counts_8_each',all(widths[w]==8 for w in WIDTHS_MM),dict(widths)),
        ('two_parameterization_levels_per_family_width',len(cells)==20 and all(v==2 for v in cells.values()),sorted(set(cells.values()))),
        ('repair_path_length_preserved',max_path<=1e-10,max_path),('repair_endpoints_preserved',max_end<=1e-10,max_end),
        ('geometry_equal_L_C_R_counts',roles['left_border']==roles['centerline']==roles['right_border'],dict(roles)),
        ('camera_n_eq_12',len(cams)==12,len(cams)),('binding_pair_n_eq_480',len(bindpairs)==480,len(bindpairs)),
        ('pair_projection_row_n_eq_480',len(pairs)==480,len(pairs)),('identity_projection_row_n_eq_40',len(identities)==40,len(identities)),
        ('constructed_reference_identity_n_eq_40',len(refs)==40,len(refs)),
        ('constructed_reference_matches_materialized_prescribed_on_neutral_surface',max_ref<=1e-9,max_ref),
    ]
    gates=[{'gate':n,'status':'PASS' if ok else 'FAIL','observed':obs} for n,ok,obs in raw]
    failed=[g['gate'] for g in gates if g['status']=='FAIL']
    return gates,{'status':'PASS' if not failed else 'FAIL','failed_gates':failed,'feature_identity_n':40,'geometry_station_n':roles['centerline'],
                  'camera_n':len(cams),'binding_n':len(bindpairs),'observability_counts':dict(bcounts),'pair_projection_n':len(pairs),
                  'identity_projection_n':len(identities),'constructed_reference_n':len(refs),
                  'reference_max_abs_prescribed_delta_mm':max_ref,'repair_max_path_length_delta_m':max_path,'repair_max_endpoint_delta_m':max_end,
                  'surface_z_min_m':surface_z_min,'surface_z_max_m':surface_z_max,'surface_z_range_m':surface_z_range}


def hash_manifest():
    rows=[]
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name!='artifact_hashes.csv': rows.append({'artifact':path.name,'size_bytes':path.stat().st_size,'sha256':sha(path)})
    write_csv(OUT/'artifact_hashes.csv',rows); return rows


def main():
    stage='startup'
    try:
        if OUT.exists(): shutil.rmtree(OUT)
        OUT.mkdir(parents=True)
        p('='*108); p('METHODSX — REPRODUCE PUBLIC NEUTRAL EXAMPLE v3'); p('='*108); p('UTC_START:',now()); p('OUT:',OUT)
        write_json(OUT/'config.json',{
            'implementation':'METHODSX_REPRODUCE_NEUTRAL_EXAMPLE_v3','scientific_boundary':'neutral public reference implementation, not numerical replica of historical worked example','repair_semantics':'collapse consecutive duplicate surface vertices; preserve every unique path vertex and endpoint; allocate extra samples inside original segments',
            'surface':{'type':'deterministic mildly nonplanar triangulated height field','width_m':SURFACE_W,'height_m':SURFACE_H,'nx':SURFACE_NX,'ny':SURFACE_NY,'wave_a1_m':SURFACE_WAVE_A1_M,'wave_a2_m':SURFACE_WAVE_A2_M,'phase_rad':SURFACE_WAVE_PHASE_RAD},
            'probe_population':{'families':FAMILIES,'widths_mm':WIDTHS_MM,'replicates':REPLICATES,'probe_length_m':PROBE_LENGTH_M,'sample_density_per_m':SAMPLE_DENSITY_PER_M,'minimum_sample_n':MIN_SAMPLE_N},
            'neutral_family_parameters':{'arc_sag_ratio':ARC_SAG_RATIO,'sinusoid_amplitude_ratio':SIN_AMP_RATIO,'sinusoid_cycles':SIN_CYCLES,'zigzag_amplitude_ratio':ZIG_AMP_RATIO,'zigzag_cycles':ZIG_CYCLES},
            'camera':{'n':CAMERA_N,'width_px':IMAGE_W,'height_px':IMAGE_H,'fx_px':FX,'fy_px':FY,'cx_px':CX,'cy_px':CY}})

        stage='surface'; p('[1/9] Surface...'); xs,ys,verts,faces=build_surface();
        write_csv(OUT/'surface_vertices.csv',[{'vertex_id':i,'x_m':float(v[0]),'y_m':float(v[1]),'z_m':float(v[2])} for i,v in enumerate(verts)])
        write_csv(OUT/'surface_faces.csv',[{'face_id':i,'v0':a,'v1':b,'v2':c} for i,(a,b,c) in enumerate(faces)])
        surface_summary={
            'surface_type':'deterministic mildly nonplanar triangulated height field',
            'vertex_n':len(verts),
            'face_n':len(faces),
            'z_min_m':float(np.min(verts[:,2])),
            'z_max_m':float(np.max(verts[:,2])),
            'z_range_m':float(np.max(verts[:,2])-np.min(verts[:,2])),
            'wave_a1_m':SURFACE_WAVE_A1_M,
            'wave_a2_m':SURFACE_WAVE_A2_M,
            'phase_rad':SURFACE_WAVE_PHASE_RAD,
        }
        write_json(OUT/'surface_summary.json',surface_summary)
        p('  vertices:',len(verts),'faces:',len(faces))
        p('  z range [m]:',surface_summary['z_range_m'])

        stage='design'; p('[2/9] Feature design...'); specs=design(); write_csv(OUT/'probe_design.csv',specs); p('  features:',len(specs))
        stage='parametric'; p('[3/9] Parametric centerlines...'); prm=parametric_centerlines(specs); write_csv(OUT/'centerline_parametric.csv',prm); p('  stations:',len(prm))
        stage='surface_binding'; p('[4/9] Surface binding + repair...'); sb=surface_bind(prm,xs,ys); write_csv(OUT/'centerline_surface_bound.csv',sb); repaired,rep_summary=repair(sb); write_csv(OUT/'centerline_repaired.csv',repaired); write_csv(OUT/'centerline_repair_summary.csv',rep_summary); p('  repaired stations:',len(repaired),'collapsed duplicates:',sum(int(r['collapsed_duplicate_n']) for r in rep_summary))
        stage='materialization'; p('[5/9] L/C/R materialization...'); geom=materialize(repaired); write_csv(OUT/'materialized_geometry_lcr.csv',geom); p('  geometry rows:',len(geom),'stations:',len(geom)//3)
        stage='cameras'; p('[6/9] Synthetic cameras...'); cams=cameras(); write_csv(OUT/'cameras.csv',cams); p('  cameras:',len(cams))
        stage='projection'; p('[7/9] Projection + bindings...'); st,pa,ident,bind=project_all(geom,cams); write_csv(OUT/'projected_scale_station_level.csv',st); write_csv(OUT/'projected_scale_pair_level.csv',pa); write_csv(OUT/'projected_scale_identity_level.csv',ident); write_csv(OUT/'identity_view_bindings.csv',bind); p('  bindings:',len(bind),'observability:',dict(Counter(r['observability_status'] for r in bind)))
        stage='reference'; p('[8/9] Constructed reference...'); refs=references(geom); write_csv(OUT/'constructed_metric_reference.csv',refs); p('  references:',len(refs))
        stage='validation'; p('[9/9] Validation...'); gates,summary=validate(specs,repaired,rep_summary,geom,cams,pa,ident,bind,refs,verts); write_csv(OUT/'validation_gates.csv',gates); summary.update({'implementation':'METHODSX_REPRODUCE_NEUTRAL_EXAMPLE_v3','timestamp_utc':now(),'output_root':str(OUT),'scientific_boundary':'neutral public reference implementation, not numerical replica of historical worked example','repair_semantics':'collapse consecutive duplicate surface vertices; preserve every unique path vertex and endpoint; allocate extra samples inside original segments','surface_semantics':'deterministic mildly nonplanar height field; centerlines bind to surface vertices; L/R use local tangent-plane offsets from the analytic surface normal'}); write_json(OUT/'summary.json',summary)
        (OUT/'README.md').write_text(f"""# MethodsX public neutral example\n\nGenerated from zero by `METHODSX_REPRODUCE_NEUTRAL_EXAMPLE_v3.py`.\n\nThis is a neutral reference implementation of the method, not a numerical replica of the historical hybrid worked example.\n\nPipeline: mildly nonplanar synthetic surface -> controlled probe -> placement -> centerline -> nearest-surface-vertex binding -> repair -> explicit L/C/R materialization -> persistent identity -> synthetic camera projection -> visibility/binding -> projected measurand scale -> constructed metric reference -> lineage gates.\n\nPopulation: 40 identities; 4 families; 5 nominal widths; 2 replicates; 12 synthetic pinhole cameras.\n\nPrimary projected scale: station `projected_width_px` on `primary_station_valid`; pair median; identity median.\n\nConstructed reference: `median_s(1000*||R_s-L_s||_2)`.\n\nValidation status: **{summary['status']}**.\n""",encoding='utf-8')
        hashes=hash_manifest()
        p(); p('='*108); p('FINAL_STATUS:',summary['status']); p('FAILED_CONDITION_N:',len(summary['failed_gates']))
        for g in summary['failed_gates']: p('FAILURE:',g)
        p('FEATURE_IDENTITY_N:',summary['feature_identity_n']); p('GEOMETRY_STATION_N:',summary['geometry_station_n']); p('CAMERA_N:',summary['camera_n']); p('BINDING_N:',summary['binding_n']); p('OBSERVABILITY_COUNTS:',summary['observability_counts']); p('PAIR_PROJECTION_N:',summary['pair_projection_n']); p('IDENTITY_PROJECTION_N:',summary['identity_projection_n']); p('CONSTRUCTED_REFERENCE_N:',summary['constructed_reference_n']); p('SURFACE_Z_RANGE_M:',summary['surface_z_range_m']); p('REFERENCE_MAX_ABS_PRESCRIBED_DELTA_MM:',summary['reference_max_abs_prescribed_delta_mm']); p('HASHED_ARTIFACT_N:',len(hashes)); p('OUT:',OUT); p('SUMMARY:',OUT/'summary.json'); p('GATES:',OUT/'validation_gates.csv'); p('HASHES:',OUT/'artifact_hashes.csv'); p('='*108)
        return 0 if summary['status']=='PASS' else 5
    except BaseException as exc:
        OUT.mkdir(parents=True,exist_ok=True); tb=traceback.format_exc(); (OUT/'UNHANDLED_EXCEPTION.txt').write_text(f'STAGE={stage}\nEXCEPTION={repr(exc)}\n\n{tb}\n',encoding='utf-8'); p('FINAL_STATUS: FAIL_EXCEPTION'); p('FAILED_STAGE:',stage); p('EXCEPTION:',repr(exc)); p('TRACEBACK:',OUT/'UNHANDLED_EXCEPTION.txt'); return 99

if __name__=='__main__': sys.exit(main())
