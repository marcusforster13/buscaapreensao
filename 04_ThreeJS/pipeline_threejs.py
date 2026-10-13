"""
Busca e Apreensao - pipeline three.js / WebXR

Entrada : 02_Cena_VR_Otimizada/busca_VR.blend  (gerado por otimizar_para_vr.py)
Saidas  : 04_ThreeJS/web/  ->  cena.glb, cena.json, lightmaps/*.png, env/*.hdr
          (o index.html do visualizador fica em web/ e nao e sobrescrito)

Uso:
  blender -b ../02_Cena_VR_Otimizada/busca_VR.blend --python pipeline_threejs.py            (padrao, ~5 min)
  blender -b ../02_Cena_VR_Otimizada/busca_VR.blend --python pipeline_threejs.py -- rapido  (teste, ~2 min)
  blender -b ../02_Cena_VR_Otimizada/busca_VR.blend --python pipeline_threejs.py -- alta    (~30-60 min)

Etapas:
  1. Materiais -> PBR com as texturas CC0 de texturas_cc0/ (cor, rugosidade, normal GL)
  2. Lightmaps: bake da iluminacao do Cycles (luz direta + indireta) numa 2a UV, um atlas por colecao
  3. HDRI diurno -> .hdr leve para o ceu e reflexos
  4. Exporta cena.glb (Draco) + cena.json (lightmaps, cameras, giroflex)
"""
import bpy, os, sys, json, math, re, time
import numpy as np
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RAPIDO = "rapido" in ARGS
try:
    BASE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE = ""
if not os.path.isdir(os.path.join(BASE, "texturas_cc0")):
    BASE = os.path.join(os.path.expanduser("~"), "Desktop", "buscaeapreensao", "04_ThreeJS")
TEX = os.path.join(BASE, "texturas_cc0")
CACHE = os.path.join(BASE, "_cache_texturas")
WEB = os.path.join(BASE, "web")
LMDIR = os.path.join(WEB, "lightmaps")
ENVDIR = os.path.join(WEB, "env")
for d in (CACHE, WEB, LMDIR, ENVDIR):
    os.makedirs(d, exist_ok=True)
scene = bpy.context.scene
T0 = time.time()

def say(m):
    print("[THREE] %s  (%.0fs)" % (m, time.time() - T0))

def hx(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))

def lin(c):
    return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)

def sanitize(name):          # igual ao PropertyBinding.sanitizeNodeName do three.js
    return re.sub(r"[\[\]\.:\/]", "", re.sub(r"\s", "_", name))

def b2t(v):                  # Blender (Z para cima) -> three.js / glTF (Y para cima)
    return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]

# ------------------------------------------------------------------ 1. materiais PBR
def maps(pasta):
    d = os.path.join(TEX, pasta)
    fs = sorted(f for f in os.listdir(d) if not f.startswith("metal_grafite"))
    pick = lambda k: next((os.path.join(d, f) for f in fs if k in f.lower()), None)
    return pick("_diff") or pick("_col"), pick("_rough"), pick("_nor_gl")

def para_png8(path, nome):
    """EXR/JPG de dados (rugosidade, normal) -> PNG 8 bits Non-Color, que o three.js le."""
    if path.lower().endswith((".jpg", ".png")):
        return path
    out = os.path.join(CACHE, nome + ".jpg")          # JPG: o .glb fica bem menor que com PNG
    if not os.path.exists(out):
        src = bpy.data.images.load(path); src.colorspace_settings.name = "Non-Color"
        w, h = src.size; px = np.empty(w * h * 4, np.float32); src.pixels.foreach_get(px)
        dst = bpy.data.images.new("_tmp_" + nome, w, h, alpha=False); dst.colorspace_settings.name = "Non-Color"
        dst.pixels.foreach_set(np.clip(px, 0, 1)); dst.filepath_raw = out; dst.file_format = "JPEG"; dst.save()
        bpy.data.images.remove(src); bpy.data.images.remove(dst)
    return out

