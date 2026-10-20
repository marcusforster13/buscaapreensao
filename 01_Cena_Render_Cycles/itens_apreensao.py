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

# ================================================================ itens feitos aqui (sem modelo do usuario): texturas desenhadas
import numpy as np
def imagem(nome, a):
    """a: H x W x 3 (0..1), primeira linha = topo da imagem."""
    h, w = a.shape[:2]; rgba = np.ones((h, w, 4), np.float32); rgba[..., :3] = np.clip(a, 0, 1)
    im = bpy.data.images.new(nome, w, h); im.pixels.foreach_set(np.flipud(rgba).ravel()); im.pack(); return im
def hx(c): return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
def ret(a, x0, y0, x1, y1, cor):                                         # retangulo em fracoes da imagem
    h, w = a.shape[:2]; a[int(y0 * h):max(int(y0 * h) + 1, int(y1 * h)), int(x0 * w):max(int(x0 * w) + 1, int(x1 * w))] = cor
def texto_falso(a, x0, y0, x1, y1, linhas, cor, rr, alt=.45):           # linhas de "texto" (palavras como tracos), para ler de longe
    h = (y1 - y0) / linhas
    for k in range(linhas):
        x = x0; fim = x1 - (rr.uniform(0, .25) * (x1 - x0) if k == linhas - 1 else 0)
        while x < fim:
            p = rr.uniform(.02, .09) * (x1 - x0); ret(a, x, y0 + k * h, min(x + p, fim), y0 + k * h + h * alt, cor); x += p + .012 * (x1 - x0)
def caixa_uv(nome, tam, pos, m, rot=(0, 0, 0)):
    """Caixa com a imagem inteira em cada face (o topo mostra a textura toda)."""
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1); bmesh.ops.scale(bm, vec=tam, verts=bm.verts); uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        ax = max(range(3), key=lambda i: abs(f.normal[i])); iu, iv = ((1, 2), (0, 2), (0, 1))[ax]
        for l in f.loops: l[uv].uv = (l.vert.co[iu] / tam[iu] + .5, l.vert.co[iv] / tam[iv] + .5)
    me = bpy.data.meshes.new(nome); bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(nome, me); bpy.context.scene.collection.objects.link(o); o.location = pos; o.rotation_euler = rot; return o
import random
def folha_impressa(nome, semente, titulo=True, tabela=False):
    rr = random.Random(semente); a = np.ones((724, 512, 3), np.float32) * hx("#f5f3ec"); tinta = hx("#2a2a2e")
    if titulo: ret(a, .12, .07, .55, .095, tinta); ret(a, .12, .11, .4, .12, hx("#6b6b70"))
    texto_falso(a, .12, .16, .88, .45, 11, tinta, rr)
    if tabela:
        for k in range(7): ret(a, .12, .48 + k * .035, .88, .482 + k * .035, hx("#9a9aa0"))
        for x in (.12, .4, .6, .88): ret(a, x, .48, x + .003, .69, hx("#9a9aa0"))
        texto_falso(a, .14, .49, .86, .68, 6, tinta, rr, .35)
    else: texto_falso(a, .12, .5, .88, .75, 9, tinta, rr)
    ret(a, .55, .86, .85, .862, tinta); texto_falso(a, .6, .87, .8, .89, 1, hx("#6b6b70"), rr)      # linha de assinatura
    return imagem(nome, a * (1 + .02 * np.random.default_rng(semente).standard_normal((724, 512, 1))))

# ---- pasta de documentos: pasta de papelao kraft com elastico, folhas impressas por cima
limpar(); rr = random.Random(3)
kr = np.ones((330, 250, 3), np.float32) * hx("#b48a56") * (1 + .05 * np.random.default_rng(1).standard_normal((330, 250, 1)))
ret(kr, .2, .1, .8, .2, hx("#efe9d8")); texto_falso(kr, .24, .12, .76, .18, 2, hx("#38342e"), rr)
m_kr = mat_img("Pasta_Kraft", imagem("pasta_kraft", kr), .85)
objs = [caixa_uv("Pasta", (.25, .33, .008), (0, 0, .004), m_kr)]
for k in range(3):
    objs.append(caixa_uv("Folha_%d" % k, (.21, .297, .0012), (.004 * k - .004, .006 * k - .004, .009 + k * .0013), mat_img("Folha_%d" % k, folha_impressa("folha_%d" % k, k + 4, tabela=k == 2), .9), rot=(0, 0, .04 * k - .03)))
for y in (-.13, .13): objs.append(caixa_uv("Elastico", (.254, .006, .011), (0, y, .006), mat_cor("Elastico", (.02, .02, .02, 1), .6)))
exportar("documentos.glb", objs)

