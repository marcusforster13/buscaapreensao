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

def tex_escovado(S=512, cor="#b8bbbe"):
    """Inox escovado: riscos finos e longos num so sentido (vertical na imagem), sem manchas."""
    r = np.random.default_rng(21); col = r.standard_normal(S); col = np.convolve(col, np.ones(3) / 3, "same") * .03
    fino = r.standard_normal((S, S)) * .012; fino = (fino + np.roll(fino, 1, 0) + np.roll(fino, 2, 0) + np.roll(fino, 3, 0)) / 2
    a = np.ones((S, S, 3)) * np.array(hx(cor)) + (col[None, :] + fino)[..., None]
    return np.clip(a, 0, 1)

def img_metal(name, img, tile_m, rough, metal):
    m = img_mat(name, img, tile_m, rough); m.node_tree.nodes.get("Principled BSDF").inputs["Metallic"].default_value = metal; return m

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
    "parede": mat("Parede_Apto", "#f3f1ea", .92), "parede_cor": mat("Parede_Corredor", "#ebe6d8", .92),
    "parede_port": mat("Parede_Portaria", "#eee9dc", .92), "teto": mat("Teto_Laje", "#f8f7f3", .95),
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
    "porta_ferro": mat("Porta_Corta_Fogo", "#8f2f28", .5), "aco_elev": img_metal("Aco_Elevador", np_image("aco_escovado", tex_escovado()), .6, .3, .45),
    "metal": mat("Metal_Escovado", "#9a9c9e", .35, .4), "inox": img_metal("Inox", np_image("inox_escovado", tex_escovado(cor="#c4c7ca")), .4, .28, .45),
    "aluminio": mat("Aluminio_Esquadria", "#c9cbcd", .4, .3), "preto": mat("Preto_Fosco", "#17181a", .6),
    "vidro": mat("Vidro_Janela", "#cfe2ea", .05, alpha=.14), "espelho": mat("Espelho", "#c8d2d6", .02, .9),
    "branco": mat("Plastico_Branco", "#eceae4", .45), "louca": mat("Louca_Branca", "#f1efe9", .2),
    "geladeira": mat("Geladeira_Branca", "#e9e9e6", .35), "fogao": mat("Fogao_Inox", "#b4b6b8", .4, .35),
    "colchao": mat("Colchao", "#e2ddd0", .9), "lencol": mat("Lencol_Azul", "#6f8fb0", .9), "lencol2": mat("Lencol_Cinza", "#8b8f94", .9),
    "travesseiro": mat("Travesseiro", "#eeeae0", .9), "roupa_a": mat("Roupa_Azul", "#2f4a6e", .9), "roupa_b": mat("Roupa_Vermelha", "#8e2f2a", .9),
    "roupa_c": mat("Roupa_Branca", "#e4e0d6", .9), "roupa_d": mat("Roupa_Cinza", "#5c5f63", .9), "roupa_e": mat("Roupa_Verde", "#476349", .9),
    "tecido_cad": mat("Tecido_Cadeira", "#6b5c4c", .9), "tapete": mat("Tapete", "#8a6f5a", 1), "cortina": mat("Cortina_Branca", "#e2dfd6", .95),
    "papel": mat("Papel", "#f4f1e8", .9), "papelao": mat("Caixa_Papelao", "#a9825a", .9),
    "texto_pr": mat("Texto_Preto", "#111111", .6), "texto_br": mat("Texto_Branco", "#f4f4f0", .6), "texto_dour": mat("Texto_Dourado", "#b08d3c", .4, .4),
    "lamp": mat("Lampada_Plafon", "#ffffff", .4, emit="#fff0d8", forca=4), "lamp_f": mat("Lampada_Fria", "#ffffff", .4, emit="#eef4ff", forca=4),
    "led_verm": mat("Led_Vermelho", "#400808", .3, emit="#ff2a1a", forca=3), "tela": mat("Tela_Apagada", "#0c0d10", .15),
    "extintor": mat("Extintor_Vermelho", "#b3201a", .4), "capacho": mat("Capacho", "#5a4a38", 1),
    # fachadas e rua
    "f_pastilha": mat("Fachada_Pastilha", "#cfc4a8", .6), "f_pastilha_az": mat("Fachada_Pastilha_Azul", "#8fa6b4", .6),
    "f_placas": mat("Fachada_Placas", "#b9b6ae", .8), "f_creme": mat("Fachada_Pintada_Creme", "#e3d6b4", .9),
    "f_salmao": mat("Fachada_Pintada_Salmao", "#d9a58a", .9), "f_branca": mat("Fachada_Pintada_Branca", "#e9e6dc", .9),
    "f_verde": mat("Fachada_Pintada_Verde", "#a9bba0", .9), "f_amarela": mat("Fachada_Amarela", "#e0c070", .9),
    "f_cinza": mat("Fachada_Pintada_Cinza", "#a3a5a8", .9), "embasamento": mat("Embasamento_Granito", "#5d5a56", .35),
    "vidro_f": mat("Vidro_Fachada", "#1f2a33", .06), "vidro_f2": mat("Vidro_Fachada_Cortina", "#a8a498", .25), "vidro_f3": mat("Vidro_Fachada_Azul", "#34485a", .06),
    "guarda": mat("Vidro_Guarda_Corpo", "#9fb9c2", .08, alpha=.4), "persiana": mat("Persiana_Aluminio", "#c2c0b8", .5), "grade": mat("Grade_Ferro", "#2c2e30", .5, .3), "ar_cond": mat("Ar_Condicionado", "#dcdad2", .5),
    "telha": mat("Telha_Ceramica", "#a8573a", .85), "muro": mat("Muro_Pintado", "#cfc9b8", .95), "pavers": mat("Piso_Intertravado", "#9a968c", .9),
    "terra": mat("Terra_Canteiro", "#4a3a2c", 1), "mata": mat("Mata_Morro", "#2f4a26", 1), "pedra": mat("Pedra_Morro", "#6f6a62", .9), "grama_longe": mat("Grama_Longe", "#557238", 1), "faixa": mat("Pintura_Viaria_Branca", "#d8d6cc", .7),
    "faixa_am": mat("Pintura_Viaria_Amarela", "#d9a514", .7), "poste": mat("Poste_Concreto", "#8f8b84", .9), "caixa_dagua": mat("Caixa_Dagua", "#3f6fa8", .5),
    "tv": mat("TV_Tela", "#07080a", .08), "micro": mat("Microondas_Preto", "#1b1c1e", .25), "cartaz": mat("Cartaz_Quarto", "#2a3f6a", .7),
    "toldo_v": mat("Toldo_Verde", "#2f6b46", .8), "toldo_r": mat("Toldo_Vinho", "#7a2630", .8), "toldo_a": mat("Toldo_Azul", "#2c4f86", .8),
    "sapato": mat("Sapato_Preto", "#1c1a19", .5), "sapato_m": mat("Sapato_Marrom", "#5a3a26", .5), "lata_a": mat("Embalagem_Vermelha", "#b8322a", .5),
    "lata_b": mat("Embalagem_Amarela", "#d9b02a", .5), "lata_c": mat("Embalagem_Azul", "#2f5a9a", .5), "panela": mat("Panela_Aluminio", "#9c9ea0", .35, .4),
    "interior": mat("Interior_Carro", "#2a2b2e", .8), "faixa_pm": mat("Viatura_Faixa_Azul", "#1e4fb8", .3), "texto_az": mat("Texto_Azul", "#16307f", .6),
    "giro_verm": mat("Giroflex_Vermelho", "#8a1010", .2, emit="#ff1010", forca=.3), "giro_azul": mat("Giroflex_Azul", "#10308a", .2, emit="#1040ff", forca=.3),
    "brasao": mat("Brasao_(inserir_imagem_oficial)", "#c8cbd0", .5), "faixa_pc": mat("Viatura_Faixa_Preta", "#111214", .3),
    "bebedouro": mat("Bebedouro_Azul", "#8fb6d9", .2, alpha=.5), "placa_verde": mat("Placa_Saida", "#1f7a3c", .5, emit="#35d06a", forca=.6),
    "frasco_a": mat("Frasco_Verde", "#3f8a5a", .3), "frasco_b": mat("Frasco_Laranja", "#d9772a", .3), "frasco_c": mat("Frasco_Branco", "#f0eee8", .3),
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
C_VEG = collection("15_Vegetacao")       # arvores, arbustos e tufos de grama: sem lightmap (folhas finas)
C_LON = collection("17_Entorno_Longe")   # terreno, morros e predios ao fundo: lightmap proprio (areas enormes)
C_FMI = collection("18_Fachada_Miudos")  # esquadrias e corrimaos das fachadas: pecas finas, sem lightmap
C_VEIC = collection("19_Veiculos")       # viaturas e carros estacionados
C_GRA = collection("16_Grama")           # tufos de grama (laminas finas): sem lightmap
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
    cd = bpy.data.cameras.new(nome); cd.lens = lente; cd.clip_end = 1200
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

def plafon(nome, x, y, watts, z=Z3 + PD, col=C_EST, cor="#ffd9b0", m="lamp"):      # lampada de casa: branco quente (~3000 K); o usuario aprovou este tom
    cyl(nome + "_Plafon", .15, .13, .05, (x, y, z - .025), M[m], col, seg=20)
    luz(nome + "_Luz", "POINT", watts * .45, cor, (x, y, z - .22), C_LUZ, shadow_soft_size=.18)      # o site clareia o interior (ganho dos lightmaps internos)

def janela(nome, cx, cy, ao_longo_x, larg, zb, zt, col, z0=Z3, folhas=2, persiana=False, dentro=1):
    """Janela de correr de aluminio no vao de uma parede: marco, trilho, folhas sobrepostas (cada uma com vidro e puxador),
    peitoril de granito com pingadeira e, nos quartos, persiana de enrolar (caixa por dentro, laminas um pouco baixadas).
    O vidro fica fora do bake (13_Vidros) para o sol entrar. dentro = +1 ou -1: lado do comodo (eixo perpendicular a parede)."""
    alt = zt - zb; zc = z0 + (zb + zt) / 2
    def pc(suf, tl, th, dl, dz, m=M["aluminio"], c=col, esp=.07, dp=0.0):
        pos = (cx + dl, cy + dp, zc + dz) if ao_longo_x else (cx + dp, cy + dl, zc + dz)
        box(nome + suf, (tl, esp, th) if ao_longo_x else (esp, tl, th), pos, m, c)
    pf = .045                                                            # perfil do marco
    pc("_Marco_Cima", larg, pf, 0, alt / 2 - pf / 2, esp=.1); pc("_Marco_Baixo", larg, pf, 0, -alt / 2 + pf / 2, esp=.1)
    for s in (-1, 1): pc("_Marco_Lado", pf, alt, s * (larg / 2 - pf / 2), 0, esp=.1)
    for k in (-1, 1): pc("_Trilho", larg - 2 * pf, .012, 0, -alt / 2 + pf + .006, m=M["metal"], esp=.006, dp=k * .02)
    # folhas: cada uma com 4 perfis, vidro e puxador; as vizinhas ficam em trilhos diferentes (uma na frente da outra)
    lf = (larg - 2 * pf) / folhas + .03; hf = alt - 2 * pf; sp = .028
    for k in range(folhas):
        dl = -larg / 2 + pf + lf / 2 + k * (larg - 2 * pf - lf) / max(1, folhas - 1); dp = (.02 if k % 2 == 0 else -.02)
        pc("_Folha_Cima", lf, sp, dl, hf / 2 - sp / 2, esp=.03, dp=dp); pc("_Folha_Baixo", lf, sp, dl, -hf / 2 + sp / 2, esp=.03, dp=dp)
        for s in (-1, 1): pc("_Folha_Lado", sp, hf, dl + s * (lf / 2 - sp / 2), 0, esp=.03, dp=dp)
        pc("_Vidro", lf - 2 * sp, hf - 2 * sp, dl, 0, M["vidro"], C_VID, .006, dp=dp)
        lado_pux = 1 if k < folhas / 2 else -1                          # puxador na borda que encontra a outra folha
        pc("_Puxador", .016, .14, dl + lado_pux * (lf / 2 - sp / 2), 0, m=M["metal"], esp=.022, dp=dp + dentro * .022)
    # peitoril: granito por dentro e, por fora, com pingadeira saliente
    pc("_Peitoril", larg + .1, .025, 0, -alt / 2 - .0125, M["granito"], col, .14, dp=dentro * .07)
    pc("_Peitoril_Fora", larg + .1, .03, 0, -alt / 2 - .015, M["granito"], col, .16, dp=-dentro * .1)
    if persiana:
        pc("_Persiana_Caixa", larg + .12, .2, 0, alt / 2 + .1, M["aluminio"], col, .16, dp=dentro * .1)
        pc("_Persiana_Laminas", larg - 2 * pf, alt * .22, 0, alt / 2 - pf - alt * .11, M["persiana"], col, .015, dp=-dentro * .05)
        for k in range(1, 6): pc("_Persiana_Friso", larg - 2 * pf, .004, 0, alt / 2 - pf - k * alt * .22 / 6, M["preto"], col, .016, dp=-dentro * .05)
        for s in (-1, 1): pc("_Persiana_Guia", .02, alt, s * (larg / 2 - pf - .01), 0, M["aluminio"], col, .03, dp=-dentro * .05)

M["friso_mad"] = mat("Porta_Madeira_Friso", "#5a3d26", .5)          # molduras das almofadas da porta de entrada
M["ferragem"] = mat("Ferragem_Inox", "#b9bcbf", .28, .7)             # macanetas, espelhos e dobradicas
def folha_porta(n, larg, m, col, parent=None, T_=None, rz=0.0, almofadas=False, olho=False, fechadura=True, alt=2.07):
    """Folha de porta detalhada, em coordenadas da folha (x de 0 = dobradica ate larg; y = espessura; z do piso).
    Com parent, as pecas sao filhas dele (porta que abre); senao T_ leva as coordenadas para o mundo (porta fixa)."""
    def b(suf, tam, pos, mm, rot=(0, 0, 0)):
        if parent: return box(n + suf, tam, pos, mm, C_INT if parent else col, parent, rot=rot)
        return box(n + suf, tam, T_(pos), mm, col, rot=(rot[0], rot[1], rot[2] + rz))
    def c(suf, r, h, pos, mm, rot=(0, 0, 0), seg=12):
        if parent: return cyl(n + suf, r, r, h, pos, mm, C_INT, parent, rot=rot, seg=seg)
        return cyl(n + suf, r, r, h, T_(pos), mm, col, rot=(rot[0], rot[1], rot[2] + rz), seg=seg)
    e = .038; z0 = .012                                                  # espessura da folha e folga embaixo (passa luz)
    b("_Folha", (larg - .004, e, alt), (larg / 2, 0, z0 + alt / 2), m)
    if almofadas:                                                        # duas almofadas por face, com moldura saliente
        for s in (-1, 1):
            for za, zb_ in ((1.12, 1.92), (.22, .98)):
                x0, x1, yf = .13, larg - .13, s * (e / 2 + .003)
                b("_Moldura", (x1 - x0, .006, .016), ((x0 + x1) / 2, yf, za), M["friso_mad"]); b("_Moldura", (x1 - x0, .006, .016), ((x0 + x1) / 2, yf, zb_), M["friso_mad"])
                b("_Moldura", (.016, .006, zb_ - za), (x0, yf, (za + zb_) / 2), M["friso_mad"]); b("_Moldura", (.016, .006, zb_ - za), (x1, yf, (za + zb_) / 2), M["friso_mad"])
    for zd in (.22, 1.05, 1.88):                                         # dobradicas (no eixo)
        c("_Dobradica", .008, .1, (0, 0, zd), M["ferragem"], seg=8)
    if fechadura:
        xm = larg - .07
        for s in (-1, 1):                                                # alavanca com espelho dos dois lados
            yf = s * (e / 2 + .003)
            b("_Espelho", (.042, .006, .19), (xm, yf, .99), M["ferragem"])
            c("_Pescoco", .009, .045, (xm, s * (e / 2 + .025), 1.04), M["ferragem"], rot=(PI / 2, 0, 0), seg=10)
            b("_Alavanca", (.125, .018, .016), (xm - .056, s * (e / 2 + .048), 1.04), M["ferragem"])
            b("_Chave", (.008, .003, .02), (xm, s * (e / 2 + .0065), .935), M["preto"])
    if olho:
        c("_Olho_Magico", .012, e + .012, (larg / 2, 0, 1.5), M["ferragem"], rot=(PI / 2, 0, 0), seg=12)
        c("_Olho_Lente", .006, e + .016, (larg / 2, 0, 1.5), M["preto"], rot=(PI / 2, 0, 0), seg=10)


# ================================================================== 1. rua, patio e vizinhanca
def ph(nome, asset, x, y, z=None, rz=0.0, col=None, alt=None, tris=2000, escala=1.0):
    return modelo_ph(nome, asset, (x, y, Z3 if z is None else z), rz, col, escala, tris, alt)

box("Terreno", (900, 900, .1), (0, 20, -.06), M["grama_longe"], C_LON)
# gramados perto do predio (textura de grama em escala real; os tufos de laminas ficam por cima)
for nome, x0, x1, y0, y1 in (("Gramado_Leste", 8.1, 10.9, -6.1, 38), ("Gramado_Fundo", -9, 8.1, 36, 38), ("Gramado_Oeste", -12, -9, 24, 38)):
    box(nome, (x1 - x0, y1 - y0, .06), ((x0 + x1) / 2, (y0 + y1) / 2, 0), M["grama"], C_RUA)

