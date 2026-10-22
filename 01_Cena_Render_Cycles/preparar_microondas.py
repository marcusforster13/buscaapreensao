# Busca e Apreensao - prepara o micro-ondas do usuario (microondas_realista.blend, ~98 mil triangulos) para o Quest e grava
# modelos/moveis/microondas.glb (~8 mil). Rodar de novo so se o usuario mandar outra versao do .blend:
#   blender -b <microondas_realista.blend> --python preparar_microondas.py -- <saida.glb>
# - grelhas repetidas (malha da porta, grelha lateral) viram uma malha por tipo, sem chanfro;
# - caixas com chanfro de 1 segmento (antes 4-6); cilindros pequenos (parafusos, rodinhas, botao) e o aro/prato reduzidos;
# - as pecas da porta (filhas de PORTA_DOBRADICA_ABRIR) saem com o prefixo "PORTA_" para o busca.py montar a porta que abre.
import bpy, bmesh, sys
from mathutils import Matrix
saida = sys.argv[sys.argv.index("--") + 1]
porta = {o.name for o in bpy.data.objects["PORTA_DOBRADICA_ABRIR"].children_recursive}
for o in bpy.data.objects:
    if o.type != "MESH": continue
    nm = o.name
    for md in list(o.modifiers):
        if md.type == "BEVEL":
            if nm.startswith(("Malha protetora", "Grelha lateral", "Numero", "Legenda")): o.modifiers.remove(md)
            else: md.segments = 1
        elif md.type == "WEIGHTED_NORMAL": o.modifiers.remove(md)
    n = len(o.data.polygons)
    alvo = 300 if nm.startswith(("Aro giratorio", "Borda do prato")) else 120 if nm.startswith(("Prato de vidro",)) else 60 if n > 400 and not o.modifiers else None
    if alvo and n > alvo * 1.5:
        d = o.modifiers.new("Reduzir", "DECIMATE"); d.ratio = alvo / n
dg = bpy.context.evaluated_depsgraph_get()
grupos = {}
fim = []
for o in [o for o in bpy.data.objects if o.type == "MESH"]:
    ev = o.evaluated_get(dg); me = bpy.data.meshes.new_from_object(ev); me.transform(o.matrix_world)
    base = o.name.split(".")[0]; chave = ("PORTA_" if o.name in porta else "") + base
    grupos.setdefault((chave, o.active_material.name if o.active_material else ""), []).append(me)
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
col = bpy.context.scene.collection
for (chave, mn), meshes in grupos.items():
    bm = bmesh.new()
    for me in meshes: bm.from_mesh(me)
    me = bpy.data.meshes.new(chave); bm.to_mesh(me); bm.free()
    if mn: me.materials.append(bpy.data.materials[mn])
    o = bpy.data.objects.new(chave.replace(" ", "_"), me); col.objects.link(o); fim.append(o)
tri = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in fim)
bpy.ops.export_scene.gltf(filepath=saida, export_format="GLB", export_apply=True)
print("[MICRO] %d pecas, %d triangulos -> %s" % (len(fim), tri, saida))