def grafite(path):
    """Tira o verde do metal pintado mantendo arranhoes e ferrugem."""
    out = os.path.join(CACHE, "metal_grafite_diff.png")
    if not os.path.exists(out):
        src = bpy.data.images.load(path)
        w, h = src.size; px = np.empty(w * h * 4, np.float32); src.pixels.foreach_get(px)
        px = px.reshape(-1, 4); rgb = px[:, :3]
        g = (rgb @ np.array([.3, .59, .11]))[:, None]
        rgb = np.clip(g + (rgb - g) * .18, 0, 1)
        rgb = rgb / max(g.mean(), 1e-3) * .5
        px[:, :3] = np.clip(rgb, 0, 1)
        dst = bpy.data.images.new("_tmp_grafite", w, h, alpha=False)
        dst.pixels.foreach_set(px.ravel()); dst.filepath_raw = out; dst.file_format = "PNG"; dst.save()
        bpy.data.images.remove(src); bpy.data.images.remove(dst)
    return out

def media_linear(img):
    w, h = img.size; px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px)
    m = px.reshape(-1, 4)[::7, :3].mean(0)
    return lin(tuple(m)) if img.colorspace_settings.name == "sRGB" else tuple(m)

def neutro(path):
    """Usa a versao neutra do tecido gerada pela cena principal (aplicar_texturas_cc0.py)."""
    p = os.path.join(os.path.dirname(path), "tecido_neutro_cor.png")
    return p if os.path.exists(p) else path