# ---- vegetacao trazida de "A Casa em Silencio": arvores de galhos ramificados com folhas individuais, arbustos com miolo
#      e cartoes de raminhos (transparencia recortada) e palmeiras jeriva com folhas arqueadas
import zlib
from mathutils import Euler, noise
def textura_raminhos(S=1024, semente=7):
    rnd = np.random.default_rng(semente)
    img = np.zeros((S, S, 4), np.float32)
    C = S // 2
    yy, xx = np.mgrid[0:C, 0:C].astype(np.float32)
    verdes = np.array([[38, 78, 30], [52, 96, 34], [70, 112, 40], [44, 88, 42], [86, 128, 48]], np.float32) / 255
    for cel in range(4):
        cx0, cy0 = (cel % 2) * C, (cel // 2) * C
        cor = np.zeros((C, C, 3), np.float32); alfa = np.zeros((C, C), np.float32)
        # galhos: 2 ou 3 hastes saindo da base, levemente curvas
        for h in range(rnd.integers(2, 4)):
            ang0 = rnd.uniform(-.45, .45); curva = rnd.uniform(-.5, .5)
            px, py = C / 2 + rnd.uniform(-20, 20), C - 4.0
            comp = rnd.uniform(.75, .95) * C
            pts = []
            for k in range(60):
                t = k / 59; a = ang0 + curva * t
                px += math.sin(a) * comp / 60; py -= math.cos(a) * comp / 60
                pts.append((px, py, a, t))
            for (px_, py_, a, t) in pts:          # haste fina
                d = np.hypot(xx - px_, yy - py_) < 2.2 - 1.2 * t
                cor[d] = (.20, .24, .10); alfa[d] = 1
            # folhas alternadas ao longo da haste (menores na ponta)
            for k in range(rnd.integers(9, 14)):
                t = .12 + .88 * k / 13
                px_, py_, a, _ = pts[min(59, int(t * 59))]
                lado = 1 if k % 2 else -1
                ang = a + lado * rnd.uniform(.55, 1.05)
                L = rnd.uniform(.17, .24) * C * (1.15 - .45 * t); W = L * rnd.uniform(.36, .48)
                ux, uy = math.sin(ang), -math.cos(ang)            # eixo da folha (da base para a ponta)
                dx, dy = xx - px_, yy - py_
                u = dx * ux + dy * uy; v = -dx * uy + dy * ux
                s = np.clip(u / L, 0, 1)
                larg = W / 2 * np.power(np.sin(np.pi * np.clip(s * .92 + .04, 0, 1)), .75)
                dentro = (u > 0) & (u < L) & (np.abs(v) < larg)
                base = verdes[rnd.integers(len(verdes))] * rnd.uniform(.85, 1.1)
                tom = base * (.78 + .32 * s[..., None]) * (1 - .25 * (np.abs(v) / (larg + 1e-3))[..., None])
                nerv = dentro & (np.abs(v) < 1.3)
                tom = np.where(nerv[..., None], base * 1.35, tom)
                cor[dentro] = tom[dentro]; alfa[dentro] = 1
        cor *= (1 + .08 * rnd.standard_normal((C, C, 1))).astype(np.float32)
        img[cy0:cy0 + C, cx0:cx0 + C, :3] = np.clip(cor, 0, 1); img[cy0:cy0 + C, cx0:cx0 + C, 3] = alfa
    # "sangra" a cor para os pixels transparentes vizinhos (evita borda escura no mipmap)
    for _ in range(4):
        vaz = img[..., 3] == 0
        viz = np.maximum.reduce([np.roll(img[..., :3], s, ax) for s in (1, -1) for ax in (0, 1)])
        img[..., :3] = np.where(vaz[..., None], viz, img[..., :3])
    return img

def textura_folha(W=1024, H=1024, semente=11):
    rnd = np.random.default_rng(semente)
    img = np.zeros((H, W, 4), np.float32)
    C = W // 2
    yy, xx = np.mgrid[0:H, 0:C].astype(np.float32)
    for cel in range(2):
        cor = np.zeros((H, C, 3), np.float32); alfa = np.zeros((H, C), np.float32)
        cx = C / 2
        # raque (nervura central), da base (v=0, embaixo da imagem) ate a ponta
        d = np.abs(xx - cx) < np.interp(yy, [0, H], [1.2, 3.2])
        cor[d] = (.42, .40, .18); alfa[d] = 1
        n = 54
        for k in range(n):
            t = (k + .5) / n                                    # 0 = ponta (topo da imagem), 1 = base
            y0 = 8 + t * (H - 20)
            for lado in (-1, 1):
                if rnd.random() < .06: continue                 # falhas naturais
                L = C * .47 * math.sin(math.pi * min(1, .12 + t * .95)) * rnd.uniform(.85, 1.08)
                ang = math.radians(rnd.uniform(50, 64))          # foliolo inclinado para a ponta
                ux, uy = lado * math.sin(ang), -math.cos(ang)
                ux2, uy2 = ux, uy + .35                          # pende levemente
                nn = math.hypot(ux2, uy2); ux2, uy2 = ux2 / nn, uy2 / nn
                dx, dy = xx - cx, yy - y0
                u = dx * ux2 + dy * uy2; v = -dx * uy2 + dy * ux2
                s = np.clip(u / max(L, 1), 0, 1)
                larg = 5.4 * np.sin(np.pi * np.clip(s * .95 + .03, 0, 1)) ** .6 + .6
                dentro = (u > 0) & (u < L) & (np.abs(v) < larg)
                base = np.array([.16, .33, .11]) * rnd.uniform(.85, 1.15) + np.array([.04, .05, .0]) * t
                tom = base * (.75 + .4 * (1 - s))[..., None] * (1 - .25 * (np.abs(v) / (larg + 1e-3)))[..., None]
                cor[dentro] = tom[dentro]; alfa[dentro] = 1
        cor *= (1 + .07 * rnd.standard_normal((H, C, 1))).astype(np.float32)
        img[:, cel * C:(cel + 1) * C, :3] = np.clip(cor, 0, 1); img[:, cel * C:(cel + 1) * C, 3] = alfa
    for _ in range(4):                                          # sangra a cor para a borda transparente (mipmap)
        vaz = img[..., 3] == 0
        viz = np.maximum.reduce([np.roll(img[..., :3], s, ax) for s in (1, -1) for ax in (0, 1)])
        img[..., :3] = np.where(vaz[..., None], viz, img[..., :3])
    return img

def imagem_rgba(nome, arr):
    h, w, _ = arr.shape; img = bpy.data.images.new(nome, w, h, alpha=True)
    img.pixels.foreach_set(np.flipud(arr).ravel()); img.pack(); return img
def mat_recorte(nome, img, rough=.55):
    """Folhas com transparencia recortada (funciona no Cycles e no three.js); UV propria."""
    m = bpy.data.materials.new(nome); nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; r = nt.nodes.new("ShaderNodeMath"); r.operation = "ROUND"
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"]); nt.links.new(t.outputs["Alpha"], r.inputs[0]); nt.links.new(r.outputs[0], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = rough; nt.links.new(b.outputs[0], out.inputs[0])
    for attr, val in (("surface_render_method", "DITHERED"), ("blend_method", "CLIP")):
        try: setattr(m, attr, val)
        except Exception: pass
    m.use_backface_culling = False
    return m
def folhagem_mat(name, c1, c2):
    m = bpy.data.materials.new(name); nt = m.node_tree; n = nt.nodes; L = nt.links.new; b = n.get("Principled BSDF")
    tc = n.new("ShaderNodeTexCoord"); nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3; nz.inputs["Detail"].default_value = 6
    L(tc.outputs["Object"], nz.inputs["Vector"])
    rp = n.new("ShaderNodeValToRGB"); e = rp.color_ramp.elements
    e[0].color = (*lin(hx(c1)), 1); e[1].color = (*lin(hx(c2)), 1)
    L(nz.outputs["Fac"], rp.inputs["Fac"]); L(rp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = .75; m.diffuse_color = (*lin(hx(c1)), 1); m.use_backface_culling = False
    return m
M["folhagem"] = folhagem_mat("Folhagem", "#274d1f", "#5d8a35"); M["ipe"] = folhagem_mat("Flores_Ipe_Amarelo", "#d9a90c", "#f5d423")
M["folha_arb"] = mat_recorte("Folha_Arbusto", imagem_rgba("textura_raminhos", textura_raminhos()))
M["folha_palm"] = mat_recorte("Folha_Palmeira", imagem_rgba("textura_folha_palmeira", textura_folha()), .5)
M["miolo"] = mat("Arbusto_Miolo", "#16300f", .9)
_TS = os.path.join(PH_DIR, "tree_small_02", "textures", "tree_small_02_diff_1k.jpg")
M["tronco"] = img_mat("Tronco_Arvore", bpy.data.images.load(_TS), .8, .9) if os.path.exists(_TS) else mat("Tronco_Arvore", "#5c4b3c", 1)
M["tronco_palm"] = mat("Tronco_Palmeira", "#6b5b4a", 1)
M["lamina"] = mat("Grama_Lamina", "#5f8a3a", .8)

def arvore(nome, x, y, z, alt, flor=False, larga=False):
    """Arvore procedural: galhos ramificados (tronco afinando) e folhas individuais."""
    rr = random.Random(sum(map(ord, nome)) * 7919); wood, leaf = bmesh.new(), bmesh.new(); k_ = alt / 6.5
    def galho(p, d, L, r, depth):
        end = p + d * L
        m = Matrix.Translation((p + end) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        bmesh.ops.create_cone(wood, cap_ends=False, segments=10 if depth > 2 else 6, radius1=r, radius2=r * .7, depth=L, matrix=m)
        if depth == 0:
            for k in range(62 if flor else 58):
                c = end + Vector((rr.gauss(0, .42), rr.gauss(0, .42), rr.gauss(.1, .28))) * k_
                sz = (rr.uniform(.07, .11) if flor else rr.uniform(.09, .15)) * k_
                q = Euler((rr.random() * PI, rr.random() * PI, rr.random() * PI)).to_matrix()
                vs = [leaf.verts.new(c + q @ (Vector(v) * sz)) for v in ((-1, -.45, 0), (0, -.6, .05), (1, 0, 0), (0, .6, .05), (-1, .45, 0))]
                leaf.faces.new(vs)
            return
        n = 3 if depth > 1 else rr.choice((2, 3))
        for i in range(n):
            ax = Vector((rr.uniform(-1, 1), rr.uniform(-1, 1), 0))
            if ax.length < .1: ax = Vector((1, 0, 0))
            ang = rr.uniform(.7, 1.1) if larga else rr.uniform(.35, .75)
            nd = Matrix.Rotation(ang, 3, ax.normalized()) @ d
            nd.z = max(nd.z, .05 if larga else .2); nd.normalize()
            galho(end, nd, L * rr.uniform(.62, .8), r * .62, depth - 1)
    galho(Vector((0, 0, 0)), Vector((rr.uniform(-.08, .08), rr.uniform(-.08, .08), 1)).normalized(), (2.6 if larga else 2.3) * k_, .17 * k_, 4)
    rz = rr.random() * 2 * PI
    finish(nome + "_Galhos", wood, (x, y, z), M["tronco"], C_VEG, smooth=True, rot=(0, 0, rz))
    finish(nome + "_Folhas", leaf, (x, y, z), M["ipe"] if flor else M["folhagem"], C_VEG, rot=(0, 0, rz))

def arbusto(nome, x, y, z, alt, col_miolo=None, col_folhas=None):
    """Arbusto: miolo escuro (da volume) e dezenas de cartoes com raminhos de folhas."""
    rr = random.Random(zlib.crc32(("%s%.2f%.2f" % (nome, x, y)).encode())); r = Vector((alt * rr.uniform(.5, .65), alt * rr.uniform(.5, .65), alt * .5)); c = Vector((x, y, z + alt * .5))
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1); sem = Vector((rr.uniform(0, 50), rr.uniform(0, 50), rr.uniform(0, 50)))
    for v in bm.verts:
        n = v.co.normalized(); k = .82 * (1 + .18 * noise.noise(n * 2.2 + sem)); v.co = Vector((n.x * r.x * k, n.y * r.y * k, n.z * r.z * k)) + c
    finish(nome + "_Miolo", bm, (0, 0, 0), M["miolo"], col_miolo or C_VEG, smooth=True)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    area = 4 * math.pi * ((r.x * r.y) ** 1.6 + (r.x * r.z) ** 1.6 + (r.y * r.z) ** 1.6) ** (1 / 1.6) / 3 ** (1 / 1.6)
    n_cart = int(min(140, max(30, area * 45))); esc = max(.6, min(1.15, (r.x + r.y) / 2 / .55)); feitos = tent = 0
    while feitos < n_cart and tent < n_cart * 4:
        tent += 1
        d = Vector((rr.gauss(0, 1), rr.gauss(0, 1), abs(rr.gauss(0, 1)) * 1.3 - .25)).normalized()
        p = Vector((d.x * r.x, d.y * r.y, d.z * r.z)) * rr.uniform(.80, 1.0) + c
        if p.z < z + .04: continue
        nrm = Vector((d.x / r.x, d.y / r.y, d.z / r.z)).normalized(); tam = rr.uniform(.30, .46) * esc
        cima = (nrm * .55 + Vector((0, 0, 1)) * .45 + Vector((rr.uniform(-.4, .4), rr.uniform(-.4, .4), 0))).normalized()
        lado = cima.cross(nrm)
        if lado.length < 1e-3: lado = Vector((1, 0, 0))
        lado.normalize(); lado = Matrix.Rotation(rr.uniform(-.6, .6), 3, cima) @ lado
        base = p - cima * tam * .25; cel = rr.randrange(4); u0, v0 = (cel % 2) * .5, 1 - (cel // 2 + 1) * .5
        vs = [bm.verts.new(q) for q in (base - lado * tam / 2, base + lado * tam / 2, base + lado * tam / 2 + cima * tam, base - lado * tam / 2 + cima * tam)]
        f = bm.faces.new(vs)
        for lp, (uu, vv) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))): lp[uvl].uv = (u0 + .005 + uu * .49, v0 + .005 + vv * .49)
        feitos += 1
    finish(nome + "_Folhas", bm, (0, 0, 0), M["folha_arb"], col_folhas or C_GRA)
def vaso_planta(nome, x, y, z, alt, col, m_vaso=None):
    """Planta de vaso para dentro de casa: vaso de ceramica, terra e folhagem de raminhos (como os arbustos)."""
    hv = min(.34, alt * .35)
    cyl(nome + "_Vaso", .13, .17, hv, (x, y, z + hv / 2), m_vaso or M["telha"], col, seg=14); cyl(nome + "_Terra", .155, .155, .02, (x, y, z + hv - .005), M["terra"], col, seg=14)
    arbusto(nome, x, y, z + hv - .08, alt - hv + .08, col, C_MIU)

def copa_palmeira(nome, topo, raio_tronco, rnd, m_folha, colecao, pai=None):
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    n_folhas = 18
    for k in range(n_folhas):
        idade = k / (n_folhas - 1)                               # 0 = folha nova (em pe), 1 = velha (caida)
        az = k * 2.39996 + rnd.uniform(-.2, .2)                  # angulo de ouro: distribui em volta
        theta = math.radians(18 + idade * 62 + rnd.uniform(-6, 6))   # inclinacao a partir da vertical
        L = rnd.uniform(2.3, 3.0) * (.85 + .15 * (1 - abs(idade - .55)))
        g = .55 + idade * 1.5                                    # quanto o peso puxa para baixo
        d = Vector((math.cos(az) * math.sin(theta), math.sin(az) * math.sin(theta), math.cos(theta)))
        p = topo + Vector((math.cos(az), math.sin(az), 0)) * raio_tronco * .6
        N = 11; passo = L / N
        pts, tans = [p.copy()], []
        for i in range(N):
            d = (d - Vector((0, 0, g * passo * .55))).normalized()
            p = p + d * passo; pts.append(p.copy()); tans.append(d.copy())
        tans.append(tans[-1])
        celula = rnd.randrange(2); u0 = celula * .5
        for faixa, giro in ((0, 0.0), (1, math.radians(rnd.choice((-1, 1)) * rnd.uniform(55, 70)))):
            largura_max = rnd.uniform(.95, 1.15) * (1 if faixa == 0 else .8)
            dobra = math.radians(rnd.uniform(22, 34))            # asas caidas (V)
            linhas = []
            for i, (pt, tg) in enumerate(zip(pts, tans)):
                tv = i / N
                w = largura_max * math.sin(math.pi * min(1, .1 + tv * .98)) ** .7 * .5 + .04
                lado = tg.cross(Vector((0, 0, 1)))
                if lado.length < 1e-4: lado = Vector((1, 0, 0))
                lado.normalize()
                lado = Matrix.Rotation(giro, 3, tg) @ lado
                baixo = tg.cross(lado).normalized()
                if baixo.z > 0: baixo = -baixo
                asaE = (-lado * math.cos(dobra) + baixo * math.sin(dobra)) * w
                asaD = (lado * math.cos(dobra) + baixo * math.sin(dobra)) * w
                linhas.append([bm.verts.new(pt + asaE), bm.verts.new(pt), bm.verts.new(pt + asaD)])
            for i in range(N):
                for j in range(2):
                    f = bm.faces.new((linhas[i][j], linhas[i][j + 1], linhas[i + 1][j + 1], linhas[i + 1][j]))
                    for lp, (uu, vv) in zip(f.loops, ((j * .5, i / N), ((j + 1) * .5, i / N), ((j + 1) * .5, (i + 1) / N), (j * .5, (i + 1) / N))):
                        lp[uvl].uv = (u0 + .004 + uu * .492, .004 + vv * .992)   # v=0 na base da folha (embaixo da textura)
    # base da copa: bainhas das folhas (um bulbo curto em volta do topo do tronco)
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me); bm.free()
    for poly in me.polygons: poly.use_smooth = True
    me.materials.append(m_folha)
    ob = bpy.data.objects.new(nome, me); colecao.objects.link(ob)
    if pai:
        ob.parent = pai; ob.matrix_parent_inverse = pai.matrix_world.inverted()
    ob["detalhado"] = True; ob["palmeira_v2"] = True
    return ob, len(me.polygons) * 2

def palmeira(nome, x, y, z, h):
    """Palmeira jeriva: tronco, palmito e 18 folhas arqueadas."""
    rr = random.Random(zlib.crc32(nome.encode()))
    cyl(nome + "_Tronco", .19, .12, h, (x, y, z + h / 2), M["tronco_palm"], C_VEG, seg=14)
    cyl(nome + "_Palmito", .15, .14, 1.0, (x, y, z + h + .45), M["folhagem"], C_VEG, seg=14)
    copa_palmeira(nome + "_Copa", Vector((x, y, z + h + .9)), .15, rr, M["folha_palm"], C_GRA)

# grama de verdade: tufos de laminas finas (9 laminas por tufo), espalhados nos gramados que o jogador ve de perto
def tufos(nome, x0, x1, y0, y1, n, z=0.0, alt=(.1, .22)):
    bm = bmesh.new()
    for k in range(n):
        cx_, cy_ = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        for j in range(9):
            a = rnd.uniform(0, 6.3); d = rnd.uniform(0, .09); h = rnd.uniform(*alt); px, py = cx_ + math.cos(a) * d, cy_ + math.sin(a) * d
            la = rnd.uniform(0, 6.3); wx, wy = math.cos(la) * .011, math.sin(la) * .011; inc = rnd.uniform(.02, .09)
            v = [bm.verts.new((px - wx, py - wy, z)), bm.verts.new((px + wx, py + wy, z)), bm.verts.new((px + math.cos(a) * inc * .5, py + math.sin(a) * inc * .5, z + h * .6)), bm.verts.new((px + math.cos(a) * inc, py + math.sin(a) * inc, z + h))]
            bm.faces.new((v[0], v[1], v[2])); bm.faces.new((v[0], v[2], v[3]))
    finish(nome, bm, (0, 0, 0), M["lamina"], C_GRA)
tufos("Grama_Jardim_Leste", 8.3, 10.85, -5.95, 2.0, 650); tufos("Grama_Jardim_Leste_B", 8.3, 10.85, 2.0, 8.0, 450)      # so onde se anda (o resto e o gramado do chao)
box("Asfalto", (130, 7, .12), (0, -12.5, .06), M["asfalto"], C_RUA)
for nome, y, larg in (("Calcada", -7.55, 2.9), ("Calcada_Frente", -17.45, 2.9)):
    box(nome, (130, larg, FZ), (0, y, FZ / 2), M["calcada"], C_RUA)
for y in (-9.05, -15.95): box("Meio_Fio", (130, .18, .2), (0, y, .1), M["meiofio"], C_RUA)
x = -62
while x < 62:
    if not (1.5 < x + 1.1 < 12.5): box("Faixa_Tracejada", (2.2, .12, .004), (x + 1.1, -12.5, .123), M["faixa_am"], C_RUA)
    x += 6.0
for k in range(7): box("Faixa_Pedestre", (.45, 6.5, .004), (4.2 + k * .9, -12.5, .123), M["faixa"], C_RUA)       # travessia perto da entrada
for x_ in (3.2, 10.6): box("Faixa_Retencao", (.3, 3.2, .004), (x_, -10.85 if x_ > 5 else -14.15, .123), M["faixa"], C_RUA)      # linha de retencao antes da faixa, em cada sentido
box("Patio_Piso", (17.1, 14.9, FZ), (-.45, 16.55, FZ / 2), M["pavers"], C_RUA)          # patio e estacionamento entre os blocos
box("Passagem_Oeste", (3.0, 30.2, FZ), (-10.5, 9.0, FZ / 2), M["pavers"], C_RUA)        # entrada de carros, ao lado do predio
for k in range(5): box("Vaga_Faixa", (.1, 4.6, .004), (-6.5 + k * 2.6, 20.8, FZ + .003), M["faixa"], C_RUA)
for nome, x0, y0, y1 in (("Muro_Oeste", -12.1, -6.1, 38), ("Muro_Leste", 11.0, -6.1, 38)):
    box(nome, (.2, y1 - y0, 2.3), (x0, (y0 + y1) / 2, FZ + 1.15), M["muro"], C_RUA); box(nome + "_Capa", (.3, y1 - y0, .06), (x0, (y0 + y1) / 2, FZ + 2.33), M["concreto"], C_RUA)
