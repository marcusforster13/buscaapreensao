"""Busca e Apreensao - baixa as texturas PBR do Poly Haven (licenca CC0) usadas na cena, em 1K JPG.

Cada textura vai para texturas_cc0/<pasta>/ com os mapas de cor (_diff), rugosidade (_rough), normal (_nor_gl) e relevo
(_disp). So baixa o que falta.  Uso:  python baixar_texturas.py   (serve o Python que vem com o Blender)
"""
import json, os, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__)); DEST = os.path.join(AQUI, "texturas_cc0")
# pasta -> textura do Poly Haven (a primeira que existir)
TEXTURAS = {
    "parede_lisa": ["beige_wall_001"], "teto_branco": ["white_plaster_02"], "azulejo": ["long_white_tiles", "square_tiles"],
    "piso_cozinha": ["floor_tiles_06", "floor_tiles_08"], "granilite": ["terrazzo_tiles"], "piso_corredor": ["large_floor_tiles_02", "large_grey_tiles"],
    "fachada_pastilha": ["rectangular_facade_tiles"], "fachada_placas": ["concrete_tile_facade"], "fachada_pintada": ["painted_concrete"],
    "fachada_amarela": ["yellow_plaster"], "pavers": ["interlocking_concrete_pavers"], "calcada": ["concrete_pavement"],
    "veludo": ["velour_velvet"], "linho": ["rough_linen"], "carpete": ["dirty_carpet"], "malha": ["cotton_jersey"], "couro_marrom": ["brown_leather"],
    "grama": ["grass_ground"], "terra": ["farm_soil"], "morro_mata": ["aerial_grass_rock"], "morro_pedra": ["rock_face"], "marmore": ["marble_01", "marble_tiles"], "telha": ["clay_roof_tiles"],
    "madeira_clara": ["wood_table_001", "oak_veneer_01"], "laminado": ["laminate_floor_02", "wood_floor"], "mdf_branco": ["white_plaster_02"],
}
MAPAS = {"Diffuse": "_diff", "Rough": "_rough", "nor_gl": "_nor_gl", "Displacement": "_disp"}

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "busca-treinamento-vr/1.0"}), timeout=120).read()

for pasta, nomes in TEXTURAS.items():
    d = os.path.join(DEST, pasta)
    if os.path.isdir(d) and any("_diff" in f for f in os.listdir(d)):
        continue
    for nome in nomes:
        try: info = json.loads(get("https://api.polyhaven.com/files/" + nome))
        except Exception: continue
        if "Diffuse" not in info: continue
        os.makedirs(d, exist_ok=True); n = 0
        for mapa, suf in MAPAS.items():
            try: url = info[mapa]["1k"]["jpg"]["url"]
            except KeyError: continue
            with open(os.path.join(d, "%s%s_1k.jpg" % (nome, suf)), "wb") as f: f.write(get(url))
            n += 1
        print("[TEX] %s <- %s (%d mapas)" % (pasta, nome, n)); break
    else:
        print("[TEX] %s: NAO ENCONTRADA (%s)" % (pasta, ", ".join(nomes)))
