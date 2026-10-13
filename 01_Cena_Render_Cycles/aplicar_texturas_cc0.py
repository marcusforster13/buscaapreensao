"""
Busca e Apreensao - aplica as texturas CC0 (Poly Haven) na CENA PRINCIPAL (Cycles).

Uso:  blender -b busca.blend --python aplicar_texturas_cc0.py
      (ou abrir o .blend, aba Scripting > Open > Run Script, e salvar)

- Materiais PBR com projecao em caixa (coordenadas do objeto, em metros): nao precisa de UV.
- Cor + rugosidade + relevo (mapa de deslocamento como Bump).
- Cada material recebe as propriedades "cc0_pasta" e "cc0_tile"; os pipelines de VR e
  three.js leem isso para converter para UV e glTF.
- Pode rodar de novo quantas vezes quiser (reconstroi os materiais a partir da tabela).
- As texturas ficam em ../04_ThreeJS/texturas_cc0 e sao referenciadas por caminho relativo.
"""
import bpy, os
import numpy as np

try:
    AQUI = os.path.dirname(os.path.abspath(__file__))
except NameError:
    AQUI = ""
if not os.path.isdir(os.path.join(AQUI, "..", "04_ThreeJS", "texturas_cc0")):
    AQUI = os.path.join(os.path.expanduser("~"), "Desktop", "buscaeapreensao", "01_Cena_Render_Cycles")
TEX = os.path.normpath(os.path.join(AQUI, "..", "04_ThreeJS", "texturas_cc0"))

def hx(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))

def lin(c):
    return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)

def arquivos(pasta):
    d = os.path.join(TEX, pasta); fs = sorted(os.listdir(d))
    pick = lambda k: next((os.path.join(d, f) for f in fs if k in f.lower()), None)
    return pick("_diff") or pick("_col"), pick("_rough"), pick("_disp")

def grafite(path):
    """Versao grafite do metal verde (mantem arranhoes e ferrugem). Salva junto das texturas."""
    out = os.path.join(os.path.dirname(path), "metal_grafite_diff.png")
    if not os.path.exists(out):
        src = bpy.data.images.load(path)
        w, h = src.size; px = np.empty(w * h * 4, np.float32); src.pixels.foreach_get(px)
        px = px.reshape(-1, 4); rgb = px[:, :3]
        g = (rgb @ np.array([.3, .59, .11]))[:, None]
        rgb = np.clip(g + (rgb - g) * .18, 0, 1) / max(g.mean(), 1e-3) * .5
        px[:, :3] = np.clip(rgb, 0, 1)
        dst = bpy.data.images.new("_tmp_grafite", w, h, alpha=False)
        dst.pixels.foreach_set(px.ravel()); dst.filepath_raw = out; dst.file_format = "PNG"; dst.save()
        bpy.data.images.remove(src); bpy.data.images.remove(dst)
    return out

def neutro(path):
    """Tecido em tom neutro e claro (sem cor), para tingir com a cor de cada estofado."""
    out = os.path.join(os.path.dirname(path), "tecido_neutro_cor.png")      # um por pasta de tecido
    if not os.path.exists(out):
        src = bpy.data.images.load(path)
        w, h = src.size; px = np.empty(w * h * 4, np.float32); src.pixels.foreach_get(px)
        px = px.reshape(-1, 4); g = (px[:, :3] @ np.array([.3, .59, .11]))[:, None]
        px[:, :3] = np.clip(g / max(g.mean(), 1e-3) * .78, 0, 1)
        dst = bpy.data.images.new("_tmp_neutro", w, h, alpha=False)
        dst.pixels.foreach_set(px.ravel()); dst.filepath_raw = out; dst.file_format = "PNG"; dst.save()
        bpy.data.images.remove(src); bpy.data.images.remove(dst)
    return out

def carregar(path, dados):
    img = bpy.data.images.load(path, check_existing=True)
    try:
        img.filepath = bpy.path.relpath(path)
    except ValueError:
        pass
    if dados:
        img.colorspace_settings.name = "Non-Color"
    return img

