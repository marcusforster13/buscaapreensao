# Busca e Apreensao - monta os itens da apreensao (celular, notebook, dinheiro) a partir dos modelos do usuario e das
# imagens de referencia (tela do celular, teclado e planilha na tela do notebook) e grava os .glb em 04_ThreeJS/web/modelos.
#   blender -b --factory-startup --python itens_apreensao.py
# Fontes em 01_Cena_Render_Cycles/modelos/itens: celular.glb, notebook.glb, maco_de_notas.glb, tela_celular.webp,
# teclado.webp, planilha.webp. O notebook sai com a tampa aberta e fechada (o site mostra fechada dentro das gavetas).
import bpy, bmesh, os, math
from mathutils import Vector, Matrix
AQUI = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.join(AQUI, "modelos", "itens")
OUT = os.path.join(AQUI, "..", "04_ThreeJS", "web", "modelos")

def limpar(): bpy.ops.wm.read_factory_settings(use_empty=True)
def importar(nome):
    antes = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, nome))
    novos = [o for o in bpy.data.objects if o not in antes]
    for o in novos:                                                       # malha em coordenadas do mundo, sem pais
        if o.type == "MESH": o.data.transform(o.matrix_world)
    for o in novos:
        if o.type == "MESH": o.parent = None; o.matrix_world = Matrix.Identity(4)
    for o in [o for o in novos if o.type != "MESH"]: bpy.data.objects.remove(o)
    return [o for o in novos if o.type == "MESH"]
def img(nome, lado_max=None):
    i = bpy.data.images.load(os.path.join(SRC, nome))
    if lado_max and max(i.size) > lado_max:
        w, h = i.size; k = lado_max / max(w, h); i.scale(int(w * k), int(h * k))
    return i
def mat_cor(nome, cor, rough=.5, metal=0.0):
    m = bpy.data.materials.new(nome); b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = cor; b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    return m
def mat_img(nome, im, rough=.5, brilho=0.0, recorte=False):
    m = bpy.data.materials.new(nome); nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = im; nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    if brilho:                                                            # tela acesa
        nt.links.new(t.outputs["Color"], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = brilho
    if recorte:
        nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
        for a, v in (("surface_render_method", "DITHERED"), ("blend_method", "CLIP")):
            try: setattr(m, a, v)
            except Exception: pass
    b.inputs["Roughness"].default_value = rough; return m
def uv_plano(o, f_uv):
    me = o.data; uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for l in me.loops: uv.data[l.index].uv = f_uv(me.vertices[l.vertex_index].co)
def quad(nome, cx, cy, z, w, h, m):
    me = bpy.data.meshes.new(nome); me.from_pydata([(cx - w / 2, cy - h / 2, z), (cx + w / 2, cy - h / 2, z), (cx + w / 2, cy + h / 2, z), (cx - w / 2, cy + h / 2, z)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for i, c in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))): uv.data[i].uv = c
    me.materials.append(m); o = bpy.data.objects.new(nome, me); bpy.context.scene.collection.objects.link(o); return o
