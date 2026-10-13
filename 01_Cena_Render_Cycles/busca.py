"""
Busca e Apreensao - cena base para Blender 5.x (gera busca.blend do zero)

Predio residencial do Rio de Janeiro, DE DIA (mandado em casa so se cumpre durante o dia): portaria no terreo,
corredor do 3o andar com quatro portas numeradas (301 a 304), elevador e escada, o apartamento 302 completo (sala,
cozinha, area de servico, dois quartos e banheiro) e a sala do vizinho 301 (variacao de endereco errado).

Objetos A_* ABREM no site (gavetas, portas de armario, portas dos comodos): a raiz fica na dobradica ou na frente da
gaveta e leva as propriedades "abre", "curso"/"ang" e "eixo". Objetos I_* sao material a apreender. Vazios P_* sao
pontos usados pelo site. Pecas Mv_* sao o casco dos moveis (ficam fora da colisao: cada movel tem uma caixa Col_*).

Uso:  blender -b --factory-startup --python busca.py
Unidades em metros. X = ao longo da rua (leste +), Y = para dentro do terreno (norte +), Z = para cima.
Sem logotipos de marcas e sem brasoes oficiais.
"""
import bpy, bmesh, math, random, os
import numpy as np
from mathutils import Vector, Matrix

PI = math.pi
rnd = random.Random(2026)
try:
    AQUI = os.path.dirname(os.path.abspath(__file__))
except NameError:
    AQUI = os.path.join(os.path.expanduser("~"), "Desktop", "buscaeapreensao", "01_Cena_Render_Cycles")

def say(m): print("[BUSCA] " + m)

# ------------------------------------------------------------------ limpeza
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)
scene = bpy.context.scene

def collection(name):
    c = bpy.data.collections.new(name); scene.collection.children.link(c); return c

# ------------------------------------------------------------------ materiais
def hx(h): return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
def lin(c): return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)

def mat(name, color, rough=.8, metal=0., emit=None, forca=0., alpha=None):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes.get("Principled BSDF")
    c = lin(hx(color))
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*lin(hx(emit)), 1)
        b.inputs["Emission Strength"].default_value = forca
    if alpha is not None:
        b.inputs["Alpha"].default_value = alpha
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
            try: setattr(m, attr, val)
            except Exception: pass
    m.diffuse_color = (*c, 1 if alpha is None else alpha)
    return m

def np_image(name, arr):
    h, w, _ = arr.shape
    rgba = np.ones((h, w, 4), dtype=np.float32); rgba[..., :3] = arr
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(np.flipud(rgba).ravel()); img.pack()
    return img

def img_mat(name, img, tile_m, rough=.6):
    """Textura gerada, projetada em caixa (coordenadas do objeto, em metros)."""
    m = bpy.data.materials.new(name); nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / tile_m,) * 3
    tex.projection = "BOX"; tex.projection_blend = .1
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (.5, .5, .5, 1)
    return m

def tex_ceramica(cor, rejunte="#8d8a84", S=256, n=4):
    r = np.random.default_rng(int(sum(cor) * 1000)); cel = S // n
    a = np.kron(r.uniform(.94, 1.03, (n, n, 1)), np.ones((cel, cel, 1))) * np.array(cor)
    a *= (1 + .02 * r.standard_normal((S, S, 1)))
    yy, xx = np.mgrid[0:S, 0:S]
    a[(xx % cel < 2) | (yy % cel < 2)] = np.array(hx(rejunte))
    return np.clip(a, 0, 1)

def tex_granito(S=256):
    r = np.random.default_rng(9); a = np.ones((S, S, 3)) * np.array(hx("#2a2a2d"))
    a += r.standard_normal((S, S, 1)) * .035; p = r.random((S, S)) > .985
    a[p] = np.array(hx("#8a8a8c")); return np.clip(a, 0, 1)

M = {
    "asfalto": mat("Asfalto", "#3a3a3c", .9), "calcada": mat("Calcada_Concreto", "#a8a49a", .95),
    "grama": mat("Grama", "#4d6b3a", 1), "meiofio": mat("Meio_Fio_Concreto", "#9c988f", .95),
    "concreto": mat("Concreto_Aparente", "#a19d95", .95),
    "fach": mat("Fachada_Areia", "#d6c8a6", .92), "fach2": mat("Fachada_Branca", "#e2ded2", .92),
    "fach3": mat("Fachada_Terracota", "#b0745a", .92), "fach4": mat("Fachada_Cinza", "#9a9ca0", .92),
    "janela_ext": mat("Janela_Fachada", "#1a2530", .15),
    "parede": mat("Parede_Apto", "#e8e3d6", .92), "parede_cor": mat("Parede_Corredor", "#d8d2c0", .92),
    "parede_port": mat("Parede_Portaria", "#dcd6c6", .92), "teto": mat("Teto_Laje", "#efede6", .95),
    "piso_lam": mat("Piso_Laminado", "#a57c52", .5),
    "piso_cer": img_mat("Piso_Ceramica", np_image("piso_ceramica", tex_ceramica(hx("#d3cdbf"))), 1.8, .35),
    "piso_cor": img_mat("Piso_Porcelanato", np_image("piso_porcelanato", tex_ceramica(hx("#b9b3a6"), "#77736b", n=2)), 1.2, .3),
    "piso_port": img_mat("Piso_Granito_Portaria", np_image("piso_portaria", tex_ceramica(hx("#9c958a"), "#5d5a55", n=2)), 1.6, .25),
    "azulejo": img_mat("Azulejo_Branco", np_image("azulejo_branco", tex_ceramica(hx("#e6e4dc"), "#a5a39c", n=8)), 1.6, .2),
    "granito": img_mat("Granito_Preto", np_image("granito_preto", tex_granito()), .6, .25),
    "rodape": mat("Rodape_Branco", "#e6e2d8", .6),
    "mdf_br": mat("MDF_Branco", "#ece9e1", .45), "mdf_int": mat("MDF_Interno", "#d8d2c4", .7),
    "mad": mat("Madeira_Movel", "#9a7650", .55), "mad_esc": mat("Madeira_Escura_Movel", "#5a3d2a", .5),
    "porta_mad": mat("Porta_Madeira", "#7a5638", .55), "porta_br": mat("Porta_Branca", "#e9e6de", .5),
    "porta_ferro": mat("Porta_Corta_Fogo", "#8f2f28", .5), "aco_elev": mat("Aco_Elevador", "#a9acb0", .35, .4),
    "metal": mat("Metal_Escovado", "#9a9c9e", .35, .4), "inox": mat("Inox", "#c2c5c8", .3, .45),
    "aluminio": mat("Aluminio_Esquadria", "#c9cbcd", .4, .3), "preto": mat("Preto_Fosco", "#17181a", .6),
    "vidro": mat("Vidro_Janela", "#cfe2ea", .05, alpha=.14), "espelho": mat("Espelho", "#c8d2d6", .08, .5),
    "branco": mat("Plastico_Branco", "#eceae4", .45), "louca": mat("Louca_Branca", "#f1efe9", .2),
    "geladeira": mat("Geladeira_Branca", "#e9e9e6", .35), "fogao": mat("Fogao_Inox", "#b4b6b8", .4, .35),
    "colchao": mat("Colchao", "#e2ddd0", .9), "lencol": mat("Lencol_Azul", "#6f8fb0", .9), "lencol2": mat("Lencol_Cinza", "#8b8f94", .9),
    "travesseiro": mat("Travesseiro", "#eeeae0", .9), "roupa_a": mat("Roupa_Azul", "#2f4a6e", .9), "roupa_b": mat("Roupa_Vermelha", "#8e2f2a", .9),
    "roupa_c": mat("Roupa_Branca", "#e4e0d6", .9), "roupa_d": mat("Roupa_Cinza", "#5c5f63", .9), "roupa_e": mat("Roupa_Verde", "#476349", .9),
    "tecido_cad": mat("Tecido_Cadeira", "#6b5c4c", .9), "tapete": mat("Tapete", "#8a6f5a", 1), "cortina": mat("Cortina_Branca", "#e2dfd6", .95),
    "papel": mat("Papel", "#f4f1e8", .9), "papelao": mat("Caixa_Papelao", "#a9825a", .9),
    "texto_pr": mat("Texto_Preto", "#111111", .6), "texto_br": mat("Texto_Branco", "#f4f4f0", .6), "texto_dour": mat("Texto_Dourado", "#b08d3c", .4, .4),
    "lamp": mat("Lampada_Plafon", "#ffffff", .4, emit="#fff0d8", forca=10), "lamp_f": mat("Lampada_Fria", "#ffffff", .4, emit="#eef4ff", forca=10),
    "led_verm": mat("Led_Vermelho", "#400808", .3, emit="#ff2a1a", forca=3), "tela": mat("Tela_Apagada", "#0c0d10", .15),
    "extintor": mat("Extintor_Vermelho", "#b3201a", .4), "capacho": mat("Capacho", "#5a4a38", 1),
}

# ------------------------------------------------------------------ geometria
def finish(name, bm, loc, mats, col, parent=None, rot=(0, 0, 0), smooth=False, bevel=0.0, seg=2):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = smooth
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]): me.materials.append(m)
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    if parent: ob.parent = parent
    ob.location = loc; ob.rotation_euler = rot
    if bevel:
        b = ob.modifiers.new("Chanfro", "BEVEL"); b.width = bevel; b.segments = seg; b.limit_method = "ANGLE"
        for p in me.polygons: p.use_smooth = True
    return ob

def box(name, tam, pos, m, col, parent=None, rot=(0, 0, 0), bevel=0.0, seg=2):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1); bmesh.ops.scale(bm, vec=Vector(tam), verts=bm.verts)
    return finish(name, bm, pos, m, col, parent, rot, bevel=bevel, seg=seg)

def cyl(name, r1, r2, h, pos, m, col, parent=None, rot=(0, 0, 0), seg=20):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=h)
    return finish(name, bm, pos, m, col, parent, rot, smooth=True)

def barra(name, a, b, r, m, col, parent=None, seg=10):
    """Cilindro fino entre dois pontos."""
    a, b = Vector(a), Vector(b); d = b - a
    ob = cyl(name, r, r, d.length, (a + b) / 2, m, col, parent, seg=seg)
    ob.rotation_euler = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()
    return ob

