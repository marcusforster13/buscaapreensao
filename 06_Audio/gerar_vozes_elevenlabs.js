// Busca e Apreensao - gera as vozes dos personagens no ElevenLabs, de uma vez.
//
// Como usar:
//   1. Crie o arquivo 06_Audio/chave_elevenlabs.txt com a sua chave da API do ElevenLabs (so a chave, uma linha).
//      Esse arquivo fica fora do GitHub (.gitignore). Ou use a variavel de ambiente ELEVENLABS_API_KEY.
//   2. Rode:   node 06_Audio/gerar_vozes_elevenlabs.js
//      Na primeira vez ele escolhe uma voz da sua conta para cada personagem e grava a escolha em
//      06_Audio/vozes_elevenlabs.json. Para trocar a voz de alguem, troque o id ali e apague os .mp3 dessa pessoa.
//   3. Os audios vao para 06_Audio/brutos e 04_ThreeJS/web/audio; o cenario passa a saber qual audio e de qual fala.
//      Rodar de novo so gera o que falta (nao gasta credito a toa).
//
// As falas vem de 06_Audio/falas_busca.json (node 06_Audio/extrair_falas.js).
const fs = require('fs'), path = require('path');
const AQUI = __dirname, RAIZ = path.join(AQUI, '..');
const BRUTOS = path.join(AQUI, 'brutos'), WEB_AUDIO = path.join(RAIZ, '04_ThreeJS', 'web', 'audio');
const CENARIOS = [path.join(RAIZ, '05_Treinamento', 'cenario_ba_01.json'), path.join(RAIZ, '04_ThreeJS', 'web', 'treinamento', 'cenario_ba_01.json')];
const API = 'https://api.elevenlabs.io/v1';
const MODELO = 'eleven_multilingual_v2';                 // fala portugues do Brasil com qualquer voz da conta

// perfil de cada personagem: usado para escolher a voz automaticamente (genero, idade) e o jeito de falar
const PERFIL = {
  inspetor: { genero: 'male', idade: ['middle_aged', 'middle aged', 'young'], estilo: { stability: .55, similarity_boost: .8, style: .15 } },
  porteiro: { genero: 'male', idade: ['middle_aged', 'middle aged', 'old'], estilo: { stability: .5, similarity_boost: .8, style: .2 } },
  morador: { genero: 'male', idade: ['young', 'middle_aged', 'middle aged'], estilo: { stability: .35, similarity_boost: .8, style: .45 } },
  mulher: { genero: 'female', idade: ['young', 'middle_aged', 'middle aged'], estilo: { stability: .35, similarity_boost: .8, style: .45 } },
  idoso: { genero: 'male', idade: ['old'], estilo: { stability: .55, similarity_boost: .8, style: .2 } },
  vizinha: { genero: 'female', idade: ['middle_aged', 'middle aged', 'old'], estilo: { stability: .45, similarity_boost: .8, style: .35 } },
};

function chave() {
  if (process.env.ELEVENLABS_API_KEY) return process.env.ELEVENLABS_API_KEY.trim();
  const f = path.join(AQUI, 'chave_elevenlabs.txt');
  if (fs.existsSync(f)) return fs.readFileSync(f, 'utf8').trim();
  console.error('Falta a chave: crie 06_Audio/chave_elevenlabs.txt com a sua chave da API do ElevenLabs.'); process.exit(1);
}
const KEY = chave();
async function api(rota, opcoes = {}) {
  const r = await fetch(API + rota, { ...opcoes, headers: { 'xi-api-key': KEY, 'Content-Type': 'application/json', ...(opcoes.headers || {}) } });
  if (!r.ok) throw new Error(`${rota}: ${r.status} ${(await r.text()).slice(0, 300)}`);
  return r;
}

