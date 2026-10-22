"""
Busca e Apreensao - gera a versao otimizada para VR a partir da cena de render.

Uso (linha de comando):
  blender -b ../01_Cena_Render_Cycles/busca.blend --python otimizar_para_vr.py
Saidas nesta pasta: busca_VR.blend, .glb, .fbx, texturas/ e RELATORIO_VR.txt
A cena original NAO e alterada (o script salva com outro nome).
"""
import bpy, bmesh, math, os, random
import numpy as np
from collections import defaultdict
from mathutils import Vector, Matrix

try:
    OUT = os.path.dirname(os.path.abspath(bpy.path.abspath(bpy.context.space_data.text.filepath)))
except Exception:
    OUT = ""
if not os.path.isdir(OUT):
    OUT = os.path.dirname(os.path.abspath(__file__))
if not os.path.isdir(OUT) or OUT.lower().endswith(".blend"):
    OUT = os.path.join(os.path.expanduser("~"), "Desktop", "buscaeapreensao", "02_Cena_VR_Otimizada")
TEX_DIR = os.path.join(OUT, "texturas")
os.makedirs(TEX_DIR, exist_ok=True)
scene = bpy.context.scene
rnd = random.Random(2026)
PI = math.pi
log = []

def say(msg):
    print("[VR] " + msg); log.append(msg)

def tri_count(objs=None):
    dg = bpy.context.evaluated_depsgraph_get()
    per = defaultdict(int)
    for ob in (objs or scene.objects):
        if ob.type not in {"MESH", "CURVE", "FONT"} or ob.hide_render:
            continue
        if any(c.hide_render for c in ob.users_collection):
            continue
        ev = ob.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except Exception:
            continue
        if me:
            me.calc_loop_triangles()
            per[ob.users_collection[0].name if ob.users_collection else "?"] += len(me.loop_triangles)
            ev.to_mesh_clear()
    return per


# ------------------------------------------------------------------ 2. ajustar modificadores antes de aplicar
lawns = []
for ob in scene.objects:
    for md in list(ob.modifiers):
        if md.type == "NODES" and md.name == "Grama":
            ob.modifiers.remove(md); lawns.append(ob.name)
        elif md.type == "SUBSURF":
            md.levels = 1; md.render_levels = 1
        elif md.type == "REMESH":
            md.voxel_size = .16
    if ob.type == "MESH" and any(md.type == "DISPLACE" for md in ob.modifiers):
        dec = ob.modifiers.new("VR_Decimate", "DECIMATE"); dec.ratio = .35
    if ob.type == "MESH" and ob.name.endswith(("_Pneu", "_Aro")):
        dec = ob.modifiers.new("VR_Decimate", "DECIMATE"); dec.ratio = .5
    if ob.type == "CURVE":
        ob.data.bevel_resolution = 0; ob.data.resolution_u = 4
say("Grama instanciada removida de %d gramados; subdivisao=1, remesh 0.16 m, decimate 35%% na folhagem." % len(lawns))

# ------------------------------------------------------------------ 3. aplicar tudo (malhas finais)
dg = bpy.context.evaluated_depsgraph_get()
fonte = None
cut_col = None
cutters = {o for o in scene.objects if o.get("cortador")}
novos = []
for ob in list(scene.objects):
    if ob.type not in {"MESH", "CURVE", "FONT"} or ob in cutters or ob == fonte:
        continue
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    novos.append((ob, me))
for ob, me in novos:
    if ob.type == "MESH":
        ob.modifiers.clear(); ob.data = me
    else:
        new = bpy.data.objects.new(ob.name, me)
        for c in ob.users_collection:
            c.objects.link(new)
        new.parent = ob.parent; new.matrix_parent_inverse = ob.matrix_parent_inverse.copy()
        new.matrix_basis = ob.matrix_basis.copy()
        nm = ob.name; bpy.data.objects.remove(ob, do_unlink=True); new.name = nm
for nm in {o.name for o in cutters} | ({fonte.name} if fonte else set()):
    o = bpy.data.objects.get(nm)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
if cut_col:
    bpy.data.collections.remove(cut_col)
say("Modificadores aplicados em %d objetos; textos e fios convertidos em malha." % len(novos))

# ------------------------------------------------------------------ 4. materiais: bake dos procedurais, UV no lugar de projecao
MAT_TILE = {}
UV_NATIVE = {"Rede_Listrada", "Tapete", "Grama_Cartao", "Cobogo_Alpha", "Folha_Costela", "Folha_Arbusto", "Folha_Palmeira", "Folha_Arvore", "Folha_Espada", "Rotulo_Frascos", "Logo_Lei_Seca", "Logo_Lei_Seca_Claro"}