def plano(name, x0, x1, y0, y1, z, m, col, para_baixo=False):
    """Retangulo horizontal (tetos: so a face de baixo, para nao gastar lightmap com a face escondida)."""
    vs = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], [(3, 2, 1, 0) if para_baixo else (0, 1, 2, 3)])
    me.materials.append(m); ob = bpy.data.objects.new(name, me); col.objects.link(ob); return ob

def texto_malha(conteudo, tam, espaco=1.0):
    cu = bpy.data.curves.new("_txt", "FONT"); cu.body = conteudo; cu.size = tam; cu.align_x = "CENTER"; cu.align_y = "CENTER"
    cu.resolution_u = 2; cu.space_character = espaco
    tmp = bpy.data.objects.new("_txt_tmp", cu); scene.collection.objects.link(tmp)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp, do_unlink=True); bpy.data.curves.remove(cu)
    return me

# para onde o texto fica virado (quem le esta desse lado)
VIRADO = {"-y": (PI / 2, 0, 0), "+y": (PI / 2, 0, PI), "-x": (PI / 2, 0, -PI / 2), "+x": (PI / 2, 0, PI / 2), "cima": (0, 0, 0)}
def texto(name, conteudo, tam, pos, virado, m, col, parent=None, espaco=1.0):
    me = texto_malha(conteudo, tam, espaco); me.name = name; me.materials.append(m)
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    if parent: ob.parent = parent
    ob.location = pos; ob.rotation_euler = VIRADO[virado] if isinstance(virado, str) else virado
    return ob

def vazio(name, pos, col, rz=0.0, parent=None):
    e = bpy.data.objects.new(name, None); col.objects.link(e); e.location = pos; e.rotation_euler = (0, 0, rz)
    e.empty_display_size = .15
    if parent: e.parent = parent
    return e

def luz(name, tipo, watts, cor, pos, col, parent=None, alvo=None, **kw):
    l = bpy.data.lights.new(name, tipo); l.energy = watts; l.color = lin(hx(cor))
    for k, v in kw.items(): setattr(l, k, v)
    ob = bpy.data.objects.new(name, l); col.objects.link(ob); ob.location = pos
    if parent: ob.parent = parent
    if alvo is not None:
        ob.rotation_euler = (Vector(alvo) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    return ob

# ================================================================== PLANTA (metros)
#   rua             y -16 .. -9       calcada  y -9 .. -6.1
#   PREDIO (Bloco B) x -9 .. 8.1, y -6.1 .. 9.1, quatro andares
#   terreo:  PORTARIA x -6.4 .. 1, y -6 .. 1.6 (entrada na fachada sul; elevador na parede oeste)
#   3o andar (piso a 6,45 m):
#     corredor      x -6.4 .. 8,  y 0 .. 1.6     elevador na ponta oeste; escada x -6.4 .. -3.8, y -3.2 .. 0
#     portas        301 (norte, x -3.4 .. -2.5)  302 (norte, x 3.5 .. 4.4)  303 e 304 (sul, fechadas)
#     APTO 302      x -1 .. 8, y 1.6 .. 9
#       banheiro  x -1 .. 1.8, y 1.6 .. 4.0     circulacao x 1.8 .. 3.1, y 1.6 .. 5.5
#       cozinha   x -1 .. 1.8, y 4.0 .. 6.8     sala       x 3.1 .. 8,   y 1.6 .. 5.5 (janela leste)
#       servico   x -1 .. 1.8, y 6.8 .. 9.0     quarto 2   x 1.8 .. 4.8, y 5.5 .. 9 (inquilino, tranca)
#                                               quarto 1   x 4.8 .. 8,   y 5.5 .. 9 (casal)
#     APTO 301 (vizinho, so a sala)  x -6.4 .. -1, y 1.6 .. 5.6
#   patio e BLOCO A ao norte (visto das janelas dos quartos): x -9 .. 8.1, y 24 .. 36
FZ = .15                       # piso do terreo e da calcada
PDT = 3.0                      # pe-direito da portaria
Z3 = 6.45                      # piso do 3o andar
PD = 2.7                       # pe-direito dos apartamentos

C_RUA = collection("01_Rua_Patio"); C_PRED = collection("02_Predio"); C_PORT = collection("03_Portaria")
C_COR = collection("04_Corredor_Escada"); C_EST = collection("05_Apto_Estrutura"); C_SAL = collection("06_Sala")
C_COZ = collection("07_Cozinha_Servico"); C_INT = collection("08_Interativos"); C_LUZ = collection("09_Luzes_Cameras")
C_QUA = collection("10_Quartos"); C_BAN = collection("11_Banheiro"); C_VIZ = collection("12_Vizinho_301")
C_VID = collection("13_Vidros")          # sem lightmap e fora do bake: o sol entra pelas janelas
C_MIU = collection("14_Miudos")          # pecas pequenas ou finas, sem lightmap (sairiam manchadas)
C_COL = collection("98_Colisao_Extra")   # caixas invisiveis: uma por movel que abre (o jogador nao entra no armario)

def parede(nome, a, b, m, col, vaos=(), h=PD, t=.2, z0=Z3, ext=None):
    """Parede reta entre a=(x, y) e b=(x, y), alinhada a um eixo, com vaos [(d0, d1, zbase, ztopo)] medidos a partir de a.
    Cada trecho e uma caixa separada: a malha de colisao usa uma caixa por objeto, entao os vaos ficam livres."""
    ax, ay = a; bx, by = b; horiz = abs(bx - ax) > abs(by - ay)
    L = abs(bx - ax) if horiz else abs(by - ay); sg = 1 if ((bx - ax) if horiz else (by - ay)) > 0 else -1
    def trecho(d0, d1, zb, zt, suf):
        if d1 - d0 < .01 or zt - zb < .01: return
        c = (d0 + d1) / 2
        pos = (ax + sg * c, ay, z0 + (zb + zt) / 2) if horiz else (ax, ay + sg * c, z0 + (zb + zt) / 2)
        box(nome + suf, (d1 - d0, t, zt - zb) if horiz else (t, d1 - d0, zt - zb), pos, m, col)
    if ext is None: ext = t / 2 if t >= .2 else -.07      # paredes internas param dentro da parede vizinha (sem faces coincidentes)
    d = -ext
    for v0, v1, zb, zt in sorted(vaos):
        trecho(d, v0, 0, h, ""); trecho(v0, v1, 0, zb, "_Mureta"); trecho(v0, v1, zt, h, "_Verga"); d = v1
    trecho(d, L + ext, 0, h, "")

def camera(nome, pos, alvo, lente=18):
    cd = bpy.data.cameras.new(nome); cd.lens = lente; cd.clip_end = 400
    ob = bpy.data.objects.new(nome, cd); C_LUZ.objects.link(ob); ob.location = pos
    ob.rotation_euler = (Vector(alvo) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    return ob

def ponto(nome, x, y, olha=(0, -1), z=Z3):
    """Ponto usado pelo site (personagens, rotas, elevador): vazio P_<nome>; rz = para onde a pessoa olha."""
    return vazio("P_" + nome, (x, y, z), C_LUZ, math.atan2(olha[0], -olha[1]))

# ---- modelos prontos do Poly Haven (CC0): modelos/polyhaven/<nome>/ (baixados por modelos/baixar_polyhaven.py)
PH_DIR = os.path.join(AQUI, "modelos", "polyhaven"); _ph = {}
def modelo_ph(nome, asset, pos, rz=0.0, col=None, escala=1.0, max_tris=2000, alt=None, parent=None):
    """Importa o modelo uma vez (junta numa malha, reduz os triangulos, base no chao e centro em XY) e reaproveita a
    malha nas copias. Os materiais ganham o prefixo Modelo_ para o pipeline manter a UV original. Devolve None se faltar."""
    if asset not in _ph:
        caminho = os.path.join(PH_DIR, asset, asset + "_1k.gltf")
        if not os.path.exists(caminho): _ph[asset] = None
        else:
            antes = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=caminho); bpy.context.view_layer.update()
            novos = [o for o in bpy.data.objects if o not in antes]; malhas = [o for o in novos if o.type == "MESH"]
            for o in malhas:
                mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
            if len(malhas) > 1:
                with bpy.context.temp_override(active_object=malhas[0], selected_objects=malhas, selected_editable_objects=malhas):
                    bpy.ops.object.join()
            ob = malhas[0]; ob.data.transform(ob.matrix_world); ob.matrix_world = Matrix.Identity(4)
            for i, sl in enumerate(ob.material_slots):
                if sl.material: sl.material.name = "Modelo_PH_%s_%d" % (asset, i)
            tris = sum(len(pl.vertices) - 2 for pl in ob.data.polygons)
            if tris > max_tris:
                d = ob.modifiers.new("Reduzir", "DECIMATE"); d.ratio = max_tris / tris
                me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get())); ob.modifiers.clear()
            else: me = ob.data.copy()
            vs = [v.co for v in me.vertices]
            mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))); mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
            me.transform(Matrix.Translation((-(mn.x + mx.x) / 2, -(mn.y + mx.y) / 2, -mn.z)))
            for pl in me.polygons: pl.use_smooth = True
            me.name = "PH_" + asset
            for o in [o for o in bpy.data.objects if o not in antes]: bpy.data.objects.remove(o, do_unlink=True)
            _ph[asset] = (me, mx - mn)
    if not _ph[asset]: return None
    me, dims = _ph[asset]
    ob = bpy.data.objects.new(nome, me); (col or C_SAL).objects.link(ob)
    if parent: ob.parent = parent
    k = escala if alt is None else alt / dims.z
    ob.location = pos; ob.rotation_euler = (0, 0, rz); ob.scale = (k, k, k)
    return ob

def plafon(nome, x, y, watts, z=Z3 + PD, col=C_EST, cor="#fff0d8", m="lamp"):
    cyl(nome + "_Plafon", .15, .13, .05, (x, y, z - .025), M[m], col, seg=20)
    luz(nome + "_Luz", "POINT", watts, cor, (x, y, z - .22), C_LUZ, shadow_soft_size=.18)

