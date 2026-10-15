// Busca e Apreensao - extrai do motor (05_Treinamento/motor_busca.js) todas as falas dos personagens e grava
// 06_Audio/falas_busca.json: [{ arquivo, quem, texto }]. Cada fala vira um audio (gerar_vozes_elevenlabs.py); o site
// acha o audio pelo texto exato (cenario -> vozes.falas). Rodar de novo sempre que mudar alguma fala.
//   node 06_Audio/extrair_falas.js
const fs = require('fs'), path = require('path');
const RAIZ = path.join(__dirname, '..');
const src = fs.readFileSync(path.join(RAIZ, '05_Treinamento', 'motor_busca.js'), 'utf8');

// quem fala, pela funcao onde a fala esta e pelo primeiro argumento de diz(...)
const POR_FUNCAO = {
  menuPorteiro: 'porteiro', chamarTestemunha: 'porteiro', menuVizinha: 'vizinha', vizinhaSai: 'vizinha',
  menuMorador: 'morador', menuMoradorPorta: 'morador', bater: 'morador', condutaMorador: 'morador', menuConduta: 'morador',
  resolverConduta: 'morador', menuQuartoInquilino: 'morador', entrar: 'morador',
};
function funcaoEm(pos) {
  const antes = src.slice(0, pos); let m, ult = null; const re = /function\s+(\w+)\s*\(/g;
  while ((m = re.exec(antes))) ult = m[1];
  return ult;
}
function strings(trecho) {                       // literais de texto ('...' ou `...` sem ${})
  const r = []; const re = /'((?:\\.|[^'\\])*)'|`((?:\\.|[^`\\])*)`/g; let m;
  while ((m = re.exec(trecho))) { const t = m[1] ?? m[2]; if (t && !/\$\{/.test(t) && t.length > 3 && !/^[a-z_]+$/.test(t)) r.push(t.replace(/\\'/g, "'")); }
  return r;
}
const falas = [], visto = new Set();
function add(quem, texto) { const k = quem + '|' + texto; if (visto.has(k)) return; visto.add(k); falas.push({ quem, texto }); }

// diz(quem, texto): pega a chamada inteira (parenteses balanceados)
let i = 0;
while ((i = src.indexOf('diz(', i)) >= 0) {
  if (/\w/.test(src[i - 1] || '')) { i += 4; continue; }          // nao e "diz(" solto (ex.: dizer()
  let d = 0, j = i + 3; for (; j < src.length; j++) { if (src[j] === '(') d++; else if (src[j] === ')') { d--; if (!d) break; } }
  const chamada = src.slice(i + 4, j), virg = chamada.indexOf(','), arg1 = chamada.slice(0, virg).trim(), resto = chamada.slice(virg + 1);
  const fn = funcaoEm(i);
  if (/menuApoio|menuParceiro/.test(fn)) { i = j; continue; }      // PMs de apoio retirados da cena
  let quem = arg1 === 'civil()' ? 'inspetor' : arg1 === 'npcs.morador' ? 'morador' : POR_FUNCAO[fn] || null;
  if (fn === 'menuFamilia') {                                      // a esposa e o idoso respondem com falas diferentes
    for (const t of strings(resto)) add(/meu filho|levanto/.test(t) ? 'idoso' : 'mulher', t);
  } else if (quem) for (const t of strings(resto)) add(quem, t);
  else console.warn('sem dono:', fn, arg1, strings(resto)[0]);
  i = j;
}
// fala de abertura do inspetor (texto montado com a hora): as duas versoes
add('inspetor', 'Bom dia. Equipe pronta. O mandado está com você: leia antes de subirmos.');
add('inspetor', 'Bom dia. São quatro e meia, a equipe está pronta. O mandado está com você: leia antes de subirmos.');

const cont = {};
// o site acha o audio pelo texto; voz feminina usa <arquivo>_f (ver vozGravada em treinamento.js)
const FEM = new Set(['mulher', 'vizinha']);
for (const f of falas) { cont[f.quem] = (cont[f.quem] || 0) + 1; f.base = `fala_${f.quem}_${String(cont[f.quem]).padStart(2, '0')}`; f.arquivo = f.base + (FEM.has(f.quem) ? '_f' : ''); }
fs.writeFileSync(path.join(__dirname, 'falas_busca.json'), JSON.stringify(falas.map(f => ({ arquivo: f.arquivo, base: f.base, quem: f.quem, texto: f.texto })), null, 1));
console.log(falas.length, 'falas,', falas.reduce((a, f) => a + f.texto.length, 0), 'caracteres:', cont);
