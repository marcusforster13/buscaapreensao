"""
Cassino clandestino - exporta o cofre do escritorio (corpo e segredo) para o autor refazer.

Uso:  blender -b ../cassino.blend --python exportar_cofre.py      (nao salva a cena)
Saida: modelos/para_editar/cofre.glb

As pecas saem NA POSICAO DA CENA (nao centralizadas): e so editar e salvar no mesmo lugar.
O cofre tem 60 cm de frente a fundo (X), 55 cm de largura (Y) e 80 cm de altura; a porta, com o segredo, olha para -X.
Para devolver: salve como modelos/cofre.glb, sem mover o conjunto.
"""
import bpy, os

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(AQUI, "para_editar"); os.makedirs(OUT, exist_ok=True)

pecas = [o for o in bpy.data.objects if o.type == "MESH" and (o.name == "Cofre" or o.name.startswith("Cofre_"))]
for o in bpy.data.objects: o.select_set(False)
for o in pecas: o.hide_set(False); o.select_set(True)
bpy.context.view_layer.objects.active = pecas[0]
dst = os.path.join(OUT, "cofre.glb")
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", use_selection=True, export_apply=True)
print("[COFRE] %d pecas (%s), %d triangulos, %.0f KB" % (len(pecas), ", ".join("%s em %s" % (o.name, [round(v, 2) for v in o.matrix_world.translation]) for o in pecas),
      sum(len(p.vertices) - 2 for o in pecas for p in o.data.polygons), os.path.getsize(dst) / 1024))