def janela(nome, cx, cy, ao_longo_x, larg, zb, zt, col, z0=Z3, folhas=2):
    """Esquadria de aluminio com vidro no vao de uma parede (o vidro fica fora do bake para o sol entrar)."""
    alt = zt - zb; zc = z0 + (zb + zt) / 2
    def pc(suf, tl, th, dl, dz, m=M["aluminio"], c=col, esp=.07):
        box(nome + suf, (tl, esp, th) if ao_longo_x else (esp, tl, th), (cx + dl, cy, zc + dz) if ao_longo_x else (cx, cy + dl, zc + dz), m, c)
    pc("_Quadro_Cima", larg, .04, 0, alt / 2 - .02); pc("_Quadro_Baixo", larg, .04, 0, -alt / 2 + .02)
    for s in (-1, 1): pc("_Quadro_Lado", .04, alt, s * (larg / 2 - .02), 0)
    for k in range(1, folhas): pc("_Montante", .04, alt, -larg / 2 + k * larg / folhas, 0, esp=.05)
    pc("_Vidro", larg - .06, alt - .06, 0, 0, M["vidro"], C_VID, .008)
    pc("_Peitoril", larg + .1, .03, 0, -alt / 2 - .015, M["granito"], col, .26)

# ================================================================== 1. rua, patio e vizinhanca
box("Terreno", (110, 100, .1), (0, 10, -.05), M["grama"], C_RUA)
box("Asfalto", (90, 7, .12), (0, -12.5, .06), M["asfalto"], C_RUA)
box("Calcada", (90, 2.9, FZ), (0, -7.55, FZ / 2), M["calcada"], C_RUA)
box("Meio_Fio", (90, .18, .2), (0, -9.05, .1), M["meiofio"], C_RUA)
box("Patio_Piso", (30, 15, FZ), (0, 16.6, FZ / 2), M["calcada"], C_RUA)          # patio entre os blocos

def bloco(nome, x0, x1, y0, y1, andares, m, face, rotulo=None, col=C_RUA):
    """Predio vizinho: caixa com fileiras de janelas na face indicada ('-y', '+y', '-x', '+x')."""
    h = .6 + andares * 3.15
    box(nome, (x1 - x0, y1 - y0, h), ((x0 + x1) / 2, (y0 + y1) / 2, FZ + h / 2), m, col)
    ao_x = face in ("-y", "+y"); comp = (x1 - x0) if ao_x else (y1 - y0); n = max(2, int(comp / 2.6))
    for a in range(andares):
        for k in range(n):
            d = -comp / 2 + (k + .5) * comp / n; z = FZ + 1.9 + a * 3.15
            if ao_x: pos = ((x0 + x1) / 2 + d, y0 - .02 if face == "-y" else y1 + .02, z); tam = (1.4, .05, 1.2)
            else: pos = (x0 - .02 if face == "-x" else x1 + .02, (y0 + y1) / 2 + d, z); tam = (.05, 1.4, 1.2)
            box(nome + "_Janela", tam, pos, M["janela_ext"], col)
    if rotulo:
        pos = ((x0 + x1) / 2, y0 - .03, FZ + h - .9) if face == "-y" else ((x0 + x1) / 2, y1 + .03, FZ + h - .9)
        texto(nome + "_Texto", rotulo, .9, pos, face, M["texto_pr"], col)
bloco("Bloco_A", -9, 8.1, 24, 36, 4, M["fach2"], "-y", "BLOCO A")
bloco("Vizinho_Leste", 20, 32, -4, 20, 5, M["fach4"], "-x")
bloco("Vizinho_Oeste", -30, -17, -6, 12, 3, M["fach3"], "+x")
for i, (x0, x1, an, m) in enumerate(((-34, -22, 3, "fach3"), (-21, -8, 5, "fach2"), (-7, 6, 4, "fach4"), (7, 19, 6, "fach"), (20, 34, 3, "fach3"))):
    bloco("Predio_Frente_%d" % i, x0, x1, -28, -17, an, M[m], "+y")

# ================================================================== 2. o predio (Bloco B): massas e fachada
HT = FZ + 4 * 3.15                                      # topo do 4o andar
box("Predio_Terreo_Leste", (7.0, 15.2, PDT), (4.6, 1.5, FZ + PDT / 2), M["fach"], C_PRED)
box("Predio_Terreo_Norte", (7.4, 7.4, PDT), (-2.7, 5.4, FZ + PDT / 2), M["fach"], C_PRED)
box("Predio_Terreo_Oeste", (2.5, 15.2, PDT), (-7.75, 1.5, FZ + PDT / 2), M["fach"], C_PRED)
for k, (x0, x1, y0, y1) in enumerate(((-3.8, 8.1, -6.1, 9.1), (-9, -3.8, -6.1, -3.3), (-9, -6.5, -3.3, 9.1), (-6.5, -3.8, .1, 9.1))):      # 2o andar, com o vazio da escada
    box("Predio_Andar_2_%d" % k, (x1 - x0, y1 - y0, Z3 - .15 - FZ - PDT), ((x0 + x1) / 2, (y0 + y1) / 2, (FZ + PDT + Z3 - .15) / 2), M["fach"], C_PRED)
box("Escada_Fundo", (2.7, 3.3, .1), (-5.15, -1.65, Z3 - 1.35), M["concreto"], C_COR)
box("Predio_3_Sul", (11.9, 6.0, PD + .15), (2.15, -3.1, Z3 - .15 + (PD + .15) / 2), M["fach"], C_PRED)          # aptos 303 e 304 (fechados)
box("Predio_3_Sudoeste", (5.2, 2.8, PD + .15), (-6.4, -4.7, Z3 - .15 + (PD + .15) / 2), M["fach"], C_PRED)
box("Predio_3_Oeste", (2.5, 12.4, PD + .15), (-7.75, 2.9, Z3 - .15 + (PD + .15) / 2), M["fach"], C_PRED)         # caixa do elevador
box("Predio_3_Fundo_301", (5.3, 3.4, PD + .15), (-3.75, 7.4, Z3 - .15 + (PD + .15) / 2), M["fach"], C_PRED)
box("Predio_Andar_4", (17.1, 15.2, HT + .9 - Z3 - PD), (-.45, 1.5, (Z3 + PD + HT + .9) / 2), M["fach"], C_PRED)
box("Predio_Marquise", (4.4, 1.3, .14), (-2.7, -6.7, FZ + 2.75), M["concreto"], C_PRED)
texto("Predio_Texto_Bloco", "BLOCO B", .32, (-2.7, -7.36, FZ + 2.75), "-y", M["texto_pr"], C_PRED)
texto("Predio_Texto_Numero", "Rua das Acácias, 120", .13, (-2.7, -6.14, FZ + 2.58), "-y", M["texto_pr"], C_PRED)
for a in (1, 3):                                         # janelas de enfeite na fachada sul (2o e 4o andares)
    for k in range(6):
        box("Predio_Janela_Sul", (1.4, .05, 1.2), (-7.2 + k * 2.7, -6.12, FZ + 1.9 + a * 3.15), M["janela_ext"], C_PRED)
for k in range(4):
    box("Predio_Janela_Sul", (1.4, .05, 1.2), (-1.8 + k * 2.7, -6.12, FZ + 1.9 + 2 * 3.15), M["janela_ext"], C_PRED)

# ================================================================== 3. portaria (terreo)
box("Portaria_Piso", (7.4, 7.6, FZ), (-2.7, -2.2, FZ / 2), M["piso_port"], C_PORT)
plano("Portaria_Teto", -6.4, 1, -6, 1.6, FZ + PDT - .001, M["teto"], C_PORT, True)
parede("Portaria_Parede_Sul", (-6.4, -6), (1, -6), M["parede_port"], C_PORT, vaos=[(.5, 2.2, .5, 2.4), (2.7, 4.7, 0, 2.4), (5.2, 6.9, .5, 2.4)], h=PDT, z0=FZ)
parede("Portaria_Parede_Oeste", (-6.4, -6), (-6.4, 1.6), M["parede_port"], C_PORT, h=PDT, z0=FZ)
parede("Portaria_Parede_Norte", (-6.4, 1.6), (1, 1.6), M["parede_port"], C_PORT, h=PDT, z0=FZ)
parede("Portaria_Parede_Leste", (1, -6), (1, 1.6), M["parede_port"], C_PORT, h=PDT, z0=FZ)
janela("Portaria_Vidro_O", -5.05, -6, True, 1.7, .5, 2.4, C_PORT, FZ, 1); janela("Portaria_Vidro_L", -.35, -6, True, 1.7, .5, 2.4, C_PORT, FZ, 1)
for s in (-1, 1):                                         # porta de vidro da entrada: duas folhas abertas para dentro
    box("Portaria_Entrada_Batente", (.06, .1, 2.4), (-2.7 + s * .97, -6, FZ + 1.2), M["aluminio"], C_PORT)
    box("Portaria_Entrada_Folha", (.03, .92, 2.3), (-2.7 + s * .93, -5.5, FZ + 1.17), M["vidro"], C_VID)
    box("Portaria_Entrada_Puxador", (.03, .03, .5), (-2.7 + s * .9, -5.12, FZ + 1.1), M["inox"], C_MIU)
box("Portaria_Entrada_Verga", (2.0, .1, .06), (-2.7, -6, FZ + 2.37), M["aluminio"], C_PORT)
box("Portaria_Capacho", (1.6, .8, .012), (-2.7, -5.3, FZ + .006), M["capacho"], C_PORT)
# balcao do porteiro (canto leste), com interfone, livro de ocorrencias e quadro de chaves
box("Portaria_Balcao_Frente", (.08, 2.4, 1.1), (-.9, -2.6, FZ + .55), M["mad_esc"], C_PORT)
box("Portaria_Balcao_Tampo", (.5, 2.5, .04), (-.72, -2.6, FZ + 1.12), M["granito"], C_PORT)
box("Portaria_Balcao_Mesa", (.7, 2.3, .04), (-.5, -2.6, FZ + .74), M["mad"], C_PORT)
box("Portaria_Balcao_Lado", (.9, .06, 1.1), (-.46, -3.8, FZ + .55), M["mad_esc"], C_PORT)
box("Portaria_Interfone", (.22, .3, .1), (-.4, -1.9, FZ + .81), M["preto"], C_MIU)
box("Portaria_Livro", (.3, .22, .03), (-.5, -2.7, FZ + .775), M["roupa_a"], C_MIU)
box("Portaria_Monitor", (.04, .5, .32), (-.25, -3.3, FZ + 1.02), M["tela"], C_MIU)
box("Portaria_Quadro_Chaves", (.04, .6, .45), (.88, -2.6, FZ + 1.6), M["mad"], C_PORT)
texto("Portaria_Texto_Portaria", "PORTARIA", .12, (.86, -2.6, FZ + 2.05), "-x", M["texto_pr"], C_PORT)
box("Portaria_Cadeira_Assento", (.45, .45, .08), (-.1, -2.6, FZ + .48), M["preto"], C_PORT)
box("Portaria_Cadeira_Encosto", (.06, .42, .5), (.14, -2.6, FZ + .8), M["preto"], C_PORT)
cyl("Portaria_Cadeira_Pe", .03, .03, .44, (-.1, -2.6, FZ + .22), M["metal"], C_PORT, seg=8)
# caixas de correio, quadro de avisos, banco de espera e vasos
for a in range(4):
    for k in range(4):
        box("Portaria_Correio", (.04, .28, .14), (-6.28, -4.6 + k * .31, FZ + 1.0 + a * .17), M["metal"], C_PORT)
        texto("Portaria_Correio_Num", "%d0%d" % (a + 1, k + 1), .035, (-6.255, -4.6 + k * .31, FZ + 1.0 + a * .17), "+x", M["texto_pr"], C_MIU)