def aplicar_pbr(mat, pasta, tile, tile_antigo=1.0, tint=None, recolor=None, metal=0.0, alvo_lin=None):
    diff, rough, nor = maps(pasta)
    if recolor:
        diff = recolor(diff)
    alvo = tuple(alvo_lin) if alvo_lin else (lin(hx(tint)) if tint else tuple(mat.diffuse_color[:3]))
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) or nt.nodes.new("ShaderNodeBsdfPrincipled")
    for n in list(nt.nodes):
        if n not in (b, out):
            nt.nodes.remove(n)
    for inp in b.inputs:
        for l in list(inp.links):
            nt.links.remove(l)
    L = nt.links.new
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    mp = nt.nodes.new("ShaderNodeMapping"); s = tile_antigo / tile
    mp.inputs["Scale"].default_value = (s, s, 1)
    L(uvn.outputs["UV"], mp.inputs["Vector"])
    def tex(path, dados):
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(path, check_existing=True)
        if dados:
            t.image.colorspace_settings.name = "Non-Color"
        L(mp.outputs["Vector"], t.inputs["Vector"])
        return t
    td = tex(diff, False)
    media = media_linear(td.image)
    fator = [min(1.6, a / max(m, 1e-3)) for a, m in zip(alvo, media)]
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    next(i for i in mix.inputs if i.name == "Factor" and i.type == "VALUE").default_value = 1.0
    L(td.outputs["Color"], next(i for i in mix.inputs if i.name == "A" and i.type == "RGBA"))
    next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA").default_value = (*fator, 1)
    L(next(o for o in mix.outputs if o.name == "Result" and o.type == "RGBA"), b.inputs["Base Color"])
    if rough:
        tr = tex(para_png8(rough, pasta + "_rough"), True)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        L(tr.outputs["Color"], sep.inputs["Color"]); L(sep.outputs["Green"], b.inputs["Roughness"])
    if nor:
        tn = tex(para_png8(nor, pasta + "_normal"), True)
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.uv_map = "UVMap"
        L(tn.outputs["Color"], nm.inputs["Color"]); L(nm.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Metallic"].default_value = metal
    b.inputs["Alpha"].default_value = 1.0
    b.inputs["Emission Strength"].default_value = 0.0

# nome do material -> (pasta, tamanho do tile em m, tile usado na cena VR, cor alvo, recolor)
PBR = {}
n_pbr = 0
for nome, (pasta, tile, antigo, tint, rec) in PBR.items():
    m = bpy.data.materials.get(nome)
    if m and os.path.isdir(os.path.join(TEX, pasta)):
        if "cc0_tile" in m:            # a versao VR ja fez a UV no tamanho do tile CC0
            antigo = float(m["cc0_tile"])
        aplicar_pbr(m, pasta, tile, antigo, tint, rec); n_pbr += 1
# qualquer outro material marcado como CC0 na cena principal (ex.: tecidos dos estofados e cortinas)
RECOLOR = {"grafite": grafite, "neutro": neutro}
for m in bpy.data.materials:
    if m.name in PBR or "cc0_pasta" not in m or not m.node_tree:
        continue
    pasta = m["cc0_pasta"]
    if not os.path.isdir(os.path.join(TEX, pasta)):
        continue
    t = float(m.get("cc0_tile", 1.0))
    aplicar_pbr(m, pasta, t, t, recolor=RECOLOR.get(m.get("cc0_recolor", "")), metal=float(m.get("cc0_metal", 0.0)), alvo_lin=m.get("cc0_tint"))
    n_pbr += 1
say("%d materiais trocados por PBR com texturas CC0" % n_pbr)

# ------------------------------------------------------------------ 2. lightmaps (bake do Cycles)
SEM_LIGHTMAP = {"09_Luzes_Cameras", "99_Colisao", "98_Colisao_Extra", "08_Interativos", "13_Vidros", "14_Miudos", "15_Vegetacao", "16_Grama", "18_Fachada_Miudos"}
# niveis:  rapido (teste, ~2 min) | padrao (~5 min) | alta (~30-60 min)
ALTA = "alta" in ARGS
RES = {"05_Apto_Estrutura": 2048, "01_Rua_Patio": 2048, "02_Predio": 1024, "15_Vegetacao": 2048, "17_Entorno_Longe": 1024, "03_Portaria": 1024, "04_Corredor_Escada": 1024, "06_Sala": 1024, "07_Cozinha_Servico": 1024, "10_Quartos": 1024, "11_Banheiro": 1024, "12_Vizinho_301": 1024}
RES_PADRAO = 512
# a luz e calculada com o ceu e o sol em nivel natural (la fora fica certo); o site clareia so os lightmaps de dentro,
# como a vista se acostuma ao entrar em casa
GANHOS = {"01_Rua_Patio": 1.6, "02_Predio": 1.6, "17_Entorno_Longe": 1.0}; GANHO_INTERIOR = 3.0      # rua e predios proximos um pouco mais claros; morros e cidade ao longe como calculados
AMOSTRAS = 24 if RAPIDO else (600 if ALTA else 256)      # alta: so mais amostras (lightmaps maiores pesam no Quest)
scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"
scene.cycles.samples = AMOSTRAS; scene.cycles.use_denoising = False
scene.cycles.sample_clamp_indirect = 3.0; scene.cycles.sample_clamp_direct = 12.0      # interior com lampadas pequenas: sem vaga-lumes
scene.cycles.caustics_reflective = False; scene.cycles.caustics_refractive = False
# o que abre (gavetas, portas) e os vidros ficam fora do bake: o interior dos moveis recebe a luz do comodo e o sol entra pelas janelas
MOVEIS = [o for o in scene.objects if any(c.name in ("08_Interativos", "13_Vidros") for c in o.users_collection)]
for o in MOVEIS:
    o.hide_render = True

def blur(a):
    k = np.array([1, 4, 6, 4, 1], np.float32) / 16
    for ax in (0, 1):
        a = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), ax, a)
    return a

