"""Confere os .glb dos personagens: pes no chao, altura, maos (T-pose = maos na altura dos ombros e longe do corpo)."""
import bpy, os
WEB = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "04_ThreeJS", "web", "personagens"))
for p in ["vitima", "agressor", "crianca", "vizinho"]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(WEB, p + ".glb"))
    arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
    corpo = [o for o in bpy.data.objects if o.type == "MESH" and o.modifiers]
    mao = next(b for b in arm.pose.bones if b.name.endswith("R Hand"))
    for tr in arm.animation_data.nla_tracks:
        st = tr.strips[0]
        for t in arm.animation_data.nla_tracks: t.mute = t != tr
        res = []
        for f in (int(st.frame_start), int((st.frame_start + st.frame_end) / 2)):
            bpy.context.scene.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
            zs = []
            for o in corpo:
                e = o.evaluated_get(dg); m = e.to_mesh()
                zs += [(e.matrix_world @ v.co).z for v in m.vertices]; e.to_mesh_clear()
            h = arm.matrix_world @ mao.head
            res.append("q%d pes %.2f topo %.2f mao(z %.2f, xy %.2f %.2f)" % (f, min(zs), max(zs), h.z, h.x, h.y))
        print("CHK", p, tr.name, " | ".join(res))
