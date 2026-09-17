#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三ツ島 区画割り（DXF）→ 2階建て街並みの3Dパース生成。

出力:
  output/mitsushima_town.html  Three.js 単一HTML（CDN読込／鳥瞰・歩行／昼・夕景・影）
  output/mitsushima_town.glb        Blender用GLB（外壁・屋根などマテリアル色付き）
  output/mitsushima_town_white.glb  Blender用GLB（PV白モデル用・全マテリアル白）
  output/mitsushima_scene.json 中間シーン定義（HTMLに埋め込むのと同じ内容）
  output/mitsushima_check.json 検証結果

パラメータはすべて tools/mitsushima_config.json 側で変更する。
依存: Python標準ライブラリのみ。
"""

import json
import math
import os
import random
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "tools", "mitsushima_config.json")


# ---------------------------------------------------------------- DXF 読込
def parse_dxf(path):
    """R12 ASCII DXF から POLYLINE(+VERTEX) をレイヤ別に取り出す。座標は図面単位のまま。"""
    raw = open(path, "rb").read().decode("cp932")
    lines = raw.split("\r\n")
    pairs = []
    i = 0
    while i + 1 < len(lines):
        code = lines[i].strip()
        if code == "":
            break
        pairs.append((int(code), lines[i + 1]))
        i += 2

    ents, cur, in_ent = [], None, False
    for code, val in pairs:
        if code == 2 and val == "ENTITIES":
            in_ent = True
            continue
        if not in_ent:
            continue
        if code == 0:
            if val == "ENDSEC":
                break
            cur = {"type": val, "pts": [], "layer": None, "text": None}
            ents.append(cur)
            continue
        if cur is None:
            continue
        if code == 8:
            cur["layer"] = val
        elif code == 10:
            cur["pts"].append([float(val), None])
        elif code == 20 and cur["pts"] and cur["pts"][-1][1] is None:
            cur["pts"][-1][1] = float(val)
        elif code == 1:
            cur["text"] = val

    polys, texts, k = [], [], 0
    while k < len(ents):
        e = ents[k]
        if e["type"] == "POLYLINE":
            verts, j = [], k + 1
            while j < len(ents) and ents[j]["type"] == "VERTEX":
                verts.append((ents[j]["pts"][0][0], ents[j]["pts"][0][1]))
                j += 1
            polys.append({"layer": e["layer"], "verts": verts})
            k = j
        else:
            if e["type"] == "TEXT" and e["pts"]:
                texts.append({"layer": e["layer"], "text": e["text"],
                              "at": (e["pts"][0][0], e["pts"][0][1])})
            k += 1
    return polys, texts


# ---------------------------------------------------------------- 幾何ユーティリティ
def area2(poly):
    s = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def polygon_area(poly):
    return abs(area2(poly))


def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def dist_point_seg(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def dist_to_boundary(p, poly):
    n = len(poly)
    return min(dist_point_seg(p, poly[i], poly[(i + 1) % n]) for i in range(n))


def triangulate(poly):
    """耳切り法。反時計回りに正規化して三角形インデックスを返す。"""
    idx = list(range(len(poly)))
    if area2(poly) < 0:
        idx.reverse()
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        ear = False
        for i in range(len(idx)):
            i0, i1, i2 = idx[i - 1], idx[i], idx[(i + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-12:
                continue
            bad = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                if point_in_triangle(poly[j], a, b, c):
                    bad = True
                    break
            if bad:
                continue
            tris.append([i0, i1, i2])
            idx.pop(i)
            ear = True
            break
        if not ear:
            break
    if len(idx) == 3:
        tris.append([idx[0], idx[1], idx[2]])
    return tris


def point_in_triangle(p, a, b, c):
    d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
    d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
    d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
    neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (neg and pos)


# ---------------------------------------------------------------- 建物ボリューム配置
def fit_building(plot, road_x, cfg):
    """区画ポリゴン（平面m）に収まる最大の矩形を探す。

    条件:
      - 区画境界から side_m 以上内側
      - 道路境界線 road_x から road_parking_depth_m 以上手前（＝駐車場スペース）
      - 幅/奥行/面積の上限
    返り値: (x0, y0, x1, y1) 平面座標の矩形、または None
    """
    b = cfg["building"]
    s = cfg["setback"]
    step = b["grid_step_m"]
    side = s["side_m"]
    x_limit = road_x - s["road_parking_depth_m"]

    xs = [p[0] for p in plot]
    ys = [p[1] for p in plot]
    x_min, x_max = min(xs), min(max(xs), x_limit)
    y_min, y_max = min(ys), max(ys)
    if x_max - x_min < 1.0:
        return None

    nx = int((x_max - x_min) / step)
    ny = int((y_max - y_min) / step)
    # セル中心が「境界から side+step/2 以上内側」なら、そのセル全体が有効域に入る
    margin = side + step * 0.71
    mask = []
    for j in range(ny):
        cy = y_min + (j + 0.5) * step
        row = []
        for i in range(nx):
            cx = x_min + (i + 0.5) * step
            ok = (cx + step * 0.5 <= x_limit) and point_in_poly((cx, cy), plot) \
                and dist_to_boundary((cx, cy), plot) >= margin
            row.append(ok)
        mask.append(row)

    max_rows = int(b["max_width_m"] / step)    # y方向＝間口方向
    max_cols = int(b["max_depth_m"] / step)    # x方向＝奥行方向
    max_cells = b["max_area_m2"] / (step * step)

    best = None  # (area_cells, j0, j1, i0, i1)
    for j0 in range(ny):
        acc = list(mask[j0])
        for j1 in range(j0, min(ny, j0 + max_rows)):
            if j1 > j0:
                row = mask[j1]
                acc = [acc[i] and row[i] for i in range(nx)]
            h = j1 - j0 + 1
            # 連続するTrueの最長ラン
            run = 0
            for i in range(nx + 1):
                if i < nx and acc[i]:
                    run += 1
                    continue
                if run > 0:
                    w = min(run, max_cols)
                    hh, ww = h, w
                    if hh * ww > max_cells:      # 面積上限：長い方を削る
                        if ww >= hh:
                            ww = max(1, int(max_cells // hh))
                        else:
                            hh = max(1, int(max_cells // ww))
                    cells = hh * ww
                    # 同面積なら正方形に近い方、さらに奥（道路から遠い方）を優先
                    key = (cells, -abs(hh - ww), -(i - run))
                    if best is None or key > best[0]:
                        best = (key, j0, j0 + hh - 1, i - run, i - run + ww - 1)
                run = 0
    if best is None:
        return None
    _, j0, j1, i0, i1 = best
    rect = (x_min + i0 * step, y_min + j0 * step,
            x_min + (i1 + 1) * step, y_min + (j1 + 1) * step)
    if (rect[2] - rect[0]) * (rect[3] - rect[1]) < cfg["building"]["min_area_m2"]:
        return None
    return rect


# ---------------------------------------------------------------- シーン組み立て
def build_scene(cfg):
    src = cfg["source"]
    polys, texts = parse_dxf(os.path.join(ROOT, src["dxf"]))
    u = src["unit_to_meter"]

    def to_m(vs):
        return [(x * u, y * u) for x, y in vs]

    plots_raw = [to_m(p["verts"]) for p in polys if p["layer"] == src["layer_plot"]]
    roads_raw = [to_m(p["verts"]) for p in polys if p["layer"] == src["layer_road"]]
    site_raw = [to_m(p["verts"]) for p in polys if p["layer"] == src["layer_site"]]
    ref_bld = [to_m(p["verts"]) for p in polys if p["layer"] == src["layer_building_ref"]]

    # 区画は南→北の順（DXFは北→南）に並べ替えて 1号地…10号地 に対応させる
    plots_raw.sort(key=lambda p: -min(y for _, y in p))

    site = site_raw[0]
    sx = [p[0] for p in site]
    sy = [p[1] for p in site]
    cx0, cy0 = (min(sx) + max(sx)) / 2.0, (min(sy) + max(sy)) / 2.0

    def W(pt):          # 平面(m) → three.js世界座標(x, z)。平面+yが北 → -z
        return [round(pt[0] - cx0, 4), round(-(pt[1] - cy0), 4)]

    rng = random.Random(cfg["seed"])
    pal = cfg["palette"]
    mats = {
        "asphalt": pal["asphalt"], "concrete": pal["concrete"],
        "ground": pal["ground"], "plot": pal["plot_ground"],
        "neighbor": pal["neighbor"], "trunk": pal["trunk"],
        "glass": "#8fb6cc", "door": "#6b4b33", "car_glass": "#2a3238",
    }
    for i, c in enumerate(pal["walls"]):
        mats["wall_%d" % i] = c
    for i, c in enumerate(pal["roofs"]):
        mats["roof_%d" % i] = c
    for i, c in enumerate(pal["cars"]):
        mats["car_%d" % i] = c
    for i, c in enumerate(pal["foliage"]):
        mats["leaf_%d" % i] = c

    objs = []

    def add_poly(group, mat, pts_plane, y):
        pts = [W(p) for p in pts_plane]
        flat = [(p[0], p[1]) for p in pts]
        tris = triangulate(flat)
        objs.append({"kind": "poly", "group": group, "mat": mat,
                     "pts": pts, "tris": tris, "y": round(y, 4)})

    def add_box(group, mat, cx, cy, cz, w, h, d, rot=0.0):
        objs.append({"kind": "box", "group": group, "mat": mat,
                     "c": [round(cx, 4), round(cy, 4), round(cz, 4)],
                     "s": [round(w, 4), round(h, 4), round(d, 4)],
                     "rot": round(rot, 5)})

    # --- 地盤
    ground = 220.0
    objs.append({"kind": "poly", "group": "ground", "mat": "ground",
                 "pts": [[-ground, -ground], [ground, -ground], [ground, ground], [-ground, ground]],
                 "tris": [[0, 1, 2], [0, 2, 3]], "y": -0.05})

    # --- 敷地・道路
    add_poly("site", "plot", site, 0.005)
    for r in roads_raw:
        add_poly("road", "asphalt", r, 0.02)

    b = cfg["building"]
    road_x = cfg["setback"]["road_frontage_x_mm"] * u
    parking_depth = cfg["setback"]["road_parking_depth_m"]

    buildings, issues = [], []
    for n, plot in enumerate(plots_raw, start=1):
        gid = "house_%02d" % n
        add_poly("plot_%02d" % n, "plot", plot, 0.01)

        rect = fit_building(plot, road_x, cfg)
        if rect is None:
            issues.append({"plot": n, "reason": "有効な建築可能範囲が取れず建物を配置できない"})
            continue
        x0, y0, x1, y1 = rect
        w_x, w_y = x1 - x0, y1 - y0            # 平面での 奥行(x) × 間口(y)
        cxp, cyp = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        wx, wz = W((cxp, cyp))

        wall = "wall_%d" % rng.randrange(len(pal["walls"]))
        roof = "roof_%d" % rng.randrange(len(pal["roofs"]))
        # three.js空間では w_x が X方向、w_y が Z方向のサイズになる
        eave = b["eave_height_m"]
        add_box(gid, wall, wx, eave / 2.0, wz, w_x, eave, w_y)

        # 棟の向き：基本は道路と平行（道路は南北＝Z方向）→ 棟はZ軸方向。一部を90°回転。
        rot90 = rng.random() < b["ridge_rotate_ratio"]
        if rot90:
            span, length, rot = w_y, w_x, math.pi / 2.0
        else:
            span, length, rot = w_x, w_y, 0.0
        objs.append({"kind": "gable", "group": gid, "mat": roof, "mat_end": wall,
                     "c": [round(wx, 4), round(wz, 4)], "base_y": eave,
                     "w": round(span, 4), "d": round(length, 4),
                     "rot": round(rot, 5), "slope": b["roof_slope"],
                     "oh": b["roof_overhang_m"]})

        # 窓・玄関（面に貼る簡易表現）
        add_openings(objs, gid, wx, wz, w_x, w_y, b, rng)

        # 駐車場土間（道路側）と車
        px0, px1 = x1 + 0.1, road_x - 0.1
        if px1 - px0 > 2.0:
            pad = [(px0, y0), (px1, y0), (px1, y1), (px0, y1)]
            add_poly(gid, "concrete", pad, 0.03)
            if rng.random() < cfg["props"]["car_ratio"]:
                cs = cfg["props"]["car_size_m"]
                cxx, czz = W(((px0 + px1) / 2.0, cyp))
                cmat = "car_%d" % rng.randrange(len(pal["cars"]))
                add_box(gid, cmat, cxx, cs[1] / 2.0, czz, cs[2], cs[1] * 0.62, cs[0], math.pi / 2.0)
                add_box(gid, "car_glass", cxx, cs[1] * 0.78, czz,
                        cs[2] * 0.5, cs[1] * 0.38, cs[0] * 0.88, math.pi / 2.0)

        # 植栽（建物の裏手側の空地）
        for _ in range(cfg["props"]["tree_per_plot"]):
            tx = x0 - 0.9 - rng.random() * 0.4
            ty = y0 + 0.9 + rng.random() * max(0.2, (y1 - y0) - 1.8)
            if point_in_poly((tx, ty), plot) and dist_to_boundary((tx, ty), plot) > 0.6:
                add_tree(objs, "plot_%02d" % n, W((tx, ty)), cfg, rng, pal)

        buildings.append({
            "plot": n, "rect": [round(v, 3) for v in rect],
            "size_m": [round(w_x, 3), round(w_y, 3)],
            "area_m2": round(w_x * w_y, 2),
            "plot_area_m2": round(polygon_area(plot), 2),
            "wall": mats[wall], "roof": mats[roof],
            "ridge": "道路と平行(南北)" if not rot90 else "道路と直交(東西)",
        })

    # --- 街路樹
    interval = cfg["props"]["street_tree_interval_m"]
    y_lo = min(min(p[1] for p in pl) for pl in plots_raw)
    y_hi = max(max(p[1] for p in pl) for pl in plots_raw)
    verge_x = max(q[0] for r in roads_raw for q in r) + 1.6   # 車道の外（東側）に並べる
    ty = y_lo + 3.0
    while ty < y_hi:
        add_tree(objs, "street", W((verge_x, ty)), cfg, rng, pal, scale=0.85)
        ty += interval

    # --- 隣接する既存街区（グレー箱）
    add_neighbors(objs, cfg, rng, site, roads_raw, W)

    scene = {
        "meta": {
            "title": "門真市三ツ島 区画割り（採用案・東辺沿い10区画）2階建て街並みパース",
            "source_dxf": src["dxf"],
            "plots": len(plots_raw),
            "buildings": len(buildings),
            "site_area_m2": round(polygon_area(site), 2),
            "unit": "meter",
        },
        "config": cfg,
        "materials": mats,
        "objects": objs,
        "buildings": buildings,
        "issues": issues,
        "view": cfg["view"],
    }
    return scene, plots_raw, ref_bld, W


def add_openings(objs, gid, wx, wz, w_x, w_y, b, rng):
    """窓と玄関を面に貼る。東（道路側）＝+X面に玄関。"""
    t = 0.06
    lv = [1.15, 1.15 + b["floor_height_m"]]
    hx, hz = w_x / 2.0, w_y / 2.0
    for y0 in lv:
        for i, off in enumerate((-0.28, 0.28)):
            objs.append({"kind": "box", "group": gid, "mat": "glass",
                         "c": [round(wx + hx + t / 2, 4), round(y0 + 0.65, 4), round(wz + off * w_y, 4)],
                         "s": [t, 1.3, round(min(1.7, w_y * 0.3), 3)], "rot": 0.0})
            objs.append({"kind": "box", "group": gid, "mat": "glass",
                         "c": [round(wx - hx - t / 2, 4), round(y0 + 0.65, 4), round(wz + off * w_y, 4)],
                         "s": [t, 1.3, round(min(1.7, w_y * 0.3), 3)], "rot": 0.0})
            objs.append({"kind": "box", "group": gid, "mat": "glass",
                         "c": [round(wx + off * w_x, 4), round(y0 + 0.65, 4), round(wz - hz - t / 2, 4)],
                         "s": [round(min(1.7, w_x * 0.3), 3), 1.3, t], "rot": 0.0})
            objs.append({"kind": "box", "group": gid, "mat": "glass",
                         "c": [round(wx + off * w_x, 4), round(y0 + 0.65, 4), round(wz + hz + t / 2, 4)],
                         "s": [round(min(1.7, w_x * 0.3), 3), 1.3, t], "rot": 0.0})
    objs.append({"kind": "box", "group": gid, "mat": "door",
                 "c": [round(wx + hx + t / 2, 4), 1.0, round(wz + w_y * 0.34, 4)],
                 "s": [t, 2.0, 0.9], "rot": 0.0})


def add_tree(objs, group, pos, cfg, rng, pal, scale=1.0):
    hmin, hmax = cfg["props"]["tree_height_m"]
    h = (hmin + rng.random() * (hmax - hmin)) * scale
    trunk_h = h * 0.38
    objs.append({"kind": "cyl", "group": group, "mat": "trunk",
                 "c": [pos[0], 0.0, pos[1]], "r": round(0.11 * scale, 3), "h": round(trunk_h, 3)})
    objs.append({"kind": "cone", "group": group,
                 "mat": "leaf_%d" % rng.randrange(len(pal["foliage"])),
                 "c": [pos[0], round(trunk_h * 0.78, 3), pos[1]],
                 "r": round(h * 0.26, 3), "h": round(h * 0.72, 3)})


def add_neighbors(objs, cfg, rng, site, roads, W):
    """敷地外に既存街区のグレー箱を並べる。"""
    p = cfg["props"]
    xs = [q[0] for q in site]
    ys = [q[1] for q in site]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    road_x_max = max(q[0] for r in roads for q in r)
    m = p["neighbor_margin_m"]
    hmin, hmax = p["neighbor_height_m"]
    bands = [
        ("w", x_min - m - 22.0, x_min - m, y_min - 14.0, y_max + 14.0),
        ("e", road_x_max + m, road_x_max + m + 22.0, y_min - 14.0, y_max + 14.0),
        ("n", x_min - 24.0, x_max + 24.0, y_max + 8.5, y_max + 26.0),
        ("s", x_min - 24.0, x_max + 24.0, y_min - 24.0, y_min - m),
    ]
    n = p["neighbor_blocks"]
    placed = []
    for i in range(n * 12):
        if len(placed) >= n:
            break
        _, bx0, bx1, by0, by1 = bands[len(placed) % len(bands)]
        w = 6.0 + rng.random() * 6.0
        d = 6.0 + rng.random() * 8.0
        cx = bx0 + 1.0 + rng.random() * max(0.5, (bx1 - bx0) - w - 2.0) + w / 2.0
        cy = by0 + 1.0 + rng.random() * max(0.5, (by1 - by0) - d - 2.0) + d / 2.0
        box = (cx - w / 2 - 1.2, cy - d / 2 - 1.2, cx + w / 2 + 1.2, cy + d / 2 + 1.2)
        if any(not (box[2] < o[0] or box[0] > o[2] or box[3] < o[1] or box[1] > o[3])
               for o in placed):
            continue                                  # 既存の箱と重なる位置は捨てる
        placed.append(box)
        h = hmin + rng.random() * (hmax - hmin)
        pos = W((cx, cy))
        objs.append({"kind": "box", "group": "neighbor", "mat": "neighbor",
                     "c": [pos[0], round(h / 2, 3), pos[1]],
                     "s": [round(w, 3), round(h, 3), round(d, 3)], "rot": 0.0})


# ---------------------------------------------------------------- 三角形メッシュ化
def face(verts, ref_normal):
    """多角形（凸）を三角形に。法線が ref_normal 向きになるよう巻きを揃える。"""
    v0, v1, v2 = verts[0], verts[1], verts[2]
    a = [v1[i] - v0[i] for i in range(3)]
    b = [v2[i] - v0[i] for i in range(3)]
    nx = a[1] * b[2] - a[2] * b[1]
    ny = a[2] * b[0] - a[0] * b[2]
    nz = a[0] * b[1] - a[1] * b[0]
    if nx * ref_normal[0] + ny * ref_normal[1] + nz * ref_normal[2] < 0:
        verts = list(reversed(verts))
    tris = []
    for i in range(1, len(verts) - 1):
        tris.append((verts[0], verts[i], verts[i + 1]))
    return tris


def tri_normal(t):
    a = [t[1][i] - t[0][i] for i in range(3)]
    b = [t[2][i] - t[0][i] for i in range(3)]
    n = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    L = math.sqrt(sum(v * v for v in n)) or 1.0
    return [v / L for v in n]


def rotY(p, ang, cx, cz):
    s, c = math.sin(ang), math.cos(ang)
    x, y, z = p[0] - cx, p[1], p[2] - cz
    return [cx + x * c + z * s, y, cz - x * s + z * c]


def obj_triangles(o):
    """プリミティブ → [(mat, [三角形...])]"""
    k = o["kind"]
    if k == "poly":
        y = o["y"]
        vs = [[p[0], y, p[1]] for p in o["pts"]]
        tris = [(vs[a], vs[b], vs[c]) for a, b, c in o["tris"]]
        out = []
        for t in tris:
            out.extend(face(list(t), [0, 1, 0]))
        return [(o["mat"], out)]
    if k == "box":
        cx, cy, cz = o["c"]
        w, h, d = o["s"]
        hx, hy, hz = w / 2, h / 2, d / 2
        P = [[cx - hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz - hz],
             [cx + hx, cy - hy, cz + hz], [cx - hx, cy - hy, cz + hz],
             [cx - hx, cy + hy, cz - hz], [cx + hx, cy + hy, cz - hz],
             [cx + hx, cy + hy, cz + hz], [cx - hx, cy + hy, cz + hz]]
        if o.get("rot"):
            P = [rotY(p, o["rot"], cx, cz) for p in P]
        quads = [([0, 1, 2, 3], [0, -1, 0]), ([4, 5, 6, 7], [0, 1, 0]),
                 ([0, 1, 5, 4], [0, 0, -1]), ([3, 2, 6, 7], [0, 0, 1]),
                 ([1, 2, 6, 5], [1, 0, 0]), ([0, 3, 7, 4], [-1, 0, 0])]
        out = []
        for ids, nrm in quads:
            n2 = nrm
            if o.get("rot"):
                s, c = math.sin(o["rot"]), math.cos(o["rot"])
                n2 = [nrm[0] * c + nrm[2] * s, nrm[1], -nrm[0] * s + nrm[2] * c]
            out.extend(face([P[i] for i in ids], n2))
        return [(o["mat"], out)]
    if k == "gable":
        cx, cz = o["c"]
        hw = o["w"] / 2 + o["oh"]
        hd = o["d"] / 2 + o["oh"]
        ye = o["base_y"] - o["oh"] * o["slope"]
        yr = o["base_y"] + (o["w"] / 2) * o["slope"]
        A = [cx - hw, ye, cz - hd]
        B = [cx + hw, ye, cz - hd]
        C = [cx + hw, ye, cz + hd]
        D = [cx - hw, ye, cz + hd]
        R0 = [cx, yr, cz - hd]
        R1 = [cx, yr, cz + hd]
        pts = [A, B, C, D, R0, R1]
        if o.get("rot"):
            pts = [rotY(p, o["rot"], cx, cz) for p in pts]
        A, B, C, D, R0, R1 = pts
        roof = []
        roof.extend(face([A, D, R1, R0], [-1, 1, 0]))   # 西流れ
        roof.extend(face([B, C, R1, R0], [1, 1, 0]))    # 東流れ
        roof.extend(face([A, B, C, D], [0, -1, 0]))     # 軒裏
        ends = []
        ends.extend(face([A, B, R0], [0, 0, -1]))       # 妻壁
        ends.extend(face([D, C, R1], [0, 0, 1]))
        return [(o["mat"], roof), (o.get("mat_end", o["mat"]), ends)]
    if k in ("cyl", "cone"):
        cx, cy, cz = o["c"]
        r, h = o["r"], o["h"]
        seg = 10
        ring = [[cx + r * math.cos(2 * math.pi * i / seg), cy,
                 cz + r * math.sin(2 * math.pi * i / seg)] for i in range(seg)]
        out = []
        if k == "cone":
            apex = [cx, cy + h, cz]
            for i in range(seg):
                a, b = ring[i], ring[(i + 1) % seg]
                nrm = [(a[0] + b[0]) / 2 - cx, r * 0.5, (a[2] + b[2]) / 2 - cz]
                out.extend(face([a, b, apex], nrm))
        else:
            top = [[p[0], cy + h, p[2]] for p in ring]
            for i in range(seg):
                a, b = ring[i], ring[(i + 1) % seg]
                nrm = [(a[0] + b[0]) / 2 - cx, 0, (a[2] + b[2]) / 2 - cz]
                out.extend(face([a, b, top[(i + 1) % seg], top[i]], nrm))
            out.extend(face(list(reversed(top)), [0, 1, 0]))
        out.extend(face(list(ring), [0, -1, 0]))
        return [(o["mat"], out)]
    return []


# ---------------------------------------------------------------- GLB書き出し
def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(h):
    h = h.lstrip("#")
    return [round(srgb_to_linear(int(h[i:i + 2], 16)), 6) for i in (0, 2, 4)] + [1.0]


def write_glb(scene, path, white=False):
    groups = {}
    for o in scene["objects"]:
        for mat, tris in obj_triangles(o):
            groups.setdefault(o["group"], {}).setdefault(mat, []).extend(tris)

    mat_names = sorted({m for g in groups.values() for m in g})
    materials = []
    mat_index = {}
    for i, m in enumerate(mat_names):
        mat_index[m] = i
        rough = 0.95
        metal = 0.0
        if m == "glass" or m == "car_glass":
            rough, metal = 0.15, 0.1
        elif m.startswith("car_"):
            rough, metal = 0.35, 0.2
        if white:                                  # PV用の白モデル（マテリアル名は残す）
            color, rough, metal = hex_to_linear("#e6e4e0"), 0.9, 0.0
        else:
            color = hex_to_linear(scene["materials"][m])
        materials.append({
            "name": m,
            "pbrMetallicRoughness": {
                "baseColorFactor": color,
                "metallicFactor": metal, "roughnessFactor": rough,
            },
            "doubleSided": True,
        })

    buf = bytearray()
    accessors, bufviews, meshes, nodes = [], [], [], []

    def push(data, target):
        while len(buf) % 4:
            buf.append(0)
        off = len(buf)
        buf.extend(data)
        bufviews.append({"buffer": 0, "byteOffset": off, "byteLength": len(data), "target": target})
        return len(bufviews) - 1

    for gname in sorted(groups):
        prims = []
        for mat, tris in sorted(groups[gname].items()):
            pos, nor, idx = bytearray(), bytearray(), bytearray()
            mn = [1e18] * 3
            mx = [-1e18] * 3
            n_v = 0
            for t in tris:
                nrm = tri_normal(t)
                for v in t:
                    pos += struct.pack("<3f", *v)
                    nor += struct.pack("<3f", *nrm)
                    for a in range(3):
                        mn[a] = min(mn[a], v[a])
                        mx[a] = max(mx[a], v[a])
                idx += struct.pack("<3I", n_v, n_v + 1, n_v + 2)
                n_v += 3
            if n_v == 0:
                continue
            bv_p, bv_n, bv_i = push(pos, 34962), push(nor, 34962), push(idx, 34963)
            accessors.append({"bufferView": bv_p, "componentType": 5126, "count": n_v,
                              "type": "VEC3", "min": [round(v, 4) for v in mn],
                              "max": [round(v, 4) for v in mx]})
            accessors.append({"bufferView": bv_n, "componentType": 5126, "count": n_v, "type": "VEC3"})
            accessors.append({"bufferView": bv_i, "componentType": 5125, "count": n_v, "type": "SCALAR"})
            a = len(accessors)
            prims.append({"attributes": {"POSITION": a - 3, "NORMAL": a - 2},
                          "indices": a - 1, "material": mat_index[mat]})
        if not prims:
            continue
        meshes.append({"name": gname, "primitives": prims})
        nodes.append({"name": gname, "mesh": len(meshes) - 1})

    gltf = {
        "asset": {"version": "2.0", "generator": "Crossactor mitsushima_build.py"},
        "scene": 0,
        "scenes": [{"name": "mitsushima_town", "nodes": list(range(len(nodes)))}],
        "nodes": nodes, "meshes": meshes, "materials": materials,
        "accessors": accessors, "bufferViews": bufviews,
        "buffers": [{"byteLength": len(buf)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    while len(buf) % 4:
        buf.append(0)
    glb = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(buf))
    glb += struct.pack("<II", len(js), 0x4E4F534A) + js
    glb += struct.pack("<II", len(buf), 0x004E4942) + bytes(buf)
    open(path, "wb").write(glb)
    return {"triangles": sum(len(t) for g in groups.values() for t in g.values()),
            "nodes": len(nodes), "materials": len(materials), "bytes": len(glb)}


# ---------------------------------------------------------------- 検証
def verify(scene, plots, cfg):
    side = cfg["setback"]["side_m"]
    park = cfg["setback"]["road_parking_depth_m"]
    road_x = cfg["setback"]["road_frontage_x_mm"] * cfg["source"]["unit_to_meter"]
    rows, bad = [], []
    for b in scene["buildings"]:
        plot = plots[b["plot"] - 1]
        x0, y0, x1, y1 = b["rect"]
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        inside = all(point_in_poly(c, plot) for c in corners)
        clear = min(dist_to_boundary(c, plot) for c in corners)
        # 辺の中点も見る（凹部の食い込み対策）
        samples = []
        for i in range(4):
            a, bb = corners[i], corners[(i + 1) % 4]
            L = math.hypot(bb[0] - a[0], bb[1] - a[1])
            steps = max(2, int(L / 0.25))
            for t in range(steps + 1):
                u = t / steps
                samples.append((a[0] + (bb[0] - a[0]) * u, a[1] + (bb[1] - a[1]) * u))
        inside = inside and all(point_in_poly(m, plot) for m in samples)
        clear = min([clear] + [dist_to_boundary(m, plot) for m in samples])
        front = road_x - x1
        ok = inside and clear >= side - 1e-6 and front >= park - 1e-6 \
            and b["area_m2"] <= cfg["building"]["max_area_m2"] + 1e-6
        row = {"plot": b["plot"], "inside": inside,
               "min_setback_m": round(clear, 3), "front_open_m": round(front, 3),
               "area_m2": b["area_m2"], "plot_area_m2": b["plot_area_m2"],
               "coverage_%": round(100 * b["area_m2"] / b["plot_area_m2"], 1),
               "ridge": b["ridge"], "ok": ok}
        rows.append(row)
        if not ok:
            bad.append(row)
    return {
        "plots": scene["meta"]["plots"],
        "buildings": scene["meta"]["buildings"],
        "count_match": scene["meta"]["plots"] == scene["meta"]["buildings"],
        "all_inside": len(bad) == 0,
        "violations": bad,
        "rows": rows,
        "issues": scene["issues"],
    }


# ---------------------------------------------------------------- HTML
def write_html(scene, path):
    tpl = open(os.path.join(ROOT, "tools", "mitsushima_template.html"), encoding="utf-8").read()
    payload = json.dumps(scene, ensure_ascii=False, separators=(",", ":"))
    open(path, "w", encoding="utf-8").write(tpl.replace("/*__SCENE__*/null", payload))


# ---------------------------------------------------------------- main
def main():
    cfg = json.load(open(CFG_PATH, encoding="utf-8"))
    scene, plots, ref, W = build_scene(cfg)
    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)

    check = verify(scene, plots, cfg)
    scene["check"] = {k: check[k] for k in ("plots", "buildings", "count_match", "all_inside")}

    json.dump(scene, open(os.path.join(ROOT, "output", "mitsushima_scene.json"), "w",
                          encoding="utf-8"), ensure_ascii=False)
    stats = write_glb(scene, os.path.join(ROOT, "output", "mitsushima_town.glb"))
    write_glb(scene, os.path.join(ROOT, "output", "mitsushima_town_white.glb"), white=True)
    write_html(scene, os.path.join(ROOT, "output", "mitsushima_town.html"))
    json.dump(check, open(os.path.join(ROOT, "output", "mitsushima_check.json"), "w",
                          encoding="utf-8"), ensure_ascii=False, indent=2)

    print("区画数=%d 建物数=%d 一致=%s 全建物が区画内=%s"
          % (check["plots"], check["buildings"], check["count_match"], check["all_inside"]))
    print("GLB: %(triangles)d三角形 / %(nodes)dノード / %(materials)dマテリアル / %(bytes)dbytes" % stats)
    print("%-4s %-9s %-9s %-8s %-8s %-7s %s" % ("区画", "建築面積", "敷地面積", "建蔽率", "離隔", "道路空地", "棟向き"))
    for r in check["rows"]:
        print("%-4d %8.2f㎡ %8.2f㎡ %6.1f%% %6.2fm %7.2fm %s%s"
              % (r["plot"], r["area_m2"], r["plot_area_m2"], r["coverage_%"],
                 r["min_setback_m"], r["front_open_m"], r["ridge"],
                 "" if r["ok"] else "  ← NG"))
    if check["violations"] or check["issues"]:
        print("例外:", json.dumps(check["violations"] + check["issues"], ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
