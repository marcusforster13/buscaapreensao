"""Renderiza previas da cena (Cycles, rapido) em ../.claude/capturas.  Uso: blender -b busca.blend --python renderizar_previa.py -- Camera_Aerea Camera_Abordagem"""
import bpy, os, sys
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["Camera_Aerea"]
sc = bpy.context.scene
out = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "capturas"))
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.cycles.samples = 32; sc.cycles.use_denoising = True
sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 85
if "Camera_Garrafas" in args and "Camera_Garrafas" not in bpy.data.objects:      # previa de perto das prateleiras do bar
    from mathutils import Vector
    _c = bpy.data.objects.new("Camera_Garrafas", bpy.data.cameras.new("Camera_Garrafas")); sc.collection.objects.link(_c)
    _c.location = (4.75, 3.3, 1.75); _c.rotation_euler = (Vector((5.76, 3.3, 1.72)) - Vector(_c.location)).to_track_quat("-Z", "Y").to_euler(); _c.data.lens = 35
for nome in args:
    sc.camera = bpy.data.objects[nome]
    sc.render.filepath = os.path.join(out, "previa_" + nome + ".jpg")
    bpy.ops.render.render(write_still=True)
    print("[PREVIA] " + sc.render.filepath)