box("Muro_Fundo", (23.3, .2, 2.3), (-.55, 38.1, FZ + 1.15), M["muro"], C_RUA)
# portao de grade da entrada de carros (aberto) e gradil do jardim leste
for k in range(14): box("Portao_Barra", (.03, .03, 2.0), (-11.9 + k * .2, -6.2, FZ + 1.05), M["grade"], C_MIU)
for z in (.1, 2.05): box("Portao_Travessa", (2.8, .04, .05), (-10.55, -6.2, FZ + z), M["grade"], C_MIU)
# gradil do jardim leste: mureta com grade de 8.1 a 9.85 e um portao de grade (abre) de 9.9 a 10.9, para descer ao jardim
for k in range(9): box("Gradil_Barra", (.03, .03, 1.6), (8.2 + k * .2, -6.2, FZ + 1.3), M["grade"], C_MIU)
box("Gradil_Mureta", (1.75, .2, .5), (8.975, -6.2, FZ + .25), M["muro"], C_RUA); box("Gradil_Travessa", (1.75, .04, .05), (8.975, -6.2, FZ + 2.05), M["grade"], C_MIU)
box("Gradil_Pilar", (.12, .2, 2.1), (9.88, -6.2, FZ + 1.05), M["muro"], C_RUA)
_pj = vazio("A_Passagem_Portao_Jardim", (10.92, -6.2, FZ), C_INT, PI); _pj["abre"] = "porta"; _pj["ang"] = -1.5; _pj["colide"] = 1; _pj["larg"] = .98
for z in (.08, 1.0, 1.95): box(_pj.name + "_Travessa", (.98, .04, .04), (.49, 0, z), M["grade"], C_INT, _pj)
for k in range(6): box(_pj.name + "_Barra", (.025, .025, 1.9), (.06 + k * .17, 0, 1.0), M["grade"], C_INT, _pj)
box(_pj.name + "_Trinco", (.08, .05, .04), (.9, -.03, 1.0), M["metal"], C_INT, _pj)
# calcadinha do jardim lateral: da entrada do portao ate a lateral do predio e ao longo dela (onde cai o que e jogado da sala)
box("Jardim_Calcada_Entrada", (2.9, 1.3, FZ), (9.55, -5.45, FZ / 2), M["calcada"], C_RUA)
box("Jardim_Calcada_Lateral", (.95, 14.2, FZ), (8.58, 2.3, FZ / 2), M["calcada"], C_RUA)
# canteiros na calcada, dos dois lados da entrada
for i, x in enumerate((-5.05, -.35)):
    box("Canteiro_%d" % i, (1.7, .6, .42), (x, -6.5, FZ + .21), M["concreto"], C_RUA); box("Canteiro_Terra_%d" % i, (1.56, .46, .04), (x, -6.5, FZ + .43), M["terra"], C_RUA)
    for k in range(3): arbusto("Canteiro_Arbusto", x - .5 + k * .5, -6.5, FZ + .42, rnd.uniform(.45, .7))
    tufos("Canteiro_Grama", x - .75, x + .75, -6.72, -6.28, 60, FZ + .45, (.06, .14))

FACES = {"-y": ((1, 0), (0, -1)), "+y": ((-1, 0), (0, 1)), "-x": ((0, -1), (-1, 0)), "+x": ((0, 1), (1, 0))}      # face -> (ao longo, para fora)
def tex_porta_enrolar(S=128):
    yy = np.mgrid[0:S, 0:S][0]; a = np.ones((S, S, 3)) * np.array(hx("#8f9296")); a *= (.78 + .22 * np.abs(np.sin(yy / S * PI * 16)))[..., None]
    return np.clip(a, 0, 1)
def tex_predio(cor, S=128):
    """Um andar por um vao de fachada: parede na cor dada e uma janela de vidro escuro com esquadria clara."""
    a = np.ones((S, S, 3)) * np.array(hx(cor)); a *= 1 + .03 * np.random.default_rng(3).standard_normal((S, S, 1))
    a[int(S * .2):int(S * .62), int(S * .2):int(S * .8)] = hx("#d9d6cc"); a[int(S * .23):int(S * .59), int(S * .23):int(S * .78)] = hx("#1d2a36")
    a[int(S * .23):int(S * .59), int(S * .495):int(S * .51)] = hx("#d9d6cc"); a[int(S * .93):, :] = np.array(hx(cor)) * .8          # montante e friso da laje
    return np.clip(a, 0, 1)
def tex_tapete(S=256):
    yy, xx = np.mgrid[0:S, 0:S]; a = np.ones((S, S, 3)) * np.array(hx("#8a3b32"))
    los = (np.abs((xx % 64) - 32) + np.abs((yy % 64) - 32)) < 20; a[los] = hx("#d9c7a0"); a[(np.abs((xx % 64) - 32) + np.abs((yy % 64) - 32)) < 9] = hx("#2c3f5a")
    a[(yy % 64 < 3) | (xx % 64 < 3)] = hx("#3a2018"); a *= 1 + .05 * np.random.default_rng(8).standard_normal((S, S, 1))
    return np.clip(a, 0, 1)
M["porta_enrolar"] = img_mat("Porta_Enrolar", np_image("porta_enrolar", tex_porta_enrolar()), 1.6, .5)
M["tapete_est"] = img_mat("Tapete_Estampado", np_image("tapete_estampado", tex_tapete()), .9, .95)
M_LONGE = [img_mat("Predio_Longe_%d" % i, np_image("predio_longe_%d" % i, tex_predio(c)), 3.2, .7) for i, c in enumerate(("#c9c4b8", "#d8cdb0", "#b7b9bc", "#d2a890", "#e2ded2", "#b9c4b4"))]
def terreo_rua(nome, fcx, fcy, face, comp, r, col, h=3.0):
    """Terreo de rua: em cada vao, loja fechada com porta de enrolar, vitrine com toldo, portaria de vidro ou garagem com grade."""
    t, n = FACES[face]; ao_x = t[0] != 0
    def cx_(suf, a, e, hh, d, fora, z, m, c=None, rot=(0, 0, 0)):
        return box(nome + suf, (a, e, hh) if ao_x else (e, a, hh), (fcx + t[0] * d + n[0] * fora, fcy + t[1] * d + n[1] * fora, z), m, c or col, rot=rot)
    nb = max(2, int(comp / 3.7)); passo = comp / nb; inc = .42 * (1 if face in ("-y", "+x") else -1)
    for k in range(nb):
        d = -comp / 2 + (k + .5) * passo; L = passo - .8; tipo = r.choice(("loja", "loja", "vitrine", "vitrine", "portaria", "garagem"))
        if tipo == "loja":
            cx_("_T_Porta", L, .06, 2.5, d, .05, FZ + 1.25, M["porta_enrolar"]); cx_("_T_Caixa", L + .1, .22, .26, d, .12, FZ + 2.63, M["persiana"])
        elif tipo == "vitrine":
            cx_("_T_Vidro", L, .04, 1.9, d, .05, FZ + 1.4, M["vidro_f3"]); cx_("_T_Mureta", L + .06, .1, .45, d, .06, FZ + .225, M["concreto"])
            cx_("_T_Quadro", L + .06, .08, .06, d, .06, FZ + 2.38, M["aluminio"], C_FMI); cx_("_T_Montante", .05, .08, 1.9, d, .06, FZ + 1.4, M["aluminio"], C_FMI)
            cx_("_T_Toldo", L + .3, 1.15, .04, d, .6, FZ + 2.52, M[r.choice(("toldo_v", "toldo_r", "toldo_a"))], rot=(inc, 0, 0) if ao_x else (0, inc, 0))
        elif tipo == "portaria":
            cx_("_T_Porta_Vidro", 1.7, .04, 2.3, d, .05, FZ + 1.15, M["vidro_f3"]); cx_("_T_Marquise", 2.4, 1.0, .1, d, .5, FZ + 2.5, M["concreto"])
            for sd in (-1, 0, 1): cx_("_T_Batente", .05, .08, 2.3, d + sd * .85, .06, FZ + 1.15, M["aluminio"], C_FMI)
            cx_("_T_Interfone", .16, .05, .24, d + 1.15, .04, FZ + 1.35, M["inox"])
        else:
            cx_("_T_Garagem", L, .05, 2.3, d, .05, FZ + 1.15, M["grade"]); cx_("_T_Garagem_Fundo", L, .03, 2.3, d, -.02, FZ + 1.15, M["preto"])

def fachada(nome, cx, cy, face, comp, zs, col, r, varandas=(), ar=.3, larg_j=1.5, pe=3.15, frisa=True, longe=False):
    """Detalhes de uma face de predio: por andar, friso da laje e uma fileira de janelas de aluminio com peitoril; algumas
    colunas viram varanda com guarda-corpo; algumas janelas tem persiana meio fechada e ar-condicionado embaixo."""
    t, n = FACES[face]; ao_x = t[0] != 0
    def P(d, fora, z): return (cx + t[0] * d + n[0] * fora, cy + t[1] * d + n[1] * fora, z)
    def cx_(suf, a, e, h, d, fora, z, m, c=None): return box(nome + suf, (a, e, h) if ao_x else (e, a, h), P(d, fora, z), m, c or (C_FMI if m in (M["aluminio"], M["grade"], M["persiana"]) else col))
    nj = max(2, int(comp / 2.9)); passo = comp / nj; rz_fora = math.atan2(n[0], -n[1])
    for zb in zs:
        if frisa: cx_("_Friso", comp + .08, .1, .16, 0, .03, zb - .08, M["concreto"], C_FMI)
        for k in range(nj):
            d = -comp / 2 + (k + .5) * passo; vid = M[r.choice(("vidro_f", "vidro_f", "vidro_f3", "vidro_f2"))]
            if k in varandas:
                lv = min(passo * .86, 2.6)
                cx_("_Var_Laje", lv, 1.0, .12, d, .5, zb + .02, M["concreto"], C_FMI); cx_("_Var_Porta", 1.7, .04, 2.1, d, .0, zb + 1.13, vid)
                cx_("_Var_Quadro", 1.8, .06, .06, d, .02, zb + 2.2, M["aluminio"]); cx_("_Var_Montante", .05, .06, 2.1, d, .02, zb + 1.13, M["aluminio"])
                cx_("_Var_Guarda", lv, .02, .95, d, .98, zb + .56, M["guarda"], C_VID); cx_("_Var_Corrimao", lv, .05, .05, d, .98, zb + 1.06, M["aluminio"])
                for sd in (-1, 1):
                    cx_("_Var_Guarda_Lado", .02, 1.0, .95, d + sd * lv / 2, .5, zb + .56, M["guarda"], C_VID); cx_("_Var_Pilarete", .05, .05, 1.0, d + sd * lv / 2, .98, zb + .58, M["aluminio"])
                continue
            zc = zb + 1.6; lj, aj = larg_j, 1.2
            cx_("_Jan_Vidro", lj - .06, .03, aj - .06, d, -.005, zc, vid)
            cx_("_Jan_Cima", lj, .07, .05, d, .02, zc + aj / 2 - .025, M["aluminio"]); cx_("_Jan_Baixo", lj, .07, .05, d, .02, zc - aj / 2 + .025, M["aluminio"])
            for sd in ((-1, 1) if longe else (-1, 0, 1)): cx_("_Jan_Lado", .05, .07, aj, d + sd * (lj / 2 - .025), .02, zc, M["aluminio"])
            if longe: continue                                           # predio distante: sem persiana nem ar-condicionado
            cx_("_Jan_Peitoril", lj + .16, .14, .04, d, .05, zc - aj / 2 - .02, M["concreto"], C_FMI)
            if r.random() < .28: cx_("_Jan_Persiana", lj - .08, .035, r.uniform(.3, .8), d, .012, zc + aj / 2 - .05 - .25, M["persiana"])
            if r.random() < ar:
                da = d + r.choice((-1, 1)) * (lj / 2 - .45); pa = P(da, .2, zb + .45)
                cx_("_ArCond", .8, .3, .55, da, .19, zb + .73, M["ar_cond"]); cx_("_ArCond_Grade", .5, .012, .44, da + .1, .345, zb + .73, M["grade"])
                cx_("_ArCond_Suporte", .86, .36, .03, da, .18, zb + .44, M["grade"])

def predio_real(nome, x0, x1, y0, y1, andares, m, faces, col=C_RUA, seed=0, varandas=(), terreo=3.3, rotulo=None, telhado=False, garagem=None, ar=.3, longe=False):
    """Predio vizinho com embasamento, frisos, janelas, varandas, ar-condicionado, platibanda, casa de maquinas e caixa d'agua."""
    r = random.Random(seed); pe = 3.15; h = terreo + andares * pe; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; w, d = x1 - x0, y1 - y0
    box(nome + "_Corpo", (w, d, h), (cx, cy, FZ + h / 2), m, col)
    box(nome + "_Embasamento", (w + .06, d + .06, terreo - .3), (cx, cy, FZ + (terreo - .3) / 2), M[r.choice(("embasamento", "f_placas", "f_cinza", "embasamento"))], col)
    box(nome + "_Marquise", (w + .5, d + .5, .14), (cx, cy, FZ + terreo - .2), M["concreto"], col)
    if telhado:
        zt = FZ + h; a = min(w, d) * .22
        vs = [(x0 - .4, y0 - .4, zt), (x1 + .4, y0 - .4, zt), (x1 + .4, y1 + .4, zt), (x0 - .4, y1 + .4, zt), (x0 - .4, cy, zt + a), (x1 + .4, cy, zt + a)]
        me = bpy.data.meshes.new(nome + "_Telhado"); me.from_pydata(vs, [], [(0, 1, 5, 4), (2, 3, 4, 5), (0, 4, 3), (1, 2, 5)]); me.materials.append(M["telha"])
        col.objects.link(bpy.data.objects.new(nome + "_Telhado", me))
    else:
        for sx, sy, tam in ((0, -1, (w + .1, .16, .7)), (0, 1, (w + .1, .16, .7)), (-1, 0, (.16, d + .1, .7)), (1, 0, (.16, d + .1, .7))):
            box(nome + "_Platibanda", tam, (cx + sx * (w / 2 - .03), cy + sy * (d / 2 - .03), FZ + h + .35), m, col)
        box(nome + "_Casa_Maquinas", (3.2, 2.8, 2.4), (cx + r.uniform(-2, 2), cy, FZ + h + 1.2), M["f_cinza"], col)
        cyl(nome + "_Caixa_Dagua", .75, .75, 1.3, (cx + r.uniform(-4, 4) * (w > 10), cy + r.uniform(-2, 2), FZ + h + .95), M["caixa_dagua"], col, seg=14)
    zs = [FZ + terreo + a * pe for a in range(andares)]
    for face in faces:
        t, n = FACES[face]; comp = w if t[0] else d
        fcx, fcy = cx + n[0] * w / 2, cy + n[1] * d / 2
        fachada(nome, fcx, fcy, face, comp, zs, col, r, varandas, ar=ar, longe=longe)
        if garagem is not None: terreo_rua(nome, fcx, fcy, face, comp, r, col)
    if rotulo:
        face = faces[0]; t, n = FACES[face]
        texto(nome + "_Texto", rotulo, .55, (cx + n[0] * (w / 2 + .3), cy + n[1] * (d / 2 + .3), FZ + terreo - .75), face, M["texto_pr"], col)

predio_real("Bloco_A", -9, 8.1, 24, 36, 4, M["f_pastilha_az"], ("-y",), seed=3, varandas=(1, 4), rotulo="BLOCO A", garagem="-y")
predio_real("Vizinho_Leste", 13, 25, -6, 16, 2, M["f_creme"], ("-x", "-y"), seed=5, telhado=True, terreo=3.0, garagem="-y", ar=.2)      # sobrado baixo: deixa o ceu a vista da janela da sala
predio_real("Vizinho_Leste_2", 27, 41, -6, 12, 6, M["f_placas"], ("-x", "-y"), seed=6, varandas=(2,), garagem="-y", longe=True)
predio_real("Vizinho_Oeste", -27, -14, -6, 12, 3, M["f_salmao"], ("+x", "-y"), seed=7, garagem="-y")
predio_real("Vizinho_Oeste_2", -44, -29, -6, 14, 7, M["f_branca"], ("+x", "-y"), seed=8, varandas=(1, 3), garagem="-y", longe=True)
for i, (x0, x1, an, m, var) in enumerate(((-62, -47, 5, "f_verde", (1,)), (-46, -33, 3, "f_amarela", ()), (-32, -19, 8, "f_placas", (0, 3)), (-18, -6, 4, "f_creme", (2,)),
                                          (-5, 9, 6, "f_pastilha", (1, 3)), (10, 22, 3, "f_salmao", ()), (23, 37, 9, "f_branca", (0, 2, 4)), (38, 52, 4, "f_cinza", (1,)), (53, 64, 6, "f_verde", ()))):
    predio_real("Predio_Frente_%d" % i, x0, x1, -31, -19, an, M[m], ("+y",), seed=20 + i, varandas=var, garagem="+y", longe=x0 > 20 or x1 < -18)
for i, (x, y, w, d, h) in enumerate(((-50, -48, 18, 14, 34), (-20, -50, 16, 14, 46), (8, -47, 20, 14, 28), (40, -50, 18, 14, 40), (-34, 62, 18, 14, 30), (22, 66, 22, 14, 38), (62, 30, 16, 20, 26), (-66, 28, 16, 22, 24))):
    box("Predio_Longe_%d" % i, (w, d, h), (x, y, h / 2), M_LONGE[i % 6], C_LON); box("Predio_Longe_Laje", (w + .3, d + .3, .5), (x, y, h + .25), M["concreto"], C_LON)     # predios ao fundo
def tex_copas(S=512, n=300, seed=4):
    """Mata vista de longe: copas de arvores lado a lado (cada uma mais clara no alto e escura na borda), em verdes variados."""
    r = np.random.default_rng(seed); px = r.random((n, 2)) * S; cor = np.array([hx(c) for c in ("#1f3d18", "#2b4d1f", "#35592a", "#27461c", "#3f6630", "#1a3314")])
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32); d1 = np.full((S, S), 1e9, np.float32); idx = np.zeros((S, S), np.int32)
    for i, (x_, y_) in enumerate(px):
        dx = np.abs(xx - x_); dx = np.minimum(dx, S - dx); dy = np.abs(yy - y_); dy = np.minimum(dy, S - dy)      # repete sem emenda
        d = dx * dx + dy * dy; m = d < d1; d1[m] = d[m]; idx[m] = i
    raio = S / math.sqrt(n) * .62; luz_ = np.clip(1.25 - np.sqrt(d1) / raio * .75, .35, 1.25)
    a = cor[r.integers(0, len(cor), n)][idx] * luz_[..., None] * (1 + .06 * r.standard_normal((S, S, 1)))
    return np.clip(a, 0, 1)
M["mata"] = img_mat("Mata_Morro", np_image("mata_copas", tex_copas()), 42.0, .95)