box("Portaria_Avisos", (.03, 1.0, .7), (-6.28, -2.4, FZ + 1.55), M["tapete"], C_PORT)
for k, (dy, dz) in enumerate(((-.25, .12), (.2, .1), (-.05, -.15))):
    box("Portaria_Aviso_Papel", (.005, .21, .29), (-6.26, -2.4 + dy, FZ + 1.55 + dz), M["papel"], C_MIU)
texto("Portaria_Texto_Avisos", "AVISOS DO CONDOMÍNIO", .05, (-6.26, -2.4, FZ + 1.97), "+x", M["texto_pr"], C_MIU)
modelo_ph("Portaria_Sofa", "sofa_02", (-4.6, .95, FZ), 0, C_PORT, max_tris=2500, alt=.8) or box("Portaria_Banco", (1.6, .5, .45), (-4.6, 1.2, FZ + .22), M["mad"], C_PORT)
modelo_ph("Portaria_Planta_A", "potted_plant_01", (-5.9, -5.5, FZ), 0, C_PORT, max_tris=2500, alt=1.1)
modelo_ph("Portaria_Planta_B", "potted_plant_02", (.5, -5.5, FZ), 1.0, C_PORT, max_tris=2500, alt=.9)
plafon("Luz_Portaria_A", -2.7, -3.6, 110, FZ + PDT, C_PORT); plafon("Luz_Portaria_B", -2.7, -.4, 110, FZ + PDT, C_PORT)

def elevador(nome, y0, z0, col, andar):
    """Porta do elevador na parede oeste (x = -6.4): duas folhas de aco fechadas, batente, botao e indicador."""
    x = -6.29
    box(nome + "_Batente", (.06, 1.14, 2.2), (x - .01, y0 + .5, z0 + 1.1), M["aluminio"], col)
    for s in (0, 1): box(nome + "_Folha", (.03, .49, 2.1), (x + .03, y0 + .25 + s * .5, z0 + 1.05), M["aco_elev"], col)
    box(nome + "_Painel", (.02, .1, .2), (x + .01, y0 + 1.22, z0 + 1.15), M["inox"], C_MIU)
    cyl(nome + "_Botao", .018, .018, .012, (x + .025, y0 + 1.22, z0 + 1.15), M["led_verm"], C_MIU, rot=(0, PI / 2, 0), seg=12)
    box(nome + "_Indicador", (.02, .22, .09), (x + .01, y0 + .5, z0 + 2.3), M["preto"], C_MIU)
    texto(nome + "_Andar", andar, .06, (x + .022, y0 + .5, z0 + 2.3), "+x", M["led_verm"], C_MIU)
elevador("Elevador_Terreo", .1, FZ, C_PORT, "T")
elevador("Elevador_Andar_3", .1, Z3, C_COR, "3")
box("Portaria_Porta_Escada", (.04, .86, 2.08), (-6.28, -.7, FZ + 1.04), M["porta_ferro"], C_PORT)
texto("Portaria_Texto_Escada", "ESCADA", .06, (-6.255, -.7, FZ + 1.7), "+x", M["texto_br"], C_MIU)

# ================================================================== 4. corredor do 3o andar e escada
box("Corredor_Piso", (14.4, 1.6, .15), (.8, .8, Z3 - .075), M["piso_cor"], C_COR)
plano("Corredor_Teto", -6.4, 8, 0, 1.6, Z3 + PD - .001, M["teto"], C_COR, True)
V_COR_N = [(3.0, 3.9, 0, 2.1), (9.9, 10.8, 0, 2.1)]                                 # portas do 301 e do 302
parede("Corredor_Parede_Norte", (-6.4, 1.55), (8, 1.55), M["parede_cor"], C_COR, vaos=V_COR_N, t=.1, ext=.05)
parede("Corredor_Parede_Sul", (-6.4, 0), (8, 0), M["parede_cor"], C_COR, vaos=[(.4, 1.3, 0, 2.1)])      # porta da escada
parede("Corredor_Parede_Oeste", (-6.4, 0), (-6.4, 1.6), M["parede_cor"], C_COR)
parede("Corredor_Parede_Leste", (8, 0), (8, 1.6), M["parede_cor"], C_COR)
for nome, x in (("303", -2.95), ("304", 3.95)):                                      # portas dos aptos do lado sul: sempre fechadas
    box("Corredor_Porta_%s" % nome, (.86, .04, 2.08), (x, .115, Z3 + 1.04), M["porta_mad"], C_COR)
    box("Corredor_Porta_%s_Batente" % nome, (1.0, .03, 2.16), (x, .108, Z3 + 1.08), M["rodape"], C_COR)
    texto("Corredor_Numero_%s" % nome, nome, .09, (x, .14, Z3 + 1.72), "+y", M["texto_dour"], C_MIU)
    cyl("Corredor_Macaneta_%s" % nome, .022, .022, .05, (x + .34, .15, Z3 + 1.02), M["metal"], C_MIU, rot=(PI / 2, 0, 0), seg=10)
    box("Corredor_Capacho_%s" % nome, (.7, .42, .012), (x, .36, Z3 + .006), M["capacho"], C_COR)
for x in (-2.95, 3.95): box("Corredor_Capacho_N", (.7, .42, .012), (x, 1.26, Z3 + .006), M["capacho"], C_COR)
for nome, tam, pos in (("Rodape_Cor_N1", (2.9, .015, .08), (-4.9, 1.49, Z3 + .04)), ("Rodape_Cor_N2", (5.9, .015, .08), (.5, 1.49, Z3 + .04)), ("Rodape_Cor_N3", (3.5, .015, .08), (6.2, 1.49, Z3 + .04))):
    box(nome, tam, pos, M["rodape"], C_COR)
cyl("Corredor_Extintor", .07, .07, .45, (7.85, .3, Z3 + .9), M["extintor"], C_COR, seg=14)
box("Corredor_Extintor_Placa", (.02, .2, .2), (7.89, .3, Z3 + 1.75), M["extintor"], C_MIU)
box("Corredor_Quadro_Luz", (.5, .04, .6), (6.6, .12, Z3 + 1.5), M["metal"], C_COR)
for x in (-4.0, .8, 5.6): plafon("Luz_Corredor_%d" % (x + 5), x, .8, 60, col=C_COR, cor="#f4f6ff", m="lamp_f")
# escada: patamar do andar, um lance que sobe e um que desce (cinco degraus cada, ate os patamares intermediarios)
box("Escada_Patamar", (1.3, 3.2, .15), (-5.75, -1.6, Z3 - .075), M["concreto"], C_COR)
parede("Escada_Parede_Oeste", (-6.4, -3.2), (-6.4, -.1), M["parede_cor"], C_COR, h=PD + 1.2, z0=Z3 - 1.2, ext=0)
parede("Escada_Parede_Leste", (-3.8, -3.2), (-3.8, -.1), M["parede_cor"], C_COR, h=PD + 1.2, z0=Z3 - 1.2, ext=0)
parede("Escada_Parede_Sul", (-6.4, -3.2), (-3.8, -3.2), M["parede_cor"], C_COR, h=PD + 1.2, z0=Z3 - 1.2)
plano("Escada_Teto", -6.4, -3.8, -3.2, 0, Z3 + PD - .001, M["teto"], C_COR, True)
for k in range(5):
    box("Escada_Degrau_Sobe", (.26, 1.5, .175 * (k + 1)), (-4.97 + k * .26, -2.4, Z3 + .175 * (k + 1) / 2), M["concreto"], C_COR)
    box("Escada_Degrau_Desce", (.26, 1.5, .15), (-4.97 + k * .26, -.85, Z3 - .175 * (k + 1) - .075), M["concreto"], C_COR)
box("Escada_Divisoria", (1.4, .1, 1.1), (-4.5, -1.62, Z3 + .1), M["parede_cor"], C_COR)
barra("Escada_Corrimao", (-5.1, -3.1, Z3 + .95), (-3.85, -3.1, Z3 + 1.82), .02, M["metal"], C_MIU)
texto("Escada_Texto_Andar", "3º ANDAR", .1, (-6.29, -1.6, Z3 + 1.7), "+x", M["texto_pr"], C_MIU)
plafon("Luz_Escada", -5.5, -1.6, 50, col=C_COR, cor="#f4f6ff", m="lamp_f")