lm_json = {}
for col in bpy.data.collections:
    if col.name in SEM_LIGHTMAP:
        continue
    objs = [o for o in col.objects if o.type == "MESH" and len(o.data.polygons)]
    if not objs:
        continue
    res = RES.get(col.name, RES_PADRAO)
    if RAPIDO:
        res //= 2
    for o in objs:
        me = o.data
        if not me.uv_layers:
            me.uv_layers.new(name="UVMap")
        me.uv_layers[0].name = "UVMap"
        lm = me.uv_layers.get("Lightmap") or me.uv_layers.new(name="Lightmap")
        me.uv_layers["UVMap"].active_render = True
        me.uv_layers.active = lm
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.004, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new("LM_" + col.name, res, res, alpha=False, float_buffer=True)
    mats = {s.material for o in objs for s in o.material_slots if s.material}
    for m in mats:
        n = m.node_tree.nodes.get("LM_BAKE") or m.node_tree.nodes.new("ShaderNodeTexImage")
        n.name = "LM_BAKE"; n.image = img; m.node_tree.nodes.active = n
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, margin=6, use_clear=True)
    px = np.empty(res * res * 4, np.float32); img.pixels.foreach_get(px)
    rgb = px.reshape(res, res, 4)[..., :3]
    rgb = np.stack([blur(rgb[..., c]) for c in range(3)], -1)
    if col.name not in GANHOS:                      # interior: menos cor refletida do piso de madeira nas paredes e no teto
        lum = rgb.mean(-1, keepdims=True); rgb = lum + (rgb - lum) * .4
    vmax = float(min(max(np.percentile(rgb, 99.7), 1e-3), 3.0))      # teto: superficies coladas nas lampadas nao roubam a escala
    enc = np.clip(rgb / vmax, 0, 1) ** (1 / 2.2)
    out = np.ones((res, res, 4), np.float32); out[..., :3] = enc
    arq = "LM_%s.png" % col.name
    dst = bpy.data.images.new("_lm_out", res, res, alpha=False)
    dst.pixels.foreach_set(out.ravel()); dst.filepath_raw = os.path.join(LMDIR, arq); dst.file_format = "PNG"; dst.save()
    bpy.data.images.remove(dst)
    for o in objs:
        lm_json[sanitize(o.name)] = {"lm": "lightmaps/" + arq, "max": round(vmax, 5), "ganho": GANHOS.get(col.name, GANHO_INTERIOR)}
    say("lightmap %s: %d objetos, %dpx, max %.3f" % (col.name, len(objs), res, vmax))
for m in bpy.data.materials:
    if m.node_tree and m.node_tree.nodes.get("LM_BAKE"):
        m.node_tree.nodes.remove(m.node_tree.nodes["LM_BAKE"])
for img in [i for i in bpy.data.images if i.name.startswith("LM_")]:
    bpy.data.images.remove(img)

# ------------------------------------------------------------------ 3. HDRI diurno
hdr_src = next((os.path.join(BASE, "hdri", f) for f in os.listdir(os.path.join(BASE, "hdri"))
                if f.lower().endswith((".exr", ".hdr"))), None) if os.path.isdir(os.path.join(BASE, "hdri")) else None