def _degrau(a, b, x): t = min(1.0, max(0.0, (x - a) / (b - a))); return t * t * (3 - 2 * t)
def _ampliar(a, S):
    """Amplia uma grade pequena para S x S com interpolacao (transicoes suaves)."""
    def eixo(n):
        x = np.linspace(0, n - 1, S); i0 = np.floor(x).astype(int).clip(0, n - 2); return i0, x - i0
    i0, f = eixo(a.shape[0]); a = a[i0] * (1 - f)[:, None] + a[i0 + 1] * f[:, None]
    i0, f = eixo(a.shape[1]); return a[:, i0] * (1 - f)[None, :] + a[:, i0 + 1] * f[None, :]
_COPAS = tex_copas(128, 70, 9)
def morro(nome, cx, cy, rx, ry, alt, seed, pico=1.6, n=36, paredao=.0, domo=False, casas=0):
    """Morro carioca: cristas e grotas (ruido fractal com dobra); a pintura (mata de copas, paredoes de granito nas faces
    ingremes, com transicao suave) e uma imagem propria de cada morro, vista de cima. domo = morro de pedra arredondado, com
    mata so na base. casas = casas subindo o pe da encosta, do lado do condominio."""
    from mathutils import noise as _nz
    sem = Vector((seed * 13.7, seed * 5.1, seed * 2.3))
    def altura(u, v):
        q = Vector((u * 2.2, v * 2.2, 0)) + sem
        q2 = q + Vector((_nz.noise(q * 1.3 + Vector((7, 0, 0))), _nz.noise(q * 1.3 + Vector((0, 9, 0))), 0)) * .32
        r_ = math.hypot(u, v) * (1 + _nz.noise(q * .9) * .24); base = max(0.0, 1 - r_ * r_)
        if domo: return alt * base ** .55 * (1 + .05 * _nz.noise(q * 3)) * _degrau(0, .22, base) ** .5
        rid = 0.0; amp = .5; f = 1.0
        for _ in range(4):
            rid += amp * (1 - abs(_nz.noise(q2 * f))) ** 2; amp *= .5; f *= 2.15
        h = base ** pico * (.3 + .8 * rid)
        if paredao: h += paredao * _degrau(-.15, .25, _nz.noise(q * .7 + Vector((3, 3, 0)))) * _degrau(.3, .36, h)      # degrau ingreme em parte do contorno
        return alt * h
    # ---- pintura: grade de alturas -> inclinacao -> mascara de pedra -> imagem
    G = 150; S = 512; rg = np.random.default_rng(seed)      # 512 px: os morros so se veem de longe
    Hg = np.array([[altura(i / (G - 1) * 2 - 1, j / (G - 1) * 2 - 1) for i in range(G)] for j in range(G)], np.float32)
    gy, gx = np.gradient(Hg, 2 * ry / (G - 1), 2 * rx / (G - 1)); incl = np.degrees(np.arctan(np.hypot(gx, gy)))
    hn = Hg / alt; rui = _ampliar(rg.random((24, 24)).astype(np.float32), G) - .5
    if domo: pedra = np.clip((hn - .16 + rui * .1) / .1, 0, 1)
    else: pedra = np.clip((incl - 43 + rui * 14) / 12, 0, 1) * np.clip((hn - .14) / .12, 0, 1)
    pedra = _ampliar(pedra.astype(np.float32), S) ** 1.3; sombra = _ampliar(np.clip(.82 + hn * .3 - incl / 300, .6, 1.15), S)
    rep = S // 64 + 1; mata = np.tile(_COPAS[::2, ::2], (rep, rep, 1))[:S, :S] * (.85 + .3 * _ampliar(rg.random((14, 14)).astype(np.float32), S))[..., None]
    listras = _ampliar(rg.random((6, 180)).astype(np.float32), S) if seed % 2 else _ampliar(rg.random((180, 6)).astype(np.float32), S)      # escorridos escuros no granito
    gran = (np.array(hx("#8b867d")) * (.72 + .4 * listras)[..., None]) * (1 + .05 * rg.standard_normal((S, S, 1))); gran[_ampliar(rg.random((60, 60)).astype(np.float32), S) > .8] *= .8
    img = (mata * (1 - pedra[..., None]) + gran * pedra[..., None]) * sombra[..., None]
    m = bpy.data.materials.new("Modelo_Morro_%d" % seed); nt = m.node_tree; bs = nt.nodes.get("Principled BSDF")
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = np_image("morro_%d" % seed, np.flipud(np.clip(img, 0, 1))); nt.links.new(t.outputs["Color"], bs.inputs["Base Color"]); bs.inputs["Roughness"].default_value = .95
    # ---- malha
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap"); g = []
    for j in range(n + 1):
        g.append([bm.verts.new((cx + (i / n * 2 - 1) * rx, cy + (j / n * 2 - 1) * ry, altura(i / n * 2 - 1, j / n * 2 - 1) - 3.0)) for i in range(n + 1)])
    for j in range(n):
        for i in range(n):
            vs = (g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i])
            if max(v.co.z for v in vs) < -2.995: continue
            f = bm.faces.new(vs)
            for lp, (di, dj) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))): lp[uvl].uv = ((i + di) / n, (j + dj) / n)
    finish(nome, bm, (0, 0, 0), m, C_LON, smooth=True)
    rr = random.Random(seed * 31); feitas = tent = 0
    while feitas < casas and tent < casas * 60:
        tent += 1; u, v = rr.uniform(-1, 1), rr.uniform(-1, 1); x, y = cx + u * rx, cy + v * ry; h = altura(u, v)
        if not (alt * .01 < h < alt * .16) or math.hypot(x, y - 10) > math.hypot(cx, cy - 10) * .92: continue
        if max(abs(altura(u + 6 / rx, v) - h), abs(altura(u, v + 6 / ry) - h)) > 2.2: continue      # so em terreno pouco inclinado
        w = rr.uniform(4, 7); d = rr.uniform(4, 6.5); a_ = rr.uniform(3, 6.5); rz = rr.uniform(0, 3.1)
        box(nome + "_Casa", (w, d, a_ + 3), (x, y, h - 3 + a_ / 2 - 1.5), M[rr.choice(("f_branca", "f_creme", "f_salmao", "f_amarela", "f_verde", "f_cinza"))], C_LON, rot=(0, 0, rz))
        box(nome + "_Casa_Telhado", (w + .4, d + .4, .3), (x, y, h - 3 + a_ + .15), M["telha" if rr.random() < .6 else "f_cinza"], C_LON, rot=(0, 0, rz))
        feitas += 1
for i, (x, y, rx, ry, alt, pico, par, dom, casas) in enumerate(((-170, 330, 250, 170, 185, 1.45, .22, False, 130), (150, 350, 280, 170, 215, 1.3, .2, False, 110), (350, 130, 160, 250, 150, 1.5, .18, False, 60),
                                                               (-350, 100, 160, 260, 140, 1.5, .2, False, 60), (25, 245, 62, 54, 128, 1.0, 0, True, 0), (-70, 262, 46, 40, 82, 1.0, 0, True, 0),
                                                               (-270, -220, 210, 160, 120, 1.5, .15, False, 40), (250, -260, 230, 160, 130, 1.4, .15, False, 40))):
    morro("Morro_%d" % i, x, y, rx, ry, alt, i + 1, pico, paredao=par, domo=dom, casas=casas)
# a cidade ao redor: predios e casas espalhados entre o condominio e os morros
_rc = random.Random(77)
for i in range(70):
    a_ = _rc.uniform(0, 2 * PI); d_ = _rc.uniform(75, 230); x, y = math.cos(a_) * d_, 10 + math.sin(a_) * d_
    if abs(x) < 70 and -60 < y < 75: continue
    casa = _rc.random() < .45; w, d = (_rc.uniform(8, 14), _rc.uniform(8, 12)) if casa else (_rc.uniform(14, 24), _rc.uniform(12, 18)); h = _rc.uniform(4, 7) if casa else _rc.uniform(14, 44)
    rz_ = _rc.choice((0, .3, -.2, .1))
    box("Predio_Longe_C%d" % i, (w, d, h), (x, y, h / 2), _rc.choice(M_LONGE), C_LON, rot=(0, 0, rz_))
    box("Predio_Longe_Telhado", (w + .6, d + .6, .5), (x, y, h + .25), M["telha" if casa else "concreto"], C_LON, rot=(0, 0, rz_))
# ---- carros prontos (codigo trazido do cassino / Lei Seca): frente para +X
def malha(name, verts, faces, m, col, parent=None, pos=(0, 0, 0), smooth=False, idx=None):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces)
    bm = bmesh.new(); bm.from_mesh(me); bpy.data.meshes.remove(me)
    if idx:
        bm.faces.ensure_lookup_table()
        for f, i in zip(bm.faces, idx): f.material_index = i
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, pos, m, col, parent, smooth=smooth)

def giroflex(R, col, x, z, larg=1.1):
    box("Giroflex_Base", (.32, larg, .05), (x, 0, z), M["preto"], col, R, bevel=.015)
    n = 6; w = larg / n
    for k in range(n):
        y = -larg / 2 + w * (k + .5)
        box("Giroflex_Lente_%d" % (k + 1), (.28, w * .92, .09), (x, y, z + .07), M["giro_verm"] if k < 3 else M["giro_azul"], col, R, bevel=.022)
    luz("Giroflex_Luz_Vermelha", "POINT", 0, "#ff1a10", (x, -.35, z + .2), col, R)
    luz("Giroflex_Luz_Azul", "POINT", 0, "#2050ff", (x, .35, z + .2), col, R)

CARROS = os.path.join(AQUI, "modelos", "carros")

def repintar(img, cor, nome):
    """Troca a cor da pintura (pixels saturados da textura) mantendo sombras, frisos e detalhes."""
    w, h = img.size; px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px); px = px.reshape(-1, 4)
    rgb = px[:, :3]; mx = rgb.max(1); mn = rgb.min(1); sat = (mx - mn) / np.maximum(mx, 1e-4)
    m = (sat > .3) & (mx > .12)
    if m.sum() < 100: return img
    ref = np.median(mx[m]); k = np.clip(mx[m] / ref, 0, 1.6)[:, None]
    rgb[m] = np.clip(np.array(lin(hx(cor)) if False else hx(cor), np.float32)[None, :] * k, 0, 1)
    novo = bpy.data.images.new(nome, w, h, alpha=True); novo.pixels.foreach_set(px.ravel()); novo.pack()
    return novo

M["int_forro"] = mat("Interior_Forro", "#1d1f22", .9)      # forro interno do carro abordado

def carro_modelo(nome, col, arquivo, pos, rz, cor=None, tirar=(), janela_aberta=False, interior=False, porta=None, escala=1.0):
    """Importa modelos/carros/<arquivo>.glb com a frente para +X. Devolve (raiz, sup_y, sup_x, info) ou None se faltar."""
    caminho = os.path.join(CARROS, arquivo + ".glb")
    if not os.path.exists(caminho): return None
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=caminho)
    novos = [o for o in bpy.data.objects if o not in antes]
    R = next(o for o in novos if o.parent is None); R.name = nome
    for o in novos:
        for c in list(o.users_collection): c.objects.unlink(o)
        col.objects.link(o)
        if o is not R: o.name = nome + "_" + o.name.split(".")[0].replace("Roda_", "Roda_")
    if escala != 1.0:
        for o in novos:
            if o.type == "MESH":
                o.data.transform(Matrix.Scale(escala, 4)); o.location = o.location * escala
    corpo = next(o for o in novos if o.type == "MESH" and "Carroceria" in o.name)
    feitos = {}
    for i, s in enumerate(corpo.material_slots):          # materiais proprios deste carro (UV do modelo e preservada no pipeline)
        m = s.material.copy(); m.name = "Modelo_%s_%s" % (nome, s.material.name.split(".")[0]); s.material = m
        b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        tex = next((n for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.outputs["Color"].is_linked and any(l.to_socket.name == "Base Color" for l in n.outputs["Color"].links)), None)
        nm = m.name.lower()
        if cor and tex and tex.image and not any(k in nm for k in ("glass", "optic", "decal")):
            tex.image = feitos.setdefault(tex.image.name, repintar(tex.image, cor, "pintura_%s_%s" % (nome, tex.image.name)))
        if "glass" in nm and b:
            for l in list(b.inputs["Alpha"].links): m.node_tree.links.remove(l)
            for l in list(b.inputs["Base Color"].links): m.node_tree.links.remove(l)
            b.inputs["Base Color"].default_value = (.03, .045, .055, 1); b.inputs["Alpha"].default_value = .38 if interior else .8
            b.inputs["Roughness"].default_value = .06; b.inputs["Metallic"].default_value = 0
            for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
                try: setattr(m, attr, val)
                except Exception: pass
        if interior: m.use_backface_culling = "glass" not in nm      # lataria so por fora: por dentro entra o forro (abaixo)
    for o in novos:                                       # rodas: mesmo prefixo "Modelo_", senao o pipeline refaz a UV e embaralha a textura
        if o.type == "MESH" and o is not corpo:
            for s in o.material_slots:
                if s.material and not s.material.name.startswith("Modelo_"):
                    m = s.material.copy(); m.name = "Modelo_%s_%s" % (nome, s.material.name.split(".")[0]); s.material = m
    me = corpo.data
    bm = bmesh.new(); bm.from_mesh(me)
    nomes = [s.material.name.lower() for s in corpo.material_slots]
    apagar = [f for f in bm.faces if any(k in nomes[f.material_index] for k in tirar)]
    vidro = [f for f in bm.faces if "glass" in nomes[f.material_index]]
    esq = [f for f in vidro if f.normal.y > .55 and abs(f.normal.z) < .6]          # vidros laterais do lado do motorista (+Y)
    info = {}
    if esq:
        xs = [f.calc_center_median().x for f in esq]; meio = (min(xs) + max(xs)) / 2
        frente = [f for f in esq if f.calc_center_median().x > meio]
        c = sum((f.calc_center_median() for f in frente), Vector()) / len(frente)
        info["janela"] = c.copy()
        info["jx"] = (min(v.co.x for f in frente for v in f.verts), max(v.co.x for f in frente for v in f.verts))
        if interior:
            # o modelo traz uma "tampa" preta horizontal dentro da cabine, na altura da base das janelas, para esconder o
            # interior vazio. Com condutor e bancos la dentro ela corta o personagem no peito: sai.
            hw_c = max(v.co.y for v in bm.verts)
            for f in bm.faces:
                cf = f.calc_center_median()
                if "glass" not in nomes[f.material_index] and f.normal.z > .7 and min(xs) - .3 < cf.x < max(xs) + .12 and abs(cf.y) < hw_c * .8 and c.z - .38 < cf.z < c.z - .05:
                    apagar.append(f)
        if janela_aberta: apagar += frente
    if apagar: bmesh.ops.delete(bm, geom=list(set(apagar)), context="FACES")
    if interior:
        # forro interno: uma copia da lataria, 2 cm para dentro e virada para o interior, em material escuro.
        # Sem isso via-se a pintura do carro pelo lado de dentro (portas, colunas e teto). Como acompanha a lataria
        # por dentro, nunca aparece do lado de fora.
        mi = len(me.materials); me.materials.append(M["int_forro"]); nomes.append("int_forro")
        dup = bmesh.ops.duplicate(bm, geom=[f for f in bm.faces if "glass" not in nomes[f.material_index]])
        nf = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMFace)]
        bm.normal_update()
        for v in {v for f in nf for v in f.verts}: v.co -= v.normal * .02
        bmesh.ops.reverse_faces(bm, faces=nf)
        for f in nf: f.material_index = mi
    tem_porta = False
    if porta and "jx" in info:
        # porta do motorista: recorta a lateral esquerda entre a coluna da frente e a do meio, da soleira ao teto,
        # e separa numa peca propria com a origem na dobradica (o site gira a peca para abrir)
        hw_ = max(v.co.y for v in bm.verts)
        xd1, zb_ = info["jx"][1] + porta[1], porta[2]; xd0 = xd1 - porta[0]       # porta = (comprimento, folga a frente da janela, altura da soleira)
        for co, no in (((xd0, 0, 0), (1, 0, 0)), ((xd1, 0, 0), (1, 0, 0)), ((0, 0, zb_), (0, 0, 1))):
            fs = [f for f in bm.faces if f.calc_center_median().y > 0]
            geom = list({v for f in fs for v in f.verts}) + list({e for f in fs for e in f.edges}) + fs
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, dist=1e-4)
        for f in bm.faces:
            c = f.calc_center_median()
            f.select = bool(c.y > hw_ * .45 and xd0 < c.x < xd1 and c.z > zb_ and abs(f.normal.z) < .8)      # lataria e forro da porta
        tem_porta = any(f.select for f in bm.faces)
        info["dobradica"] = Vector((xd1, hw_ - .04, zb_ + .35))
    bm.to_mesh(me); bm.free()
    if tem_porta:
        mp = me.copy(); mp.name = nome + "_Porta"
        for malha_, manter_sel in ((me, False), (mp, True)):
            b2 = bmesh.new(); b2.from_mesh(malha_)
            bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.select != manter_sel], context="FACES")
            if manter_sel: bmesh.ops.translate(b2, verts=b2.verts, vec=-info["dobradica"])
            b2.to_mesh(malha_); b2.free()
        P = bpy.data.objects.new(nome + "_Porta", mp); col.objects.link(P); P.parent = R; P.location = info["dobradica"]
        for p_ in mp.polygons: p_.use_smooth = True
    R.location = pos; R.rotation_euler = (0, 0, rz)
    bpy.context.view_layer.update()
    pts = [Vector(c) for c in corpo.bound_box]
    hw = max(abs(p.y) for p in pts); comp = max(p.x for p in pts) - min(p.x for p in pts); alt = max(p.z for p in pts)
    info.update(hw=hw, comp=comp, alt=alt)
    if interior and "janela" in info:                     # o modelo e oco: bancos, painel e assoalho simples
        j = info["janela"]; xb = j.x - .18; zb = j.z - .62; yb = hw * .45
        for sy in (-1, 1):
            box(nome + "_Banco", (.5, .48, .1), (xb, sy * yb, zb), M["interior"], col, R, bevel=.04)
            box(nome + "_Encosto", (.12, .46, .6), (xb - .3, sy * yb, zb + .34), M["interior"], col, R, rot=(0, .2, 0), bevel=.04)
        box(nome + "_Banco_Tras", (.5, hw * 1.5, .1), (xb - .95, 0, zb + .02), M["interior"], col, R, bevel=.04)
        box(nome + "_Encosto_Tras", (.12, hw * 1.5, .5), (xb - 1.22, 0, zb + .32), M["interior"], col, R, rot=(0, .2, 0), bevel=.04)
        box(nome + "_Painel", (.3, hw * 1.55, .22), (xb + .8, 0, zb + .21), M["interior"], col, R, bevel=.05)      # topo abaixo do peitoril: nao tapa o condutor
        # volante: aro (anel), cubo e tres raios. Um disco cheio tapava o peito e os bracos do condutor
        _vp, _vr = (xb + .52, yb, zb + .39), (0, -1.15, 0)
        torno(nome + "_Volante", [(.17 + .013 * math.cos(2 * PI * k / 8), .013 * math.sin(2 * PI * k / 8)) for k in range(9)], M["preto"], col, R, pos=_vp, rot=_vr, seg=24)
        cyl(nome + "_Volante_Cubo", .045, .045, .03, _vp, M["preto"], col, R, rot=_vr, seg=12)
        for _a in (PI / 2, PI * 7 / 6, PI * 11 / 6):
            _b = box(nome + "_Volante_Raio", (.15, .028, .012), _vp, M["preto"], col, R, rot=_vr)
            _b.rotation_euler = (Matrix.Rotation(-1.15, 4, "Y") @ Matrix.Rotation(_a, 4, "Z")).to_euler()
            _b.location = Vector(_vp) + (Matrix.Rotation(-1.15, 4, "Y") @ Matrix.Rotation(_a, 4, "Z")) @ Vector((.095, 0, 0))
        box(nome + "_Assoalho", (comp * .62, hw * 1.5, .03), (xb - .2, 0, zb - .28), M["preto"], col, R)
        info["banco"] = [xb, yb, zb + .05]
    ev = corpo.evaluated_get(bpy.context.evaluated_depsgraph_get())
    def sup_y(x, z, lado):
        ok, lc, _, _ = ev.ray_cast(Vector((x, lado * 3.0, z)), Vector((0, -lado, 0)))
        return lc.y if ok else lado * hw
    def sup_x(y, z, ponta):
        ok, lc, _, _ = ev.ray_cast(Vector((ponta * 6.0, y, z)), Vector((-ponta, 0, 0)))
        return lc.x if ok else ponta * comp / 2
    return R, sup_y, sup_x, info