async function escolherVozes() {
  const arq = path.join(AQUI, 'vozes_elevenlabs.json');
  const salvas = fs.existsSync(arq) ? JSON.parse(fs.readFileSync(arq, 'utf8')) : {};
  if (Object.keys(PERFIL).every(k => salvas[k])) return salvas;
  const { voices } = await (await api('/voices')).json();
  const lab = v => v.labels || {};
  const br = v => /brazil|portug|pt-br|brasil/i.test(JSON.stringify(lab(v)) + ' ' + (v.name || '') + ' ' + (v.description || ''));
  const usadas = new Set(Object.values(salvas));
  for (const [quem, p] of Object.entries(PERFIL)) {
    if (salvas[quem]) continue;
    const nota = v => (lab(v).gender === p.genero ? 10 : 0) + (p.idade.includes(lab(v).age) ? 4 - p.idade.indexOf(lab(v).age) : 0) + (br(v) ? 6 : 0) + (usadas.has(v.voice_id) ? -20 : 0);
    const melhor = [...voices].sort((a, b) => nota(b) - nota(a))[0];
    if (!melhor) throw new Error('Nenhuma voz encontrada na conta.');
    salvas[quem] = melhor.voice_id; usadas.add(melhor.voice_id);
    console.log(`  ${quem.padEnd(9)} -> ${melhor.name} (${[lab(melhor).gender, lab(melhor).age, lab(melhor).accent].filter(Boolean).join(', ')})`);
  }
  fs.writeFileSync(arq, JSON.stringify(salvas, null, 1));
  console.log('Vozes escolhidas e gravadas em 06_Audio/vozes_elevenlabs.json (pode trocar os ids ali).');
  return salvas;
}

(async () => {
  const falas = JSON.parse(fs.readFileSync(path.join(AQUI, 'falas_busca.json'), 'utf8'));
  fs.mkdirSync(BRUTOS, { recursive: true }); fs.mkdirSync(WEB_AUDIO, { recursive: true });
  console.log(`${falas.length} falas, ${falas.reduce((a, f) => a + f.texto.length, 0)} caracteres no total.`);
  const vozes = await escolherVozes();
  let feitas = 0, chars = 0;
  for (const f of falas) {
    const destino = path.join(BRUTOS, f.arquivo + '.mp3');
    if (!fs.existsSync(destino)) {
      const p = PERFIL[f.quem];
      const r = await api(`/text-to-speech/${vozes[f.quem]}?output_format=mp3_44100_128`, {
        method: 'POST', headers: { Accept: 'audio/mpeg' },
        body: JSON.stringify({ text: f.texto, model_id: MODELO, voice_settings: { ...p.estilo, use_speaker_boost: true } }),
      });
      fs.writeFileSync(destino, Buffer.from(await r.arrayBuffer()));
      feitas++; chars += f.texto.length; console.log(`  ${f.arquivo}: ${f.texto.slice(0, 60)}`);
    }
    fs.copyFileSync(destino, path.join(WEB_AUDIO, f.arquivo + '.mp3'));
  }
  // lista de audios do site e catalogo de falas do cenario (o site acha o audio pelo texto)
  const man = path.join(WEB_AUDIO, 'manifest.json');
  const lista = new Set(fs.existsSync(man) ? JSON.parse(fs.readFileSync(man, 'utf8')) : []);
  for (const f of falas) lista.add(f.arquivo + '.mp3');
  fs.writeFileSync(man, JSON.stringify([...lista].sort()));
  for (const c of CENARIOS) {
    // "vozes" fica como ultima chave do cenario; o resto do arquivo (formatado a mao) nao muda
    let t = fs.readFileSync(c, 'utf8');
    const k = t.indexOf(',\n  "vozes":'); if (k >= 0) t = t.slice(0, k) + '\n}';      // tira o catalogo antigo
    t = t.replace(/\s*\}\s*$/, '');                                                   // tira o fecha-chaves final
    t += ',\n  "vozes": { "falas": [\n' + falas.map(f => '    ' + JSON.stringify({ texto: f.texto, arquivo: f.base, quem: f.quem })).join(',\n') + '\n  ] }\n}\n';
    JSON.parse(t); fs.writeFileSync(c, t);
  }
  console.log(`Pronto: ${feitas} audios novos (${chars} caracteres gastos). Avise o Claude para publicar.`);
})().catch(e => { console.error('Erro:', e.message); process.exit(1); });