# ================================================================== 5. apartamento 302: estrutura
box("Apto_Piso_Sala", (6.2, 3.9, .15), (4.9, 3.55, Z3 - .075), M["piso_lam"], C_EST)
box("Apto_Piso_Quartos", (6.2, 3.5, .15), (4.9, 7.25, Z3 - .075), M["piso_lam"], C_EST)
box("Apto_Piso_Molhado", (2.8, 7.4, .15), (.4, 5.3, Z3 - .075), M["piso_cer"], C_EST)
plano("Apto_Teto", -1, 8, 1.6, 9, Z3 + PD - .001, M["teto"], C_EST, True)
parede("Apto_Parede_Sul", (-1.1, 1.65), (8, 1.65), M["parede"], C_EST, vaos=[(4.6, 5.5, 0, 2.1)], t=.1, ext=.05)        # entrada do 302
parede("Apto_Parede_Norte", (-1, 9), (8, 9), M["parede"], C_EST, vaos=[(.5, 1.9, 1.1, 2.1), (3.6, 5.0, 1.0, 2.2), (6.9, 8.3, 1.0, 2.2)])
parede("Apto_Parede_Leste", (8, 1.6), (8, 9), M["parede"], C_EST, vaos=[(.9, 3.1, .9, 2.2)])
parede("Apto_Parede_Oeste", (-1, 1.6), (-1, 9), M["parede"], C_EST)
parede("Apto_Parede_Banheiro_Cozinha", (-1, 4.0), (1.8, 4.0), M["parede"], C_EST, t=.12)
parede("Apto_Parede_Circulacao_O", (1.8, 1.6), (1.8, 5.5), M["parede"], C_EST, t=.12, vaos=[(1.3, 2.0, 0, 2.1), (2.9, 3.8, 0, 2.1)])   # banheiro; cozinha
parede("Apto_Parede_Cozinha_Quarto", (1.8, 5.5), (1.8, 9), M["parede"], C_EST, t=.12, ext=.06)
parede("Apto_Parede_Cozinha_Servico", (-1, 6.8), (1.8, 6.8), M["parede"], C_EST, t=.12, vaos=[(1.3, 2.2, 0, 2.1)])
parede("Apto_Parede_Circulacao_L", (3.1, 1.6), (3.1, 5.5), M["parede"], C_EST, t=.12, vaos=[(2.2, 3.9, 0, 2.3)])                  # vao largo para a sala
parede("Apto_Parede_Quartos_Sul", (1.8, 5.5), (8, 5.5), M["parede"], C_EST, t=.12, vaos=[(.2, 1.1, 0, 2.1), (3.2, 4.1, 0, 2.1)])    # quarto 2; quarto 1
parede("Apto_Parede_Entre_Quartos", (4.8, 5.5), (4.8, 9), M["parede"], C_EST, t=.12)
janela("Janela_Servico", .2, 9, True, 1.4, 1.1, 2.1, C_EST); janela("Janela_Quarto_2", 3.3, 9, True, 1.4, 1.0, 2.2, C_EST)
janela("Janela_Quarto_1", 6.6, 9, True, 1.4, 1.0, 2.2, C_EST); janela("Janela_Sala", 8, 3.6, False, 2.2, .9, 2.2, C_EST, folhas=3)
# azulejo ate o teto no banheiro e ate 1,5 m na cozinha e na area de servico (placas finas coladas na parede)
for nome, tam, pos in (("Azulejo_Banheiro_O", (.01, 2.3, PD), (-.895, 2.8, Z3 + PD / 2)), ("Azulejo_Banheiro_S", (2.7, .01, PD), (.4, 1.705, Z3 + PD / 2)),
                       ("Azulejo_Banheiro_N", (2.7, .01, PD), (.4, 3.935, Z3 + PD / 2)), ("Azulejo_Cozinha_S", (2.7, .01, 1.5), (.4, 4.065, Z3 + .75)),
                       ("Azulejo_Cozinha_O", (.01, 2.7, 1.5), (-.895, 5.4, Z3 + .75)), ("Azulejo_Servico_O", (.01, 2.1, 1.5), (-.895, 7.9, Z3 + .75))):
    box(nome, tam, pos, M["azulejo"], C_EST)
for nome, tam, pos in (("Rodape_Sala_S", (3.5, .015, .08), (6.2, 1.71, Z3 + .04)), ("Rodape_Sala_N1", (1.8, .015, .08), (4.05, 5.43, Z3 + .04)),
                       ("Rodape_Sala_N2", (2.0, .015, .08), (6.95, 5.43, Z3 + .04)), ("Rodape_Q1_L", (.015, 3.3, .08), (7.89, 7.25, Z3 + .04)),
                       ("Rodape_Q2_O", (.015, 3.3, .08), (1.87, 7.25, Z3 + .04)), ("Rodape_Q_Meio_A", (.015, 3.3, .08), (4.73, 7.25, Z3 + .04)),
                       ("Rodape_Q_Meio_B", (.015, 3.3, .08), (4.87, 7.25, Z3 + .04))):
    box(nome, tam, pos, M["rodape"], C_EST)
plafon("Luz_Sala", 5.6, 3.5, 20); plafon("Luz_Circulacao", 2.45, 3.4, 45); plafon("Luz_Banheiro", .4, 2.8, 50, cor="#f4f6ff", m="lamp_f")
plafon("Luz_Cozinha", .4, 5.4, 60, cor="#f4f6ff", m="lamp_f"); plafon("Luz_Servico", .4, 7.9, 15, cor="#f4f6ff", m="lamp_f")
plafon("Luz_Quarto_1", 6.4, 7.25, 18); plafon("Luz_Quarto_2", 3.3, 7.25, 18)

# ================================================================== 6. moveis que abrem
T = .018                                                 # espessura das chapas
class Movel:
    """Movel com partes que abrem. Eixos do movel: X = largura (centrado), Y = 0 no fundo e -d na frente, Z = altura.
    rz = 0: a frente olha para o sul (-Y); PI/2: leste; PI: norte; -PI/2: oeste."""
    def __init__(s, nome, x, y, rz, col, d, z=Z3):
        s.nome, s.col, s.rz, s.d, s.n = nome, col, rz, d, 0
        s.o = Vector((x, y, z)); s.R = Matrix.Rotation(rz, 3, "Z")
    def W(s, p): return s.o + s.R @ Vector(p)
    def cx(s, suf, tam, pos, m, col=None, bevel=0.0):
        return box("Mv_%s_%s" % (s.nome, suf), tam, s.W(pos), m, col or s.col, rot=(0, 0, s.rz), bevel=bevel)
    def casco(s, x0, x1, z0, z1, m, prat=(), fundo=True, d=None, y0=0.0):
        """Caixa aberta na frente, de x0 a x1 e de z0 a z1 (medidas de fora), com prateleiras nas alturas dadas."""
        d = d or s.d; w = x1 - x0; xc = (x0 + x1) / 2; yc = y0 - d / 2
        for sx, x in ((-1, x0 + T / 2), (1, x1 - T / 2)): s.cx("Lado", (T, d, z1 - z0), (x, yc, (z0 + z1) / 2), m)
        s.cx("Base", (w - 2 * T, d, T), (xc, yc, z0 + T / 2), m); s.cx("Topo", (w - 2 * T, d, T), (xc, yc, z1 - T / 2), m)
        if fundo: s.cx("Fundo", (w - 2 * T, .008, z1 - z0 - 2 * T), (xc, y0 - .004, (z0 + z1) / 2), m)
        for z in prat: s.cx("Prateleira", (w - 2 * T, d - .03, T), (xc, yc + .015, z), m)
    def raiz(s, tipo, pos):
        s.n += 1; return vazio("A_%s_%s_%d" % (tipo, s.nome, s.n), s.W(pos), C_INT, s.rz)
    def gaveta(s, cx, z, w, h, m, mi=None, d=None, roupas=None, tf=T):
        """Gaveta completa (frente, laterais, fundo, traseira e puxador). A raiz fica na face da frente; abre para -Y do movel."""
        d = d or s.d; db = d - .06; mi = mi or M["mdf_int"]; wb = w - .05; hb = max(.04, h - .05); ts = .012
        r = s.raiz("Gav", (cx, -d - tf, z)); r["abre"] = "gaveta"; r["curso"] = round(db - .07, 3); n = r.name
        box(n + "_Frente", (w, tf, h), (0, tf / 2, h / 2), m, C_INT, r)
        for sx in (-1, 1): box(n + "_Lado", (ts, db, hb), (sx * (wb / 2 - ts / 2), tf + db / 2, .014 + hb / 2), mi, C_INT, r)
        box(n + "_Chao", (wb, db, .008), (0, tf + db / 2, .018), mi, C_INT, r)
        box(n + "_Tras", (wb, ts, hb), (0, tf + db - ts / 2, .014 + hb / 2), mi, C_INT, r)
        lp = min(.16, w * .35)
        box(n + "_Puxador", (lp, .012, .012), (0, -.024, h / 2), M["metal"], C_INT, r)
        for sx in (-1, 1): box(n + "_Puxador_Pe", (.01, .02, .01), (sx * (lp / 2 - .01), -.01, h / 2), M["metal"], C_INT, r)
        for k, mr in enumerate(roupas or ()):
            wr = (wb - .06) / max(len(roupas), 1); hr = min(hb - .02, rnd.uniform(.04, .09))
            box(n + "_Roupa", (wr - .02, db * .8, hr), (-wb / 2 + .03 + wr * (k + .5), tf + db / 2, .022 + hr / 2), M[mr], C_INT, r, bevel=.008)
        return r
    def folha(s, xh, z, w, h, m, lado=1, tf=T, ang=1.75, zp=None, d=None, pux=.12):
        """Porta de armario. xh = posicao da dobradica; lado = +1 se a folha corre para +X a partir dela, -1 para -X."""
        d = s.d if d is None else d
        r = s.raiz("Fol", (xh, -d - tf, z)); r["abre"] = "porta"; r["ang"] = round(-lado * ang, 3); n = r.name
        box(n + "_Painel", (w, tf, h), (lado * w / 2, tf / 2, h / 2), m, C_INT, r)
        zp = h / 2 if zp is None else zp
        box(n + "_Puxador", (.012, .012, pux), (lado * (w - .035), -.024, zp), M["metal"], C_INT, r)
        for sz in (-1, 1): box(n + "_Puxador_Pe", (.01, .02, .01), (lado * (w - .035), -.01, zp + sz * (pux / 2 - .01)), M["metal"], C_INT, r)
        return r
    def tampa(s, pos, tam, m, ang, deitada=False):
        """Peca que gira num eixo horizontal (X do movel). Em pe (porta do forno): a raiz fica na borda de baixo e ela cai para a
        frente. Deitada (tampa da lavadora ou do vaso): a raiz fica na borda de tras e ela levanta."""
        r = s.raiz("Tam", pos); r["abre"] = "porta"; r["eixo"] = "x"; r["ang"] = ang; n = r.name
        w, a, e = tam
        if deitada: box(n + "_Painel", (w, a, e), (0, -a / 2, e / 2), m, C_INT, r)
        else:
            box(n + "_Painel", (w, e, a), (0, e / 2, a / 2), m, C_INT, r)
            box(n + "_Puxador", (w * .7, .015, .015), (0, -.03, a - .06), M["metal"], C_INT, r)
        return r
    def colisao(s, w, h, x=0.0, z0=0.0, d=None):
        d = (d or s.d) - .03
        ob = box("Col_" + s.nome, (w, d, h), s.W((x, -d / 2, z0 + h / 2)), M["preto"], C_COL, rot=(0, 0, s.rz)); ob.hide_render = True