def faixa_lateral(nome, R, col, sup_y, x0, x1, z0, z1, m, n=24):
    """Faixa pintada que acompanha a lateral do carro (dos dois lados)."""
    for lado in (1, -1):
        vs, fs = [], []
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            for z in (z0, z1): vs.append((x, sup_y(x, z, lado) + lado * .006, z))
        for i in range(n): fs.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
        malha(nome, vs, fs, m, col, R)


def viatura(nome, x, y, rz, texto_lado, m_faixa, arquivo="perua", cor="#eceded"):
    r = carro_modelo(nome, C_VEIC, arquivo, (x, y, .12), rz, cor=cor, escala=1.08)
    if not r: return
    V_, sy_, sx_, inf = r
    giroflex(V_, C_VEIC, -.25, inf["alt"] + .03, larg=1.05)
    faixa_lateral(nome + "_Listra", V_, C_VEIC, sy_, -2.0, 1.68, .54, .71, m_faixa)
    for lado in (1, -1):
        v = "+y" if lado > 0 else "-y"
        texto(nome + "_Adesivo", texto_lado, .085, (-.15, sy_(-.15, .89, lado) + lado * .008, .89), v, M["texto_az"] if m_faixa is M["faixa_pm"] else M["texto_pr"], C_VEIC, V_)
        cyl(nome + "_Brasao_Imagem", .09, .09, .004, (1.03, sy_(1.03, .89, lado) + lado * .006, .89), M["brasao"], C_VEIC, V_, rot=(PI / 2, 0, 0), seg=28)
# (viatura da PM tirada a pedido do usuario)
viatura("Viatura_PC", -12.6, -10.15, 0, "POLÍCIA CIVIL", M["faixa_pc"], "seda", "#e6e6e4")
# (taxi e hatch tirados para economizar triangulos: na rua fica so a viatura da Civil)

# arvores, postes, carros e mobiliario urbano
# (as arvores do outro lado da rua e as mais distantes sairam para economizar triangulos)
for i, e in enumerate(((-7.5, -8.3, 6.5), (6.5, -8.3, 7.5), None, None, None, None, None, (-5.5, 17.5, 6.2), (4.0, 15.5, 7.0), (9.6, 4.0, 5.5), (9.6, 20, 6.5))):
    if e is None: continue
    x, y, alt = e
    if i in (9, 10): palmeira("Palmeira_%d" % i, x, y, 0, alt)
    else: arvore(("Ipe_Amarelo_%d" if i in (1, 5) else "Amendoeira_%d") % i, x, y, FZ, alt, flor=i in (1, 5), larga=i not in (1, 5))
    if y < 0: box("Arvore_Canteiro", (1.1, 1.1, .03), (x, y, FZ + .015), M["terra"], C_RUA)
for i, (x, y, rz) in enumerate(((-15, -8.6, 0), (12, -8.6, 0), (38, -8.6, 0), (-36, -8.6, 0), (-2, -16.4, PI), (26, -16.4, PI), (-28, -16.4, PI))):
    if not ph("Poste_Luz_%d" % i, "street_lamp_01", x, y, FZ, rz, C_RUA, alt=6.5, tris=900):
        cyl("Poste_Luz_%d" % i, .09, .07, 6.5, (x, y, FZ + 3.25), M["poste"], C_RUA, seg=10)
for i, x in enumerate((-30, 0, 30)):                         # postes de concreto com fiacao, do outro lado da rua
    cyl("Poste_Fio_%d" % i, .14, .1, 8.5, (x, -16.2, FZ + 4.25), M["poste"], C_RUA, seg=10); box("Poste_Fio_Cruzeta", (.1, 1.6, .1), (x, -16.2, FZ + 7.9), M["poste"], C_RUA)
    if i:
        for dy in (-.7, 0, .7): barra("Fio", (x - 30, -16.2 + dy, FZ + 7.95), (x, -16.2 + dy, FZ + 7.95), .012, M["preto"], C_MIU, seg=4)
for i, (x, y, rz) in enumerate(((-2.2, 20.8, 0), (5.6, 20.8, PI))):
    ph("Carro_Coberto_%d" % i, "covered_car", x, y, FZ if y > 0 else .12, rz, C_RUA, alt=1.45, tris=2500)
cyl("Hidrante", .09, .09, .6, (2.6, -8.6, FZ + .3), M["extintor"], C_RUA, seg=12); cyl("Hidrante_Tampa", .11, .05, .1, (2.6, -8.6, FZ + .65), M["extintor"], C_RUA, seg=12); cyl("Hidrante_Boca", .05, .05, .26, (2.6, -8.6, FZ + .42), M["extintor"], C_RUA, rot=(PI / 2, 0, 0), seg=10)
palmeira("Palmeira_Patio", -7.6, 22.0, FZ, 6.8); palmeira("Palmeira_Calcada", 23.5, -8.2, FZ, 7.4)
ph("Banco_Patio", "painted_wooden_bench", -7.9, 14.5, FZ, PI / 2, C_RUA, alt=.85, tris=1200)
cyl("Lixeira_Rua", .2, .17, .7, (1.4, -6.5, FZ + .45), M["f_verde"], C_RUA, seg=14); cyl("Lixeira_Rua_Pe", .03, .03, .2, (1.4, -6.5, FZ + .1), M["grade"], C_RUA, seg=8)
for i, (x, y) in enumerate(((-7, -12), (18, -13.5))): cyl("Bueiro_%d" % i, .32, .32, .012, (x, y, .124), M["grade"], C_RUA, seg=20)
for i in range(46):                                           # arbustos e tufos ao longo dos muros e do jardim leste
    lado = i % 3; t_ = rnd.random()
    x, y = ((10.6 - rnd.uniform(0, 1.6), -5 + t_ * 40) if lado == 0 else (-8.3 + rnd.uniform(-.4, .4), 10 + t_ * 13) if lado == 1 else (-8 + t_ * 15.5, 23.4 + rnd.uniform(-.3, .3)))
    arbusto("Arbusto", x, y, FZ * (lado != 0), rnd.uniform(.5, 1.3))

# ================================================================== 2. o predio (Bloco B): massas e fachada
HT = FZ + 4 * 3.15                                      # topo do 4o andar
MF = M["f_pastilha"]
box("Predio_Terreo_Leste", (7.0, 15.2, PDT), (4.6, 1.5, FZ + PDT / 2), M["embasamento"], C_PRED)
box("Predio_Terreo_Norte", (7.4, 7.4, PDT), (-2.7, 5.4, FZ + PDT / 2), M["embasamento"], C_PRED)
for k, (x0, x1, y0, y1) in enumerate(((-9, -6.5, -6.1, -.14), (-9, -6.5, 1.34, 9.1), (-9, -8.06, -.14, 1.34))):      # em volta da cabine do elevador
    box("Predio_Terreo_Oeste_%d" % k, (x1 - x0, y1 - y0, PDT), ((x0 + x1) / 2, (y0 + y1) / 2, FZ + PDT / 2), M["embasamento"], C_PRED)
box("Predio_Terreo_Oeste_Verga", (1.56, 1.48, PDT - 2.34), (-7.28, .6, FZ + 2.34 + (PDT - 2.34) / 2), M["embasamento"], C_PRED)
for k, (x0, x1, y0, y1) in enumerate(((-3.8, 8.1, -6.1, 9.1), (-9, -3.8, -6.1, -3.3), (-9, -6.5, -3.3, 9.1), (-6.5, -3.8, .1, 9.1))):      # 2o andar, com o vazio da escada
    box("Predio_Andar_2_%d" % k, (x1 - x0, y1 - y0, Z3 - .15 - FZ - PDT), ((x0 + x1) / 2, (y0 + y1) / 2, (FZ + PDT + Z3 - .15) / 2), MF, C_PRED)
box("Escada_Fundo", (2.7, 3.3, .1), (-5.15, -1.65, Z3 - 1.35), M["concreto"], C_COR)
box("Predio_3_Sul", (11.9, 6.0, PD + .15), (2.15, -3.1, Z3 - .15 + (PD + .15) / 2), MF, C_PRED)          # aptos 303 e 304 (fechados)
box("Predio_3_Sudoeste", (5.2, 2.8, PD + .15), (-6.4, -4.7, Z3 - .15 + (PD + .15) / 2), MF, C_PRED)
for k, (x0, x1, y0, y1) in enumerate(((-9, -6.5, -3.3, -.14), (-9, -6.5, 1.34, 9.1), (-9, -8.06, -.14, 1.34))):      # em volta da cabine do elevador
    box("Predio_3_Oeste_%d" % k, (x1 - x0, y1 - y0, PD + .15), ((x0 + x1) / 2, (y0 + y1) / 2, Z3 - .15 + (PD + .15) / 2), MF, C_PRED)
box("Predio_3_Oeste_Verga", (1.56, 1.48, PD - 2.34), (-7.28, .6, Z3 + 2.34 + (PD - 2.34) / 2), MF, C_PRED); box("Predio_3_Oeste_Base", (1.56, 1.48, .12), (-7.28, .6, Z3 - .09 - .06), MF, C_PRED)
box("Predio_3_Fundo_301", (5.3, 3.4, PD + .15), (-3.75, 7.4, Z3 - .15 + (PD + .15) / 2), MF, C_PRED)
box("Predio_Andar_4", (17.1, 15.2, HT - Z3 - PD), (-.45, 1.5, (Z3 + PD + HT) / 2), MF, C_PRED)
for sx, sy, tam in ((0, -1, (17.2, .16, .7)), (0, 1, (17.2, .16, .7)), (-1, 0, (.16, 15.3, .7)), (1, 0, (.16, 15.3, .7))):
    box("Predio_Platibanda", tam, (-.45 + sx * 8.52, 1.5 + sy * 7.57, HT + .35), MF, C_PRED)
box("Predio_Casa_Maquinas", (3.0, 3.0, 2.4), (-7.2, 1.0, HT + 1.2), M["f_cinza"], C_PRED); cyl("Predio_Caixa_Dagua", .8, .8, 1.4, (2, 3, HT + 1.0), M["caixa_dagua"], C_PRED, seg=14)
_r = random.Random(11)
fachada("Predio_Sul", -.45, -6.1, "-y", 17.1, [FZ + 3.15, Z3, Z3 + 3.15], C_PRED, _r, varandas=(), ar=.35)
fachada("Predio_Leste_Alto", 8.1, 1.5, "+x", 15.2, [FZ + 3.15, Z3 + 3.15], C_PRED, _r, ar=.3)
fachada("Predio_Norte_Alto", -.45, 9.1, "+y", 17.1, [FZ + 3.15, Z3 + 3.15], C_PRED, _r, ar=.3)
box("Predio_Friso_Terreo", (17.2, .12, .2), (-.45, -6.12, FZ + PDT + .0), M["concreto"], C_PRED)
box("Predio_Marquise", (4.6, 1.5, .16), (-2.7, -6.8, FZ + 2.75), M["concreto"], C_PRED)
for sx in (-1, 1): cyl("Predio_Marquise_Pilar", .07, .07, 2.7, (-2.7 + sx * 2.1, -7.4, FZ + 1.35), M["inox"], C_PRED, seg=12)
texto("Predio_Texto_Bloco", "BLOCO B", .3, (-2.7, -7.56, FZ + 2.75), "-y", M["texto_pr"], C_PRED)
texto("Predio_Texto_Numero", "Rua das Acácias, 120", .12, (-2.7, -6.14, FZ + 2.55), "-y", M["texto_br"], C_PRED)
box("Predio_Interfone_Painel", (.22, .05, .32), (-1.45, -6.13, FZ + 1.35), M["inox"], C_PRED); box("Predio_Luminaria", (.3, .12, .1), (-2.7, -6.2, FZ + 2.62), M["lamp"], C_PRED)
ph("Predio_Camera", "security_camera_01", -4.3, -6.25, FZ + 2.45, PI, C_PRED, alt=.22, tris=500)

# ================================================================== 3. portaria (terreo)
box("Portaria_Piso", (7.4, 7.6, FZ), (-2.7, -2.2, FZ / 2), M["piso_port"], C_PORT)
plano("Portaria_Teto", -6.4, 1, -6, 1.6, FZ + PDT - .001, M["teto"], C_PORT, True)
parede("Portaria_Parede_Sul", (-6.4, -6), (1, -6), M["parede_port"], C_PORT, vaos=[(.5, 2.2, .5, 2.4), (2.7, 4.7, 0, 2.4), (5.2, 6.9, .5, 2.4)], h=PDT, z0=FZ)
parede("Portaria_Parede_Oeste", (-6.4, -6), (-6.4, 1.6), M["parede_port"], C_PORT, h=PDT, z0=FZ, vaos=[(6.1, 7.1, 0, 2.1)])       # vao do elevador
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
modelo_ph("Portaria_Sofa", "sofa_02", (-2.4, .95, FZ), 0, C_PORT, max_tris=2500, alt=.8)      # longe da porta do elevador or box("Portaria_Banco", (1.6, .5, .45), (-4.6, 1.2, FZ + .22), M["mad"], C_PORT)
vaso_planta("Portaria_Planta_A", -5.9, -5.5, FZ, 1.1, C_PORT, M["louca"])
vaso_planta("Portaria_Planta_B", .5, -5.5, FZ, .9, C_PORT, M["louca"])
plafon("Luz_Portaria_A", -2.7, -3.6, 130, FZ + PDT, C_PORT); plafon("Luz_Portaria_B", -2.7, -.4, 130, FZ + PDT, C_PORT)

