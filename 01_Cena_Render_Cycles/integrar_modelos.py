"""
Busca e Apreensao - integra modelos feitos a mao (.glb) na CENA PRINCIPAL.

Como usar:
  1. Exporte o modelo do Blender como .glb, MANTENDO a mesma posicao da cena (como foi feito com os livros).
  2. Coloque o .glb em 01_Cena_Render_Cycles/modelos/
  3. Registre em modelos/modelos.json:  { "arquivo.glb": { "substitui": "NomeDoObjetoRaiz", "colecao": "02_Sala" } }
  4. Rode:  blender -b busca.blend --python integrar_modelos.py
     (ou pelo atualizar_tudo.ps1, que ja chama este script antes de gerar as versoes VR e three.js)

O que o script faz:
  - backup automatico em backup/ antes de alterar
  - apaga o objeto antigo (e todos os filhos) indicado em "substitui"
  - importa o .glb no lugar, na colecao indicada
  - religa materiais pelo nome (ex.: "Madeira_Freijo.001" -> "Madeira_Freijo"), entao as texturas CC0 da cena valem
  - so reintegra se o .glb mudou (guarda a data do arquivo no proprio .blend)
"""
import bpy, os, json, time, shutil, re

try:
    AQUI = os.path.dirname(os.path.abspath(__file__))
except NameError:
    AQUI = os.path.join(os.path.expanduser("~"), "Desktop", "buscaeapreensao", "01_Cena_Render_Cycles")
MOD = os.path.join(AQUI, "modelos")
CFG = os.path.join(MOD, "modelos.json")

def say(m):
    print("[MODELOS] " + m)

def apagar_hierarquia(ob):
    for c in list(ob.children):
        apagar_hierarquia(c)
    bpy.data.objects.remove(ob, do_unlink=True)

def base(nome):
    return re.sub(r"\.\d{3}$", "", nome)

if not os.path.exists(CFG):
    say("nenhum modelos.json encontrado; nada a fazer")