def bake_tile(mat, tile, res, vertical=False):
    img = bpy.data.images.new(mat.name + "_bake", res, res, alpha=False)
    h = tile / 2
    vs = [(-h, 0, -h), (h, 0, -h), (h, 0, h), (-h, 0, h)] if vertical else [(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)]
    me = bpy.data.meshes.new("_bake"); me.from_pydata(vs, [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new()
    for li, uvv in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uvl.data[li].uv = uvv
    me.materials.append(mat)
    ob = bpy.data.objects.new("_bake", me); scene.collection.objects.link(ob)
    nt = mat.node_tree; node = nt.nodes.new("ShaderNodeTexImage"); node.image = img; nt.nodes.active = node
    for o in scene.objects:
        o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=0, use_clear=True)
    nt.nodes.remove(node); bpy.data.objects.remove(ob, do_unlink=True); bpy.data.meshes.remove(me)
    img.pack()
    return img

def set_image_base(mat, img, rough=None):
    nt = mat.node_tree; b = nt.nodes.get("Principled BSDF")
    for inp in ("Base Color", "Normal", "Roughness"):
        for l in list(b.inputs[inp].links):
            nt.links.remove(l)
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    if rough is not None:
        b.inputs["Roughness"].default_value = rough

scene.render.engine = "CYCLES"; scene.cycles.samples = 4; scene.cycles.device = "CPU"
PROC = {  # material: (tamanho do tile em m, resolucao, vertical, rugosidade)
    "Madeira_Freijo": (1.0, 512, False, .55), "Madeira_Jacaranda": (1.0, 512, False, .45),
    "Madeira_Forro": (1.0, 512, False, .7), "Asfalto": (4.0, 1024, False, .88),
    "Filete_de_Pedra": (1.0, 512, True, .9), "Piso_Intertravado": (1.0, 512, False, .85),
    "Folhagem": (2.0, 512, False, .75), "Folhagem_Escura": (2.0, 512, False, .75),
    "Flores_Ipe_Amarelo": (2.0, 512, False, .75),
}
for name, (tile, res, vert, rough) in PROC.items():
    m = bpy.data.materials.get(name)
    if not m or "cc0_pasta" in m:      # materiais CC0 sao tratados abaixo, sem bake
        continue
    img = bake_tile(m, tile, res, vert)
    set_image_base(m, img, rough); MAT_TILE[name] = tile
say("Bake de %d materiais procedurais em texturas de imagem." % len(MAT_TILE))

# materiais com texturas CC0 (aplicadas na cena principal por aplicar_texturas_cc0.py):
# projecao em caixa -> UV em metros; EXR -> PNG; relevo -> normal map GL
TEX_CC0 = os.path.normpath(os.path.join(OUT, "..", "04_ThreeJS", "texturas_cc0"))
CACHE_CC0 = os.path.normpath(os.path.join(OUT, "..", "04_ThreeJS", "_cache_texturas"))
os.makedirs(CACHE_CC0, exist_ok=True)

def cc0_arquivo(pasta, chave):
    d = os.path.join(TEX_CC0, pasta)
    return next((os.path.join(d, f) for f in sorted(os.listdir(d)) if chave in f.lower()), None)

def cc0_png(path, nome):
    if path is None or path.lower().endswith((".jpg", ".png")):
        return path
    out = os.path.join(CACHE_CC0, nome + ".png")
    if not os.path.exists(out):
        src = bpy.data.images.load(path); src.colorspace_settings.name = "Non-Color"
        w, h = src.size; px = np.empty(w * h * 4, np.float32); src.pixels.foreach_get(px)
        dst = bpy.data.images.new("_tmp_" + nome, w, h, alpha=False); dst.colorspace_settings.name = "Non-Color"
        dst.pixels.foreach_set(np.clip(px, 0, 1)); dst.filepath_raw = out; dst.file_format = "PNG"; dst.save()
        bpy.data.images.remove(src); bpy.data.images.remove(dst)
    return out

n_cc0 = 0
for m in bpy.data.materials:
    if not m.node_tree or "cc0_pasta" not in m:
        continue
    pasta = m["cc0_pasta"]
    if not os.path.isdir(os.path.join(TEX_CC0, pasta)):
        continue
    nt = m.node_tree
    diff = next((n.image for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and n.image.colorspace_settings.name == "sRGB"), None)
    mix = next((n for n in nt.nodes if n.type == "MIX"), None)
    fator = tuple(next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA").default_value) if mix else (1, 1, 1, 1)
    rough = cc0_png(cc0_arquivo(pasta, "_rough"), pasta + "_rough")
    nor = cc0_png(cc0_arquivo(pasta, "_nor_gl"), pasta + "_normal")
    out_n = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    for n in list(nt.nodes):
        if n not in (b, out_n):
            nt.nodes.remove(n)
    for inp in b.inputs:
        for l in list(inp.links):
            nt.links.remove(l)
    L = nt.links.new
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    def tex(img):
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; L(uvn.outputs["UV"], t.inputs["Vector"]); return t
    td = tex(diff)
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"
    next(i for i in mx.inputs if i.name == "Factor" and i.type == "VALUE").default_value = 1.0
    L(td.outputs["Color"], next(i for i in mx.inputs if i.name == "A" and i.type == "RGBA"))
    next(i for i in mx.inputs if i.name == "B" and i.type == "RGBA").default_value = fator
    L(next(o for o in mx.outputs if o.name == "Result" and o.type == "RGBA"), b.inputs["Base Color"])
    if rough:
        img = bpy.data.images.load(rough, check_existing=True); img.colorspace_settings.name = "Non-Color"
        sep = nt.nodes.new("ShaderNodeSeparateColor"); L(tex(img).outputs["Color"], sep.inputs["Color"])
        L(sep.outputs["Green"], b.inputs["Roughness"])
    if nor:
        img = bpy.data.images.load(nor, check_existing=True); img.colorspace_settings.name = "Non-Color"
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.uv_map = "UVMap"
        L(tex(img).outputs["Color"], nm.inputs["Color"]); L(nm.outputs["Normal"], b.inputs["Normal"])
    MAT_TILE[m.name] = float(m["cc0_tile"]); n_cc0 += 1
say("%d materiais com texturas CC0 convertidos para UV + PNG (cor, rugosidade, normal)." % n_cc0)

for m in bpy.data.materials:
    if not m.node_tree:
        continue
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    mp = next((n for n in nt.nodes if n.type == "MAPPING"), None)
    img_node = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
    if img_node and mp and m.name not in MAT_TILE:          # projecao em caixa -> UV
        MAT_TILE[m.name] = 1.0 / max(mp.inputs["Scale"].default_value[0], 1e-6)
        for l in list(img_node.inputs["Vector"].links):
            nt.links.remove(l)
        img_node.projection = "FLAT"
    if b and b.inputs["Emission Strength"].is_linked:          # janelas com cortina -> emissao constante
        mr = next((n for n in nt.nodes if n.type == "MAP_RANGE"), None)
        val = mr.inputs["To Max"].default_value if mr else 3.0
        for l in list(b.inputs["Emission Strength"].links):
            nt.links.remove(l)
        b.inputs["Emission Strength"].default_value = val

# ------------------------------------------------------------------ 5. UV em caixa (metros) para todas as malhas
def box_uv(ob):
    me = ob.data
    bm = bmesh.new(); bm.from_mesh(me)
    had = len(me.uv_layers) > 0
    uvl = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
    mats = me.materials
    for f in bm.faces:
        mn = mats[f.material_index].name if f.material_index < len(mats) and mats[f.material_index] else ""
        if (mn in UV_NATIVE or mn.startswith(("Modelo_", "Img_"))) and had:      # modelos prontos mantem a UV original
            continue
        t = MAT_TILE.get(mn, 1.0)
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            u, v = ((c.y, c.z), (c.x, c.z), (c.x, c.y))[ax]
            l[uvl].uv = (u / t, v / t)
    bm.to_mesh(me); bm.free()

for ob in scene.objects:
    if ob.type == "MESH":
        box_uv(ob)
say("UVs em caixa (escala real em metros) aplicadas em todas as malhas.")


# ------------------------------------------------------------------ 6b. malha de colisao simplificada
# Uma caixa orientada (OBB) por objeto relevante: paredes, pisos, moveis, carros, postes, troncos.
# Sai como objeto "Colisao" (colecao 99_Colisao, fora do render) e em colisao.fbx / colisao.glb.
COL_FORA = {"09_Luzes_Cameras", "08_Interativos", "13_Vidros", "14_Miudos", "16_Grama", "18_Fachada_Miudos"}
COL_PULAR = ("Mv_", "_Cabine", "Rodape_", "_Revista", "_Roda", "Giroflex", "_Listra", "_Adesivo", "_Casa", "_Copa", "_Galhos", "_Folhas", "_Miolo", "_Palmito", "Arbusto", "_Jan_", "_Var_", "_Friso", "_ArCond", "Morro", "Predio_Longe", "Faixa", "Vaga_", "Cortina", "Varal", "_Telhado", "Bueiro", "Arvore_Canteiro", "Azulejo_", "Capacho", "Tapete", "Quadro_", "_Plafon", "_Correio", "_Avisos", "_Copa", "_Moldura", "_Peitoril", "_Ar_Cond", "_Letreiro", "_Vitrine", "_Pilar", "_Pilastra", "_Varanda", "_Cornija", "_Platibanda", "_Rodape", "_Casa_Maquinas", "_Caixa_Dagua", "_Marquise_Testeira", "_Galhos", "_Texto", "Texto_", "Adesivo", "Faixa", "Marca_", "Giroflex", "Balao_Estai", "Cone_", "Asfalto_Remendo", "Tampa_", "Sarjeta", "Brasao", "_Placa", "_Janela", "_Porta_Loja", "_Trelica", "_Luz")
caixas = []
for ob in scene.objects:
    if ob.type != "MESH" or not ob.users_collection:
        continue
    cn = ob.users_collection[0].name
    if cn in COL_FORA and "Tronco" not in ob.name:
        continue
    if any(p in ob.name for p in COL_PULAR):
        continue
    dims = ob.dimensions
    if max(dims) < .25:                 # objetos pequenos nao bloqueiam a passagem
        continue
    caixas.append([ob.matrix_world @ Vector(c) for c in ob.bound_box])
for ob in [o for o in scene.objects if any(c.name == "98_Colisao_Extra" for c in o.users_collection)]:      # caixas dos moveis que abrem: ja entraram na colisao
    bpy.data.objects.remove(ob, do_unlink=True)
say("Colisao: %d caixas orientadas preparadas." % len(caixas))

# ------------------------------------------------------------------ 7. juntar geometria estatica por colecao
# conjuntos moveis/interativos: cada raiz (carro abordado, etilometro, maleta...) vira uma malha so, presa a raiz
INTERATIVO_COL = {"08_Interativos", "10_Carro_Abordado", "09_Luzes_Cameras"}
INTERATIVO_PAI = ("I_", "A_")
n_conj = 0
for cn in ("08_Interativos", "10_Carro_Abordado"):
    col = bpy.data.collections.get(cn)
    for raiz in [o for o in (col.objects if col else []) if o.parent is None and o.type == "EMPTY"]:
        objs = [o for o in raiz.children_recursive if o.type == "MESH" and not any(k in o.name for k in ("_Roda_", "_Porta"))]   # rodas ficam soltas para girar
        if not objs:
            continue
        for o in objs:
            mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
        alvo = objs[0]
        if len(objs) > 1:
            with bpy.context.temp_override(active_object=alvo, selected_objects=objs, selected_editable_objects=objs):
                bpy.ops.object.join()
        for o in [o for o in raiz.children_recursive if not any(k in o.name for k in ("_Roda_", "_Porta"))]:
            bpy.data.objects.remove(o, do_unlink=True)
        alvo.name = raiz.name + "_Malha"; alvo.data.name = alvo.name
        mw = alvo.matrix_world.copy(); alvo.parent = raiz; alvo.matrix_world = mw
        n_conj += 1
say("%d conjuntos interativos unidos (1 malha por conjunto)." % n_conj)

def interativo(ob):
    if any(c.name in INTERATIVO_COL for c in ob.users_collection):
        return True
    p = ob
    while p:
        if p.name.startswith(INTERATIVO_PAI):
            return True
        p = p.parent
    return False

juntados = 0
for col in list(bpy.data.collections):
    objs = [o for o in col.objects if o.type == "MESH" and not interativo(o)]
    if len(objs) < 2:
        continue
    for o in objs:
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
    alvo = objs[0]
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = alvo
    with bpy.context.temp_override(active_object=alvo, selected_objects=objs, selected_editable_objects=objs):
        bpy.ops.object.join()
    alvo.name = col.name + "_Estatico"; alvo.data.name = alvo.name
    juntados += len(objs)
say("%d objetos estaticos unidos em 1 malha por colecao (menos draw calls)." % juntados)

# empties que ficaram sem filhos
for ob in list(scene.objects):
    if ob.type == "EMPTY" and not ob.children and not interativo(ob):
        bpy.data.objects.remove(ob, do_unlink=True)
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

# ------------------------------------------------------------------ 8. relatorio, salvar e exportar
per = tri_count()
total = sum(per.values())
meshes = [o for o in scene.objects if o.type == "MESH"]
slots = sum(len(o.data.materials) for o in meshes)
luzes = [o for o in scene.objects if o.type == "LIGHT"]

for img in bpy.data.images:
    if img.type != "IMAGE" or img.size[0] == 0:
        continue
    path = os.path.join(TEX_DIR, bpy.path.clean_name(img.name) + ".png")
    img.filepath_raw = path; img.file_format = "PNG"
    try:
        img.save()
    except Exception as e:
        say("Aviso: nao salvou %s (%s)" % (img.name, e))

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "busca_VR.blend"))
try:
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "busca_VR.glb"), export_format="GLB", export_lights=True, export_cameras=True)
    say("Exportado: busca_VR.glb")