env_arq = None
if hdr_src:
    for w in (1024, 2048):
        img = bpy.data.images.load(hdr_src); img.scale(w, w // 2)
        env_arq = "env/dia_%dk.hdr" % (w // 1024)
        img.filepath_raw = os.path.join(WEB, env_arq); img.file_format = "HDR"; img.save()
        bpy.data.images.remove(img)
    env_arq = "env/dia_1k.hdr"
    say("HDRI convertido: %s" % os.path.basename(hdr_src))

# ------------------------------------------------------------------ 4. exportar
# texturas dos modelos prontos (carros): PNG grandes -> JPG de ate 1024 px (o .glb cai de ~40 MB para ~15 MB)
def para_jpg(img, dados):
    out = os.path.join(CACHE, "modelo_" + bpy.path.clean_name(img.name) + ".jpg")
    if not os.path.exists(out):
        w, h = img.size
        copia = img.copy()
        if max(w, h) > 1024:
            k = 1024 / max(w, h); copia.scale(max(1, int(w * k)), max(1, int(h * k)))
        copia.filepath_raw = out; copia.file_format = "JPEG"; copia.save(); bpy.data.images.remove(copia)
    novo = bpy.data.images.load(out, check_existing=True)
    if dados: novo.colorspace_settings.name = "Non-Color"
    return novo
n_jpg = 0
for m in bpy.data.materials:
    if not m.node_tree or not m.name.startswith(("Modelo_", "Wheel", "Wheek")):
        continue
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and n.image.size[0] and not n.image.name.startswith("modelo_"):
            dados = n.image.colorspace_settings.name == "Non-Color"
            try:
                n.image = para_jpg(n.image, dados); n_jpg += 1
            except Exception as e:
                say("aviso: textura %s nao convertida (%s)" % (n.image.name, e))
say("%d texturas de modelos prontos convertidas para JPG" % n_jpg)

cams = {}
for o in scene.objects:
    if o.type == "CAMERA" and "Planta" not in o.name:
        fw = o.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        cams[o.name] = {"pos": b2t(o.matrix_world.translation), "alvo": b2t(o.matrix_world.translation + fw * 10)}
# pontos do treinamento: vazios P_<nome> da cena (posicao no site e para onde a pessoa olha)
pontos = {o.name[2:]: {"pos": b2t(o.matrix_world.translation), "rz": round(o.matrix_world.to_euler().z, 4)}
          for o in scene.objects if o.type == "EMPTY" and o.name.startswith("P_")}
# pecas que abrem: raizes A_* com as propriedades gravadas por busca.py
abre = {}
for o in scene.objects:
    if o.get("abre"):
        d = {"tipo": o["abre"]}
        for k in ("curso", "ang", "eixo", "colide", "larg", "tranca"):
            if k in o: d[k] = o[k] if isinstance(o[k], str) else round(float(o[k]), 4)
        abre[sanitize(o.name)] = d
for o in MOVEIS:
    o.hide_render = False
for o in [o for o in scene.objects if o.type in {"LIGHT", "CAMERA"}]:
    o.hide_render = True
bpy.ops.export_scene.gltf(filepath=os.path.join(WEB, "cena.glb"), export_format="GLB",
                          export_lights=False, export_cameras=False, export_texcoords=True, export_normals=True,
                          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
                          export_draco_texcoord_quantization=14, export_image_format="AUTO", export_image_quality=88,
                          use_renderable=True)
import shutil
col_src = os.path.normpath(os.path.join(BASE, "..", "02_Cena_VR_Otimizada", "colisao.glb"))
if os.path.exists(col_src):
    shutil.copy2(col_src, os.path.join(WEB, "colisao.glb"))
    say("colisao.glb copiado para web/")
cen_src = os.path.normpath(os.path.join(BASE, "..", "05_Treinamento"))
if os.path.isdir(cen_src):
    os.makedirs(os.path.join(WEB, "treinamento"), exist_ok=True)
    for f in os.listdir(cen_src):
        if f.endswith(".json"):
            shutil.copy2(os.path.join(cen_src, f), os.path.join(WEB, "treinamento", f))
    say("cenarios de treinamento copiados para web/treinamento/")
aud_src = os.path.normpath(os.path.join(BASE, "..", "06_Audio", "brutos"))
if os.path.isdir(aud_src):
    aud_dst = os.path.join(WEB, "audio"); os.makedirs(aud_dst, exist_ok=True)
    sons = sorted(f for f in os.listdir(aud_src) if f.lower().endswith((".mp3", ".ogg", ".wav")))
    for f in sons:
        shutil.copy2(os.path.join(aud_src, f), os.path.join(aud_dst, f))
    with open(os.path.join(aud_dst, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(sons, fh, ensure_ascii=False)
    say("%d sons copiados para web/audio/ (%s)" % (len(sons), ", ".join(sons)))
cfg = {"gerado_em": time.strftime("%Y-%m-%d %H:%M"), "qualidade": "rapida" if RAPIDO else ("alta" if ALTA else "padrao"),
       "lightmaps": lm_json, "lightmap_ganho": round(math.pi, 5), "exposicao": 1.0,
       "env": env_arq, "env_intensidade": .5, "cameras": cams, "abre": abre,
       "luz_dinamica": 1.0, "luz_externa": 2.4, "ceu_intensidade": 1.0, "pontos": pontos}
with open(os.path.join(WEB, "cena.json"), "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BASE, "busca_THREE.blend"))
say("PRONTO: web/cena.glb + cena.json (%d objetos com lightmap)" % len(lm_json))