else:
    cfg = json.load(open(CFG, encoding="utf-8"))
    estado = bpy.context.scene.get("modelos_integrados", "{}")
    estado = json.loads(estado) if isinstance(estado, str) else {}
    pendentes = []
    for arq, info in cfg.items():
        caminho = os.path.join(MOD, arq)
        if not os.path.exists(caminho):
            say("AVISO: %s nao encontrado" % arq); continue
        mtime = os.path.getmtime(caminho)
        if estado.get(arq) == mtime and "--forcar" not in os.sys.argv:
            say("%s ja integrado (sem mudancas)" % arq); continue
        pendentes.append((arq, caminho, mtime, info))

    if pendentes and bpy.data.filepath:
        bk = os.path.join(AQUI, "backup")
        os.makedirs(bk, exist_ok=True)
        destino = os.path.join(bk, "cassino_%s.blend" % time.strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(bpy.data.filepath, destino)
        say("backup: %s" % os.path.basename(destino))

    for arq, caminho, mtime, info in pendentes:
        nomes = info["substitui"] if isinstance(info["substitui"], list) else [info["substitui"]]
        for nome in nomes:                          # aceita um nome, uma lista de nomes ou um prefixo terminado em *
            if nome.endswith("*"):
                for alvo in [o for o in bpy.data.objects if o.name.startswith(nome[:-1]) and o.type == "MESH"]:
                    bpy.data.objects.remove(alvo, do_unlink=True)
                continue
            alvo = bpy.data.objects.get(nome)
            if alvo:
                apagar_hierarquia(alvo)
        antes = set(bpy.data.objects)
        mats_antes = set(bpy.data.materials)
        bpy.ops.import_scene.gltf(filepath=caminho)
        novos = [o for o in bpy.data.objects if o not in antes]
        for o in [o for o in novos if o.name.startswith(tuple(info.get("ignorar", ()))) ] if info.get("ignorar") else []:
            novos.remove(o); bpy.data.objects.remove(o, do_unlink=True)      # pecas que vieram no arquivo so como referencia
        col = bpy.data.collections.get(info.get("colecao", "")) or bpy.context.scene.collection
        religados = 0
        for o in novos:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            col.objects.link(o)
            o["modelo_usuario"] = arq          # os scripts de detalhamento nao mexem em modelos feitos a mao
            for slot in o.material_slots:
                m = slot.material
                # materiais com textura de imagem sao do autor e nunca sao trocados (um "Material.008" com a foto da
                # placa era religado ao "Material" branco que ja existia na cena)
                if m and m not in mats_antes and not (m.node_tree and any(n.type == "TEX_IMAGE" and n.image for n in m.node_tree.nodes)):
                    existente = bpy.data.materials.get(base(m.name))
                    if existente and existente not in (m,) and existente in mats_antes:
                        slot.material = existente; religados += 1
        # "materiais": {"prefixo": "Material_Da_Cena"} - pecas que vieram sem material (vale o prefixo mais longo)
        # "*maior" vale para a maior peca sem material e "*" para as outras (os nomes mudam na importacao: Cylinder -> Cylinder.006)
        sem = [o for o in novos if o.type == "MESH" and not [s for s in o.material_slots if s.material]]
        maior = max(sem, key=lambda o: max(o.dimensions), default=None) if "*maior" in info.get("materiais", {}) else None
        for o in sem:
            pref = max((p for p in info.get("materiais", {}) if not p.startswith("*") and o.name.startswith(p)), key=len, default=None)
            chave = pref or ("*maior" if o is maior else "*")
            mt = bpy.data.materials.get(info.get("materiais", {}).get(chave, ""))
            if mt: o.data.materials.clear(); o.data.materials.append(mt)
        # "virar": ["prefixo"] - pecas planas que vieram com a face para baixo (a luz calculada caia no lado de baixo e a peca ficava preta)
        for pref in info.get("virar", []):
            for o in [o for o in novos if o.name.startswith(pref) and o.type == "MESH"]:
                o.data.flip_normals(); o.data.update()
        # "vazios": {"prefixo": "Material_Da_Cena"} - a peca veio com parte das faces sem material (o autor so texturizou um
        # detalhe, ex.: o segredo do cofre): os espacos de material vazios recebem o material indicado
        for pref, nome_mat in info.get("vazios", {}).items():
            mt = bpy.data.materials.get(nome_mat)
            for o in [o for o in novos if o.name.startswith(pref) and o.type == "MESH"] if mt else []:
                n = 0
                for i, m_ in enumerate(o.data.materials):
                    if m_ is None: o.data.materials[i] = mt; n += 1
                say("%s: %d espaco(s) de material vazio(s) com %s" % (o.name, n, mt.name))
        # "resto": {"prefixo": {"frente": [x, y, z], "material": "Nome"}} - a peca veio com uma imagem so, feita para a frente:
        # as faces que nao olham para "frente" (laterais, topo, fundo) recebem o material indicado, da cena
        from mathutils import Vector as _V
        for pref, r in info.get("resto", {}).items():
            mt = bpy.data.materials.get(r["material"]); fr = _V(r["frente"]).normalized()
            for o in [o for o in novos if o.name.startswith(pref) and o.type == "MESH"] if mt else []:
                o.data.materials.append(mt); i_novo = len(o.data.materials) - 1; rot = o.matrix_world.to_3x3(); n = 0
                for pl in o.data.polygons:
                    if (rot @ pl.normal).normalized().dot(fr) < r.get("limite", .35): pl.material_index = i_novo; n += 1
                say("%s: %d de %d faces com %s" % (o.name, n, len(o.data.polygons), mt.name))
        # "deslocar": {"prefixo": [x, y, z]} - ajuste fino de posicao (ex.: disco no mesmo plano do fundo da bacia, que pisca)
        for pref, d in info.get("deslocar", {}).items():
            for o in [o for o in novos if o.name.startswith(pref)]:
                mw = o.matrix_world.copy(); mw.translation.x += d[0]; mw.translation.y += d[1]; mw.translation.z += d[2]; o.matrix_world = mw
        # "pai": {"prefixo": "I_Raiz"} - pecas que passam a ser filhas de um item interativo (ex.: fichas que o aluno
        # apreende): vao para a colecao da raiz e mantem a posicao em que o autor deixou
        bpy.context.view_layer.update()
        for pref, nome_pai in info.get("pai", {}).items():
            pai = bpy.data.objects.get(nome_pai)
            if not pai: say("AVISO: raiz %s nao existe" % nome_pai); continue
            for o in [o for o in novos if o.name.startswith(pref)]:
                for c in list(o.users_collection): c.objects.unlink(o)
                for c in pai.users_collection: c.objects.link(o)
                o.parent = pai; o.matrix_parent_inverse = pai.matrix_world.inverted()
        for m in [m for m in bpy.data.materials if m.users == 0 and m not in mats_antes]:
            bpy.data.materials.remove(m)
        # materiais novos com textura de imagem: o prefixo Modelo_ faz o pipeline manter a UV do autor e reduzir a
        # imagem para JPG de ate 1024 px (as placas vieram com 23 MB de texturas)
        n_img = 0
        for m in [m for m in bpy.data.materials if m not in mats_antes and m.node_tree]:
            if any(n.type == "TEX_IMAGE" and n.image for n in m.node_tree.nodes) and not m.name.startswith(("Modelo_", "Img_")):
                m.name = "Modelo_%s_%d" % (os.path.splitext(arq)[0], n_img); n_img += 1
        if n_img: say("%d materiais com textura de imagem marcados como Modelo_" % n_img)
        estado[arq] = mtime
        say("%s -> substituiu '%s' com %d objetos em %s (%d materiais religados aos da cena)"
            % (arq, info["substitui"], len(novos), col.name, religados))

    bpy.context.scene["modelos_integrados"] = json.dumps(estado)
    if pendentes and bpy.app.background:
        bpy.ops.wm.save_mainfile()
        say("cena principal salva")