ROUPAS = ("roupa_a", "roupa_b", "roupa_c", "roupa_d", "roupa_e")
def comoda(nome, x, y, rz, col, w=1.0, d=.45, h=.86, n=4, m=None, mf=None, roupas=True):
    m = m or M["mad"]; mf = mf or m; mv = Movel(nome, x, y, rz, col, d)
    mv.casco(-w / 2, w / 2, .06, h, m); mv.cx("Rodape", (w - .04, .02, .06), (0, -d + .04, .03), m)
    hz = (h - .06 - 2 * T) / n
    for k in range(n):
        mv.gaveta(0, .06 + T + k * hz + .002, w - .006, hz - .004, mf, roupas=[rnd.choice(ROUPAS) for _ in range(rnd.randint(1, 3))] if roupas else None)
    mv.colisao(w, h); return mv

def guarda_roupa(nome, x, y, rz, col, w=1.8, d=.55, h=2.2, portas=3, m=None, mf=None):
    """Guarda-roupa: um modulo por porta; embaixo uma gaveta por modulo; dentro, prateleira alta, cabideiro e roupas."""
    m = m or M["mdf_br"]; mf = mf or m; mv = Movel(nome, x, y, rz, col, d); wm = w / portas; zg = .08 + .3
    lados = {2: (1, -1), 3: (1, -1, -1), 4: (1, -1, 1, -1)}[portas]
    mv.cx("Rodape", (w - .04, .02, .08), (0, -d + .04, .04), m)
    for i in range(portas):
        x0 = -w / 2 + i * wm; xc = x0 + wm / 2
        mv.casco(x0, x0 + wm, .08, h, m, prat=(zg, h - .42))
        mv.gaveta(xc, .08 + T + .002, wm - .006, zg - .08 - T - .004, mf, roupas=[rnd.choice(ROUPAS) for _ in range(2)])
        mv.folha(x0 + (.003 if lados[i] > 0 else wm - .003), zg + .01, wm - .006, h - zg - .012, mf, lados[i], zp=.75, pux=.16)
        barra("Mv_%s_Cabideiro" % nome, mv.W((x0 + T, -d / 2, h - .52)), mv.W((x0 + wm - T, -d / 2, h - .52)), .012, M["metal"], C_MIU)
        for k in range(rnd.randint(2, 4)):                 # roupas penduradas
            xr = x0 + .08 + k * (wm - .16) / 4 + rnd.uniform(0, .03); hr = rnd.uniform(.7, 1.0)
            mv.cx("Roupa", (.035, d - .16, hr), (xr, -d / 2, h - .56 - hr / 2), M[rnd.choice(ROUPAS)], bevel=.01)
        mv.cx("Caixa", (wm * .5, d * .6, .2), (xc, -d / 2, h - .42 + T / 2 + .1), M["papelao"])
    mv.colisao(w, h); return mv

def criado(nome, x, y, rz, col, m=None):
    mv = comoda(nome, x, y, rz, col, w=.45, d=.4, h=.55, n=2, m=m, roupas=False); return mv

def cama(nome, x, y, rz, larg, col, m_lencol):
    """Cama com a cabeceira no fundo (Y = 0 do movel) e os pes na frente."""
    mv = Movel(nome, x, y, rz, col, 1.95)
    mv.cx("Cabeceira", (larg + .1, .05, 1.0), (0, -.025, .5), M["mad_esc"]); mv.cx("Base", (larg, 1.9, .3), (0, -1.0, .15), M["mad_esc"])
    mv.cx("Colchao", (larg - .02, 1.88, .2), (0, -1.0, .4), M["colchao"], bevel=.03)
    mv.cx("Lencol", (larg, 1.25, .21), (0, -1.32, .405), m_lencol, bevel=.03)
    for k in range(2 if larg > 1.2 else 1):
        xk = (k - .5) * larg / 2 if larg > 1.2 else 0
        mv.cx("Travesseiro", (.55, .36, .11), (xk, -.3, .55), M["travesseiro"], bevel=.04)
    ob = box("Col_" + nome, (larg, 1.95, .5), mv.W((0, -.975, .25)), M["preto"], C_COL, rot=(0, 0, rz)); ob.hide_render = True
    return mv

def cadeira(nome, x, y, rz, col, z=Z3):
    mv = Movel(nome, x, y, rz, col, .42, z)
    mv.cx("Assento", (.42, .42, .04), (0, -.21, .45), M["tecido_cad"], bevel=.01); mv.cx("Encosto", (.4, .03, .42), (0, -.015, .72), M["mad_esc"])
    for sx in (-1, 1):
        for sy in (-.03, -.39): mv.cx("Pe", (.035, .035, .45 if sy < -.1 else .93), (sx * .18, sy, .225 if sy < -.1 else .465), M["mad_esc"])

def mesa(nome, x, y, tam, alt, col, m=None, z=Z3):
    m = m or M["mad"]; box(nome + "_Tampo", (tam[0], tam[1], .035), (x, y, z + alt - .0175), m, col, bevel=.006)
    for sx in (-1, 1):
        for sy in (-1, 1): box(nome + "_Pe", (.05, .05, alt - .035), (x + sx * (tam[0] / 2 - .06), y + sy * (tam[1] / 2 - .06), z + (alt - .035) / 2), m, col)

def passagem(nome, dobradica, rz, m, larg=.88, rotulo=None, lado_rotulo=-1, ang=1.5, z0=Z3, tranca=False, m_rot="texto_dour", olho=False):
    """Folha de porta com a origem na dobradica (o site gira a raiz para abrir). rz = 0: a folha corre para +X."""
    r = vazio("A_Passagem_" + nome, (dobradica[0], dobradica[1], z0), C_INT, rz)
    r["abre"] = "porta"; r["ang"] = ang; r["colide"] = 1; r["larg"] = larg
    if tranca: r["tranca"] = 1
    n = r.name
    box(n + "_Folha", (larg, .04, 2.08), (larg / 2, 0, 1.04), m, C_INT, r)
    for s in (-1, 1):
        cyl(n + "_Macaneta", .022, .022, .05, (larg - .08, s * .045, 1.02), M["metal"], C_INT, r, rot=(PI / 2, 0, 0), seg=10)
        box(n + "_Macaneta_Haste", (.11, .016, .016), (larg - .125, s * .07, 1.02), M["metal"], C_INT, r)
    if rotulo: texto(n + "_Rotulo", rotulo, .09 if len(rotulo) < 4 else .06, (larg / 2, lado_rotulo * .024, 1.72), "-y" if lado_rotulo < 0 else "+y", M[m_rot], C_INT, r)
    if olho: cyl(n + "_Olho_Magico", .012, .012, .05, (larg / 2, 0, 1.5), M["preto"], C_INT, r, rot=(PI / 2, 0, 0), seg=10)
    return r
def batente(nome, x, y, ao_longo_x, larg, col, z0=Z3):
    for s in (-1, 1):
        box(nome + "_Batente", (.04, .16, 2.1) if ao_longo_x else (.16, .04, 2.1), (x + s * (larg / 2 + .0), y, z0 + 1.05) if ao_longo_x else (x, y + s * larg / 2, z0 + 1.05), M["rodape"], col)
    box(nome + "_Batente_Cima", (larg, .16, .04) if ao_longo_x else (.16, larg, .04), (x, y, z0 + 2.1), M["rodape"], col)

# portas dos comodos (todas abrem para dentro do comodo)
passagem("Apto_302", (3.5, 1.6), 0, M["porta_mad"], rotulo="302", olho=True); batente("Batente_302", 3.95, 1.6, True, .9, C_EST)
passagem("Apto_301", (-3.4, 1.6), 0, M["porta_mad"], rotulo="301", olho=True); batente("Batente_301", -2.95, 1.6, True, .9, C_VIZ)
passagem("Escada", (-6.0, 0), 0, M["porta_ferro"], rotulo="ESCADA", lado_rotulo=1, ang=-1.5, m_rot="texto_br"); batente("Batente_Escada", -5.55, 0, True, .9, C_COR)
passagem("Banheiro", (1.8, 2.9), PI / 2, M["porta_br"], larg=.68); batente("Batente_Banheiro", 1.8, 3.25, False, .7, C_EST)
passagem("Quarto_2", (2.0, 5.5), 0, M["porta_br"], tranca=True); batente("Batente_Quarto_2", 2.45, 5.5, True, .9, C_EST)
passagem("Quarto_1", (5.9, 5.5), PI, M["porta_br"], ang=-1.5); batente("Batente_Quarto_1", 5.45, 5.5, True, .9, C_EST)

# ------------------------------------------------------------------ quarto 1 (casal)
cama("Cama_Casal", 6.1, 8.88, 0, 1.4, C_QUA, M["lencol"])                      # cabeceira na parede norte, sob a janela
criado("Criado_A", 5.12, 8.88, 0, C_QUA); criado("Criado_B", 7.08, 8.88, 0, C_QUA)
guarda_roupa("Guarda_Roupa_Casal", 7.88, 6.52, -PI / 2, C_QUA, w=1.8, portas=3)
comoda("Comoda", 4.87, 6.45, PI / 2, C_QUA, w=1.0)
box("Abajur_Base", (.1, .1, .22), (5.12, 8.7, Z3 + .66), M["louca"], C_QUA); cyl("Abajur_Cupula", .09, .13, .16, (5.12, 8.7, Z3 + .85), M["cortina"], C_MIU, seg=14)
box("Quadro_Quarto_1", (.02, .7, .5), (4.875, 7.9, Z3 + 1.6), M["roupa_e"], C_QUA)
box("Tapete_Quarto_1", (1.9, 1.1, .012), (6.1, 6.6, Z3 + .006), M["tapete"], C_QUA)

# ------------------------------------------------------------------ quarto 2 (inquilino)
cama("Cama_Solteiro", 4.3, 8.88, 0, .9, C_QUA, M["lencol2"])                   # cabeceira na parede norte, no canto leste
guarda_roupa("Guarda_Roupa_Inquilino", 1.87, 7.25, PI / 2, C_QUA, w=1.0, d=.5, h=2.1, portas=2, m=M["mad"])
def escrivaninha(nome, x, y, rz, col, w=1.1, d=.55):
    mv = Movel(nome, x, y, rz, col, d); m = M["mad"]
    mv.cx("Tampo", (w, d, .03), (0, -d / 2, .745), m); mv.cx("Lado", (T, d - .04, .73), (-w / 2 + T / 2, -d / 2, .365), m)
    mv.cx("Fundo", (w - .44, .012, .35), (-.2, -.04, .55), m)
    mv.casco(w / 2 - .42, w / 2, 0, .73, m, d=d - .02, y0=-.0)
    for k in range(3): mv.gaveta(w / 2 - .21, .02 + k * .235, .414, .228, m, d=d - .02)
    mv.colisao(w, .76); return mv
