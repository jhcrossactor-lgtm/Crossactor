#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三ツ島 区画割り → Blenderモデリング。

output/mitsushima_scene.json（DXFから生成した確定座標）を読み、
Blenderのネイティブメッシュ・マテリアル・カメラ・ライトとして組み立てて .blend に保存する。

使い方:
  A) この環境（bpyモジュール）  : python3 tools/mitsushima_blender.py [--render]
  B) Blender GUI               : Scriptingタブで開いて実行（Blender 4.x）
  C) Blender CLI               : blender -b -P tools/mitsushima_blender.py

出力:
  output/mitsushima.blend        Blenderファイル（メートル単位・Z-up・実寸）
  output/renders/*.png           --render 指定時のみ。ChatGPT画像加工に渡す元絵

座標: シーンJSONはthree.js系（Y-up）。Blenderへは (x, y, z)_blender = (x, -z, y)_three で変換。
      北＝+Y、東＝+X、上＝+Z。敷地中心が原点。
"""

import json
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENE_JSON = os.path.join(ROOT, "output", "mitsushima_scene.json")
OUT_BLEND = os.path.join(ROOT, "output", "mitsushima.blend")
OUT_RENDER = os.path.join(ROOT, "output", "renders")

# ---------------------------------------------------------------- 設定
RENDER = {
    "resolution": (1920, 1080),
    "samples": 48,
    "engine": "CYCLES",
    "sun_elevation_deg": 48.0,     # 太陽高度
    "sun_azimuth_deg": 132.0,      # 方位（0=北, 90=東, 180=南）
    "sun_strength": 4.6,
    "sun_angle_deg": 0.9,          # 影のやわらかさ
}

# 動画用カメラパス。連番PNGを出し、Blender側にもキーフレームで残す。
# look: "follow" = カメラ位置からの相対（前方・横・高さ）、"fixed" = 注視点も始点終点で補間
PATHS = {
    "street": {                      # 開発道路を南→北へ歩く
        "frames": 25, "lens": 32, "samples": 28, "resolution": [1280, 720],
        "start": [6.6, -38.0, 1.55], "end": [6.6, 26.0, 1.55],
        "look": "follow", "look_ahead_m": 16.0, "look_side_m": -6.0, "look_height_m": 2.6,
    },
    "drone": {                       # 南東上空から降りながら街区へ寄る
        "frames": 12, "lens": 35, "samples": 28, "resolution": [1280, 720],
        "start": [62.0, -62.0, 42.0], "end": [24.0, -16.0, 11.0],
        "look": "fixed", "look_start": [0.0, -6.0, 4.0], "look_end": [-2.0, 4.0, 3.2],
    },
    "entry": {                       # 道路から3号地（カーポート・車なし）の玄関へ寄る
        "frames": 8, "lens": 30, "samples": 28, "resolution": [1280, 720],
        "start": [8.6, 13.8, 1.60], "end": [3.3, 17.2, 1.60],
        "look": "fixed", "look_start": [-2.1, 19.6, 2.2], "look_end": [-2.1, 19.73, 1.8],
    },
}

# マテリアル名の日本語対応（Blenderのアウトライナで読めるように）
MAT_JA = {
    "tire": "車_タイヤ",
    "fence_block": "外構_ブロック", "fence_mesh": "外構_メッシュフェンス",
    "gate_post": "外構_門柱", "gate_plate": "外構_表札", "approach": "外構_アプローチ",
    "carport_post": "外構_カーポート柱", "carport_roof": "外構_カーポート屋根",
    "shrub": "外構_低木",
    "asphalt": "道路アスファルト", "concrete": "駐車土間コンクリート",
    "ground": "地盤", "plot": "区画地面", "neighbor": "隣接街区",
    "trunk": "樹木_幹", "glass": "ガラス", "door": "玄関扉", "car_glass": "車_ガラス",
}


def ja_mat(name):
    if name in MAT_JA:
        return MAT_JA[name]
    for pre, ja in (("wall_", "外壁"), ("accent_", "外壁アクセント"), ("roof_", "屋根"),
                    ("car_", "車体"), ("leaf_", "樹木_葉")):
        if name.startswith(pre):
            return "%s_%s" % (ja, name.split("_")[1])
    return name


def B(v3):
    """three.js (x, y, z) → Blender (x, -z, y)"""
    return (v3[0], -v3[2], v3[1])


# ---------------------------------------------------------------- 下ごしらえ
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.length_unit = "METERS"
    sc.render.engine = RENDER["engine"]
    sc.render.resolution_x, sc.render.resolution_y = RENDER["resolution"]
    sc.render.film_transparent = False
    sc.cycles.samples = RENDER["samples"]
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "Standard"   # 実色に近い。img2imgの元絵向き
    sc.view_settings.exposure = -0.15


def get_collection(name, parent=None):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(col)
    return col


def make_material(name, hex_color, kind):
    key = ja_mat(name)
    if key in bpy.data.materials:
        return bpy.data.materials[key]
    h = hex_color.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]

    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    if kind == "carport_roof":                      # ポリカ板（すりガラス状の半透明）
        bsdf.inputs["Roughness"].default_value = 0.35
        bsdf.inputs["IOR"].default_value = 1.5
        if "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = 0.0   # 屈折は切る（描画が重いわりに見た目が変わらない）
        bsdf.inputs["Alpha"].default_value = 0.38
        mat.blend_method = "BLEND"
    elif kind == "fence_mesh":                       # メッシュフェンス（透ける）
        bsdf.inputs["Roughness"].default_value = 0.6
        bsdf.inputs["Metallic"].default_value = 0.4
        bsdf.inputs["Alpha"].default_value = 0.55
        mat.blend_method = "BLEND"
    elif kind in ("glass", "car_glass"):
        bsdf.inputs["Roughness"].default_value = 0.08
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["IOR"].default_value = 1.45
        if "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = 0.85 if kind == "glass" else 0.6
        mat.diffuse_color = (*lin, 0.4)
    elif kind.startswith("car_"):
        bsdf.inputs["Roughness"].default_value = 0.25
        bsdf.inputs["Metallic"].default_value = 0.6
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = 0.6
    elif kind == "asphalt":
        bsdf.inputs["Roughness"].default_value = 1.0
    elif kind.startswith("roof_"):
        bsdf.inputs["Roughness"].default_value = 0.75
    mat.diffuse_color = mat.diffuse_color if kind in ("glass", "car_glass") else (*lin, 1.0)
    return mat


def new_mesh_object(name, verts, faces, mats, mat_slots, collection, shade_smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([B(v) for v in verts], [], faces)
    me.validate()
    for m in mats:
        me.materials.append(m)
    if len(mats) > 1:
        for poly, slot in zip(me.polygons, mat_slots):
            poly.material_index = slot
    if shade_smooth:
        for poly in me.polygons:
            poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


# ---------------------------------------------------------------- プリミティブ→メッシュ
def box_mesh(c, s, rot):
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    pts = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz),
           (-hx, hy, -hz), (hx, hy, -hz), (hx, hy, hz), (-hx, hy, hz)]
    ca, sa = math.cos(rot or 0.0), math.sin(rot or 0.0)
    verts = []
    for x, y, z in pts:                       # three.js空間でY軸まわりに回す
        verts.append((c[0] + x * ca + z * sa, c[1] + y, c[2] - x * sa + z * ca))
    faces = [(0, 1, 2, 3), (5, 4, 7, 6), (4, 5, 1, 0), (3, 2, 6, 7),
             (1, 5, 6, 2), (4, 0, 3, 7)]
    return verts, faces


def gable_mesh(o):
    cx, cz = o["c"]
    hw, hd = o["w"] / 2 + o["oh"], o["d"] / 2 + o["oh"]
    ye = o["base_y"] - o["oh"] * o["slope"]
    yr = o["base_y"] + (o["w"] / 2) * o["slope"]
    pts = [(-hw, ye, -hd), (hw, ye, -hd), (hw, ye, hd), (-hw, ye, hd), (0, yr, -hd), (0, yr, hd)]
    ca, sa = math.cos(o["rot"] or 0.0), math.sin(o["rot"] or 0.0)
    verts = [(cx + x * ca + z * sa, y, cz - x * sa + z * ca) for x, y, z in pts]
    # 0:A 1:B 2:C 3:D 4:R0(北棟端) 5:R1(南棟端)
    faces = [(0, 3, 5, 4), (2, 1, 4, 5), (3, 2, 1, 0), (1, 0, 4), (3, 5, 2)]
    slots = [0, 0, 0, 1, 1]        # 0=屋根, 1=妻壁
    return verts, faces, slots


def wedge_mesh(o):
    """上端が片流れに傾いた躯体。"""
    cx, cz = o["c"]
    hw, hd = o["w"] / 2.0, o["d"] / 2.0
    yl = o["y_low"]
    yh = yl + o["w"] * o["slope"]
    y0 = o["y0"]
    verts = [(cx - hw, y0, cz - hd), (cx + hw, y0, cz - hd),
             (cx + hw, y0, cz + hd), (cx - hw, y0, cz + hd),
             (cx - hw, yl, cz - hd), (cx + hw, yh, cz - hd),
             (cx + hw, yh, cz + hd), (cx - hw, yl, cz + hd)]
    faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4),
             (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
    return verts, faces


def shed_mesh(o):
    """片流れ屋根スラブ。道路側（+X）が高い。"""
    cx, cz = o["c"]
    hw, hd = o["w"] / 2.0 + o["oh"], o["d"] / 2.0 + o["oh"]
    th = o["th"]
    yl = o["y_low"] + (-hw + o["w"] / 2.0) * o["slope"]
    yh = o["y_low"] + (hw + o["w"] / 2.0) * o["slope"]
    base = [(cx - hw, yl, cz - hd), (cx + hw, yh, cz - hd),
            (cx + hw, yh, cz + hd), (cx - hw, yl, cz + hd)]   # 壁天端の面
    top = [(x, y + th, z) for x, y, z in base]
    verts = list(top) + list(base)
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
             (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return verts, faces


def cyl_cone_mesh(o, seg=16):
    cx, cy, cz = o["c"]
    r, h = o["r"], o["h"]
    ring = [(cx + r * math.cos(2 * math.pi * i / seg), cy, cz + r * math.sin(2 * math.pi * i / seg))
            for i in range(seg)]
    if o["kind"] == "cone":
        verts = ring + [(cx, cy + h, cz)]
        faces = [(i, (i + 1) % seg, seg) for i in range(seg)]
        faces.append(tuple(range(seg - 1, -1, -1)))
    else:
        top = [(x, cy + h, z) for x, _, z in ring]
        verts = ring + top
        faces = [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
        faces.append(tuple(range(seg - 1, -1, -1)))
        faces.append(tuple(range(seg, 2 * seg)))
    return verts, faces


# ---------------------------------------------------------------- 構築
def role_of(o):
    """マテリアル名から部材名を決める。"""
    m = o["mat"]
    if m.startswith("wall_"):
        return "外壁" if o["kind"] == "wedge" else "外壁付属"
    if m.startswith("accent_"):
        return "外壁アクセント"
    if m.startswith("roof_"):
        return "屋根"
    if m == "glass":
        return "窓"
    if m == "door":
        return "玄関"
    if m == "concrete":
        return "駐車土間"
    if m.startswith("car_") or m == "car_glass":
        return "車"
    if m == "trunk":
        return "植栽_幹"
    if m.startswith("leaf_"):
        return "植栽_葉"
    if m == "asphalt":
        return "道路"
    if m == "plot":
        return "地面"
    if m == "neighbor":
        return "隣接建物"
    if m.startswith("fence_"):
        return "境界フェンス"
    if m.startswith("gate_"):
        return "門柱"
    if m.startswith("carport_"):
        return "カーポート"
    if m == "approach":
        return "玄関アプローチ"
    if m == "shrub":
        return "低木"
    return m


def collection_for(group, root):
    if group.startswith("house_") or group.startswith("plot_"):
        n = int(group.split("_")[1])
        return get_collection("%02d号地" % n, root)
    return get_collection({"road": "道路", "site": "敷地", "street": "街路樹",
                           "neighbor": "隣接街区", "ground": "地盤",
                           "fence": "境界フェンス"}.get(group, group), root)


def build(scene_data):
    root = get_collection("三ツ島街区")
    mats = {name: make_material(name, hexc, name) for name, hexc in scene_data["materials"].items()}
    counters = {}

    for o in scene_data["objects"]:
        col = collection_for(o["group"], root)
        prefix = col.name
        role = role_of(o)
        key = (prefix, role)
        counters[key] = counters.get(key, 0) + 1
        idx = counters[key]
        name = "%s_%s" % (prefix, role) if idx == 1 else "%s_%s_%02d" % (prefix, role, idx)

        if o["kind"] == "poly":
            verts = [(p[0], o["y"], p[1]) for p in o["pts"]]
            faces = [tuple(range(len(verts)))]
            new_mesh_object(name, verts, faces, [mats[o["mat"]]], [0], col)
        elif o["kind"] == "box":
            v, f = box_mesh(o["c"], o["s"], o.get("rot"))
            new_mesh_object(name, v, f, [mats[o["mat"]]], [0] * len(f), col)
        elif o["kind"] == "wedge":
            v, f = wedge_mesh(o)
            new_mesh_object(name, v, f, [mats[o["mat"]]], [0] * len(f), col)
        elif o["kind"] == "shed":
            v, f = shed_mesh(o)
            new_mesh_object(name, v, f, [mats[o["mat"]]], [0] * len(f), col)
        elif o["kind"] == "gable":
            v, f, slots = gable_mesh(o)
            new_mesh_object(name, v, f, [mats[o["mat"]], mats[o["mat_end"]]], slots, col)
        elif o["kind"] in ("cyl", "cone"):
            v, f = cyl_cone_mesh(o)
            new_mesh_object(name, v, f, [mats[o["mat"]]], [0] * len(f), col,
                            shade_smooth=(o["kind"] == "cyl"))
    return root


def build_world():
    world = bpy.data.worlds.new("三ツ島_空")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(RENDER["sun_elevation_deg"])
    sky.sun_rotation = math.radians(90.0 - RENDER["sun_azimuth_deg"])
    sky.altitude = 30.0
    sky.air_density = 1.1
    sky.dust_density = 1.4
    sky.sun_disc = False
    # 照明用（強め）と、カメラに映る背景用（弱め＝白飛び防止）を Light Path で切り替える
    bg_light = nt.nodes.new("ShaderNodeBackground")
    bg_light.inputs["Strength"].default_value = 0.34
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Strength"].default_value = 0.15
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg_light.inputs["Color"])
    nt.links.new(sky.outputs["Color"], bg_cam.inputs["Color"])
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_light.outputs["Background"], mix.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])


def build_sun(root):
    col = get_collection("ライト", root)
    data = bpy.data.lights.new("太陽", type="SUN")
    data.energy = RENDER["sun_strength"]
    data.angle = math.radians(RENDER["sun_angle_deg"])
    data.color = (1.0, 0.96, 0.9)
    sun = bpy.data.objects.new("太陽", data)
    col.objects.link(sun)
    el = math.radians(RENDER["sun_elevation_deg"])
    az = math.radians(RENDER["sun_azimuth_deg"])
    d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    sun.location = d * 120.0
    sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    return sun


def add_camera(name, loc, target, lens, root, dof_dist=None):
    col = get_collection("カメラ", root)
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.clip_end = 2000.0
    cam = bpy.data.objects.new(name, data)
    cam.location = loc
    col.objects.link(cam)

    tgt = bpy.data.objects.new(name + "_注視点", None)
    tgt.empty_display_size = 0.6
    tgt.location = target
    col.objects.link(tgt)
    con = cam.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    if dof_dist:
        data.dof.use_dof = True
        data.dof.focus_object = tgt
        data.dof.aperture_fstop = 5.6
    return cam


def build_cameras(scene_data, root):
    v = scene_data["view"]
    cams = []
    cams.append(add_camera("01_鳥瞰", (52.0, -56.0, 34.0), (0.0, -3.0, 4.0), 35, root))
    w = v["walk"]
    eye = B([w["position"][0], w["eye_height_m"], w["position"][2]])
    fwd = (-math.sin(w["yaw"]), -math.cos(w["yaw"]))              # three.js平面の前方向
    look = B([w["position"][0] + fwd[0] * 22, 2.4, w["position"][2] + fwd[1] * 22])
    cams.append(add_camera("02_歩行目線", eye, look, 32, root))
    cams.append(add_camera("03_玄関アプローチ", (7.5, 21.0, 1.55), (-2.5, 12.0, 2.8), 35, root))
    cams.append(add_camera("04_俯瞰45", (34.0, 34.0, 22.0), (-1.0, 6.0, 3.0), 45, root))
    bpy.context.scene.camera = cams[0]
    return cams


def build_path_camera(root, name, spec):
    """カメラパスを1本つくる。位置・注視点をフレーム1〜Nにキーフレームで打つ。"""
    col = get_collection("カメラ", root)
    n = spec["frames"]
    label = "05_パス_%s" % name
    data = bpy.data.cameras.new(label)
    data.lens = spec["lens"]
    data.clip_end = 2000.0
    cam = bpy.data.objects.new(label, data)
    col.objects.link(cam)

    tgt = bpy.data.objects.new(label + "_注視点", None)
    tgt.empty_display_size = 0.6
    col.objects.link(tgt)
    con = cam.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        pos = [spec["start"][k] + (spec["end"][k] - spec["start"][k]) * t for k in range(3)]
        if spec["look"] == "follow":
            look = (pos[0] + spec["look_side_m"],
                    pos[1] + spec["look_ahead_m"],
                    spec["look_height_m"])
        else:
            look = [spec["look_start"][k] + (spec["look_end"][k] - spec["look_start"][k]) * t
                    for k in range(3)]
        cam.location = pos
        tgt.location = look
        cam.keyframe_insert("location", frame=i + 1)
        tgt.keyframe_insert("location", frame=i + 1)

    for ob in (cam, tgt):                       # 等速にする
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    return cam


# ---------------------------------------------------------------- main
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    do_render = "--render" in argv
    path_name, only, rng_arg = None, None, None
    for a in argv:
        if a == "--path":
            path_name = "street"
        if a.startswith("--path="):
            path_name = a.split("=", 1)[1]
        if a.startswith("--only="):
            only = a.split("=", 1)[1]
        if a.startswith("--path-range="):
            rng_arg = a.split("=", 1)[1]
    do_path = path_name is not None

    scene_data = json.load(open(SCENE_JSON, encoding="utf-8"))
    reset_scene()
    root = build(scene_data)
    build_world()
    build_sun(root)
    cams = build_cameras(scene_data, root)
    path_cams = {nm: build_path_camera(root, nm, sp) for nm, sp in PATHS.items()}
    sc0 = bpy.context.scene
    sc0.frame_start, sc0.frame_end, sc0.frame_current = 1, max(
        sp["frames"] for sp in PATHS.values()), 1

    os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    n_obj = sum(len(c.objects) for c in bpy.data.collections)
    n_tri = sum(len(o.data.loop_triangles) for o in bpy.data.objects
                if o.type == "MESH" and (o.data.calc_loop_triangles() or True))
    print("saved %s / オブジェクト%d / 三角形%d / マテリアル%d / カメラ%d"
          % (OUT_BLEND, n_obj, n_tri, len(bpy.data.materials), len(cams)))

    if do_path:
        spec = PATHS[path_name]
        out = os.path.join(OUT_RENDER, "path_" + path_name)
        os.makedirs(out, exist_ok=True)
        sc = bpy.context.scene
        sc.camera = path_cams[path_name]
        sc.cycles.samples = spec["samples"]
        sc.render.resolution_x, sc.render.resolution_y = spec["resolution"]
        a, bnd = 1, spec["frames"]
        if rng_arg:
            a, bnd = (int(v) for v in rng_arg.split(":"))
        for f in range(a, bnd + 1):
            sc.frame_set(f)
            sc.render.filepath = os.path.join(out, "%s_%02d.png" % (path_name, f))
            bpy.ops.render.render(write_still=True)
            print("rendered %s_%02d" % (path_name, f))

    if do_render:
        os.makedirs(OUT_RENDER, exist_ok=True)
        for cam in cams:
            if only and only not in cam.name:
                continue
            bpy.context.scene.camera = cam
            bpy.context.scene.render.filepath = os.path.join(OUT_RENDER, cam.name + ".png")
            bpy.ops.render.render(write_still=True)
            print("rendered", cam.name)


if __name__ == "__main__":
    main()