except Exception as e:
    say("Falha no GLB: %s" % e)
try:
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "busca_VR.fbx"), path_mode="COPY", embed_textures=True,
                             object_types={"MESH", "LIGHT", "CAMERA", "EMPTY"}, apply_scale_options="FBX_SCALE_ALL")
    say("Exportado: busca_VR.fbx")
except Exception as e:
    say("Falha no FBX: %s" % e)

# malha de colisao (depois das exportacoes principais, para nao entrar nelas)
if caixas:
    bmc = bmesh.new()
    FACES = ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0))
    for cs in caixas:
        vs = [bmc.verts.new(c) for c in cs]
        for f in FACES:
            try:
                bmc.faces.new([vs[i] for i in f])
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bmc, faces=bmc.faces)
    mec = bpy.data.meshes.new("Colisao"); bmc.to_mesh(mec); bmc.free()
    colc = bpy.data.collections.get("99_Colisao") or bpy.data.collections.new("99_Colisao")
    if colc.name not in scene.collection.children:
        scene.collection.children.link(colc)
    obc = bpy.data.objects.new("Colisao", mec); colc.objects.link(obc)
    obc.display_type = "WIRE"; obc.hide_render = True
    for o in scene.objects:
        o.select_set(False)
    obc.select_set(True); bpy.context.view_layer.objects.active = obc
    try:
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "colisao.glb"), export_format="GLB", use_selection=True,
                                  export_materials="NONE", export_texcoords=False)
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "colisao.fbx"), use_selection=True, object_types={"MESH"},
                                 apply_scale_options="FBX_SCALE_ALL")
        say("Colisao: %d caixas, %d tris -> colisao.glb / colisao.fbx" % (len(caixas), len(caixas) * 12))
    except Exception as e:
        say("Falha ao exportar colisao: %s" % e)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "busca_VR.blend"))