escrivaninha("Escrivaninha", 3.0, 8.88, 0, C_QUA)
cadeira("Cadeira_Escrivaninha", 2.9, 8.05, PI, C_QUA)
box("Mochila", (.3, .2, .42), (2.1, 8.6, Z3 + .21), M["roupa_d"], C_QUA, bevel=.04)

# ------------------------------------------------------------------ sala
def rack(nome, x, y, rz, col, w=1.6, d=.42, h=.52):
    mv = Movel(nome, x, y, rz, col, d); m = M["mad_esc"]; wl = .46
    mv.cx("Tampo", (w, d + .02, .025), (0, -d / 2 - .01, h + .0125), m)
    mv.casco(-w / 2, -w / 2 + wl, .06, h, m, prat=(.3,)); mv.casco(w / 2 - wl, w / 2, .06, h, m, prat=(.3,)); mv.casco(-w / 2 + wl, w / 2 - wl, .06, h, m)
    mv.folha(-w / 2 + .003, .06 + .002, wl - .006, h - .064, m, 1); mv.folha(w / 2 - .003, .06 + .002, wl - .006, h - .064, m, -1)
    wc = w - 2 * wl; hz = (h - .06 - 2 * T) / 2
    for k in range(2): mv.gaveta(0, .06 + T + k * hz + .002, wc - .006, hz - .004, m)
    mv.colisao(w, h + .03); return mv
rack("Rack_TV", 6.5, 1.72, PI, C_SAL)
modelo_ph("TV", "Television_01", (6.5, 1.95, Z3 + .545), PI, C_SAL, max_tris=1500, alt=.62) or box("TV", (1.0, .06, .6), (6.5, 1.9, Z3 + .9), M["tela"], C_SAL)
modelo_ph("Sofa", "sofa_03", (6.9, 4.95, Z3), PI, C_SAL, max_tris=3500, alt=.85) or box("Sofa", (1.9, .85, .8), (6.9, 5.0, Z3 + .4), M["tecido_cad"], C_SAL)
modelo_ph("Mesa_Centro", "coffee_table_round_01", (6.7, 3.5, Z3), 0, C_SAL, max_tris=1500, alt=.42) or mesa("Mesa_Centro", 6.7, 3.5, (.8, .5), .42, C_SAL)
box("Tapete_Sala", (2.2, 1.6, .012), (6.7, 3.5, Z3 + .006), M["tapete"], C_SAL)
mesa("Mesa_Jantar", 4.9, 3.2, (.8, 1.2), .76, C_SAL)
for k, (dx, dy, rz) in enumerate(((-.62, -.28, -PI / 2), (-.62, .28, -PI / 2), (.62, -.28, PI / 2), (.62, .28, PI / 2))):
    cadeira("Cadeira_Jantar_%d" % k, 4.9 + dx + (-.21 if dx < 0 else .21), 3.2 + dy, rz + PI, C_SAL)
modelo_ph("Planta_Sala", "potted_plant_01", (7.55, 2.1, Z3), 0, C_SAL, max_tris=2500, alt=1.2)
box("Quadro_Sala", (1.1, .02, .7), (6.9, 5.43, Z3 + 1.6), M["roupa_a"], C_SAL)
def armario_alto(nome, x, y, rz, col, w=1.2, d=.5, h=2.2, m=None, prat=(.5, .95, 1.4, 1.85)):
    m = m or M["mdf_br"]; mv = Movel(nome, x, y, rz, col, d)
    mv.casco(-w / 2, w / 2, .06, h, m, prat=prat); mv.cx("Rodape", (w - .04, .02, .06), (0, -d + .04, .03), m)
    mv.folha(-w / 2 + .003, .062, w / 2 - .005, h - .064, m, 1, zp=1.0, pux=.16); mv.folha(w / 2 - .003, .062, w / 2 - .005, h - .064, m, -1, zp=1.0, pux=.16)
    for z in prat[:3]:
        for k in range(2): mv.cx("Dobrados", (w * .32, d * .6, rnd.uniform(.1, .22)), ((k - .5) * w * .45, -d / 2, z + T / 2 + .11), M[rnd.choice(ROUPAS)], bevel=.01)
    mv.colisao(w, h); return mv
armario_alto("Armario_Circulacao", 2.45, 1.71, PI, C_SAL)

# ------------------------------------------------------------------ cozinha e area de servico
def bancada_cozinha(nome, x, y, rz, col, w=2.2, d=.55, h=.86):
    """Armario de baixo com quatro modulos (porta, porta, gaveteiro, porta), tampo de granito e cuba; e armario de cima."""
    mv = Movel(nome, x, y, rz, col, d); m = M["mdf_br"]; wm = w / 4
    mv.cx("Rodape", (w - .04, .02, .1), (0, -d + .05, .05), M["preto"])
    for i in range(4):
        x0 = -w / 2 + i * wm
        mv.casco(x0, x0 + wm, .1, h, m, prat=() if i == 2 else (.5,))
        if i == 2:
            hz = (h - .1 - 2 * T) / 3
            for k in range(3): mv.gaveta(x0 + wm / 2, .1 + T + k * hz + .002, wm - .006, hz - .004, m)
        else: mv.folha(x0 + (.003 if i != 1 else wm - .003), .102, wm - .006, h - .104, m, 1 if i != 1 else -1, zp=h - .22)
    mv.cx("Tampo", (w + .02, d + .04, .03), (0, -d / 2 - .02, h + .015), M["granito"])
    mv.cx("Cuba", (.46, .36, .012), (-w / 2 + wm, -d / 2, h + .032), M["inox"]); mv.cx("Torneira", (.03, .03, .26), (-w / 2 + wm, -.07, h + .16), M["inox"])
    mv.cx("Torneira_Bica", (.025, .16, .025), (-w / 2 + wm, -.15, h + .28), M["inox"])
    mv.colisao(w, h + .03)
    # armario de cima
    ma = Movel(nome + "_Aereo", x, y, rz, col, .32); za = 1.5
    for i in range(4):
        x0 = -w / 2 + i * wm
        ma.casco(x0, x0 + wm, za, za + .62, m, prat=(za + .31,))
        ma.folha(x0 + (.003 if i % 2 == 0 else wm - .003), za + .002, wm - .006, .616, m, 1 if i % 2 == 0 else -1, zp=.1, pux=.1)
    return mv
bancada_cozinha("Bancada", .25, 4.075, PI, C_COZ)
def geladeira(nome, x, y, rz, col, w=.66, d=.62, h=1.75):
    mv = Movel(nome, x, y, rz, col, d); m = M["geladeira"]; zf = h - .46
    mv.casco(-w / 2, w / 2, .04, zf, m, prat=(.45, .8, 1.05)); mv.casco(-w / 2, w / 2, zf, h, m)
    mv.folha(w / 2 - .003, .05, w - .006, zf - .056, m, -1, tf=.05, ang=1.9, zp=zf - .5, pux=.3)
    mv.folha(w / 2 - .003, zf + .004, w - .006, h - zf - .008, m, -1, tf=.05, ang=1.9, zp=.12, pux=.14)
    mv.colisao(w, h); return mv
geladeira("Geladeira", -.88, 6.1, PI / 2, C_COZ)
def fogao(nome, x, y, rz, col, w=.56, d=.58, h=.86):
    mv = Movel(nome, x, y, rz, col, d); m = M["fogao"]
    mv.casco(-w / 2, w / 2, .08, h, m, prat=(.26, .45)); mv.cx("Mesa", (w, d, .02), (0, -d / 2, h + .01), M["preto"])
    for k, (dx, dy) in enumerate(((-.13, -.16), (.13, -.16), (-.13, -.42), (.13, -.42))): cyl("Mv_%s_Boca" % nome, .07, .07, .02, mv.W((dx, dy, h + .03)), M["preto"], C_MIU, seg=14)
    mv.cx("Painel", (w, .03, .09), (0, -d - .015, h - .045), m)
    mv.tampa((0, -d - .03, .27), (w - .01, h - .37, .03), M["preto"], 1.45)
    for sx in (-1, 1):
        for sy in (-.05, -d + .05): mv.cx("Pe", (.04, .04, .08), (sx * (w / 2 - .04), sy, .04), M["preto"])
    mv.colisao(w, h); return mv
fogao("Fogao", -.88, 5.15, PI / 2, C_COZ)
def lavadora(nome, x, y, rz, col, w=.6, d=.62, h=.95):
    mv = Movel(nome, x, y, rz, col, d); m = M["branco"]
    for sx in (-1, 1): mv.cx("Lado", (.02, d, h), (sx * (w / 2 - .01), -d / 2, h / 2), m)
    mv.cx("Frente", (w - .04, .02, h), (0, -d + .01, h / 2), m); mv.cx("Tras", (w - .04, .02, h + .12), (0, -.01, h / 2 + .06), m)
    mv.cx("Fundo", (w - .04, d - .04, .02), (0, -d / 2, .35), m)
    cyl("Mv_%s_Cesto" % nome, .22, .22, .5, mv.W((0, -d / 2 - .02, .62)), M["inox"], C_MIU, seg=20)
    mv.cx("Borda", (w - .04, .12, .02), (0, -.08, h - .01), m)
    mv.tampa((0, -.14, h), (w - .06, d - .16, .02), m, -1.5, deitada=True)
    mv.colisao(w, h); return mv
lavadora("Lavadora", 1.73, 8.4, -PI / 2, C_COZ)
box("Tanque_Cuba", (.5, .55, .28), (-.7, 7.6, Z3 + .76), M["louca"], C_COZ, bevel=.02); box("Tanque_Coluna", (.2, .2, .62), (-.75, 7.6, Z3 + .31), M["louca"], C_COZ)
armario_alto("Armario_Servico", 1.73, 7.45, -PI / 2, C_COZ, w=.7, d=.36, h=1.9, prat=(.5, .95, 1.4))
box("Balde", (.28, .28, .26), (-.6, 8.6, Z3 + .13), M["roupa_a"], C_COZ, bevel=.03)

