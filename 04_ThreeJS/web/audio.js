/*
  Cassino clandestino - sons do visualizador.
  Le audio/manifest.json (gerado pelo pipeline a partir de 06_Audio/brutos) e toca so o que existir.
  - ambientes: tocam em loop, com volume diferente dentro e fora da casa
  - posicionais: saem de um ponto da cena (geladeira, TV, viatura), ficam mais altos quanto mais perto
  - eventos: tocados pelo treinamento (porta, camera, fita, algemas, radio, passos)
  O navegador so libera som depois de um clique/tecla/entrada no VR; o modulo espera isso.
*/
import * as THREE from 'three';

// posicoes em coordenadas da cena web (Y para cima)
const DEF = {
  amb_transito_noite:  { tipo: 'ambiente', fora: .45, dentro: .12 },
  amb_bar:             { tipo: 'ambiente', fora: .06, dentro: .3 },
  maquinas_caca_niquel: { tipo: 'posicional', pos: [-1.3, 1.2, -11.0], vol: .55, ref: 2.2, rolloff: 1.5 },
  musica_sala_reservada: { tipo: 'posicional', pos: [9, 1.4, -11.5], vol: .5, ref: 2.0, rolloff: 1.5 },
  cachorro_longe:      { tipo: 'esporadico', area: [[-30, -15], [-20, 20]], vol: .4, intervalo: [25, 60] },
  sirene_longe:        { tipo: 'evento', vol: .4 },
  radio_chiado:        { tipo: 'evento', vol: .3 },
  radio_bip:           { tipo: 'evento', vol: .6 },
  porta_abrindo:       { tipo: 'evento', vol: .5 },
  movel_arrastado:     { tipo: 'evento', vol: .7 },
  algemas:             { tipo: 'evento', vol: .6 },
  tiro_pistola:        { tipo: 'evento', vol: 1 },
  recarregar_pistola:  { tipo: 'evento', vol: .8 },
  granada_efeito_moral: { tipo: 'evento', vol: 1 },
  granada_quique:      { tipo: 'evento', vol: .5 }
};

