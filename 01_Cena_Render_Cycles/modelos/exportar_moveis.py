"""Busca e Apreensao - exporta os moveis que abrem para o autor remodelar: modelos/para_editar/<movel>.glb

Cada arquivo traz o movel no centro, com a base em z = 0 e a FRENTE virada para -Y (no Blender: vista frontal, tecla 1).
Pecas: "Corpo" (casco fixo) e uma peca para cada parte que abre ("Gaveta_1", "Porta_2", "Tampa_1"...). A ORIGEM de cada
peca que abre fica onde ela se move: na frente da gaveta, na dobradica da porta. Ao remodelar, manter os nomes das pecas,
as origens e o tamanho geral; o resto e livre.

Uso:  blender -b busca.blend --python modelos/exportar_moveis.py            (todos)
      blender -b busca.blend --python modelos/exportar_moveis.py -- Comoda  (so um)
"""
import bpy, bmesh, os, re, sys, math
from mathutils import Matrix, Vector

AQUI = os.path.dirname(os.path.abspath(__file__)); DEST = os.path.join(AQUI, "para_editar"); os.makedirs(DEST, exist_ok=True)
so = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
dg = bpy.context.evaluated_depsgraph_get(); sc = bpy.context.scene
TIPO = {"Gav": "Gaveta", "Fol": "Porta", "Tam": "Tampa"}

def juntar(nome, pares):
    bm = bmesh.new(); mats = []
    for o, mtx in pares:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(mtx); idx = []
        for m in me.materials:
            if m not in mats: mats.append(m)
            idx.append(mats.index(m))
        n0 = len(bm.faces); bm.from_mesh(me); bm.faces.ensure_lookup_table()
        for f in bm.faces[n0:]: f.material_index = idx[f.material_index] if idx else 0
        bpy.data.meshes.remove(me)
    out = bpy.data.meshes.new(nome); bm.to_mesh(out); bm.free()
    for m in mats: out.materials.append(m)
    return out

moveis = {}
for o in sc.objects:
    m = re.match(r"A_(Gav|Fol|Tam)_(.+)_(\d+)$", o.name)
    if m and o.type == "EMPTY": moveis.setdefault(m.group(2), []).append((int(m.group(3)), m.group(1), o))
nomes = sorted(moveis, key=len, reverse=True)
cascos = {n: [] for n in nomes}
for o in sc.objects:
    if o.type == "MESH" and o.name.startswith("Mv_"):
        dono = next((n for n in nomes if o.name.startswith("Mv_" + n + "_")), None)
        if dono: cascos[dono].append(o)

for nome in sorted(moveis):
    if so and nome not in so: continue
    raizes = sorted(moveis[nome]); rz = raizes[0][2].matrix_world.to_euler().z
    R = Matrix.Rotation(-rz, 4, "Z")
    pts = [R @ (o.matrix_world @ Vector(c)) for o in cascos[nome] for c in o.bound_box]
    if not pts: continue
    mn = Vector([min(p[i] for p in pts) for i in range(3)]); mx = Vector([max(p[i] for p in pts) for i in range(3)])
    Tm = Matrix.Translation((-(mn.x + mx.x) / 2, -(mn.y + mx.y) / 2, -mn.z)) @ R          # da cena para o arquivo
    novos = []
    ob = bpy.data.objects.new("Corpo", juntar("Corpo", [(o, Tm @ o.matrix_world) for o in cascos[nome]])); sc.collection.objects.link(ob); novos.append(ob)
    cont = {}
    for n, tipo, raiz in raizes:
        cont[tipo] = cont.get(tipo, 0) + 1; nm = "%s_%d" % (TIPO[tipo], cont[tipo]); inv = raiz.matrix_world.inverted()
        filhos = [c for c in raiz.children_recursive if c.type in {"MESH", "FONT"}]
        ob = bpy.data.objects.new(nm, juntar(nm, [(c, inv @ c.matrix_world) for c in filhos])); sc.collection.objects.link(ob)
        ob.matrix_world = Tm @ raiz.matrix_world; ob["raiz"] = raiz.name; novos.append(ob)
    for o in sc.objects: o.select_set(False)
    for o in novos: o.select_set(True)
    bpy.context.view_layer.objects.active = novos[0]
    arq = os.path.join(DEST, nome.lower() + ".glb")
    bpy.ops.export_scene.gltf(filepath=arq, export_format="GLB", use_selection=True, export_extras=True, export_apply=True)
    d = mx - mn
    print("[MOVEIS] %-28s %.2f x %.2f x %.2f m (largura x fundo x altura), %d pecas: %s" % (nome.lower() + ".glb", d.x, d.y, d.z, len(novos), ", ".join(o.name for o in novos)))
    for o in novos: bpy.data.objects.remove(o, do_unlink=True)