def exportar(nome, objs):
    for o in bpy.context.scene.objects: o.select_set(o in objs)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, nome), use_selection=True, export_format="GLB", export_image_format="AUTO", export_apply=True)
    tri = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    print("[ITENS] %s: %d triangulos, %d KB" % (nome, tri, os.path.getsize(os.path.join(OUT, nome)) // 1024))

# ---------------------------------------------------------------- celular: corpo preto e tela com a imagem (cantos recortados)
limpar(); (c,) = importar("celular.glb")
def _area(ang):                                                           # o modelo vem girado no arquivo: alinha o lado comprido com Y
    R_ = Matrix.Rotation(ang, 3, "Z"); ps = [R_ @ v.co for v in c.data.vertices]
    return (max(p.x for p in ps) - min(p.x for p in ps)) * (max(p.y for p in ps) - min(p.y for p in ps)), max(p.y for p in ps) - min(p.y for p in ps)
ang = min((k * math.pi / 360 for k in range(360)), key=lambda a_: (round(_area(a_)[0], 7), -_area(a_)[1]))
c.data.transform(Matrix.Rotation(ang, 4, "Z")); cc = sum((v.co for v in c.data.vertices), Vector()) / len(c.data.vertices); c.data.transform(Matrix.Translation((-cc.x, -cc.y, 0)))
vs = [v.co.copy() for v in c.data.vertices]; z0 = min(v.z for v in vs); c.data.transform(Matrix.Translation((0, 0, -z0)))
zt = max(v.co.z for v in c.data.vertices); c.name = "Celular_Corpo"; c.data.materials.clear(); c.data.materials.append(mat_cor("Celular_Corpo", (.012, .013, .015, 1), .25, .4))
w = max(v.x for v in vs) - min(v.x for v in vs); h = max(v.y for v in vs) - min(v.y for v in vs)
im = img("tela_celular.webp"); ar = im.size[0] / im.size[1]; hh = min(h * .985, w * .99 / ar)
tela = quad("Celular_Tela", 0, 0, zt + .0004, hh * ar, hh, mat_img("Celular_Tela", im, .15, .5, recorte=True))
exportar("celular.glb", [c, tela])

# ---------------------------------------------------------------- notebook: teclado da referencia projetado de cima, planilha na tela
limpar(); ob = {o.name.split(".")[0] + ("_" + o.name.split(".")[1] if "." in o.name else ""): o for o in importar("notebook.glb")}
tec = img("teclado.webp"); W, H = tec.size; esc = .0002207 * 1536 / W      # metros por pixel (a imagem e uma vista de cima na mesma escala)
def uv_teclado(co):                                                       # imagem: Esc no canto do lado +Y, perto da dobradica
    px = 88 * W / 1536 + (.15 - co.y) / esc; py = 122 * H / 1024 + (.059 - co.x) / esc
    px = min(max(px, 50 * W / 1536), 1488 * W / 1536); py = min(max(py, 58 * H / 1024), 968 * H / 1024)      # fica na chapa cinza (fora dela a imagem e branca)
    return (px / W, 1 - py / H)
m_tec = mat_img("Teclado_Notebook", tec, .55)
for n in ("I_Notebook_Base", "Cube", "Cube_001"):
    o = ob[n]; o.data.materials.clear(); o.data.materials.append(m_tec); uv_plano(o, uv_teclado)
pla = img("planilha.webp"); W2, H2 = pla.size; x0, x1, y0, y1 = 87 * W2 / 1536, 1450 * W2 / 1536, 104 * H2 / 1024, 958 * H2 / 1024
ta = ob["I_Notebook_Tela_Acesa"]; zs = [v.co.z for v in ta.data.vertices]; za, zb = min(zs), max(zs)
ta.data.materials.clear(); ta.data.materials.append(mat_img("Tela_Planilha", pla, .2, .35))
uv_plano(ta, lambda co: ((x0 + (.15 - co.y) / .30 * (x1 - x0)) / W2, 1 - (y1 - (co.z - za) / (zb - za) * (y1 - y0)) / H2))
tp = ob["I_Notebook_Tela"]; tp.data.materials.clear(); tp.data.materials.append(mat_cor("Tampa_Notebook", (.28, .29, .3, 1), .45, .5))
# tampa fechada: copia da tampa girada na dobradica ate deitar sobre o teclado
baixo = [v.co for v in tp.data.vertices if v.co.z < .05]; cima = [v.co for v in tp.data.vertices if v.co.z > .2]
pb = sum(baixo, Vector()) / len(baixo); pc = sum(cima, Vector()) / len(cima); d = pc - pb
fi = math.atan2(d.z, d.x); piv = Vector((max(v.co.x for v in tp.data.vertices if v.co.z < .05), 0, min(v.co.z for v in tp.data.vertices)))
R = Matrix.Translation(piv) @ Matrix.Rotation(fi - math.pi, 4, "Y") @ Matrix.Translation(-piv)
fech = []
for o, nome in ((tp, "Tampa_Fechada"), (ta, "Tela_Fechada")):
    f = o.copy(); f.data = o.data.copy(); f.name = nome; bpy.context.scene.collection.objects.link(f); f.data.transform(R); fech.append(f)
topo = max(v.co.z for v in ob["I_Notebook_Base"].data.vertices)      # deita na chapa (as teclas ficam dentro da tampa)
dz = topo + .0005 - min(v.co.z for f in fech for v in f.data.vertices)
for f in fech: f.data.transform(Matrix.Translation((0, 0, dz)))
tp.name = "Tampa_Aberta"; ta.name = "Tela_Aberta"
exportar("notebook.glb", list(ob.values()) + fech)

# ---------------------------------------------------------------- dinheiro: seis macos de notas (2 x 3), como no treinamento
limpar(); (mc,) = importar("maco_de_notas.glb")
for i in list(bpy.data.images):
    if max(i.size) > 1024: w_, h_ = i.size; i.scale(1024, max(1, int(h_ * 1024 / w_)))
zs = [v.co.z for v in mc.data.vertices]; mc.data.transform(Matrix.Translation((0, 0, -min(zs)))); hz = max(zs) - min(zs)
macos = []
for k in range(6):
    o = mc if k == 0 else mc.copy()
    if k: bpy.context.scene.collection.objects.link(o)
    o.name = "Maco_%d" % (k + 1); o.location = ((k % 2) * .165 - .0825, 0, (k // 2) * (hz + .001)); o.rotation_euler = (0, 0, (k * .37 % .1) - .05)
    macos.append(o)
exportar("dinheiro.glb", macos)