export async function iniciarAudio({ scene, camera, renderer }) {
  let manifest = [];
  try { manifest = await fetch('audio/manifest.json?v=' + (window.__versao || '')).then(r => r.ok ? r.json() : []); } catch (e) { }
  const VQ = '?v=' + (window.__versao || '');
  const arquivos = Object.fromEntries(manifest.map(f => [f.replace(/\.(mp3|ogg|wav)$/i, ''), (window.__h ? window.__h('audio/' + f) : 'audio/' + f + VQ)]));
  window.__somArquivos = arquivos;                        // o treinamento consulta: se o arquivo existe, nao usa o som sintetizado
  const listener = new THREE.AudioListener(); camera.add(listener);
  const loader = new THREE.AudioLoader(), buffers = {}, ganho = {}, ambientes = [], posicionais = [];
  const fala = {};                                       // trecho util de cada fala gravada (sem os silencios das pontas)
  const V = new THREE.Vector3();
  let ligado = false, mudo = false, gesto = false, pronto = false;
  const iniciados = new Set();

  // botao visivel enquanto o navegador nao liberar o audio (regra dos navegadores: precisa de um clique)
  const bt = document.createElement('button'); bt.type = 'button'; bt.textContent = 'Ativar som';
  Object.assign(bt.style, { position: 'fixed', left: '16px', bottom: 'calc(16px + env(safe-area-inset-bottom, 0px))', zIndex: 7,
    background: 'rgba(12,15,24,.9)', color: '#efe9df', border: '1px solid #f0a340', borderRadius: '4px', padding: '10px 14px',
    font: '600 13px "Segoe UI", system-ui, sans-serif', cursor: 'pointer' });
  document.body.appendChild(bt);

  // libera o audio no primeiro gesto, mesmo que os arquivos ainda estejam carregando
  function desbloquear() {
    gesto = true;
    listener.context.resume?.().catch(() => { });
    if (pronto) ligar();
  }
  for (const ev of ['pointerdown', 'keydown', 'touchstart']) addEventListener(ev, desbloquear, { passive: true });
  renderer.xr.addEventListener('sessionstart', desbloquear);
  bt.onclick = desbloquear;
  if (navigator.userActivation?.hasBeenActive) desbloquear();     // ja houve clique antes deste modulo carregar

  // Os sons de evento (tiro, recarga, estouro, radio) sao pequenos e carregam primeiro; os ambientes, que sao grandes,
  // seguem em segundo plano. Antes, tudo esperava o maior arquivo e, ate la, o tiro saia com o som sintetizado.
  const carregar = ([n, url]) => loader.loadAsync(url).then(b => { buffers[n] = b; ganho[n] = normalizar(b); if (n.startsWith('fala_')) fala[n] = silencio(b); }).catch(() => console.warn('som nao carregou:', url));
  const todos = Object.entries(arquivos).filter(([n]) => DEF[n] || n.startsWith('fala_'));
  const curtos = todos.filter(([n]) => DEF[n]?.tipo === 'evento');
  await Promise.all(curtos.map(carregar));
  pronto = true; if (gesto) ligar();
  for (const x of todos.filter(x => !curtos.includes(x))) carregar(x).then(() => { if (gesto) ligar(); });      // cada ambiente entra quando chega

  // normaliza cada arquivo para ~-20 dB RMS sem passar de 0,95 de pico (arquivos baixos ficam audiveis)
  // falas gravadas: descobre onde a voz comeca e termina, para tocar sem os silencios das pontas
  // (deixa ~0,10 s antes e ~0,30 s depois). Assim a gravacao pode vir "crua", sem edicao.
  function silencio(b) {
    const d = b.getChannelData(0), sr = b.sampleRate; let pico = 1e-4;
    for (let i = 0; i < d.length; i += 4) { const v = Math.abs(d[i]); if (v > pico) pico = v; }
    const lim = Math.max(.012, pico * .06); let a = 0, z = d.length - 1;
    while (a < d.length && Math.abs(d[a]) < lim) a++;
    while (z > a && Math.abs(d[z]) < lim) z--;
    const ini = Math.max(0, a / sr - .1), fim = Math.min(b.duration, z / sr + .3);
    return { ini, dur: Math.max(.2, fim - ini), fade: .06 };
  }
  function normalizar(b) {
    const d = b.getChannelData(0); let pico = 1e-4, s = 0, n = 0;
    for (let i = 0; i < d.length; i += 8) { const v = Math.abs(d[i]); if (v > pico) pico = v; s += v * v; n++; }
    const rms = Math.sqrt(s / n) || 1e-4;
    return Math.min(.95 / pico, Math.pow(10, (-20 - 20 * Math.log10(rms)) / 20), 12);
  }
  const vol = (n, v) => v * (ganho[n] || 1);
  // toca so um trecho do arquivo (ini, dur em segundos), com 1 s de saida suave
  function recorte(a, d, v) {
    if (d.ritmo) a.setPlaybackRate(d.ritmo);              // fala mais lenta (e um pouco mais grave)
    if (d.ini != null) a.offset = d.ini;
    if (!d.dur) return;
    a.duration = d.dur; const t = listener.context.currentTime, real = d.dur / (d.ritmo || 1), sai = Math.min(d.fade ?? 1, real / 2);
    a.gain.gain.setValueAtTime(v, t + real - sai); a.gain.gain.linearRampToValueAtTime(0, t + real);
  }

  function ligar() {
    if (!pronto) return;
    const primeira = !ligado; ligado = true;
    if (primeira) { listener.context.resume?.().catch(() => { }); bt.remove(); }
    // pode ser chamada varias vezes: cada som de ambiente comeca assim que o proprio arquivo termina de carregar
    for (const [n, b] of Object.entries(buffers)) {
      const d = DEF[n];
      if (!d || iniciados.has(n)) continue;           // falas: so tocam quando o treinamento chama
      if (d.tipo === 'ambiente') {
        const a = new THREE.Audio(listener); a.setBuffer(b); a.setLoop(true); a.setVolume(0); a.play();
        ambientes.push({ a, d, n }); iniciados.add(n);
      } else if (d.tipo === 'posicional' && !d.soTreino) {
        posicional(n, d); iniciados.add(n);
      }
    }
    if (primeira) agendarEsporadicos();
  }
  function posicional(n, d) {
    const a = new THREE.PositionalAudio(listener); a.setBuffer(buffers[n]); a.setLoop(true);
    a.setRefDistance(d.ref); a.setRolloffFactor(d.rolloff); a.setDistanceModel('exponential'); a.setVolume(mudo ? 0 : vol(n, d.vol));
    const o = new THREE.Object3D(); o.position.fromArray(d.pos); o.add(a); scene.add(o); a.play();
    posicionais.push({ n, a, o, d, k: 1 });
    return a;
  }
  function agendarEsporadicos() {
    for (const [n, d] of Object.entries(DEF)) {
      if (d.tipo !== 'esporadico' || !buffers[n]) continue;
      const tocar = () => {
        if (!mudo) {
          const a = new THREE.PositionalAudio(listener); a.setBuffer(buffers[n]); a.setRefDistance(8); a.setVolume(vol(n, d.vol));
          const o = new THREE.Object3D();
          o.position.set(THREE.MathUtils.randFloat(...d.area[0]), 1, THREE.MathUtils.randFloat(...d.area[1]));
          o.add(a); scene.add(o); a.play(); a.onEnded = () => { a.isPlaying = false; scene.remove(o); };
        }
        setTimeout(tocar, THREE.MathUtils.randFloat(...d.intervalo) * 1000);
      };
      setTimeout(tocar, THREE.MathUtils.randFloat(5, 15) * 1000);
    }
  }

  // volume dos ambientes conforme dentro/fora da casa (transicao suave)
  let dentro = 0;
  function quadro(dt) {
    if (!ligado) return;
    camera.getWorldPosition(V);
    const alvo = (V.x > -6 && V.x < 6 && V.z > -13 && V.z < 0) ? 1 : 0;      // dentro do predio do bar
    dentro += (alvo - dentro) * Math.min(1, dt * 1.5);
    for (const { a, d, n } of ambientes) a.setVolume(mudo ? 0 : vol(n, d.fora * (1 - dentro) + d.dentro * dentro));
  }

  const api = {
    tem: n => !!buffers[n],
    duracao: n => fala[n]?.dur || buffers[n]?.duration || 0,           // segundos (falas gravadas)
    // eventos do treinamento; retorna false se o arquivo nao existe. Com analisar=true devolve um medidor de volume
    // da fala (0 a 1, antes da atenuacao por distancia) para mexer a boca do personagem
    tocar(n, pos, analisar = false, trecho = null) {     // trecho = { ini, dur, ritmo }: toca so uma parte do arquivo, ou mais devagar
      if (!buffers[n]) return false;
      ligar();
      const d = { ...(DEF[n] || { vol: n.startsWith('fala_') ? 1 : .7 }), ...(fala[n] || {}), ...(trecho || {}) };
      if (mudo) return true;
      let a;
      if (pos) {
        a = new THREE.PositionalAudio(listener); a.setBuffer(buffers[n]); a.setRefDistance(1.2); a.setVolume(vol(n, d.vol));
        const o = new THREE.Object3D(); o.position.copy(pos); o.add(a); scene.add(o); recorte(a, d, vol(n, d.vol)); a.play();
        a.onEnded = () => { a.isPlaying = false; scene.remove(o); };
      } else {
        a = new THREE.Audio(listener); a.setBuffer(buffers[n]); a.setVolume(vol(n, d.vol)); recorte(a, d, vol(n, d.vol)); a.play();
      }
      if (!analisar || !a.source) return true;
      const an = listener.context.createAnalyser(); an.fftSize = 512; a.source.connect(an);
      const buf = new Uint8Array(an.fftSize), g = ganho[n] || 1;
      return () => { an.getByteTimeDomainData(buf); let s = 0; for (const x of buf) { const v = (x - 128) / 128; s += v * v; } return Math.min(1, Math.sqrt(s / buf.length) * g * 4); };
    },
    iniciarTreino() { if (buffers.choro_crianca_baixo && !posicionais.some(p => p.n === 'choro_crianca_baixo')) { ligar(); posicional('choro_crianca_baixo', DEF.choro_crianca_baixo); } },
    pararChoro() { const p = posicionais.find(p => p.n === 'choro_crianca_baixo'); if (p) { p.a.stop(); scene.remove(p.o); posicionais.splice(posicionais.indexOf(p), 1); } },
    mudo(v) { mudo = v; for (const p of posicionais) p.a.setVolume(v ? 0 : vol(p.n, p.d.vol) * p.k); },
    // abafa ou libera um som posicional (porta fechada, estante no lugar): k de 0 a 1, com transicao curta
    nivel(n, k) { const p = posicionais.find(p => p.n === n); if (!p || p.k === k) return; p.k = k; if (!mudo) p.a.gain.gain.setTargetAtTime(vol(p.n, p.d.vol) * k, listener.context.currentTime, .4); },
    desbloquear,
    quadro, carregados: () => Object.keys(buffers),
    falas: () => Object.fromEntries(Object.entries(fala).map(([k, v]) => [k, [+v.ini.toFixed(2), +v.dur.toFixed(2), +buffers[k].duration.toFixed(2), +(ganho[k] || 1).toFixed(2)]])),
    estado: () => ({ contexto: listener.context.state, ligado, mudo, dentro: +dentro.toFixed(2), ganho: Object.fromEntries(Object.entries(ganho).map(([k, v]) => [k, +v.toFixed(2)])),
      ambientes: ambientes.map(({ a }) => ({ tocando: a.isPlaying, volume: +a.getVolume().toFixed(2) })),
      posicionais: posicionais.map(({ n, a }) => ({ n, tocando: a.isPlaying })) })
  };
  window.__som = api;
  return api;
}