def media_linear(img):
    w, h = img.size; px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px)
    m = px.reshape(-1, 4)[::7, :3].mean(0)
    return lin(tuple(m))

def pbr_caixa(mat, pasta, tile, tint=None, recolor=None, relevo=.35, metal=0.0):
    diff, rough, disp = arquivos(pasta)
    if recolor:
        diff = recolor(diff)
    alvo = lin(hx(tint)) if tint else tuple(mat.diffuse_color[:3])
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) or nt.nodes.new("ShaderNodeBsdfPrincipled")
    for n in list(nt.nodes):
        if n not in (b, out):
            nt.nodes.remove(n)
    for inp in b.inputs:
        for l in list(inp.links):
            nt.links.remove(l)
    if not out.inputs["Surface"].is_linked:
        nt.links.new(b.outputs[0], out.inputs["Surface"])
    L = nt.links.new
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / tile,) * 3
    L(tc.outputs["Object"], mp.inputs["Vector"])
    def tex(path, dados):
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = carregar(path, dados)
        t.projection = "BOX"; t.projection_blend = .2
        L(mp.outputs["Vector"], t.inputs["Vector"])
        return t
    td = tex(diff, False)
    fator = [min(1.6, a / max(m, 1e-3)) for a, m in zip(alvo, media_linear(td.image))]      # pode clarear ate 60%: paredes brancas de verdade
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    next(i for i in mix.inputs if i.name == "Factor" and i.type == "VALUE").default_value = 1.0
    L(td.outputs["Color"], next(i for i in mix.inputs if i.name == "A" and i.type == "RGBA"))
    next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA").default_value = (*fator, 1)
    L(next(o for o in mix.outputs if o.name == "Result" and o.type == "RGBA"), b.inputs["Base Color"])
    if rough:
        tr = tex(rough, True); sep = nt.nodes.new("ShaderNodeSeparateColor")
        L(tr.outputs["Color"], sep.inputs["Color"]); L(sep.outputs["Green"], b.inputs["Roughness"])
    if disp:
        tdp = tex(disp, True); bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = relevo; bp.inputs["Distance"].default_value = .02
        L(tdp.outputs["Color"], bp.inputs["Height"]); L(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Metallic"].default_value = metal
    mat["cc0_metal"] = float(metal)
    mat["cc0_pasta"] = pasta
    mat["cc0_tile"] = float(tile)
    mat["cc0_tint"] = list(alvo)
    mat["cc0_recolor"] = recolor.__name__ if recolor else ""

# nome do material -> (pasta, tile em metros, cor alvo, recolor, forca do relevo)
TABELA = {
    "Asfalto":            ("asfalto", 3.0, "#3a3a3c", None, .5),
    "Meio_Fio_Concreto":  ("concreto", 1.5, None, None, .35),
    "Calcada_Concreto":   ("calcada", 2.0, "#a8a49a", None, .35),
    "Piso_Intertravado":  ("pavers", 1.6, "#a39f95", None, .4),
    "Grama":              ("grama", 1.6, "#3f6a2c", None, .9),
    "Grama_Longe":        ("grama", 9.0, "#3a4d2c", None, .5),
    "Terra_Canteiro":     ("terra", 1.2, "#4a3a2c", None, .6),
    "Pedra_Morro":        ("morro_pedra", 38.0, "#75706a", None, .9),
    "Concreto_Aparente":  ("concreto", 2.0, None, None, .25),
    "Poste_Concreto":     ("concreto", 1.0, None, None, .25),
    "Muro_Pintado":       ("parede_lisa", 2.5, "#cfc9b8", None, .3),
    "Fachada_Pastilha":   ("azulejo", 1.0, "#d6cbb0", None, .3),
    "Fachada_Pastilha_Azul": ("azulejo", 1.0, "#a9bcc6", None, .3),
    "Fachada_Placas":     ("fachada_placas", 2.4, "#b9b6ae", None, .3),
    "Fachada_Pintada_Creme": ("parede_lisa", 3.0, "#e3d6b4", None, .25),
    "Fachada_Pintada_Salmao": ("parede_lisa", 3.0, "#d9a58a", None, .25),
    "Fachada_Pintada_Branca": ("parede_lisa", 3.0, "#e9e6dc", None, .25),
    "Fachada_Pintada_Verde": ("parede_lisa", 3.0, "#a9bba0", None, .25),
    "Fachada_Pintada_Cinza": ("parede_lisa", 3.0, "#a3a5a8", None, .25),
    "Fachada_Amarela":    ("fachada_amarela", 2.5, "#e0c070", None, .3),
    "Embasamento_Granito": ("marmore", 1.5, "#5d5a56", None, .05),
    "Telha_Ceramica":     ("telha", 1.6, "#a8573a", None, .7),
    "Piso_Laminado":      ("laminado", 1.8, "#b39a7c", None, .15),
    "Piso_Ceramica":      ("piso_cozinha", 1.8, "#dcd6c8", None, .2),
    "Piso_Porcelanato":   ("piso_corredor", 2.0, "#c9c3b6", None, .15),
    "Piso_Granito_Portaria": ("granilite", 2.0, "#c2bcae", None, .08),
    "Azulejo_Branco":     ("azulejo", 1.2, "#ecebe5", None, .2),
    "Granito_Preto":      ("marmore", 1.2, "#2c2c30", None, .05),
    "Madeira_Movel":      ("madeira_clara", 1.2, "#a8845c", None, .1),
    "Madeira_Escura_Movel": ("madeira_escura", 1.2, "#5a3d2a", None, .12),
    "Porta_Madeira":      ("madeira_escura", 1.4, "#7a5638", None, .12),
    "Lencol_Azul":        ("malha", .5, "#6f8fb0", neutro, .3),
    "Lencol_Cinza":       ("malha", .5, "#8b8f94", neutro, .3),
    "Colchao":            ("malha", .5, "#e2ddd0", neutro, .3),
    "Travesseiro":        ("malha", .4, "#eeeae0", neutro, .3),
    "Cortina_Branca":     ("linho", .6, "#e6e2d8", neutro, .4),
    "Tecido_Cadeira":     ("linho", .4, "#6b5c4c", neutro, .3),
    "Tapete":             ("carpete", .8, "#8a7866", neutro, .6),
    "Capacho":            ("carpete", .4, "#5a4a38", neutro, .6),
    "Roupa_Azul":         ("malha", .4, "#2f4a6e", neutro, .3),
    "Roupa_Vermelha":     ("malha", .4, "#8e2f2a", neutro, .3),
    "Roupa_Branca":       ("malha", .4, "#e4e0d6", neutro, .3),
    "Roupa_Cinza":        ("malha", .4, "#5c5f63", neutro, .3),
    "Roupa_Verde":        ("malha", .4, "#476349", neutro, .3),
    "Porta_Corta_Fogo":   ("metal_pintado", 1.0, "#8f2f28", grafite, .15),
    "Grade_Ferro":        ("metal_pintado", 1.0, "#2c2e30", grafite, .15),
    "Aco_Elevador":       ("metal_inox", .5, "#c8c8c8", None, .08),
    "Inox":               ("metal_inox", .3, "#ffffff", None, .08),
}
METAL = {"Inox": .45, "Aco_Elevador": .4}      # brilho de metal moderado: metal puro fica escuro no site
feitos = []
for nome, (pasta, tile, tint, rec, relevo) in TABELA.items():
    m = bpy.data.materials.get(nome)
    if m and os.path.isdir(os.path.join(TEX, pasta)):
        pbr_caixa(m, pasta, tile, tint, rec, relevo, METAL.get(nome, 0.0)); feitos.append(nome)
print("[CC0] %d materiais com texturas Poly Haven: %s" % (len(feitos), ", ".join(feitos)))
if bpy.app.background:
    bpy.ops.wm.save_mainfile()
    print("[CC0] cena principal salva")