# ------------------------------------------------------------------ banheiro
def gabinete_banheiro(nome, x, y, rz, col, w=.8, d=.42):
    mv = Movel(nome, x, y, rz, col, d); m = M["mdf_br"]
    mv.casco(-w / 2, w / 2, .25, .82, m, prat=(.52,)); mv.cx("Tampo", (w + .02, d + .03, .03), (0, -d / 2 - .015, .835), M["louca"])
    mv.cx("Cuba", (.4, .3, .1), (0, -d / 2, .9), M["louca"], bevel=.02); mv.cx("Torneira", (.03, .03, .16), (0, -.06, .93), M["inox"])
    mv.folha(-w / 2 + .003, .252, w / 2 - .005, .566, m, 1, zp=.46, pux=.1); mv.folha(w / 2 - .003, .252, w / 2 - .005, .566, m, -1, zp=.46, pux=.1)
    mv.colisao(w, .85)
    me = Movel(nome + "_Espelheira", x, y, rz, col, .13)
    me.casco(-w / 2, w / 2, 1.25, 1.85, m, prat=(1.55,))
    me.folha(-w / 2 + .003, 1.252, w / 2 - .005, .596, M["espelho"], 1, zp=.08, pux=.06); me.folha(w / 2 - .003, 1.252, w / 2 - .005, .596, M["espelho"], -1, zp=.08, pux=.06)
    return mv
gabinete_banheiro("Gabinete_Banheiro", .9, 3.93, 0, C_BAN)
def vaso(nome, x, y, rz, col):
    mv = Movel(nome, x, y, rz, col, .66)
    mv.cx("Caixa", (.38, .17, .36), (0, -.085, .58), M["louca"], bevel=.015); mv.cx("Bacia", (.36, .46, .4), (0, -.42, .2), M["louca"], bevel=.05)
    mv.cx("Agua", (.24, .3, .005), (0, -.42, .403), M["tela"], col=C_MIU)
    mv.tampa((0, -.2, .405), (.36, .44, .025), M["louca"], -1.6, deitada=True)
    mv.colisao(.4, .42, d=.66); return mv
vaso("Vaso", .45, 1.72, PI, C_BAN)
box("Box_Vidro", (.008, 1.2, 1.9), (-.2, 2.2, Z3 + .97), M["vidro"], C_VID); box("Box_Mureta", (.06, 1.2, .06), (-.2, 2.2, Z3 + .03), M["granito"], C_BAN)
cyl("Chuveiro", .06, .09, .08, (-.6, 1.9, Z3 + 2.05), M["branco"], C_BAN, seg=14); barra("Chuveiro_Cano", (-.6, 1.72, Z3 + 2.1), (-.6, 1.9, Z3 + 2.1), .012, M["inox"], C_MIU)
box("Toalha", (.02, .45, .6), (1.72, 2.2, Z3 + 1.25), M["roupa_c"], C_BAN); box("Lixeira_Banheiro", (.2, .2, .26), (1.0, 1.86, Z3 + .13), M["branco"], C_BAN, bevel=.02)

# ------------------------------------------------------------------ vizinho 301 (so a sala)
box("Vizinho_Piso", (5.4, 4.0, .15), (-3.7, 3.6, Z3 - .075), M["piso_cer"], C_VIZ)
plano("Vizinho_Teto", -6.4, -1, 1.6, 5.6, Z3 + PD - .001, M["teto"], C_VIZ, True)
parede("Vizinho_Parede_Sul", (-6.4, 1.65), (-1.1, 1.65), M["parede"], C_VIZ, vaos=[(3.0, 3.9, 0, 2.1)], t=.1, ext=.05)
parede("Vizinho_Parede_Oeste", (-6.4, 1.6), (-6.4, 5.6), M["parede"], C_VIZ)
parede("Vizinho_Parede_Norte", (-6.4, 5.6), (-1.1, 5.6), M["parede"], C_VIZ, ext=0)
box("Vizinho_Porta_Interna", (.82, .04, 2.08), (-2.2, 5.48, Z3 + 1.04), M["porta_br"], C_VIZ)
modelo_ph("Vizinho_Sofa", "sofa_02", (-5.9, 3.6, Z3), PI / 2, C_VIZ, max_tris=2500, alt=.8)
modelo_ph("Vizinho_Poltrona", "modern_arm_chair_01", (-4.6, 5.0, Z3), PI, C_VIZ, max_tris=2000, alt=.85)
mesa("Vizinho_Mesa", -2.2, 3.4, (.9, .9), .76, C_VIZ, M["mad_esc"])
for k, (dx, dy, rz) in enumerate(((0, -.62, 0), (0, .62, PI))): cadeira("Vizinho_Cadeira_%d" % k, -2.2 + dx, 3.4 + dy + (-.21 if dy < 0 else .21), rz + PI, C_VIZ)
comoda("Vizinho_Aparador", -4.2, 1.77, PI, C_VIZ, w=1.2, d=.4, h=.8, n=2, m=M["mad_esc"], roupas=False)
box("Vizinho_TV", (.95, .05, .56), (-4.2, 1.95, Z3 + 1.12), M["tela"], C_VIZ)
box("Vizinho_Tapete", (1.8, 1.4, .012), (-4.6, 3.6, Z3 + .006), M["tapete"], C_VIZ)
box("Vizinho_Quadro", (.02, .9, .6), (-6.28, 3.6, Z3 + 1.6), M["roupa_b"], C_VIZ)
plafon("Luz_Vizinho", -3.7, 3.6, 110, col=C_VIZ)

# ================================================================== 7. sol, ceu, pontos, cameras
# Ceu: HDRI diurno do Poly Haven (CC0), so como luz difusa do ceu (o disco do sol do arquivo e cortado). O sol e uma lampada
# a parte, para vir do nordeste (manha) e entrar pelas janelas da sala e dos quartos. As forcas funcionam como a exposicao de
# uma camera regulada para o interior (la fora fica estourado, como numa foto tirada de dentro de casa).
HDRI = os.path.normpath(os.path.join(AQUI, "..", "04_ThreeJS", "hdri", "kloofendal_48d_partly_cloudy_puresky_2k.hdr"))
FORCA_CEU = 5.0
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); scene.world = world
nt = world.node_tree; bg = nt.nodes.get("Background")
if bg and os.path.exists(HDRI):
    env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(HDRI)
    corte = nt.nodes.new("ShaderNodeVectorMath"); corte.operation = "MINIMUM"; corte.inputs[1].default_value = (6, 6, 6)
    nt.links.new(env.outputs["Color"], corte.inputs[0]); nt.links.new(corte.outputs["Vector"], bg.inputs["Color"])
elif bg:
    bg.inputs["Color"].default_value = (*lin(hx("#a9c8ee")), 1)
if bg: bg.inputs["Strength"].default_value = FORCA_CEU
luz("Sol", "SUN", 18, "#fff1dc", (60, 45, 62), C_LUZ, alvo=(0, 0, 0), angle=math.radians(1.6))

ponto("Inicio", -2.7, -4.3, (0, 1), FZ); ponto("Parceiro", -1.6, -4.0, (-.4, 1), FZ); ponto("Porteiro", -.1, -2.6, (-1, 0), FZ)
ponto("Elevador_Terreo", -5.7, .6, (1, 0), FZ); ponto("Elevador_Andar_3", -5.7, .6, (1, 0))
ponto("Porta_302", 3.95, 1.0, (0, 1)); ponto("Porta_301", -2.95, 1.0, (0, 1)); ponto("Apoio_Escada", -5.6, -1.0, (0, 1)); ponto("Apoio_Corredor", 6.8, .8, (-1, 0))
ponto("Parceiro_Corredor", 4.9, .9, (-.6, 1)); ponto("Morador_Sala", 4.0, 2.6, (0, -1)); ponto("Vizinho", -2.95, 2.6, (0, -1))
camera("Camera_Portaria", (-2.7, -4.6, FZ + 1.65), (-3.4, 1.0, FZ + 1.4), 16)
camera("Camera_Rua", (-2.7, -11.5, 1.75), (-2.2, -6, 4.0), 16)
camera("Camera_Corredor", (-5.6, .8, Z3 + 1.65), (8, .8, Z3 + 1.3), 16)
camera("Camera_Sala", (3.5, 2.1, Z3 + 1.65), (7.5, 4.6, Z3 + 1.0), 14)
camera("Camera_Cozinha", (1.5, 4.5, Z3 + 1.65), (-.6, 6.3, Z3 + 1.0), 13)
camera("Camera_Quarto_1", (5.3, 5.8, Z3 + 1.65), (7.6, 8.6, Z3 + .9), 13)
camera("Camera_Quarto_2", (2.3, 5.8, Z3 + 1.65), (4.2, 8.8, Z3 + .9), 13)
camera("Camera_Banheiro", (1.6, 3.2, Z3 + 1.65), (-.4, 2.6, Z3 + .9), 13)
camera("Camera_Vizinho", (-2.9, 2.0, Z3 + 1.65), (-5.4, 4.6, Z3 + 1.0), 14)
p = camera("Camera_Planta", (2.0, 4.0, Z3 + 30.0), (2.0, 4.0, 0)); p.data.type = "ORTHO"; p.data.ortho_scale = 19; p.data.clip_start = 30 - PD + .06
p.rotation_euler = (0, 0, 0)
scene.camera = bpy.data.objects["Camera_Sala"]

scene.unit_settings.system = "METRIC"
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.render.engine = "CYCLES"; scene.cycles.samples = 128; scene.cycles.use_denoising = True
for attr, val in (("view_transform", "AgX"), ("look", "AgX - Medium High Contrast")):
    try: setattr(scene.view_settings, attr, val)
    except Exception: pass
scene.view_settings.exposure = 0.0

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(AQUI, "busca.blend"))
tris = 0
dg = bpy.context.evaluated_depsgraph_get()
for o in scene.objects:
    if o.type == "MESH" and not o.hide_render:
        e = o.evaluated_get(dg); m = e.to_mesh(); tris += sum(len(p.vertices) - 2 for p in m.polygons); e.to_mesh_clear()
abre = [o for o in scene.objects if o.get("abre")]
say("cena criada: %d objetos, ~%d triangulos, %d pecas que abrem (%d gavetas) -> busca.blend" % (len(bpy.data.objects), tris, len(abre), sum(1 for o in abre if o["abre"] == "gaveta")))