with open(os.path.join(OUT, "RELATORIO_VR.txt"), "w", encoding="utf-8") as f:
    f.write("BUSCA E APREENSAO - VERSAO VR OTIMIZADA\n\n")
    f.write("DEPOIS: %d tris | %d malhas | %d slots de material (~draw calls) | %d luzes\n\n" % (total, len(meshes), slots, len(luzes)))
    f.write("Triangulos por colecao:\n")
    for k, v in sorted(per.items(), key=lambda kv: -kv[1]):
        f.write("  %-32s %10d\n" % (k, v))
    f.write("\nEtapas:\n")
    for m in log:
        f.write("  - " + m + "\n")
    f.write("""
Proximos passos no motor (Unity/Unreal):
  - Iluminacao: marcar a geometria estatica como Static e fazer bake de lightmaps
    (Unity: ativar "Generate Lightmap UVs" no import do FBX). Manter dinamicas so:
    giroflex (vermelho/azul), farois da viatura, TV e a lanterna do policial.
  - O giroflex esta animado apenas no Blender (Cycles); recriar o pisca no motor
    com um script alternando as luzes e a emissao das lentes.
  - Colisao: use colisao.fbx (uma caixa por parede/piso/movel/carro).
      Unity: arraste colisao.fbx para a cena, adicione Mesh Collider e desligue o Mesh Renderer.
      Unreal: importe colisao.fbx e em Collision Complexity escolha "Use Complex Collision As Simple",
              deixe o ator invisivel (Hidden in Game).
  - Objetos interativos ja estao separados: colecao 08_Interativos (portas com a origem na
    dobradica e material a apreender), cada conjunto com 1 malha presa a uma raiz. Os vazios P_* marcam pontos do treinamento.
  - Neblina: usar a fog do motor no lugar do volume do Blender.
  - Quest 3 standalone: alvo de ~750 mil tris e < 200 draw calls; se precisar,
    desligar as casas vizinhas laterais ou gerar LODs (Unity LOD Group / Unreal Nanite
    nao se aplica ao Quest).
""")
say("TOTAL: %d tris, %d malhas, %d slots de material, %d luzes" % (total, len(meshes), slots, len(luzes)))