def elevador(nome, y0, z0, col, andar):
    """Elevador na parede oeste (x = -6.4), como os de predio residencial carioca: portal de granito com soleira de aluminio,
    duas folhas de inox escovado que correm para os lados (A_Elevador_*), botoeira com seta e anel aceso, visor do andar em
    cima, e a cabine por tras (paineis de inox com juntas, espelho, corrimao com suportes, rodape, teto com spots de LED,
    botoeira com os andares, alarme e placa de capacidade). Sem marca de fabricante."""
    x = -6.29
    # portal: granito em volta do vao, um pouco saliente da parede, e a soleira no piso
    box(nome + "_Portal_Cima", (.05, 1.4, .16), (-6.27, y0 + .5, z0 + 2.2), M["granito"], col)
    for sy in (-.13, 1.13): box(nome + "_Portal_Lado", (.05, .14, 2.12), (-6.27, y0 + sy, z0 + 1.06), M["granito"], col)
    for sy in (-.04, 1.04): box(nome + "_Batente_Lado", (.24, .06, 2.12), (-6.42, y0 + sy, z0 + 1.06), M["inox"], col)
    box(nome + "_Batente_Cima", (.24, 1.14, .06), (-6.42, y0 + .5, z0 + 2.13), M["inox"], col)
    box(nome + "_Soleira", (.3, 1.1, .012), (-6.4, y0 + .5, z0 + .006), M["aluminio"], col)
    box(nome + "_Soleira_Ranhura", (.012, 1.06, .004), (-6.43, y0 + .5, z0 + .013), M["preto"], col)
    for k, (yc, rz) in enumerate(((y0 + .25, 0), (y0 + .75, PI))):                 # folha 1 corre para -Y; folha 2 para +Y
        r = vazio("A_%s_%d" % (nome, k + 1), (-6.42, yc, z0), C_INT, rz); r["abre"] = "gaveta"; r["curso"] = .47
        box(r.name + "_Folha", (.03, .5, 2.1), (0, 0, 1.05), M["aco_elev"], C_INT, r)
        box(r.name + "_Borracha", (.034, .008, 2.1), (0, -.246, 1.05), M["preto"], C_INT, r)      # junta escura no meio
    # botoeira do pavimento: placa de inox, botao redondo com anel aceso e seta (no terreo so sobe)
    box(nome + "_Painel", (.012, .1, .24), (x + .006, y0 + 1.32, z0 + 1.12), M["inox"], C_MIU)
    setas = ((1, z0 + 1.17),) if andar == "T" else ((1, z0 + 1.17), (-1, z0 + 1.07))
    for s, zb in setas:
        cyl(nome + "_Botao_Anel", .024, .024, .006, (x + .014, y0 + 1.32, zb), M["led_verm"], C_MIU, rot=(0, PI / 2, 0), seg=16)
        cyl(nome + "_Botao", .019, .019, .01, (x + .017, y0 + 1.32, zb), M["inox"], C_MIU, rot=(0, PI / 2, 0), seg=16)
        cyl(nome + "_Seta", .008, .008, .004, (x + .023, y0 + 1.32, zb), M["preto"], C_MIU, rot=(0, PI / 2, PI / 2 * s), seg=3)
    # visor em cima do portal: vidro preto com o andar e a seta em vermelho
    box(nome + "_Visor", (.015, .3, .1), (x + .01, y0 + .5, z0 + 2.38), M["tela"], C_MIU)
    texto(nome + "_Andar", andar, .06, (x + .019, y0 + .55, z0 + 2.35), "+x", M["led_verm"], C_MIU)
    cyl(nome + "_Visor_Seta", .018, .018, .004, (x + .019, y0 + .42, z0 + 2.38), M["led_verm"], C_MIU, rot=(0, PI / 2, -PI / 2), seg=3)
    # cabine: x -8.0 .. -6.5, y y0-0.2 .. y0+1.2
    xa, xb, ya, yb = -8.0, -6.52, y0 - .2, y0 + 1.2; cab = nome + "_Cabine"; xm, ym = (xa + xb) / 2, (ya + yb) / 2
    box(cab + "_Piso", (xb - xa, yb - ya, .06), (xm, ym, z0 - .03), M["granito"], col)
    plano(cab + "_Teto", xa, xb, ya, yb, z0 + 2.3, M["inox"], col, True)
    box(cab + "_Fundo", (.04, yb - ya, 2.3), (xa - .02, ym, z0 + 1.15), M["aco_elev"], col)
    for yl in (ya - .02, yb + .02): box(cab + "_Lado", (xb - xa, .04, 2.3), (xm, yl, z0 + 1.15), M["aco_elev"], col)
    for yl, ll in ((y0 - .12, .16), (y0 + 1.12, .16)): box(cab + "_Frente", (.04, ll, 2.3), (xb, yl, z0 + 1.15), M["aco_elev"], col)
    # juntas entre os paineis de inox (linhas escuras finas) e rodape
    for yj in (ya + .47, yb - .47): box(cab + "_Junta", (.004, .006, 2.3), (xa + .002, yj, z0 + 1.15), M["preto"], col)
    for s, yl in ((1, ya), (-1, yb)):
        box(cab + "_Junta", (.006, .004, 2.3), (xm, yl + s * .002, z0 + 1.15), M["preto"], col)
        box(cab + "_Rodape", (xb - xa, .012, .1), (xm, yl + s * .006, z0 + .05), M["inox"], col)
    box(cab + "_Rodape", (.012, yb - ya, .1), (xa + .006, ym, z0 + .05), M["inox"], col)
    # espelho do fundo (da cintura para cima) e corrimao com suportes no fundo e num dos lados
    box(cab + "_Espelho", (.008, 1.1, 1.25), (xa + .004, ym, z0 + 1.55), M["espelho"], C_MIU)
    barra(cab + "_Corrimao", (xa + .07, ya + .12, z0 + .92), (xa + .07, yb - .12, z0 + .92), .018, M["inox"], C_MIU, seg=10)
    for yc in (ya + .2, yb - .2): barra(cab + "_Corrimao_Suporte", (xa + .005, yc, z0 + .92), (xa + .07, yc, z0 + .92), .01, M["inox"], C_MIU, seg=8)
    barra(cab + "_Corrimao_Lado", (xa + .15, ya + .07, z0 + .92), (xb - .45, ya + .07, z0 + .92), .018, M["inox"], C_MIU, seg=10)
    # teto: moldura e quatro spots de LED
    box(cab + "_Teto_Moldura", (xb - xa - .2, yb - ya - .2, .02), (xm, ym, z0 + 2.285), M["preto"], col)
    for dx in (-.3, .3):
        for dy in (-.35, .35): cyl(cab + "_Spot", .04, .04, .012, (xm + dx, ym + dy, z0 + 2.27), M["lamp_f"], col, seg=14)
    box(cab + "_Ventilacao", (.3, .08, .004), (xm, ym, z0 + 2.272), M["grade"], col)
    # botoeira da cabine no lado +Y, perto da porta: visor, andares T 1 2 3 4, alarme e placa de capacidade
    yp = yb - .012; xp = xb - .22
    box(cab + "_Botoeira", (.18, .012, .7), (xp, yp, z0 + 1.2), M["inox"], C_MIU)
    box(cab + "_Botoeira_Visor", (.1, .004, .05), (xp, yp - .008, z0 + 1.48), M["tela"], C_MIU)
    texto(cab + "_Botoeira_Andar", andar, .03, (xp, yp - .011, z0 + 1.47), "-y", M["led_verm"], C_MIU)
    for k, rot in enumerate(("T", "1", "2", "3", "4")):
        zb = z0 + 1.0 + k * .075; aceso = (k == 0) if andar == "T" else (k == 3)
        cyl(cab + "_Botao", .016, .016, .008, (xp + .03, yp - .01, zb), M["led_verm"] if aceso else M["inox"], C_MIU, rot=(PI / 2, 0, 0), seg=14)
        cyl(cab + "_Botao_Aro", .02, .02, .004, (xp + .03, yp - .007, zb), M["preto"], C_MIU, rot=(PI / 2, 0, 0), seg=14)
        texto(cab + "_Botao_Num", rot, .026, (xp - .03, yp - .008, zb - .01), "-y", M["texto_pr"], C_MIU)
    cyl(cab + "_Alarme", .018, .018, .01, (xp + .03, yp - .01, z0 + .9), M.get("amarelo", M["led_verm"]), C_MIU, rot=(PI / 2, 0, 0), seg=14)
    box(cab + "_Placa", (.14, .004, .05), (xp, yp - .006, z0 + 1.66), M["metal"], C_MIU)
    texto(cab + "_Placa_Texto", "8 PESSOAS  600 kg", .011, (xp, yp - .009, z0 + 1.655), "-y", M["texto_pr"], C_MIU)
    luz(cab + "_Luz", "POINT", 24, "#f4f6ff", (xm, ym, z0 + 2.2), C_LUZ, shadow_soft_size=.05)
    ponto(nome.replace("Elevador_", "Cabine_"), -7.3, y0 + .5, (1, 0), z0)
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
parede("Corredor_Parede_Oeste", (-6.4, 0), (-6.4, 1.6), M["parede_cor"], C_COR, vaos=[(.1, 1.1, 0, 2.1)])       # vao do elevador
parede("Corredor_Parede_Leste", (8, 0), (8, 1.6), M["parede_cor"], C_COR)
for nome, x in (("303", -2.95), ("304", 3.95)):                                      # portas dos aptos do lado sul: sempre fechadas
    folha_porta("Corredor_Porta_%s" % nome, .86, M["porta_mad"], C_COR, T_=lambda q, x=x: (x - .43 + q[0], .115 + q[1], Z3 + q[2]), almofadas=True, olho=True)
    box("Corredor_Porta_%s_Batente" % nome, (1.0, .03, 2.16), (x, .108, Z3 + 1.08), M["rodape"], C_COR)
    texto("Corredor_Numero_%s" % nome, nome, .09, (x, .14, Z3 + 1.72), "+y", M["texto_dour"], C_MIU)
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
parede("Apto_Parede_Norte", (-1, 9), (8, 9), M["parede"], C_EST, vaos=[(.5, 1.9, 1.1, 2.1), (3.6, 5.0, 1.0, 2.2), (6.7, 8.1, 1.0, 2.2)])      # janela do quarto 1 centrada na parede (x 6.4)
parede("Apto_Parede_Leste", (8, 1.6), (8, 9), M["parede"], C_EST, vaos=[(.7, 3.3, .7, 2.25)])
parede("Apto_Parede_Oeste", (-1, 1.6), (-1, 9), M["parede"], C_EST)
parede("Apto_Parede_Banheiro_Cozinha", (-1, 4.0), (1.8, 4.0), M["parede"], C_EST, t=.12)
parede("Apto_Parede_Circulacao_O", (1.8, 1.6), (1.8, 5.5), M["parede"], C_EST, t=.12, vaos=[(1.3, 2.0, 0, 2.1), (2.9, 3.8, 0, 2.1)])   # banheiro; cozinha
parede("Apto_Parede_Cozinha_Quarto", (1.8, 5.5), (1.8, 9), M["parede"], C_EST, t=.12, ext=.06)
parede("Apto_Parede_Cozinha_Servico", (-1, 6.8), (1.8, 6.8), M["parede"], C_EST, t=.12, vaos=[(1.3, 2.2, 0, 2.1)])
parede("Apto_Parede_Circulacao_L", (3.1, 1.6), (3.1, 5.5), M["parede"], C_EST, t=.12, vaos=[(2.2, 3.9, 0, 2.3)])                  # vao largo para a sala
parede("Apto_Parede_Quartos_Sul", (1.8, 5.5), (8, 5.5), M["parede"], C_EST, t=.12, vaos=[(.2, 1.1, 0, 2.1), (3.2, 4.1, 0, 2.1)])    # quarto 2; quarto 1
parede("Apto_Parede_Entre_Quartos", (4.8, 5.5), (4.8, 9), M["parede"], C_EST, t=.12)
janela("Janela_Servico", .2, 9, True, 1.4, 1.1, 2.1, C_EST, dentro=-1); janela("Janela_Quarto_2", 3.3, 9, True, 1.4, 1.0, 2.2, C_EST, persiana=True, dentro=-1)
janela("Janela_Quarto_1", 6.4, 9, True, 1.4, 1.0, 2.2, C_EST, persiana=True, dentro=-1); janela("Janela_Sala", 8, 3.6, False, 2.6, .7, 2.25, C_EST, folhas=3, dentro=-1)
# azulejo ate o teto no banheiro e ate 1,5 m na cozinha e na area de servico (placas finas coladas na parede)
for nome, tam, pos in (("Azulejo_Banheiro_O", (.01, 2.3, PD), (-.895, 2.8, Z3 + PD / 2)), ("Azulejo_Banheiro_S", (2.7, .01, PD), (.4, 1.705, Z3 + PD / 2)),
                       ("Azulejo_Banheiro_N", (2.7, .01, PD), (.4, 3.935, Z3 + PD / 2)), ("Azulejo_Cozinha_S", (2.7, .01, 1.5), (.4, 4.065, Z3 + .75)),
                       ("Azulejo_Cozinha_O", (.01, 2.7, 1.5), (-.895, 5.4, Z3 + .75)), ("Azulejo_Servico_O", (.01, 2.1, 1.5), (-.895, 7.9, Z3 + .75))):
    box(nome, tam, pos, M["azulejo"], C_EST)
# rodapes da sala, do corredor e dos quartos: um por face de parede, com recorte nos vaos de porta
# (nome, parede em X?, coordenada fixa, meia espessura da parede, lado da face, inicio, fim, vaos de porta)
RODAPES = (("Sala_S", True, 1.65, .05, 1, 3.1, 8, [(3.5, 4.4)]), ("Sala_N", True, 5.5, .06, -1, 3.1, 8, [(5.0, 5.9)]),
           ("Sala_L", False, 8, .1, -1, 1.65, 5.5, []), ("Sala_O", False, 3.1, .06, 1, 1.65, 5.5, [(3.8, 5.5)]),
           ("Circ_O", False, 1.8, .06, 1, 1.65, 5.5, [(2.9, 3.6), (4.5, 5.4)]), ("Circ_L", False, 3.1, .06, -1, 1.65, 5.5, [(3.8, 5.5)]),
           ("Circ_S", True, 1.65, .05, 1, 1.8, 3.1, []), ("Circ_N", True, 5.5, .06, -1, 1.8, 3.1, [(2.0, 2.9)]),
           ("Q2_S", True, 5.5, .06, 1, 1.8, 4.8, [(2.0, 2.9)]), ("Q2_O", False, 1.8, .06, 1, 5.5, 9, []),
           ("Q2_L", False, 4.8, .06, -1, 5.5, 9, []), ("Q2_N", True, 9, .1, -1, 1.8, 4.8, []),
           ("Q1_S", True, 5.5, .06, 1, 4.8, 8, [(5.0, 5.9)]), ("Q1_O", False, 4.8, .06, 1, 5.5, 9, []),
           ("Q1_L", False, 8, .1, -1, 5.5, 9, []), ("Q1_N", True, 9, .1, -1, 4.8, 8, []))
for nome, em_x, c, meia, lado, ini, fim, vaos in RODAPES:
    pos_c = c + lado * (meia + .0075); trechos, d = [], ini + .06
    for v0, v1 in vaos: trechos.append((d, v0)); d = v1
    trechos.append((d, fim - .06))
    for k, (t0, t1) in enumerate(trechos):
        if t1 - t0 < .05: continue
        m_ = (t0 + t1) / 2
        box("Rodape_%s_%d" % (nome, k), (t1 - t0, .015, .08) if em_x else (.015, t1 - t0, .08), (m_, pos_c, Z3 + .04) if em_x else (pos_c, m_, Z3 + .04), M["rodape"], C_EST)
plafon("Luz_Sala", 5.6, 3.5, 45); plafon("Luz_Circulacao", 2.45, 3.4, 45); plafon("Luz_Banheiro", .4, 2.8, 50, cor="#f4f6ff", m="lamp_f")
plafon("Luz_Cozinha", .4, 5.4, 60, cor="#f4f6ff", m="lamp_f"); plafon("Luz_Servico", .4, 7.9, 15, cor="#f4f6ff", m="lamp_f")
plafon("Luz_Quarto_1", 6.4, 7.25, 36); plafon("Luz_Quarto_2", 3.3, 7.25, 36)

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
    def casco(s, x0, x1, z0, z1, m, prat=(), fundo=True, d=None, y0=0.0, topo=True, baixos={}):
        """Caixa aberta na frente, de x0 a x1 e de z0 a z1 (medidas de fora), com prateleiras nas alturas dadas."""
        d = d or s.d; w = x1 - x0; xc = (x0 + x1) / 2; yc = y0 - d / 2
        for sx, x in ((-1, x0 + T / 2), (1, x1 - T / 2)):      # baixos = {lado: altura}: lateral mais baixa (passa por baixo da cuba)
            zt = baixos.get(sx, z1); s.cx("Lado", (T, d, zt - z0), (x, yc, (z0 + zt) / 2), m)
        s.cx("Base", (w - 2 * T, d, T), (xc, yc, z0 + T / 2), m)
        if topo: s.cx("Topo", (w - 2 * T, d, T), (xc, yc, z1 - T / 2), m)
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
    folha_porta(n, larg, m, C_INT, parent=r, almofadas=(m == M["porta_mad"]), olho=olho, fechadura=(m != M["porta_ferro"]))
    if m == M["porta_ferro"]:                                            # porta corta-fogo: barra antipanico
        for s in (-1, 1): box(n + "_Barra", (larg * .6, .03, .04), (larg * .5, s * .045, 1.0), M["ferragem"], C_INT, r)
    if rotulo: texto(n + "_Rotulo", rotulo, .09 if len(rotulo) < 4 else .06, (larg / 2, lado_rotulo * .024, 1.72), "-y" if lado_rotulo < 0 else "+y", M[m_rot], C_INT, r)
    return r
def batente(nome, x, y, ao_longo_x, larg, col, z0=Z3, prof=.16):
    """Batente (marco) e guarnicao (alizar) dos dois lados da parede; prof = espessura da parede."""
    pj = prof + .02
    for s in (-1, 1):
        box(nome + "_Batente", (.04, pj, 2.08) if ao_longo_x else (pj, .04, 2.08), (x + s * larg / 2, y, z0 + 1.04) if ao_longo_x else (x, y + s * larg / 2, z0 + 1.04), M["rodape"], col)      # ate a peca de cima, sem sobrepor (canto preto no render)
    box(nome + "_Batente_Cima", (larg + .04, pj, .04) if ao_longo_x else (pj, larg + .04, .04), (x, y, z0 + 2.1), M["rodape"], col)
    for f in (-1, 1):                                                    # guarnicao: 7 cm de largura, 1,2 cm saliente
        d = f * (prof / 2 + .006)
        for s in (-1, 1):
            p_ = (x + s * (larg / 2 + .035), y + d, z0 + 1.06) if ao_longo_x else (x + d, y + s * (larg / 2 + .035), z0 + 1.06)
            box(nome + "_Guarnicao", (.07, .012, 2.12) if ao_longo_x else (.012, .07, 2.12), p_, M["rodape"], col)
        box(nome + "_Guarnicao_Cima", (larg + .14, .012, .07) if ao_longo_x else (.012, larg + .14, .07), (x, y + d, z0 + 2.155) if ao_longo_x else (x + d, y, z0 + 2.155), M["rodape"], col)

# portas dos comodos (todas abrem para dentro do comodo)
passagem("Apto_302", (3.5, 1.6), 0, M["porta_mad"], rotulo="302", olho=True); batente("Batente_302", 3.95, 1.6, True, .9, C_EST, prof=.2)
passagem("Apto_301", (-3.4, 1.6), 0, M["porta_mad"], rotulo="301", olho=True); batente("Batente_301", -2.95, 1.6, True, .9, C_VIZ, prof=.2)
passagem("Escada", (-6.0, 0), 0, M["porta_ferro"], rotulo="ESCADA", lado_rotulo=1, ang=-1.5, m_rot="texto_br"); batente("Batente_Escada", -5.55, 0, True, .9, C_COR, prof=.1)
passagem("Banheiro", (1.8, 2.9), PI / 2, M["porta_br"], larg=.68); batente("Batente_Banheiro", 1.8, 3.25, False, .7, C_EST, prof=.12)
passagem("Quarto_2", (2.0, 5.5), 0, M["porta_br"], tranca=True); batente("Batente_Quarto_2", 2.45, 5.5, True, .9, C_EST, prof=.12)
passagem("Quarto_1", (5.9, 5.5), PI, M["porta_br"], ang=-1.5); batente("Batente_Quarto_1", 5.45, 5.5, True, .9, C_EST, prof=.12)

# para onde olha a frente dos modelos prontos (conferido nas previas): giro que faz a frente olhar para o sul (-Y)
SOFA_RZ = 0.0; QUADRO_RZ = 0.0; CADEIRA_RZ = PI      # a cadeira de jantar do Poly Haven vem de costas: meia volta para olhar a mesa
# ------------------------------------------------------------------ quarto 1 (casal)
cama("Cama_Casal", 6.4, 8.88, 0, 1.4, C_QUA, M["lencol"])                      # cabeceira na parede norte, sob a janela
criado("Criado_A", 5.42, 8.88, 0, C_QUA); criado("Criado_B", 7.38, 8.88, 0, C_QUA)
guarda_roupa("Guarda_Roupa_Casal", 7.88, 6.52, -PI / 2, C_QUA, w=1.8, portas=3)
# (a comoda do quarto do casal foi tirada a pedido do usuario)
box("Abajur_Base", (.1, .1, .22), (5.42, 8.7, Z3 + .66), M["louca"], C_QUA); cyl("Abajur_Cupula", .09, .13, .16, (5.42, 8.7, Z3 + .85), M["cortina"], C_MIU, seg=14)
ph("Quadro_Quarto_1", "hanging_picture_frame_03", 4.9, 7.9, Z3 + 1.4, QUADRO_RZ - PI / 2, C_QUA, alt=.6, tris=600)
box("Tapete_Quarto_1", (1.9, 1.1, .012), (6.4, 6.6, Z3 + .006), M["tapete"], C_QUA)

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
box("TV_Tela", (1.15, .035, .66), (6.5, 1.93, Z3 + .93), M["tv"], C_SAL, bevel=.004); box("TV_Pe", (.5, .2, .02), (6.5, 1.93, Z3 + .555), M["preto"], C_SAL); box("TV_Haste", (.08, .04, .08), (6.5, 1.94, Z3 + .59), M["preto"], C_SAL)
modelo_ph("Sofa", "Sofa_01", (6.95, 4.93, Z3), SOFA_RZ, C_SAL, max_tris=4000, alt=.82) or box("Sofa", (1.9, .85, .8), (6.9, 5.0, Z3 + .4), M["tecido_cad"], C_SAL)
modelo_ph("Mesa_Centro", "modern_coffee_table_01", (6.8, 3.6, Z3), 0, C_SAL, max_tris=1500, alt=.4) or mesa("Mesa_Centro", 6.7, 3.5, (.8, .5), .42, C_SAL)
box("Tapete_Sala", (2.3, 1.7, .012), (6.8, 3.6, Z3 + .006), M["tapete_est"], C_SAL)
mesa("Mesa_Jantar", 4.9, 3.2, (.8, 1.2), .76, C_SAL)
for k, (dx, dy, rz) in enumerate(((-.62, -.28, -PI / 2), (-.62, .28, -PI / 2), (.62, -.28, PI / 2), (.62, .28, PI / 2))):
    if not ph("Cadeira_Jantar_%d" % k, "dining_chair_02", 4.9 + dx * 1.05, 3.2 + dy, Z3, rz + CADEIRA_RZ, C_SAL, alt=.92, tris=1200):
        cadeira("Cadeira_Jantar_%d" % k, 4.9 + dx + (-.21 if dx < 0 else .21), 3.2 + dy, rz + PI, C_SAL)
vaso_planta("Planta_Sala", 7.55, 2.15, Z3, 1.1, C_SAL)
ph("Quadro_Sala_A", "hanging_picture_frame_01", 6.5, 5.4, Z3 + 1.45, QUADRO_RZ, C_SAL, alt=.55, tris=600); ph("Quadro_Sala_B", "hanging_picture_frame_02", 7.3, 5.4, Z3 + 1.5, QUADRO_RZ, C_SAL, alt=.42, tris=600)
def armario_alto(nome, x, y, rz, col, w=1.2, d=.5, h=2.2, m=None, prat=(.5, .95, 1.4, 1.85)):
    m = m or M["mdf_br"]; mv = Movel(nome, x, y, rz, col, d)
    mv.casco(-w / 2, w / 2, .06, h, m, prat=prat); mv.cx("Rodape", (w - .04, .02, .06), (0, -d + .04, .03), m)
    mv.folha(-w / 2 + .003, .062, w / 2 - .005, h - .064, m, 1, zp=1.0, pux=.16, ang=1.5); mv.folha(w / 2 - .003, .062, w / 2 - .005, h - .064, m, -1, zp=1.0, pux=.16, ang=1.5)      # ate ~86 graus: nao entram na parede do lado
    for z in prat[:3]:
        for k in range(2): mv.cx("Dobrados", (w * .32, d * .6, rnd.uniform(.1, .22)), ((k - .5) * w * .45, -d / 2, z + T / 2 + .11), M[rnd.choice(ROUPAS)], bevel=.01)
    mv.colisao(w, h); return mv
