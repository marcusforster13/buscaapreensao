"""Carimba a versao do site e a marca de cada arquivo. Rodar antes de cada envio ao GitHub.

- index.html recebe a data e a hora (aparece na tela);
- versao.json recebe a versao e, para cada arquivo do site, um resumo do conteudo. A pagina le esse arquivo sem usar
  copia guardada e poe o resumo no endereco de cada arquivo: o navegador (inclusive o do Quest) so baixa de novo o que
  mudou, e nunca usa versao antiga."""
import hashlib, io, json, os, re, time
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "04_ThreeJS", "web")
p = os.path.join(WEB, "index.html")
s = io.open(p, encoding="utf-8").read(); v = time.strftime("%m%d-%H%M")
s, n = re.subn(r"const VERSAO = '[^']*';", "const VERSAO = '%s';" % v, s); assert n == 1
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
arq = {}
for raiz, _, nomes in os.walk(WEB):
    for nome in nomes:
        if nome in ("index.html", "versao.json") or nome.endswith(".bat"): continue
        cam = os.path.join(raiz, nome)
        arq[os.path.relpath(cam, WEB).replace(os.sep, "/")] = hashlib.md5(open(cam, "rb").read()).hexdigest()[:10]
json.dump({"versao": v, "arquivos": arq}, io.open(os.path.join(WEB, "versao.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("[VERSAO] %s, %d arquivos marcados" % (v, len(arq)))
