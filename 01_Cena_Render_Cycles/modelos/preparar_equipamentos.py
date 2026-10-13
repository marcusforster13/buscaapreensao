"""
Cassino clandestino - prepara os equipamentos do policial para o site (modelos fornecidos pelo usuario).

  arma.glb     pistola (180 pecas)  -> 1 malha, 21 cm de comprimento, cano para a frente, origem na empunhadura
  granada.glb  granada de efeito moral -> 1 malha, 13 cm de altura, origem no centro, textura de ate 512 px

Saida: ../../04_ThreeJS/web/modelos/arma.glb e granada.glb  (no site: frente = -Z, cima = +Y)
Uso:   blender -b --factory-startup --python preparar_equipamentos.py
"""
import bpy, os
from mathutils import Vector, Matrix

AQUI = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.normpath(os.path.join(AQUI, "..", "..", "04_ThreeJS", "web", "modelos"))
os.makedirs(WEB, exist_ok=True)

def say(m): print("[EQUIP] " + m)

def importar(arquivo):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(AQUI, arquivo))
    bpy.context.view_layer.update()
    return [o for o in bpy.data.objects if o.type == "MESH"]

def juntar(objs, nome):
    for o in objs:
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
    for o in bpy.data.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    with bpy.context.temp_override(active_object=objs[0], selected_objects=objs, selected_editable_objects=objs):
        bpy.ops.object.join()
    ob = objs[0]; ob.name = nome; ob.data.name = nome
    ob.data.transform(ob.matrix_world); ob.matrix_world = Matrix.Identity(4)
    for o in [o for o in bpy.data.objects if o is not ob]: bpy.data.objects.remove(o, do_unlink=True)
    return ob

def caixa(ob):
    vs = [v.co for v in ob.data.vertices]
    return Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))), Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))

def exportar(ob, nome):
    for o in bpy.data.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=os.path.join(WEB, nome), export_format="GLB", use_selection=True,
                              export_image_format="JPEG", export_image_quality=85, export_animations=False)
    mn, mx = caixa(ob)
    say("%s: %d tris, caixa %s a %s" % (nome, sum(len(p.vertices) - 2 for p in ob.data.polygons), [round(v, 3) for v in mn], [round(v, 3) for v in mx]))

# ---------------------------------------------------------------- pistola
import numpy as np
objs = importar("arma.glb")
def pontos(prefixo):
    return [o.matrix_world @ v.co for o in objs if o.name.startswith(prefixo) for v in o.data.vertices]
media = lambda vs: sum(vs, Vector()) / len(vs)
# O modelo vem girado no arquivo (cano ~46 graus para baixo). A direcao real do cano e a normal do aro da boca,
# no sentido da alca de mira para a boca; "para cima" e o lado da massa de mira.
aro = pontos("Muzzle outer rim"); boca = media(aro); alca = media(pontos("Rear sight base")); massa = media(pontos("Front sight"))
a = np.array([list(v - boca) for v in aro]); _, vec = np.linalg.eigh(np.cov(a.T))
frente = Vector([float(x) for x in vec[:, 0]]).normalized()
if frente.dot(boca - alca) < 0: frente = -frente
cima = (massa - boca); cima = (cima - frente * cima.dot(frente)).normalized()
lado = frente.cross(cima).normalized()
arma = juntar(objs, "Arma")
R = Matrix((lado, frente, cima)).to_4x4()                 # leva o cano para +Y e a mira para +Z
arma.data.transform(R); boca = R @ boca
mn, mx = caixa(arma)
k = .20 / (mx.y - mn.y)                                   # 20 cm de comprimento, medido ao longo do cano
arma.data.transform(Matrix.Scale(k, 4)); boca = boca * k
# origem SOBRE o eixo do cano, 15 cm atras da boca: no site o cano coincide com o raio de mira (frente = -Z)
arma.data.transform(Matrix.Translation((-boca.x, -boca.y + .15, -boca.z)))
for p in arma.data.polygons: p.use_smooth = False
exportar(arma, "arma.glb")
say("cano alinhado: boca em (0, 0.15, 0) no Blender = (0, 0, -0.15) no site; inclinacao corrigida de %.1f graus" % __import__("math").degrees(__import__("math").asin(abs(frente.z))))

# ---------------------------------------------------------------- granada de efeito moral
objs = importar("granada.glb")
for img in bpy.data.images:
    if img.size[0] > 512: img.scale(512, 512)
gr = juntar(objs, "Granada")
mn, mx = caixa(gr)
k = .13 / (mx.z - mn.z)
gr.data.transform(Matrix.Scale(k, 4)); mn, mx = caixa(gr)
gr.data.transform(Matrix.Translation(-(mn + mx) / 2))
exportar(gr, "granada.glb")