armario_alto("Armario_Circulacao", 2.45, 1.71, PI, C_SAL, w=1.06)      # o corredor tem 1,18 m: folga dos dois lados para as portas

# ------------------------------------------------------------------ cozinha e area de servico
def bancada_cozinha(nome, x, y, rz, col, w=2.2, d=.55, h=.86):
    """Armario de baixo com quatro modulos (porta, porta, gaveteiro, porta), tampo de granito e cuba; e armario de cima."""
    mv = Movel(nome, x, y, rz, col, d); m = M["mdf_br"]; wm = w / 4
    mv.cx("Rodape", (w - .04, .02, .1), (0, -d + .05, .05), M["preto"])
    for i in range(4):
        x0 = -w / 2 + i * wm
        mv.casco(x0, x0 + wm, .1, h, m, prat=() if i == 2 else (.5,), topo=i > 1, baixos={1: h - .18} if i == 0 else ({-1: h - .18} if i == 1 else {}))      # sob a cuba: sem tampo e com a lateral do meio baixa
        if i == 2:
            hz = (h - .1 - 2 * T) / 3
            for k in range(3): mv.gaveta(x0 + wm / 2, .1 + T + k * hz + .002, wm - .006, hz - .004, m)
        else:
            mv.folha(x0 + (.003 if i != 1 else wm - .003), .102, wm - .006, h - .104, m, 1 if i != 1 else -1, zp=h - .22)
            xc = x0 + wm / 2                                # o que se guarda no armario de baixo: panelas, pratos, potes
            if i == 0:
                for k in range(3): cyl("Mv_%s_Panela" % nome, .11 - k * .015, .11 - k * .015, .1, mv.W((xc, -d / 2, .1 + T + .05 + k * .1)), M["panela"], col, seg=14)
                cyl("Mv_%s_Frigideira" % nome, .12, .12, .04, mv.W((xc, -d / 2, .5 + T / 2 + .02)), M["preto"], col, seg=14)
            elif i == 3:
                for k, m_ in enumerate(("lata_a", "lata_b", "lata_c")): mv.cx("Pote", (.1, .1, .16), (xc - .14 + k * .14, -d / 2, .1 + T + .08), M[m_])
                cyl("Mv_%s_Pratos" % nome, .11, .11, .09, mv.W((xc, -d / 2, .5 + T / 2 + .045)), M["louca"], col, seg=16)
            else:
                for k, m_ in enumerate(("frasco_a", "frasco_c", "frasco_b")): cyl("Mv_%s_Limpeza" % nome, .04, .04, .24, mv.W((xc - .12 + k * .12, -d / 2 - .08, .1 + T + .12)), M[m_], col, seg=10)
    # tampo de granito em quatro pecas em volta do furo da cuba
    xs, yc = -w / 2 + wm, -d / 2 - .02; cl, cp, fd = .5, .38, .19                  # centro da cuba, largura, profundidade, fundo
    x_ini, x_fim, y_ini, y_fim = -w / 2 - .01, w / 2 + .01, -d - .04, 0.0
    for (a0, a1, b0, b1) in ((x_ini, xs - cl / 2, y_ini, y_fim), (xs + cl / 2, x_fim, y_ini, y_fim),
                             (xs - cl / 2, xs + cl / 2, y_ini, yc - cp / 2), (xs - cl / 2, xs + cl / 2, yc + cp / 2, y_fim)):
        mv.cx("Tampo", (a1 - a0, b1 - b0, .03), ((a0 + a1) / 2, (b0 + b1) / 2, h + .015), M["granito"])
    mv.cx("Tampo_Frontao", (w + .02, .02, .1), (0, -.01, h + .08), M["granito"])      # rodabanca de granito na parede
    # cuba de inox embutida: fundo, quatro paredes, borda fina e ralo
    zf = h + .03 - fd
    mv.cx("Cuba_Fundo", (cl, cp, .008), (xs, yc, zf), M["inox"])
    for sx in (-1, 1): mv.cx("Cuba_Parede", (.008, cp, fd), (xs + sx * (cl / 2 - .004), yc, zf + fd / 2), M["inox"])
    for sy in (-1, 1): mv.cx("Cuba_Parede", (cl, .008, fd), (xs, yc + sy * (cp / 2 - .004), zf + fd / 2), M["inox"])
    for sx in (-1, 1): mv.cx("Cuba_Borda", (.015, cp + .03, .004), (xs + sx * (cl / 2 + .0075), yc, h + .032), M["inox"])
    for sy in (-1, 1): mv.cx("Cuba_Borda", (cl + .03, .015, .004), (xs, yc + sy * (cp / 2 + .0075), h + .032), M["inox"])
    cyl("Mv_%s_Ralo" % nome, .04, .04, .006, mv.W((xs, yc, zf + .006)), M["inox"], col, seg=16)
    cyl("Mv_%s_Ralo_Furo" % nome, .03, .03, .004, mv.W((xs, yc, zf + .01)), M["preto"], col, seg=16)
    # torneira gourmet: base, coluna, curva e bica para dentro da cuba, alavanca do lado
    bx, by = xs, yc + cp / 2 + .06
    cyl("Mv_%s_Torneira_Base" % nome, .028, .028, .03, mv.W((bx, by, h + .045)), M["inox"], col, seg=16)
    pts = [(bx, by, h + .05), (bx, by, h + .3)] + [(bx, by - .08 + .08 * math.cos(t), h + .3 + .08 * math.sin(t)) for t in (.6, 1.2, 1.8, 2.4, PI)] + [(bx, by - .16, h + .22)]
    for p0, p1 in zip(pts, pts[1:]): barra("Mv_%s_Torneira" % nome, mv.W(p0), mv.W(p1), .013, M["inox"], col, seg=10)
    cyl("Mv_%s_Torneira_Bico" % nome, .016, .016, .02, mv.W((bx, by - .16, h + .215)), M["inox"], col, seg=12)
    barra("Mv_%s_Torneira_Alavanca" % nome, mv.W((bx + .03, by, h + .2)), mv.W((bx + .1, by, h + .23)), .007, M["inox"], col, seg=8)
    # louca suja dentro da cuba, copo, esponja e detergente ao lado
    for k in range(3): cyl("Mv_%s_Prato_Pia" % nome, .1, .1, .014, mv.W((xs - .13 + k * .012, yc - .04, zf + .012 + k * .014)), M["louca"], col, seg=18)
    cyl("Mv_%s_Copo_Pia" % nome, .035, .03, .1, mv.W((xs + .14, yc - .08, zf + .055)), M["vidro_f2"], col, seg=12)
    mv.cx("Esponja", (.1, .065, .03), (xs + cl / 2 + .12, yc + .1, h + .045), M.setdefault("esponja", mat("Esponja", "#e3c13a", .95)))
    mv.cx("Esponja_Verde", (.1, .065, .012), (xs + cl / 2 + .12, yc + .1, h + .066), M.setdefault("esponja_v", mat("Esponja_Verde", "#2f6b3a", .95)))
    cyl("Mv_%s_Detergente" % nome, .028, .028, .2, mv.W((xs + cl / 2 + .1, yc + .2, h + .13)), M.setdefault("detergente", mat("Detergente", "#d7e8a8", .25, alpha=.75)), col, seg=12)
    cyl("Mv_%s_Detergente_Tampa" % nome, .012, .012, .03, mv.W((xs + cl / 2 + .1, yc + .2, h + .245)), M["branco"], col, seg=10)
    mv.colisao(w, h + .03)
    # armario de cima
    ma = Movel(nome + "_Aereo", x, y, rz, col, .32); za = 1.5
    for i in range(4):
        x0 = -w / 2 + i * wm
        ma.casco(x0, x0 + wm, za, za + .62, m, prat=(za + .31,))
        ma.folha(x0 + (.003 if i % 2 == 0 else wm - .003), za + .002, wm - .006, .616, m, 1 if i % 2 == 0 else -1, zp=.1, pux=.1)
        xc = x0 + wm / 2                                    # armario de cima: copos, pratos e mantimentos
        if i < 2:
            for k in range(4): cyl("Mv_%s_Copo" % nome, .032, .028, .1, ma.W((xc - .15 + k * .1, -.16, za + T + .05)), M["vidro_f2"], col, seg=10)
            cyl("Mv_%s_Pratos" % nome, .105, .105, .1, ma.W((xc, -.16, za + .31 + T / 2 + .05)), M["louca"], col, seg=16)
        else:
            for k, m_ in enumerate(("lata_b", "lata_a", "lata_c", "frasco_c")): ma.cx("Mantimento", (.09, .12, rnd.uniform(.14, .22)), (xc - .17 + k * .115, -.17, za + T + .1), M[m_])
            for k, m_ in enumerate(("lata_c", "lata_b")): cyl("Mv_%s_Lata" % nome, .04, .04, .11, ma.W((xc - .08 + k * .16, -.16, za + .31 + T / 2 + .055)), M[m_], col, seg=12)
    return mv
bancada_cozinha("Bancada", .25, 4.075, PI, C_COZ)
def geladeira(nome, x, y, rz, col, w=.66, d=.62, h=1.75):
    mv = Movel(nome, x, y, rz, col, d); m = M["geladeira"]; zf = h - .46
    mv.casco(-w / 2, w / 2, .04, zf, m, prat=(.45, .8, 1.05)); mv.casco(-w / 2, w / 2, zf, h, m)
    pg = mv.folha(w / 2 - .003, .05, w - .006, zf - .056, m, -1, tf=.05, ang=1.9, zp=zf - .5, pux=.3)
    for k, (ix, iz, m_) in enumerate(((-.2, .95, "lata_a"), (-.33, 1.05, "lata_b"), (-.26, .82, "lata_c"), (-.42, .9, "frasco_a"))):      # imas e um papel na porta
        box(pg.name + "_Ima", (.045, .006, .045), (ix, -.003, iz), M[m_], C_INT, pg)
    box(pg.name + "_Recado", (.12, .003, .16), (-.3, -.002, 1.0 - .2), M["papel"], C_INT, pg)
    for z_, itens in ((.04 + T, ("frasco_a", "frasco_c", "lata_b")), (.45 + T / 2, ("lata_a", "frasco_b")), (.8 + T / 2, ("frasco_c", "lata_c", "frasco_a")), (1.05 + T / 2, ("lata_b",))):      # dentro da geladeira
        for k, m_ in enumerate(itens): cyl("Mv_%s_Item" % nome, .04, .04, rnd.uniform(.14, .24), mv.W((-.18 + k * .16, -d / 2, z_ + .11)), M[m_], col, seg=10)
    mv.folha(w / 2 - .003, zf + .004, w - .006, h - zf - .008, m, -1, tf=.05, ang=1.9, zp=.12, pux=.14)
    mv.colisao(w, h); return mv
geladeira("Geladeira", -.88, 6.1, PI / 2, C_COZ)
def fogao(nome, x, y, rz, col, w=.56, d=.58, h=.86):
    """Fogao de 4 bocas de apartamento: mesa de inox, queimadores com espalhador e capa, duas trempes de ferro fundido,
    painel com quatro botoes, porta do forno com visor de vidro escuro e puxador (abre), pes reguláveis."""
    mv = Movel(nome, x, y, rz, col, d); m = M["fogao"]
    ferro = M.setdefault("ferro_fundido", mat("Ferro_Fundido", "#1b1b1c", .55, .2))
    vidro_forno = M.setdefault("vidro_forno", mat("Vidro_Forno", "#121416", .08, .1))
    mv.casco(-w / 2, w / 2, .08, h - .02, m, prat=(.26, .45), topo=False)
    mv.cx("Mesa", (w + .01, d + .01, .015), (0, -d / 2, h - .0075), M["inox"])
    mv.cx("Mesa_Borda", (w + .01, .02, .03), (0, -d - .005, h - .015), M["inox"])
    mv.cx("Encosto", (w + .01, .02, .05), (0, -.01, h + .025), M["inox"])
    bocas = ((-.13, -.17, .045), (.13, -.17, .04), (-.13, -.41, .04), (.13, -.41, .05))      # tamanhos diferentes, como no real
    for k, (dx, dy, r) in enumerate(bocas):
        cyl("Mv_%s_Boca_Base" % nome, r + .012, r + .012, .006, mv.W((dx, dy, h + .003)), M["preto"], C_MIU, seg=18)
        cyl("Mv_%s_Boca_Espalhador" % nome, r, r, .016, mv.W((dx, dy, h + .014)), M["metal"], C_MIU, seg=18)
        cyl("Mv_%s_Boca_Capa" % nome, r * .72, r * .72, .008, mv.W((dx, dy, h + .026)), ferro, C_MIU, seg=16)
    # duas trempes de ferro (uma para cada par de bocas): moldura, travessas sobre as bocas e pezinhos
    zt, bt = h + .045, .011
    for sx in (-1, 1):
        cxt, lt, pt = sx * w / 4, w / 2 - .03, d - .07
        for yy in (-.035, -d + .035): mv.cx("Trempe", (lt, bt, bt), (cxt, yy, zt), ferro)
        for xx in (cxt - lt / 2 + bt / 2, cxt + lt / 2 - bt / 2): mv.cx("Trempe", (bt, pt, bt), (xx, -d / 2, zt), ferro)
        mv.cx("Trempe", (bt, pt, bt), (cxt, -d / 2, zt), ferro)
        for yy in (-.17, -.41): mv.cx("Trempe", (lt, bt, bt), (cxt, yy, zt), ferro)
        for xx in (cxt - lt / 2 + .02, cxt + lt / 2 - .02):
            for yy in (-.05, -d + .05): mv.cx("Trempe_Pe", (.012, .012, .04), (xx, yy, h + .02), ferro)
    # painel com os botoes (frente, no alto)
    mv.cx("Painel", (w, .03, .09), (0, -d - .015, h - .065), m)
    for k in range(4):
        px = -w / 2 + .1 + k * (w - .2) / 3
        cyl("Mv_%s_Botao" % nome, .02, .02, .028, mv.W((px, -d - .045, h - .065)), M["preto"], C_MIU, rot=(PI / 2, 0, rz), seg=16)
        mv.cx("Botao_Marca", (.004, .002, .014), (px, -d - .06, h - .058), M["branco"])
    # porta do forno: visor de vidro escuro com moldura (vai junto quando abre)
    pf = mv.tampa((0, -d - .03, .27), (w - .01, h - .38, .03), m, 1.45); hp = h - .38
    box(pf.name + "_Visor", (w * .66, .004, hp * .42), (0, -.002, hp * .5), vidro_forno, C_INT, pf)
    box(pf.name + "_Visor_Moldura", (w * .7, .002, hp * .46), (0, -.0005, hp * .5), M["preto"], C_INT, pf)
    mv.cx("Gaveta_Fundo", (w - .01, .02, .17), (0, -d - .01, .17), m)          # gaveta de baixo (fechada)
    mv.cx("Gaveta_Fundo_Puxador", (w * .5, .015, .012), (0, -d - .025, .22), M["metal"])
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

# ================================================================== 6b. objetos de casa, cortinas, tomadas
def cortina(nome, x, y, ao_longo_x, larg, col, lado=1, z0=Z3 + .12, h=2.3, m=None):
    """Cortina recolhida para um lado da janela (pregas) e varao ao longo do vao."""
    m = m or M["cortina"]; passo = .07; n = 7
    for k in range(n):
        d = lado * (larg / 2 + .12 - k * passo); f = .03 * (k % 2)
        box(nome, (passo * 1.1, .05, h) if ao_longo_x else (.05, passo * 1.1, h), (x + d, y + f, z0 + h / 2) if ao_longo_x else (x + f, y + d, z0 + h / 2), m, col)
    barra(nome + "_Varao", (x - larg / 2 - .2, y, z0 + h + .03) if ao_longo_x else (x, y - larg / 2 - .2, z0 + h + .03), (x + larg / 2 + .2, y, z0 + h + .03) if ao_longo_x else (x, y + larg / 2 + .2, z0 + h + .03), .012, M["metal"], C_MIU, seg=6)
def tomada(nome, pos, virado, col, interruptor=False):
    box(nome, {"x": (.012, .075, .115), "y": (.075, .012, .115)}[virado], pos, M["branco"], C_MIU, bevel=.003)
cortina("Cortina_Sala", 7.84, 3.6, False, 2.6, C_SAL, -1); cortina("Cortina_Sala_B", 7.84, 3.6, False, 2.6, C_SAL, 1)
cortina("Cortina_Quarto_1", 6.4, 8.84, True, 1.4, C_QUA, 1, m=M["lencol"]); cortina("Cortina_Quarto_2", 3.3, 8.84, True, 1.4, C_QUA, -1, m=M["lencol2"])
for nome, pos, v in (("Interruptor_Sala", (4.62, 1.705, Z3 + 1.1), "y"), ("Interruptor_Q1", (5.94, 5.565, Z3 + 1.1), "y"), ("Interruptor_Q2", (3.02, 5.565, Z3 + 1.1), "y"),
                     ("Interruptor_Cozinha", (1.735, 5.5, Z3 + 1.1), "x"), ("Interruptor_Banheiro", (1.735, 2.75, Z3 + 1.1), "x"), ("Tomada_Sala", (6.0, 1.705, Z3 + .3), "y"),
                     ("Tomada_Q1", (7.895, 6.0, Z3 + .3), "x"), ("Tomada_Q2", (2.4, 8.895, Z3 + .3), "y"), ("Tomada_Cozinha", (.9, 4.07, Z3 + 1.15), "y"), ("Interruptor_Corredor", (3.3, 1.495, Z3 + 1.1), "y")):
    tomada(nome, pos, v, C_MIU)
