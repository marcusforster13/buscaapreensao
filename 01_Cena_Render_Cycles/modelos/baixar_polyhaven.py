"""
Busca e Apreensao - baixa os modelos prontos do Poly Haven (licenca CC0) usados na cena.

Cada modelo vai para modelos/polyhaven/<nome>/ (.gltf + .bin + texturas de 1k). So baixa o que falta.
Uso:  python baixar_polyhaven.py        (serve o Python que vem com o Blender)
"""
import json, os, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(AQUI, "polyhaven")
MODELOS = ["plastic_monobloc_chair_01", "bar_chair_round_01", "sofa_02", "sofa_03", "coffee_table_round_01", "plastic_crate_01",
           "cardboard_box_01", "steel_frame_shelves_01", "ceiling_fan", "korean_fire_extinguisher_01", "trashbag", "metal_trash_can",
           "planter_pot_clay", "utility_box_01", "modern_arm_chair_01", "painted_wooden_cabinet", "Television_01", "wooden_stool_01", "potted_plant_01", "potted_plant_02"]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "busca-treinamento-vr/1.0"})
    return urllib.request.urlopen(req, timeout=120).read()

total = 0
for m in MODELOS:
    pasta = os.path.join(DEST, m)
    try:
        info = json.loads(get("https://api.polyhaven.com/files/" + m))["gltf"]["1k"]["gltf"]
    except Exception as e:
        print("[PH] %s: nao encontrado (%s)" % (m, e)); continue
    arqs = [(m + "_1k.gltf", info["url"], info["size"])] + [(k, v["url"], v["size"]) for k, v in info.get("include", {}).items()]
    tam = 0
    for rel, url, size in arqs:
        dst = os.path.join(pasta, rel.replace("/", os.sep)); tam += size
        if os.path.exists(dst) and os.path.getsize(dst) == size: continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f: f.write(get(url))
    total += tam
    print("[PH] %s: %d arquivos, %.1f MB" % (m, len(arqs), tam / 1e6))
print("[PH] total %.1f MB em %s" % (total / 1e6, DEST))
