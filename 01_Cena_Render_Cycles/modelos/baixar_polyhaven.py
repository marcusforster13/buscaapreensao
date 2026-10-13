"""
Busca e Apreensao - baixa os modelos prontos do Poly Haven (licenca CC0) usados na cena.

Cada modelo vai para modelos/polyhaven/<nome>/ (.gltf + .bin + texturas de 1k). So baixa o que falta.
Uso:  python baixar_polyhaven.py        (serve o Python que vem com o Blender)
"""
import json, os, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(AQUI, "polyhaven")
MODELOS = ["sofa_02", "sofa_03", "coffee_table_round_01", "modern_arm_chair_01", "Television_01", "potted_plant_01", "potted_plant_02",
           "exterior_aircon_unit", "street_lamp_01", "jacaranda_tree", "tree_small_02", "shrub_01", "shrub_03", "fire_hydrant", "painted_wooden_bench", "covered_car", "water_manhole_cover",
           "Sofa_01", "ArmChair_01", "modern_coffee_table_01", "dining_chair_02", "wooden_bookshelf_worn", "book_encyclopedia_set_01", "decorative_book_set_01", "throw_pillows_01", "standing_picture_frame_01", "hanging_picture_frame_01", "hanging_picture_frame_02", "hanging_picture_frame_03", "ceramic_vase_01", "ceramic_vase_03", "potted_plant_04", "pachira_aquatica_01", "calathea_orbifolia_01", "desk_lamp_arm_01", "classic_laptop", "alarm_clock_01", "vintage_electric_kettle", "pot_enamel_01", "wooden_cutting_board", "bananas", "food_apple_01", "wooden_bowl_01", "all_purpose_cleaner", "bleach_bottle", "plastic_broom", "wicker_basket_01", "binder_notebook", "clipboard", "office_notepads", "Ottoman_01", "rubber_boots", "football", "gamepad", "WetFloorSign_01", "security_camera_01", "ClassicNightstand_01", "side_table_01", "grass_medium_01", "grass_bermuda_01", "grass_medium_02"]

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