# sala
# (poltrona da sala tirada a pedido do usuario)
ph("Vaso_Rack", "ceramic_vase_01", 5.95, 1.9, Z3 + .545, 0, C_SAL, alt=.28, tris=500); ph("Livros_Rack", "book_encyclopedia_set_01", 7.05, 1.9, Z3 + .545, PI, C_SAL, alt=.26, tris=800)
ph("Estante_Sala", "wooden_bookshelf_worn", 5.0, 1.9, None, PI, C_SAL, alt=1.7, tris=2500)
ph("Porta_Retrato", "standing_picture_frame_01", 6.45, 3.55, Z3 + .4, .5, C_SAL, alt=.2, tris=400)
box("Controle_TV", (.05, .17, .02), (6.95, 3.7, Z3 + .41), M["preto"], C_SAL); box("Roteador", (.2, .13, .03), (7.15, 1.85, Z3 + .56), M["branco"], C_SAL)
ph("Fruteira", "wooden_bowl_01", 4.9, 3.2, Z3 + .76, 0, C_SAL, alt=.09, tris=500); ph("Bananas", "bananas", 4.92, 3.2, Z3 + .79, 1, C_SAL, alt=.07, tris=500); ph("Maca", "food_apple_01", 4.84, 3.24, Z3 + .79, 0, C_SAL, alt=.07, tris=200)
# quartos
ph("Despertador", "alarm_clock_01", 7.08, 8.7, Z3 + .55, 0, C_QUA, alt=.13, tris=500); ph("Pufe", "Ottoman_01", 6.1, 6.55, None, 0, C_QUA, alt=.42, tris=1200)
# (vaso e retrato iam em cima da comoda, que saiu)
ph("Notebook", "classic_laptop", 2.85, 8.62, Z3 + .76, PI, C_QUA, alt=.24, tris=1200)
box("Caderno", (.21, .29, .018), (2.62, 8.55, Z3 + .769), M["roupa_a"], C_QUA, rot=(0, 0, .3)); box("Folhas_Soltas", (.21, .297, .004), (3.32, 8.5, Z3 + .762), M["papel"], C_QUA, rot=(0, 0, -.4))
ph("Bola", "football", 4.5, 5.85, None, 0, C_QUA, alt=.22, tris=500)
ph("Botas", "rubber_boots", 2.1, 6.2, None, 1.2, C_QUA, alt=.32, tris=700); box("Cartaz_Quarto_2", (.7, .012, 1.0), (4.0, 5.57, Z3 + 1.5), M["cartaz"], C_QUA)
# (a planta do quarto do casal foi tirada a pedido do usuario)
# cozinha e area de servico
def microondas(nome, x, y, z, col, w=.48, d=.36, h=.28):
    """Micro-ondas de bancada com a frente para +Y: gabinete com cantos arredondados, porta com visor escuro e moldura,
    puxador embutido, painel com visor digital e teclado, grade de ventilacao na lateral e pezinhos."""
    fy = y + d / 2; zc = z + .01 + h / 2
    box(nome, (w, d, h), (x, y, zc), M["inox"], col, bevel=.012, seg=3)
    wp = w * .7; xp = x - w / 2 + .01 + wp / 2                               # porta (lado esquerdo)
    box(nome + "_Porta", (wp, .012, h - .03), (xp, fy + .004, zc), M["branco"], col, bevel=.006)
    box(nome + "_Visor", (wp - .08, .006, h - .1), (xp - .01, fy + .011, zc + .005), M["micro"], col)
    box(nome + "_Visor_Tela", (wp - .1, .004, h - .12), (xp - .01, fy + .0145, zc + .005), M.setdefault("tela_micro", mat("Tela_Microondas", "#2a2c2e", .5, .3)), col)
    box(nome + "_Puxador", (.018, .02, h - .08), (xp + wp / 2 - .025, fy + .02, zc), M["metal"], col, bevel=.004)
    xpn = x + w / 2 - .01 - (w - wp - .03) / 2; lp = w - wp - .03            # painel de controle (lado direito)
    box(nome + "_Painel", (lp, .008, h - .03), (xpn, fy + .003, zc), M["preto"], col)
    box(nome + "_Display", (lp - .03, .004, .03), (xpn, fy + .008, zc + h / 2 - .045), M.setdefault("display_verde", mat("Display_Verde", "#062010", .3, emit="#3dff8a", forca=1.2)), col)
    for i in range(4):
        for j in range(3): box(nome + "_Tecla", (.018, .004, .012), (xpn - .025 + j * .025, fy + .008, zc + .03 - i * .02), M["metal"], col)
    cyl(nome + "_Botao_Gira", .016, .016, .012, (xpn, fy + .01, zc - h / 2 + .045), M["metal"], col, rot=(PI / 2, 0, 0), seg=16)
    for k in range(6): box(nome + "_Ventilacao", (.003, .12, .006), (x + w / 2 + .0005, y - .05, zc + .06 - k * .015), M["preto"], col)
    for sx in (-1, 1):
        for sy in (-1, 1): cyl(nome + "_Pe", .012, .012, .01, (x + sx * (w / 2 - .04), y + sy * (d / 2 - .04), z + .005), M["preto"], col, seg=8)
microondas("Microondas", -.5, 4.3, Z3 + .89, C_COZ)
ph("Chaleira", "vintage_electric_kettle", 1.2, 4.3, Z3 + .89, 2.5, C_COZ, alt=.22, tris=700); ph("Panela", "pot_enamel_01", -.72, 5.03, Z3 + .9, 0, C_COZ, alt=.14, tris=700)
box("Tabua", (.34, .22, .02), (-.05, 4.42, Z3 + .9), M["mad"], C_COZ, rot=(0, 0, .4), bevel=.004)
for k in range(5): box("Escorredor_Prato", (.012, .2, .2), (.13 + k * .05, 4.28, Z3 + 1.0), M["louca"], C_COZ, bevel=.004)
box("Escorredor", (.34, .28, .03), (.23, 4.28, Z3 + .905), M["inox"], C_COZ)
cyl("Relogio_Cozinha", .15, .15, .03, (.4, 6.725, Z3 + 2.05), M["louca"], C_COZ, rot=(PI / 2, 0, 0), seg=24); box("Relogio_Ponteiro", (.012, .01, .11), (.4, 6.705, Z3 + 2.09), M["preto"], C_MIU)
cyl("Lixeira_Cozinha", .13, .16, .42, (1.5, 6.5, Z3 + .21), M["branco"], C_COZ, seg=16); cyl("Lixeira_Cozinha_Tampa", .17, .17, .03, (1.5, 6.5, Z3 + .435), M["inox"], C_COZ, seg=16)
ph("Limpador", "all_purpose_cleaner", -.72, 7.35, Z3 + .9, 0, C_COZ, alt=.26, tris=400); ph("Agua_Sanitaria", "bleach_bottle", -.6, 7.2, None, 0, C_COZ, alt=.3, tris=400)
barra("Vassoura_Cabo", (-.82, 8.82, Z3 + .12), (-.86, 8.9, Z3 + 1.35), .012, M["mad"], C_MIU, seg=6); box("Vassoura_Cerdas", (.3, .06, .14), (-.82, 8.8, Z3 + .07), M["roupa_b"], C_COZ)
cyl("Cesto_Roupa", .2, .24, .45, (.9, 8.55, Z3 + .225), M["branco"], C_COZ, seg=16); box("Cesto_Roupa_Dentro", (.3, .3, .1), (.9, 8.55, Z3 + .44), M["roupa_a"], C_COZ, bevel=.04)
for k in range(2): barra("Varal", (-.85, 7.2 + k * .3, Z3 + 2.2), (1.7, 7.2 + k * .3, Z3 + 2.2), .006, M["branco"], C_MIU, seg=4)
for k, (xr, m_) in enumerate(((-.3, "roupa_c"), (.3, "roupa_a"), (.95, "roupa_b"))): box("Varal_Roupa", (.42, .02, .55), (xr, 7.2 + (k % 2) * .3, Z3 + 1.92), M[m_], C_COZ)
# banheiro
cyl("Papel_Higienico", .055, .055, .1, (.95, 1.76, Z3 + .7), M["papel"], C_BAN, rot=(0, PI / 2, 0), seg=14)
for k, m_ in enumerate(("frasco_a", "frasco_b", "frasco_c")): cyl("Frasco_Box", .035, .035, .2, (-.82, 2.5 + k * .12, Z3 + 1.2), M[m_], C_BAN, seg=10)
box("Prateleira_Box", (.12, .5, .02), (-.82, 2.62, Z3 + 1.09), M["vidro"], C_VID); box("Tapete_Banheiro", (.5, .8, .015), (.85, 3.0, Z3 + .0075), M["lencol"], C_BAN)
for k, m_ in enumerate(("frasco_c", "frasco_a")): cyl("Frasco_Pia", .03, .03, .14, (.58 + k * .1, 3.82, Z3 + .92), M[m_], C_BAN, seg=10)
# portaria e corredor
# (placa de piso molhado tirada: o modelo vem escrito em ingles)
ph("Portaria_Camera", "security_camera_01", .7, 1.3, FZ + 2.7, 2.4, C_PORT, alt=.22, tris=500); box("Portaria_Prancheta", (.23, .32, .008), (-.55, -3.3, FZ + .766), M["mad"], C_PORT, rot=(0, 0, .3)); box("Portaria_Prancheta_Folha", (.21, .29, .003), (-.55, -3.3, FZ + .772), M["papel"], C_MIU, rot=(0, 0, .3))
ph("Portaria_Quadro", "hanging_picture_frame_03", -3.2, 1.47, FZ + 1.6, QUADRO_RZ, C_PORT, alt=.7, tris=600)
vaso_planta("Corredor_Planta", 7.5, 1.1, Z3, .9, C_COR, M["louca"]); ph("Corredor_Camera", "security_camera_01", -6.1, 1.35, Z3 + 2.45, -2.2, C_COR, alt=.2, tris=500)

# sapatos, mochila e roupas pelo quarto; objetos nos armarios do banheiro e do corredor
for nome, x, y, rz, m_ in (("Sapato_A", 5.55, 8.2, .2, "sapato"), ("Sapato_B", 5.68, 8.22, -.1, "sapato"), ("Sapato_C", 3.75, 6.4, 1.3, "sapato_m"), ("Sapato_D", 3.78, 6.55, 1.5, "sapato_m"), ("Chinelo_A", 6.9, 6.75, .3, "roupa_a"), ("Chinelo_B", 7.03, 6.72, .1, "roupa_a")):
    box(nome, (.1, .27, .08 if "Sapato" in nome else .03), (x, y, Z3 + (.04 if "Sapato" in nome else .015)), M[m_], C_QUA, rot=(0, 0, rz), bevel=.015)
box("Roupa_Cadeira", (.4, .05, .5), (2.9, 8.07, Z3 + .75), M["roupa_d"], C_QUA, bevel=.015); box("Toalha_Cama", (.5, .7, .03), (6.5, 7.3, Z3 + .525), M["roupa_c"], C_QUA, bevel=.01)
for k, m_ in enumerate(("frasco_c", "frasco_a", "frasco_b", "frasco_c")): cyl("Banheiro_Frasco_Gabinete", .035, .035, .16, (.62 + k * .13, 3.72, Z3 + .25 + T + .08), M[m_], C_BAN, seg=10)
for k in range(3): cyl("Banheiro_Papel_Reserva", .055, .055, .1, (.7 + k * .12, 3.72, Z3 + .52 + T / 2 + .05), M["papel"], C_BAN, seg=12)
for k, m_ in enumerate(("frasco_b", "frasco_c", "frasco_a")): cyl("Banheiro_Frasco_Espelheira", .025, .025, .1, (.7 + k * .15, 3.86, Z3 + 1.25 + T + .05), M[m_], C_BAN, seg=10)

# ================================================================== 6c. portaria e corredor: detalhes de uso
for nome, tam, pos in (("Rodape_Port_N", (7.2, .015, .1), (-2.7, 1.49, FZ + .05)), ("Rodape_Port_L", (.015, 7.4, .1), (.89, -2.2, FZ + .05)), ("Rodape_Port_O", (.015, 5.4, .1), (-6.29, -3.2, FZ + .05))):
    box(nome, tam, pos, M["rodape"], C_PORT)
box("Portaria_Tapete", (2.4, 1.6, .012), (-2.4, -.4, FZ + .006), M["tapete_est"], C_PORT)
mesa("Portaria_Mesa_Centro", -2.4, -.2, (.9, .5), .4, C_PORT, M["mad_esc"], z=FZ)
for k, (dx, m_) in enumerate(((-.2, "roupa_b"), (.05, "roupa_a"), (.22, "papel"))): box("Portaria_Revista", (.21, .28, .008), (-2.4 + dx, -.2, FZ + .405 + k * .008), M[m_], C_PORT, rot=(0, 0, k * .4))
cyl("Portaria_Relogio", .16, .16, .03, (-2.0, 1.48, FZ + 2.3), M["louca"], C_PORT, rot=(PI / 2, 0, 0), seg=24); box("Portaria_Relogio_Ponteiro", (.012, .01, .12), (-2.0, 1.46, FZ + 2.34), M["preto"], C_MIU)
box("Portaria_Bebedouro", (.32, .32, 1.0), (.7, .9, FZ + .5), M["branco"], C_PORT, bevel=.02); cyl("Portaria_Bebedouro_Galao", .13, .13, .38, (.7, .9, FZ + 1.2), M["bebedouro"], C_VID, seg=14)
cyl("Portaria_Extintor", .07, .07, .45, (-6.2, -5.4, FZ + .9), M["extintor"], C_PORT, seg=14); box("Portaria_Extintor_Placa", (.02, .2, .2), (-6.29, -5.4, FZ + 1.75), M["extintor"], C_MIU)
box("Portaria_Placa_Saida", (.4, .03, .16), (-2.7, -5.88, FZ + 2.6), M["placa_verde"], C_PORT); texto("Portaria_Texto_Saida", "SAÍDA", .07, (-2.7, -5.86, FZ + 2.6), "+y", M["texto_br"], C_MIU)
texto("Portaria_Texto_Elevador", "ELEVADOR", .07, (-6.285, .6, FZ + 2.5), "+x", M["texto_pr"], C_MIU)
for k in range(3): box("Portaria_Chave", (.01, .03, .08), (.855, -2.8 + k * .2, FZ + 1.6), M["metal"], C_MIU)
cyl("Portaria_Lixeira", .13, .11, .5, (-6.1, 1.3, FZ + .25), M["inox"], C_PORT, seg=14); cyl("Portaria_Guarda_Chuva", .12, .12, .5, (-1.2, -5.6, FZ + .25), M["preto"], C_PORT, seg=12)
box("Portaria_Regras", (.5, .02, .7), (-.6, 1.49, FZ + 1.6), M["papel"], C_PORT); texto("Portaria_Texto_Regras", "REGULAMENTO INTERNO", .035, (-.6, 1.475, FZ + 1.88), "-y", M["texto_pr"], C_MIU)
for k in range(9): box("Portaria_Regras_Linha", (.4, .005, .012), (-.6, 1.478, FZ + 1.8 - k * .06), M["preto"], C_MIU)
# corredor
for nome, tam, pos in (("Rodape_Cor_S1", (1.8, .015, .08), (-4.3, .11, Z3 + .04)), ("Rodape_Cor_S2", (5.9, .015, .08), (.5, .11, Z3 + .04)), ("Rodape_Cor_S3", (3.5, .015, .08), (6.2, .11, Z3 + .04))):
    box(nome, tam, pos, M["rodape"], C_COR)
for x, y in ((-2.3, 1.49), (4.6, 1.49), (-2.3, .11), (4.6, .11)):                 # campainhas ao lado das quatro portas
    box("Corredor_Campainha", (.07, .012, .1), (x, y, Z3 + 1.25), M["branco"], C_MIU); cyl("Corredor_Campainha_Botao", .012, .012, .006, (x, y + (.008 if y < 1 else -.008), Z3 + 1.25), M["preto"], C_MIU, rot=(PI / 2, 0, 0), seg=10)
texto("Corredor_Texto_Andar", "3º ANDAR", .09, (-6.285, 1.42, Z3 + 2.35), "+x", M["texto_pr"], C_MIU)
box("Corredor_Placa_Saida", (.4, .03, .16), (-5.55, .12, Z3 + 2.32), M["placa_verde"], C_COR); texto("Corredor_Texto_Saida", "SAÍDA", .07, (-5.55, .14, Z3 + 2.32), "+y", M["texto_br"], C_MIU)
for x in (-.9, 6.0): box("Corredor_Quadro_%d" % x, (.6, .02, .45), (x, 1.49, Z3 + 1.55), M[("roupa_e", "roupa_a")[x > 0]], C_COR); box("Corredor_Quadro_Moldura_%d" % x, (.68, .015, .53), (x, 1.495, Z3 + 1.55), M["mad_esc"], C_COR)
cyl("Corredor_Lixeira", .12, .1, .45, (7.75, 1.35, Z3 + .225), M["inox"], C_COR, seg=14)
box("Corredor_Banco", (.9, .32, .05), (1.2, .28, Z3 + .43), M["mad"], C_COR); [box("Corredor_Banco_Pe", (.05, .28, .42), (1.2 + sx * .4, .28, Z3 + .21), M["mad"], C_COR) for sx in (-1, 1)]

# ================================================================== 7. sol, ceu, pontos, cameras
# Ceu: HDRI diurno do Poly Haven (CC0), so como luz difusa do ceu (o disco do sol do arquivo e cortado). O sol e uma lampada
# a parte, para vir do nordeste (manha) e entrar pelas janelas da sala e dos quartos. As forcas funcionam como a exposicao de
# uma camera regulada para o interior (la fora fica estourado, como numa foto tirada de dentro de casa).
HDRI = os.path.normpath(os.path.join(AQUI, "..", "04_ThreeJS", "hdri", "kloofendal_43d_clear_puresky_2k.hdr"))      # ceu limpo, sol a ~43 graus (Poly Haven, CC0)
SOL_DIR = (60, 45, 59)                      # de onde vem o sol (nordeste, ~38 graus): a lampada e o ponto mais claro do HDRI ficam alinhados
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); scene.world = world
nt = world.node_tree; bg = nt.nodes.get("Background")
FORCA_CEU = 2.2
if bg and os.path.exists(HDRI):
    import numpy as np
    def ler(caminho):
        im = bpy.data.images.load(caminho); w, h = im.size; px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px)
        return im, px.reshape(h, w, 4)[..., :3]
    img, px = ler(HDRI)
    lum = px.mean(-1); h, w = lum.shape; r, c = np.unravel_index(int(np.argmax(lum)), lum.shape)
    phi_img = ((c + .5) / w - .5) * 2 * PI                                       # azimute do sol na foto (convencao do Blender)
    giro = PI - phi_img - math.atan2(SOL_DIR[1], SOL_DIR[0])
    # forca do ceu: a mesma luz media do ceu antigo (o sol da foto e cortado em 6; a lampada faz o sol)
    antigo = os.path.join(os.path.dirname(HDRI), "_antigo", "kloofendal_48d_partly_cloudy_puresky_2k.hdr")
    if os.path.exists(antigo):
        im2, px2 = ler(antigo); FORCA_CEU = 2.2 * float(np.minimum(px2, 6).mean()) / max(float(np.minimum(px, 6).mean()), 1e-4); bpy.data.images.remove(im2)
    env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = img
    coord = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value[2] = giro
    nt.links.new(coord.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    corte = nt.nodes.new("ShaderNodeVectorMath"); corte.operation = "MINIMUM"; corte.inputs[1].default_value = (6, 6, 6)
    nt.links.new(env.outputs["Color"], corte.inputs[0]); nt.links.new(corte.outputs["Vector"], bg.inputs["Color"])
    scene["ceu_hdri"] = HDRI; scene["ceu_giro"] = giro      # o pipeline gira o HDRI do site do mesmo jeito
    print("[BUSCA] ceu: %s, giro %.0f graus, forca %.2f" % (os.path.basename(HDRI), math.degrees(giro), FORCA_CEU))
elif bg:
    bg.inputs["Color"].default_value = (*lin(hx("#a9c8ee")), 1)
if bg: bg.inputs["Strength"].default_value = FORCA_CEU
# sol de meio da manha, mais baixo (~32 graus) e quente: entra fundo pela janela da sala e pelos quartos e desenha faixas no piso
luz("Sol", "SUN", 7.5, "#ffe0b5", SOL_DIR, C_LUZ, alvo=(0, 0, 0), angle=math.radians(1.2))

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
camera("Camera_Patio", (6.6, 9.4, Z3 + 1.6), (-2, 26, 4.0), 16); camera("Camera_Morros", (9.5, 10, Z3 + 6.5), (40, 250, 60), 14); camera("Camera_Faixa", (-2, -12.5, 1.7), (12, -12.5, .2), 16); camera("Camera_Viaturas", (-2.5, -7.4, 1.7), (-11, -10.6, .8), 16); camera("Camera_Elevador", (-3.6, -.4, FZ + 1.6), (-7.3, .6, FZ + 1.2), 16); camera("Camera_Mesa_Q2", (3.6, 7.2, Z3 + 1.7), (2.9, 8.8, Z3 + .7), 16); camera("Camera_Sala_N", (5.6, 2.6, Z3 + 1.6), (6.2, 5.5, Z3 + .9), 14); camera("Camera_Rua_2", (14, -8.0, 1.7), (-8, -7.0, 5.0), 16)
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