# ---- cartoes bancarios genericos (sem bandeira): chip, numeros em relevo, faixa de cor
limpar(); objs = []
for k, (c1, c2) in enumerate((("#163f8f", "#2d6fd1"), ("#8e1a1a", "#d23a2a"), ("#151517", "#3a3a40"), ("#a8801c", "#e1bd4f"))):
    rr = random.Random(10 + k); H, W = 270, 428; yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    a = hx(c1) * (1 - xx[..., None] / W) + hx(c2) * (xx[..., None] / W); a = a * (1 + .08 * np.sin(xx / W * 9 + yy / H * 4)[..., None])
    ret(a, .09, .35, .24, .58, hx("#d9b45a")); ret(a, .1, .45, .23, .46, hx("#a8873a")); ret(a, .165, .36, .17, .57, hx("#a8873a"))      # chip
    for g in range(4): texto_falso(a, .09 + g * .21, .66, .27 + g * .21, .72, 1, hx("#e8e8e8"), rr, .9)                              # numero
    texto_falso(a, .09, .8, .5, .85, 1, hx("#e0e0e0"), rr, .8); ret(a, .72, .08, .9, .2, hx("#ffffff") * .85)                          # nome e marca generica
    objs.append(caixa_uv("Cartao_%d" % k, (.0856, .054, .0008), (k * .02, k * .01, .0004 + k * .0009), mat_img("Cartao_%d" % k, imagem("cartao_%d" % k, a), .35), rot=(0, 0, k * .3)))
exportar("cartoes.glb", objs)

# ---- tabletes prensados enrolados em fita marrom, com um simbolo carimbado
limpar(); H, W = 256, 512; yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); rng = np.random.default_rng(7)
a = np.ones((H, W, 3), np.float32) * hx("#7a5530") * (1 + .05 * rng.standard_normal((H, W, 1)))
for k in range(-6, 9):                                                    # voltas de fita em diagonal (bordas mais claras)
    d = (xx * .55 + yy - k * 60) % 60; a[(d < 2)] *= 1.1; a[(d > 57)] *= .8; a[(d > 20) & (d < 34)] *= 1.04      # sobreposicao das voltas de fita
cx, cy, R = W * .5, H * .5, 46
ang = np.arctan2(yy - cy, xx - cx); r = np.hypot(xx - cx, yy - cy); est = R * (.55 + .45 * np.cos(5 * ang) ** 2)      # estrela carimbada
a[(r < est) & (r > est - 9)] = hx("#1a1410"); a *= (1 + .12 * (np.sin(xx / W * 30) > .9))[..., None]
m_tb = mat_img("Tablete", imagem("tablete", a), .22)      # fita plastica: brilho
objs = [caixa_uv("Tablete_%d" % k, (.2, .1, .05), (.006 * (k - 1), (k - 1) * .104, .025), m_tb, rot=(0, 0, .03 * (k - 1))) for k in range(3)]      # lado a lado, deitados: cabem na gaveta do criado-mudo
for o in objs:                                                            # quinas arredondadas
    b = o.modifiers.new("Chanfro", "BEVEL"); b.width = .006; b.segments = 2
exportar("droga.glb", objs)

# ---- documentos de outra pessoa: carteira de identidade generica e comprovante em outro nome
limpar(); rr = random.Random(21); H, W = 270, 428
a = np.ones((H, W, 3), np.float32) * hx("#cfe0c8"); yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); a *= (1 + .05 * np.sin(xx / 7 + np.sin(yy / 11) * 2))[..., None]
ret(a, .05, .05, .95, .16, hx("#2f6b3a")); texto_falso(a, .2, .08, .8, .13, 1, hx("#e9f2e6"), rr, .8)
ret(a, .06, .24, .3, .78, hx("#9aa3a8")); ret(a, .12, .3, .24, .5, hx("#6e777c")); ret(a, .09, .52, .27, .78, hx("#6e777c"))       # foto
texto_falso(a, .36, .26, .92, .76, 6, hx("#26302a"), rr, .4); ret(a, .36, .84, .7, .845, hx("#26302a"))
objs = [caixa_uv("Identidade", (.086, .054, .0009), (.06, -.04, .0045), mat_img("Identidade", imagem("identidade", a), .5), rot=(0, 0, .2))]
objs.append(caixa_uv("Comprovante", (.21, .15, .0012), (0, 0, .0006), mat_img("Comprovante", folha_impressa("comprovante", 33, tabela=True), .9)))
exportar("doc_terceiro.glb", objs)
