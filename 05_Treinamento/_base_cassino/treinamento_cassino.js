/*
  Cassino clandestino - motor do treinamento
  Le treinamento/cenario_cs_01.json (fases, acoes, pontos, falhas graves, variacoes, dialogos, historia).

  Controles
    Computador: clique = falar / usar / botoes   T = menu   K = checklist   Q = saca ou guarda a arma (clique dispara)   R = recarrega   E = granada
    Quest:      gatilho = falar / usar / botoes / teleporte   A = saca a arma (gatilho direito dispara; apertar o analogico direito recarrega)   X = pega a granada na mao esquerda; segurar e soltar o gatilho esquerdo arremessa
                grip (qualquer mao) = lanterna   botao Y ou B = menu do treinamento
  Variacoes forcadas pela URL (para o instrutor):  ?v=indicios:visiveis,seguranca:armado_reage,fuga:tentam_sair
*/
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';

export async function iniciar(ctx) {
  const { scene, camera, rig, renderer, CFG } = ctx;
  const HQ = p => window.__h ? window.__h(p) : p;      // endereco com a marca do conteudo do arquivo
  const CEN = await fetch(HQ('treinamento/cenario_cs_01.json')).then(r => r.json());
  const V = new THREE.Vector3(), V2 = new THREE.Vector3(), UP = new THREE.Vector3(0, 1, 0);

  /* ================= estado ================= */
  const S = { ativo: false, inicio: 0, fim: 0, variacao: {}, feitos: new Map(), erros: [], graves: [], log: [],
    modo: 'avaliacao', historia: false, fila: [], armaNaMao: false, granadas: 2 };
  let A = null;                 // ocorrencia em curso
  const HIST = [];              // atendimentos concluidos (para o relatorio)
  const npcs = {};
  const acoes = {};
  CEN.fases.forEach(f => {
    (f.acoes || []).forEach(a => acoes[a.id] = { ...a, fase: f.id, tipo: 'acao' });
    (f.erros || []).forEach(a => acoes[a.id] = { ...a, fase: f.id, tipo: 'erro' });
    (f.falhas_graves || []).forEach(a => acoes[a.id] = { ...a, fase: f.id, tipo: 'grave' });
  });
  const cond1 = c => {
    const m = c.match(/variacao\.(\w+)\s*(==|!=)\s*'([^']*)'/);
    if (!m) return true;
    return m[2] === '==' ? S.variacao[m[1]] === m[3] : S.variacao[m[1]] !== m[3];
  };
  // "a == 'x' && b != 'y' || c == 'z'"  (&& tem precedencia sobre ||)
  const cond = c => !c || c.split('||').some(ou => ou.split('&&').every(cond1));
  const tempo = () => ((S.fim || performance.now()) - S.inicio) / 1000;
  const fmt = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  const nAt = () => (A ? A.n : HIST.length);

  function registrar(id, extra = '') {
    const a = acoes[id]; if (!a || !S.ativo) return;
    if (a.tipo === 'acao') {
      if (S.feitos.has(id) || !cond(a.condicao)) return;
      S.feitos.set(id, tempo());
    } else if (a.tipo === 'erro') {
      S.erros.push({ id, texto: a.texto, pontos: a.pontos, t: tempo(), extra, atendimento: nAt() });
    } else {
      S.graves.push({ id, texto: a.texto, pontos: a.pontos, base: a.base, t: tempo(), extra, atendimento: nAt() });
      legenda('Instrutor', 'Falha grave registrada: ' + a.texto, 4);
    }
    S.log.push({ t: +tempo().toFixed(1), atendimento: nAt(), id, extra });
    status();
  }
  function penalidade(pontos, texto, feedback) {
    S.erros.push({ id: 'conduta', texto, pontos, feedback, t: tempo(), atendimento: nAt() });
    S.log.push({ t: +tempo().toFixed(1), atendimento: nAt(), id: 'conduta', extra: texto }); status();
  }
  const npcPorNome = quem => Object.values(npcs).find(n => n.userData.nome === quem) || null;

  /* ================= paineis 3D (funcionam no computador e no Quest) ================= */
  const paineis = [];
  class Painel {
    constructor(largura = 1.1) {
      this.largura = largura; this.botoes = [];
      this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
        new THREE.MeshBasicMaterial({ transparent: true, depthTest: false, toneMapped: false, fog: false }));
      this.mesh.renderOrder = 1000; this.mesh.visible = false; scene.add(this.mesh); paineis.push(this);
      // realce do botao apontado pelo controle (no VR a linha do controle some atras do painel)
      this.realce = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: 0xf0a340, transparent: true, opacity: .32, depthTest: false, toneMapped: false, fog: false }));
      this.realce.renderOrder = 1001; this.realce.visible = false; this.mesh.add(this.realce);
    }
    apontar(ray) {                                   // devolve o ponto atingido e realca o botao embaixo do raio
      if (!this.mesh.visible) return null;
      const h = ray.intersectObject(this.mesh, false)[0]; if (!h) return null;
      const py = (1 - h.uv.y) * this.H, b = this.botoes.find(b => py >= b.y0 && py <= b.y1);
      if (b) { this.realce.position.set(0, .5 - (b.y0 + b.y1) / 2 / this.H, .001); this.realce.scale.set(1 - 2 * 56 / 1024, (b.y1 - b.y0) / this.H, 1); this.realce.visible = true; }
      return h;
    }
    mostrar({ tag = '', titulo = '', texto = '', botoes = [], longe = 1.15 }) {
      const W = 1024, P = 56, cv = document.createElement('canvas'), g = cv.getContext('2d');
      cv.width = W; cv.height = 2400;
      const linhas = (txt, fonte, maxW) => { g.font = fonte; const out = []; for (const par of String(txt).split('\n')) { let l = ''; for (const w of par.split(' ')) { const t = l ? l + ' ' + w : w; if (g.measureText(t).width > maxW && l) { out.push(l); l = w; } else l = t; } out.push(l); } return out; };
      const lt = titulo ? linhas(titulo, '700 46px Segoe UI, sans-serif', W - 2 * P) : [];
      const lx = texto ? linhas(texto, '400 32px Segoe UI, sans-serif', W - 2 * P) : [];
      const lb = botoes.map(b => linhas(b.label, '600 30px Segoe UI, sans-serif', W - 2 * P - 40));     // rotulos longos quebram em linhas
      let y = P; const H0 = P + (tag ? 40 : 0) + lt.length * 56 + (lx.length ? 16 + lx.length * 44 : 0) + lb.reduce((s, l) => s + 54 + l.length * 38, 0) + P + 10;
      cv.height = Math.min(2400, H0);
      g.fillStyle = 'rgba(11,14,22,.95)'; g.beginPath(); g.roundRect(0, 0, W, cv.height, 22); g.fill();
      g.strokeStyle = 'rgba(240,163,64,.5)'; g.lineWidth = 3; g.stroke();
      if (tag) { g.fillStyle = '#f0a340'; g.font = '500 24px Consolas, monospace'; g.fillText(tag.toUpperCase(), P, y + 22); y += 40; }
      g.fillStyle = '#efe9df'; g.font = '700 46px Segoe UI, sans-serif'; lt.forEach(l => { g.fillText(l, P, y + 44); y += 56; });
      if (lx.length) { y += 16; g.fillStyle = 'rgba(239,233,223,.86)'; g.font = '400 32px Segoe UI, sans-serif'; lx.forEach(l => { g.fillText(l, P, y + 32); y += 44; }); }
      y += 10; this.botoes = [];
      for (const [bi, b] of botoes.entries()) {
        y += 12; const h = 34 + lb[bi].length * 38;
        g.fillStyle = b.cor || 'rgba(240,163,64,.14)'; g.beginPath(); g.roundRect(P, y, W - 2 * P, h, 12); g.fill();
        g.strokeStyle = 'rgba(240,163,64,.55)'; g.lineWidth = 2; g.stroke();
        g.fillStyle = '#efe9df'; g.font = '600 30px Segoe UI, sans-serif';
        lb[bi].forEach((l, li) => g.fillText(l, P + 20, y + 46 + li * 38));
        this.botoes.push({ ...b, y0: y, y1: y + h }); y += h + 8;
      }
      const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
      this.mesh.material.map?.dispose(); this.mesh.material.map = tex; this.mesh.material.needsUpdate = true;
      this.H = cv.height; this.mesh.scale.set(this.largura, this.largura * cv.height / W, 1);
      camera.getWorldPosition(V); camera.getWorldDirection(V2); V2.y = 0; V2.normalize();
      this.mesh.position.copy(V).addScaledVector(V2, longe); this.mesh.position.y = V.y - .08;
      this.mesh.lookAt(V.x, this.mesh.position.y, V.z); this.mesh.visible = true;
      return this;
    }
    esconder() { this.mesh.visible = false; this.realce.visible = false; }
    clique(ray) {
      if (!this.mesh.visible) return false;
      const h = ray.intersectObject(this.mesh, false)[0]; if (!h) return false;
      const py = (1 - h.uv.y) * this.H, b = this.botoes.find(b => py >= b.y0 && py <= b.y1);
      if (b && b.acao) b.acao();
      return true;
    }
  }
  const menu = new Painel(1.1), dialogo = new Painel(1.15);
  const cursorVR = new THREE.Mesh(new THREE.CircleGeometry(.012, 20), new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, toneMapped: false, fog: false }));
  cursorVR.renderOrder = 1003; cursorVR.visible = false; scene.add(cursorVR);
  // chamado a cada quadro pelo index.html com o raio de cada controle; devolve o acerto de cada raio (ou null)
  function apontar(raios) {
    for (const p of paineis) p.realce.visible = false;
    let ultimo = null;
    const hs = raios.map(r => { let h = null; for (const p of paineis) h = p.apontar(r) || h; if (h) ultimo = h; return h; });
    cursorVR.visible = !!ultimo;
    if (ultimo) { cursorVR.position.copy(ultimo.point); cursorVR.quaternion.copy(ultimo.object.quaternion); cursorVR.translateZ(.002); }
    return hs;
  }
  const fecharPaineis = () => paineis.forEach(p => p.esconder());

  /* legenda presa a camera */
  const lcv = document.createElement('canvas'); lcv.width = 1400; lcv.height = 200;
  const ltex = new THREE.CanvasTexture(lcv); ltex.colorSpace = THREE.SRGBColorSpace;
  const leg = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 1.0 * 200 / 1400), new THREE.MeshBasicMaterial({ map: ltex, transparent: true, depthTest: false, toneMapped: false, fog: false }));
  leg.position.set(0, -.3, -.95); leg.renderOrder = 1001; leg.visible = false; camera.add(leg);
  let legAte = 0;
  function legenda(quem, texto, seg = 4) {
    const g = lcv.getContext('2d'); g.clearRect(0, 0, 1400, 200);
    g.fillStyle = 'rgba(5,7,12,.82)'; g.beginPath(); g.roundRect(0, 0, 1400, 200, 18); g.fill();
    g.fillStyle = '#f0a340'; g.font = '600 34px Segoe UI, sans-serif'; g.fillText(quem, 36, 54);
    g.fillStyle = '#efe9df'; g.font = '400 38px Segoe UI, sans-serif';
    let l = '', y = 108; for (const w of texto.split(' ')) { const t = l ? l + ' ' + w : w; if (g.measureText(t).width > 1330 && l) { g.fillText(l, 36, y); y += 46; l = w; } else l = t; } g.fillText(l, 36, y);
    ltex.needsUpdate = true; legAte = performance.now() + seg * 1000;
    const vr = renderer.xr.isPresenting; leg.visible = vr;          // no VR: legenda no espaco; no computador: faixa HTML
    const hl = document.getElementById('legendaHTML'); if (hl && !vr) { hl.innerHTML = `<b>${quem}:</b> ${texto}`; hl.hidden = false; }
  }
  // catalogo de vozes gravadas (cenario -> vozes.falas): o texto falado encontra o arquivo
  const VOZ = new Map((CEN.vozes?.falas || []).filter(f => !/_f$/.test(f.arquivo)).map(f => [f.texto, f.arquivo]));
  // arquivo gravado para um texto, na voz certa: a condutora usa <arquivo>_f; se so houver a gravacao masculina, ela
  // fica com a voz sintetica (nao fala com voz de homem)
  function vozGravada(texto, voz = 'm') {
    const a = VOZ.get(texto) || VOZ.get(texto.replace(/\bObrigada\b/g, 'Obrigado')); if (!a) return null;
    if (/^f/.test(voz)) return window.__som?.tem(a + '_f') ? a + '_f' : (/^fala_condutor_/.test(a) ? null : (window.__som?.tem(a) ? a : null));
    return window.__som?.tem(a) ? a : null;
  }
  const gravacao = texto => { const a = VOZ.get(texto); return a && window.__som?.tem(a) ? a : null; };
  const duracaoFala = texto => { const a = gravacao(texto); return a ? window.__som.duracao(a) : Math.max(2.6, texto.length / 14); };
  const espera = ms => new Promise(r => setTimeout(r, ms));
  function falar(quem, texto, voz = 'f') {
    const npc = npcPorNome(quem), arq = gravacao(texto);
    if (arq) {                                            // voz gravada: sai da personagem (ou do radio/telefone)
      const seg = window.__som.duracao(arq);
      legenda(quem, texto, seg + .6);
      const med = window.__som.tocar(arq, npc ? npc.position.clone().setY(1.55) : null, !!npc);
      if (npc) npc.userData.fala = { medidor: typeof med === 'function' ? med : null, sintetica: typeof med !== 'function', ate: performance.now() + seg * 1000 };
      return espera(seg * 1000);
    }
    const seg = Math.max(3, texto.length / 14);
    legenda(quem, texto, seg);
    const p = vozSintetica(texto, voz);
    if (npc) { const f = { sintetica: true, ate: performance.now() + (p ? seg + 6 : seg * .8) * 1000 }; npc.userData.fala = f; p?.then(() => { if (npc.userData.fala === f) npc.userData.fala = null; }); }
    return p;
  }
  // chamada da coordenacao pelo radio: bip, a fala e um bip curto no fim
  const BIP = () => Math.min(.8, window.__som?.duracao('radio_bip') || .4) + .15;
  async function radio(texto) {
    window.__som?.tocar('radio_bip'); await espera(BIP() * 1000);
    await falar('Rádio · Sala de operações', texto, 'm');
    window.__som?.tocar('radio_bip', null, false, { vol: .35 });
  }
  // voz do navegador (pt-BR). Retorna uma promessa que termina quando a fala acaba (ou null sem voz)
  function vozSintetica(texto, voz = 'f') {
    const lento = /_lento$/.test(voz); voz = voz.replace('_lento', '');      // fala arrastada (condutor com sinais de embriaguez)
    if (S.voz === false || !('speechSynthesis' in window)) return null;
    const vs = speechSynthesis.getVoices().filter(v => v.lang && v.lang.replace('_', '-').startsWith('pt'));
    if (!vs.length) { if (!S.avisoVoz) { S.avisoVoz = true; console.warn('Sem voz sintética em português neste navegador: só legendas.'); } return null; }
    try {
      const u = new SpeechSynthesisUtterance(texto); u.lang = 'pt-BR';
      const br = vs.filter(v => /BR/i.test(v.lang)), lista = br.length ? br : vs;
      const fem = lista.filter(v => /francisca|thalita|maria|luciana|feminin|female|google/i.test(v.name));
      const mas = lista.filter(v => /antonio|daniel|ricardo|masculin|male/i.test(v.name) && !/female/i.test(v.name));
      u.voice = (voz === 'm' ? mas[0] : fem[0]) || lista[(voz === 'm' ? 1 : 0) % lista.length];
      u.pitch = voz === 'c' ? 1.6 : voz === 'm' ? .85 : 1.05; u.rate = voz === 'm' ? 1 : .95;
      if (lento) { u.rate = .66; u.pitch *= .9; }
      return new Promise(r => { u.onend = u.onerror = () => r(); speechSynthesis.speak(u); });
    } catch (e) { return null; }
  }
  if ('speechSynthesis' in window) speechSynthesis.getVoices();      // o Chrome carrega a lista de vozes na primeira chamada

  /* fala com audio gravado (06_Audio/brutos/<audio>.mp3) ou voz sintetica, legenda e gesto; termina quando a fala acaba */
  async function dizer(npc, quem, linha, voz = 'f') {
    const { texto, gesto } = linha, audio = linha.audio || vozGravada(texto, voz);
    const som = window.__som, gravado = audio && som?.tem(audio);
    const ritmo = /_lento$/.test(voz) ? .84 : 1;            // condutor com sinais de embriaguez: a mesma gravacao, mais devagar
    const seg = gravado ? som.duracao(audio) / ritmo : Math.max(2.5, texto.length / 13);
    legenda(quem, texto, seg + .6);
    if (npc && gesto) animar(npc, gesto, seg + 1.5);
    if (gravado) {
      const med = som.tocar(audio, npc ? npc.position.clone().setY(1.55) : null, true, ritmo !== 1 ? { ritmo } : null);
      const f = npc && { medidor: typeof med === 'function' ? med : null, sintetica: typeof med !== 'function', ate: performance.now() + seg * 1000 };
      if (npc) npc.userData.fala = f;
      await espera(seg * 1000 + 350); if (npc?.userData.fala === f) npc.userData.fala = null; return;
    }
    const p = vozSintetica(texto, voz);
    const f = npc && { sintetica: true, ate: performance.now() + (p ? seg + 6 : seg) * 1000 };
    if (npc) npc.userData.fala = f;
    await (p ? Promise.race([p, espera(seg * 1000 + 1500)]) : espera(seg * 1000));      // nao fica preso se a voz do navegador nao avisar o fim
    if (npc?.userData.fala === f) npc.userData.fala = null;
    await espera(350);
  }
  /* ================= personagens provisorios (fase 3 troca por modelos reais) ================= */
  function boneco(nome, corRoupa, altura = 1.7, corCalca = 0x2b2f3a) {
    const g = new THREE.Group(), s = altura / 1.7; g.name = 'NPC_' + nome;
    const pele = new THREE.MeshStandardMaterial({ color: 0xb98a68, roughness: .7 });
    const roupa = new THREE.MeshStandardMaterial({ color: corRoupa, roughness: .85 });
    const calca = new THREE.MeshStandardMaterial({ color: corCalca, roughness: .85 });
    const cap = (r, l, m, x, y, z, rz = 0) => { const k = new THREE.Mesh(new THREE.CapsuleGeometry(r * s, l * s, 4, 12), m); k.position.set(x * s, y * s, z * s); k.rotation.z = rz; g.add(k); return k; };
    cap(.075, .7, calca, -.1, .44, 0); cap(.075, .7, calca, .1, .44, 0);
    cap(.17, .4, roupa, 0, 1.14, 0);
    cap(.055, .52, roupa, -.25, 1.1, 0, .1); const bracoD = cap(.055, .52, roupa, .25, 1.1, 0, -.1);
    cap(.05, .05, pele, 0, 1.47, 0);
    const cab = new THREE.Mesh(new THREE.SphereGeometry(.115 * s, 24, 16), pele); cab.position.set(0, 1.62 * s, 0); g.add(cab);
    const hit = new THREE.Mesh(new THREE.CylinderGeometry(.38 * s, .38 * s, altura, 8), new THREE.MeshBasicMaterial({ visible: false }));
    hit.position.y = altura / 2; hit.userData.npc = nome; g.add(hit);
    const ecv = document.createElement('canvas'); ecv.width = 256; ecv.height = 64; const eg = ecv.getContext('2d');
    eg.fillStyle = 'rgba(5,7,12,.7)'; eg.beginPath(); eg.roundRect(0, 0, 256, 64, 14); eg.fill();
    eg.fillStyle = '#efe9df'; eg.font = '600 32px Segoe UI, sans-serif'; eg.textAlign = 'center'; eg.fillText(nome, 128, 44);
    const et = new THREE.CanvasTexture(ecv); et.colorSpace = THREE.SRGBColorSpace;
    const rotulo = new THREE.Sprite(new THREE.SpriteMaterial({ map: et, depthTest: true, transparent: true, fog: false }));
    rotulo.scale.set(.5, .125, 1); rotulo.position.y = altura + .25; rotulo.renderOrder = 999; rotulo.visible = false; g.add(rotulo);   // nomes ocultos
    g.userData = { hit, bracoD, rotulo, nome };
    return g;
  }
  /* personagens reais (Rocketbox, licenca MIT) convertidos para personagens/*.glb; se faltar, usa o boneco */
  const modelos = {};
  const modelosProntos = fetch(HQ('personagens/manifest.json')).then(r => r.ok ? r.json() : {}).then(man => {
    const gl = new GLTFLoader();
    return Promise.all(Object.entries(man).map(([papel, info]) => gl.loadAsync(HQ(info.arquivo)).then(g => { modelos[papel] = g; }).catch(() => { })));
  }).catch(() => { });
  function personagem(papel, nome, cor, altura, calca) {
    const base = modelos[papel];
    if (!base) return boneco(nome, cor, altura, calca);
    const g = new THREE.Group(); g.name = 'NPC_' + nome;
    const m = SkeletonUtils.clone(base.scene);
    m.traverse(o => { if (o.isMesh) o.frustumCulled = false; });
    g.add(m);
    const mixer = new THREE.AnimationMixer(m), acoes = {};
    for (const clip of base.animations) acoes[clip.name.replace(/\.\d+$/, '')] = mixer.clipAction(clip);
    const parada = acoes.parada || Object.values(acoes)[0];
    if (parada) { parada.play(); parada.time = Math.random() * parada.getClip().duration; }
    // area de clique: cilindro do chao ao topo da cabeca (a altura acompanha a pose a cada quadro: em pe, agachado, escalando)
    const alt = altura;
    const hit = new THREE.Mesh(new THREE.CylinderGeometry(.42, .42, 1, 10), new THREE.MeshBasicMaterial({ visible: false }));
    hit.scale.y = alt; hit.position.y = alt / 2; hit.userData.npc = nome; g.add(hit);
    const ecv = document.createElement('canvas'); ecv.width = 256; ecv.height = 64; const eg = ecv.getContext('2d');
    eg.fillStyle = 'rgba(5,7,12,.7)'; eg.beginPath(); eg.roundRect(0, 0, 256, 64, 14); eg.fill();
    eg.fillStyle = '#efe9df'; eg.font = '600 32px Segoe UI, sans-serif'; eg.textAlign = 'center'; eg.fillText(nome, 128, 44);
    const et = new THREE.CanvasTexture(ecv); et.colorSpace = THREE.SRGBColorSpace;
    const rotulo = new THREE.Sprite(new THREE.SpriteMaterial({ map: et, depthTest: true, transparent: true, fog: false }));
    rotulo.scale.set(.5, .125, 1); rotulo.position.y = alt + .25; rotulo.visible = false; g.add(rotulo);   // nomes ocultos
    const mao = m.getObjectByName('Bip01_R_Hand') || m.getObjectByName('Bip01 R Hand');
    g.userData = { hit, rotulo, nome, mixer, acoes, atual: parada, modelo: m, bracoD: mao || g, real: true, rosto: montarRosto(m), olhar: montarOlhar(m) };
    return g;
  }
  /* rosto: boca acompanha o volume da fala e as palpebras piscam (ossos faciais do esqueleto adulto) */
  function montarRosto(m) {
    const jaw = m.getObjectByName('Bip01_MJaw');
    if (!jaw) return null;                                   // crianca (Bip02) tem eixos diferentes: fica sem
    const palp = [['Bip01_REyeBlinkTop', -1.25], ['Bip01_LEyeBlinkTop', -1.25], ['Bip01_REyeBlinkBottom', .35], ['Bip01_LEyeBlinkBottom', .35]]
      .map(([n, k]) => { const b = m.getObjectByName(n); return b && { b, base: b.position.clone(), k }; }).filter(Boolean);
    return { jaw, jawBase: jaw.quaternion.clone(), escrito: null, boca: 0, palp, piscaIni: 0, proxPisca: performance.now() + 1000 + Math.random() * 3000 };
  }
  const QZ = new THREE.Quaternion(), EIXO_Z = new THREE.Vector3(0, 0, 1);
  /* olhar: pescoco e cabeca acompanham o policial quando ele chega perto. A frente do rosto e medida na pose de
     repouso (modelo olhando para +Z) e guardada no espaco do osso da cabeca: funciona em qualquer esqueleto */
  function montarOlhar(m) {
    let cabeca, pescoco, olhoE, olhoD;
    m.traverse(o => { if (!o.isBone) return;
      if (/_Head$/.test(o.name)) cabeca = o; else if (/_Neck$/.test(o.name)) pescoco = o;
      else if (/_LEye$/.test(o.name)) olhoE = o; else if (/_REye$/.test(o.name)) olhoD = o; });
    if (!(cabeca && olhoE && olhoD)) return null;
    // base de cada osso: se a animacao nao mexe nele (trilha constante removida na exportacao), o giro nao pode acumular
    const clavs = pescoco ? pescoco.children.filter(b => /Clavicle$/.test(b.name)) : [];
    const ossos = [pescoco, cabeca, ...clavs].filter(Boolean).map(b => ({ b, base: b.quaternion.clone(), escrito: null }));
    m.updateMatrixWorld(true);
    const frenteLocal = new THREE.Vector3(0, 0, 1).applyQuaternion(cabeca.getWorldQuaternion(new THREE.Quaternion()).invert());
    return { cabeca, pescoco, olhoE, olhoD, ossos, clavs, frenteLocal, peso: 0 };
  }
  const OV1 = new THREE.Vector3(), OV2 = new THREE.Vector3(), OV3 = new THREE.Vector3(), OQ1 = new THREE.Quaternion(), OQ2 = new THREE.Quaternion(), OQ3 = new THREE.Quaternion(), OQ0 = new THREE.Quaternion();
  const AH = new THREE.Vector3();
  function ajustarAreaClique(n) {
    const u = n.userData, cab = u.olhar?.cabeca; if (!cab || !u.hit) return;
    cab.getWorldPosition(AH);
    const h = Math.max(.6, AH.y - n.position.y + .2);    // ate o topo da cabeca
    u.hit.scale.y = h; u.hit.position.y = h / 2;
  }
  function girarNoMundo(osso, q, fracao, maxAng) {       // aplica parte de uma rotacao do mundo ao osso, com limite
    OQ3.copy(OQ0).slerp(q, fracao);
    const ang = 2 * Math.acos(Math.min(1, Math.abs(OQ3.w)));
    if (ang > maxAng) { const parcial = OQ3.clone(); OQ3.copy(OQ0).slerp(parcial, maxAng / ang); }   // para no limite
    osso.parent.getWorldQuaternion(OQ1); osso.getWorldQuaternion(OQ2);
    osso.quaternion.copy(OQ1.invert().multiply(OQ3.multiply(OQ2)));
    osso.updateMatrixWorld(true);
  }
  function frenteCabeca(o) {
    o.olhoE.getWorldPosition(OV1); o.olhoD.getWorldPosition(OV2); OV1.add(OV2).multiplyScalar(.5);   // OV1 = ponto entre os olhos
    return OV3.copy(o.frenteLocal).applyQuaternion(o.cabeca.getWorldQuaternion(OQ2)).normalize();
  }
  function olhar(n, dt, posPolicial) {
    const o = n.userData.olhar; if (!o) return;
    const perto = n.visible && !n.userData.destino && n.position.distanceTo(OV1.copy(posPolicial).setY(n.position.y)) < (n.userData.assento ? 6.5 : 4.5);
    o.peso += ((perto ? 1 : 0) - o.peso) * Math.min(1, dt * 2.5);
    for (const x of o.ossos) {                            // parte da pose da animacao deste quadro (ou da base)
      if (x.escrito && x.b.quaternion.equals(x.escrito)) x.b.quaternion.copy(x.base); else x.base.copy(x.b.quaternion);
      x.escrito = null;
    }
    if (o.peso < .01) return;
    n.updateMatrixWorld(true);
    const ombros = o.clavs.map(b => b.getWorldQuaternion(new THREE.Quaternion()));     // orientacao dos ombros antes de girar o pescoco
    // sentado no carro, o agente fica de lado: pescoco e cabeca giram bem mais para encarar quem aborda
    const limites = n.userData.assento ? [[o.pescoco, .5, .85], [o.cabeca, 1, 1.15]] : [[o.pescoco, .4, .55], [o.cabeca, 1, .75]];
    for (const [osso, fr, max] of limites) {
      if (!osso) continue;
      const frente = frenteCabeca(o).clone(), alvo = OV2.copy(posPolicial).sub(OV1).normalize();
      girarNoMundo(osso, OQ0.clone().setFromUnitVectors(frente, alvo), fr * o.peso, max);
    }
    if (o.pescoco) o.clavs.forEach((b, i) => { o.pescoco.getWorldQuaternion(OQ1); b.quaternion.copy(OQ1.invert().multiply(ombros[i])); b.updateMatrixWorld(true); });   // ombros e bracos ficam onde estavam
    for (const x of o.ossos) x.escrito = x.b.quaternion.clone();
  }
  function animarRosto(n, dt, agora) {
    const r = n.userData.rosto; if (!r) return;
    let alvo = 0; const f = n.userData.fala;
    if (f) {
      if (agora > f.ate) n.userData.fala = null;
      else if (f.medidor) alvo = Math.pow(Math.min(1, Math.max(0, f.medidor() - .06) / .75), .8);   // silencio ~0,04; fala 0,3 a 0,8
      else if (f.sintetica) alvo = Math.max(0, .3 + .45 * Math.sin(agora * .019) * Math.sin(agora * .0063 + 1.7));   // ritmo de silabas
    }
    r.boca += (alvo - r.boca) * Math.min(1, dt * (alvo > r.boca ? 28 : 14));
    const q = r.jaw.quaternion;
    if (r.escrito && q.equals(r.escrito)) q.copy(r.jawBase);   // a animacao nao mexeu na mandibula neste quadro
    q.multiply(QZ.setFromAxisAngle(EIXO_Z, r.boca * .17)); r.escrito = q.clone();     // ate ~10 graus de abertura
    // piscar: ~150 ms fechando e abrindo, a cada 2,5 a 6,5 s
    if (agora > r.proxPisca) { r.piscaIni = agora; r.proxPisca = agora + 2500 + Math.random() * 4000; }
    const t = (agora - r.piscaIni) / 75, k = t < 1 ? t : t < 2 ? 2 - t : 0;
    for (const p of r.palp) { p.b.position.copy(p.base); p.b.position.x += p.k * k; }
  }
  const AGACHADO = new Set(['escondido', 'rendido', 'algemado_agachado']);
  function animar(npc, nome, segundos = 6, fade = .5) {
    const u = npc?.userData; if (!u?.real) return;
    if (u.algemado && !nome.startsWith('algemado'))       // algemado: maos sempre nas costas
      nome = nome === 'andando' || nome === 'correndo' ? 'algemado_andando'
        : AGACHADO.has(nome) || (AGACHADO.has(u.pose) && nome !== 'parada') ? 'algemado_agachado' : 'algemado';
    if (!u.acoes[nome]) return;
    u.pose = nome;
    const nova = u.acoes[nome];
    if (u.atual !== nova) { nova.reset().play(); u.atual?.crossFadeTo(nova, fade, false); u.atual = nova; }
    clearTimeout(u.volta);
    if (nome !== (u.base || 'parada')) u.volta = setTimeout(() => animar(npc, u.base || 'parada'), segundos * 1000);
  }
  function moverNPC(n, dt) {
    const u = n.userData;
    if (!u.destino && u.rota?.length) u.destino = u.rota.shift();
    if (!u.destino) return;
    V2.copy(u.destino).sub(n.position); V2.y = 0;
    const L = V2.length();
    if (L < .12) { u.destino = null; if (!u.rota?.length) { const cb = u.aoChegar; u.aoChegar = null; cb?.(); } return; }
    n.position.addScaledVector(V2.normalize(), Math.min(L, (u.vel || 1.4) * dt));
    const alvo = Math.atan2(V2.x, V2.z); let d = alvo - n.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d));
    n.rotation.y += d * Math.min(1, dt * 8);
    camera.getWorldDirection(V2);                         // V2 volta a ser a direcao do olhar (usada no quadro)
  }
  const ocv = document.createElement('canvas'); ocv.width = 640; ocv.height = 300;
  const otex = new THREE.CanvasTexture(ocv); otex.colorSpace = THREE.SRGBColorSpace;
  const objVR = new THREE.Mesh(new THREE.PlaneGeometry(.42, .42 * 300 / 640), new THREE.MeshBasicMaterial({ map: otex, transparent: true, depthTest: false, toneMapped: false, fog: false }));
  objVR.position.set(-.32, .2, -.9); objVR.renderOrder = 1002; objVR.visible = false; camera.add(objVR);
  const objHTML = document.createElement('div'); objHTML.id = 'objetivosHTML'; objHTML.hidden = true;
  Object.assign(objHTML.style, { position: 'fixed', right: '16px', top: '16px', maxWidth: 'min(340px, calc(100vw - 32px))', zIndex: 6,
    background: 'rgba(11,14,22,.88)', color: '#efe9df', border: '1px solid rgba(240,163,64,.5)', borderRadius: '6px', padding: '10px 14px',
    font: '13px/1.45 "Segoe UI", system-ui, sans-serif', pointerEvents: 'none' });
  document.body.appendChild(objHTML);
  let ultimoObj = '';
  function mostrarObjetivos() {
    const on = S.ativo && S.modo === 'treino', L = on ? objetivos() : [], chave = on + L.join('|') + renderer.xr.isPresenting;
    if (chave === ultimoObj) return; ultimoObj = chave;
    objHTML.hidden = !on || renderer.xr.isPresenting; objVR.visible = on && renderer.xr.isPresenting;
    if (!on) return;
    objHTML.innerHTML = '<b style="color:#f0a340;font:600 11px Consolas,monospace;letter-spacing:.08em">OBJETIVOS</b><br>' + L.map(t => '▸ ' + t).join('<br>');
    const g = ocv.getContext('2d'); g.clearRect(0, 0, 640, 300);
    g.fillStyle = 'rgba(11,14,22,.85)'; g.beginPath(); g.roundRect(0, 0, 640, 300, 16); g.fill();
    g.fillStyle = '#f0a340'; g.font = '600 22px Consolas, monospace'; g.fillText('OBJETIVOS', 22, 38);
    g.fillStyle = '#efe9df'; g.font = '400 25px Segoe UI, sans-serif';
    let y = 80; for (const t of L) { let l = '▸ ', first = true; for (const w of t.split(' ')) { const tt = l + w + ' '; if (g.measureText(tt).width > 600 && l.trim()) { g.fillText(l, 22, y); y += 30; l = '  '; first = false; } else l = tt; } g.fillText(l, 22, y); y += 38; if (y > 290) break; }
    otex.needsUpdate = true;
  }


  /* ================= cena: pontos, portas, material a apreender ================= */
  const PT = CFG.pontos || {};
  const B = (x, y) => new THREE.Vector3(x, .15, -y);          // coordenadas da planta (Blender: X, Y) -> cena web
  const olharPara = (dx, dy) => Math.atan2(dx, -dy);         // giro para a pessoa olhar na direcao (dx, dy) da planta
  const noSalao = p => p.x > -3.5 && p.x < 2.5 && p.z < -6.05 && p.z > -13;
  const noBar = p => Math.abs(p.x) < 6 && p.z < -.2 && p.z > -6;
  const suave = (seg, passo) => new Promise(fim => {          // interpola de 0 a 1 em 'seg' segundos (setTimeout: funciona com a aba oculta)
    const t0 = performance.now();
    const tic = () => { const k = Math.min(1, (performance.now() - t0) / (seg * 1000)); passo(k * k * (3 - 2 * k)); k < 1 ? setTimeout(tic, 16) : fim(); };
    tic();
  });
  const invisivel = () => new THREE.MeshBasicMaterial({ visible: false });

  // portas: a raiz fica na dobradica; enquanto fechada, uma caixa invisivel entra na colisao
  const portas = {};
  for (const [k, nome, aberta] of [['salao', 'I_Porta_Salao', 1.45], ['escritorio', 'I_Porta_Escritorio', -1.45], ['fundos', 'I_Porta_Fundos', 1.45]]) {
    const o = ctx.cena.getObjectByName(nome); if (!o) continue;
    o.updateWorldMatrix(true, false);
    const q = o.getWorldQuaternion(new THREE.Quaternion());
    const col = new THREE.Mesh(new THREE.BoxGeometry(.9, 2.1, .16), invisivel());
    o.getWorldPosition(col.position); col.position.addScaledVector(new THREE.Vector3(1, 0, 0).applyQuaternion(q), .44); col.position.y += 1.05;
    col.quaternion.copy(q); col.userData.porta = k; col.geometry.computeBoundsTree(); scene.add(col); col.updateMatrixWorld(true);
    portas[k] = { o, base: o.rotation.y, aberta, col, ang: 0 };
  }
  function moverPorta(k, frac = 1, seg = .8) {
    const p = portas[k]; if (!p) return Promise.resolve();
    const cols = ctx.colisao(), i = cols.indexOf(p.col), alvo = p.aberta * frac, a0 = p.ang;
    if (frac > .5) { if (i >= 0) cols.splice(i, 1); } else if (i < 0) cols.push(p.col);
    if (seg > .3 && p.frac !== frac) window.__som?.tocar('porta_abrindo', p.col.position);
    p.frac = frac;
    return suave(seg, e => { p.ang = a0 + (alvo - a0) * e; p.o.rotation.y = p.base + p.ang; });
  }

  // cofre do escritorio: a raiz da porta fica na dobradica; uma caixa invisivel recebe o clique enquanto ele esta fechado
  const cofre = (() => {
    const o = ctx.cena.getObjectByName('I_Cofre_Porta'), d = ctx.cena.getObjectByName('I_Dinheiro_Cofre'); if (!o || !d) return null;
    o.updateWorldMatrix(true, false); d.updateWorldMatrix(true, false);
    const h = new THREE.Mesh(new THREE.BoxGeometry(.66, .8, .64), invisivel());
    d.getWorldPosition(h.position); h.position.y = .15 + .4; h.userData.cofre = true; scene.add(h); h.updateMatrixWorld(true);
    // por dentro o modelo e uma casca sem piso, do mesmo cinza de fora (via-se o chao escuro do comodo e nao dava nocao de
    // fundo): um forro de aco mais escuro, visto so por dentro, com piso, fundo, laterais e teto
    let aco = null; o.traverse(m => { if (!aco && m.isMesh) aco = [].concat(m.material).find(x => /Aco_Cofre/.test(x.name)); });
    if (aco) {
      const mf = aco.clone(); mf.side = THREE.BackSide; mf.color.multiplyScalar(.5);
      const forro = new THREE.Mesh(new THREE.BoxGeometry(.48, .66, .5), mf); d.getWorldPosition(forro.position); forro.position.x -= .02; forro.position.y += .335; scene.add(forro); forro.updateMatrixWorld(true);
    }
    return { o, base: o.rotation.y, h, aberto: false, ang: 0 };
  })();
  function moverCofre(aberto, seg = 1.2) {
    if (!cofre) return Promise.resolve();
    const a0 = cofre.ang, alvo = aberto ? 1.9 : 0;
    if (seg > .3 && cofre.aberto !== aberto) window.__som?.tocar('porta_abrindo', cofre.h.position);
    cofre.aberto = aberto;
    return suave(seg, e => { cofre.ang = a0 + (alvo - a0) * e; cofre.o.rotation.y = cofre.base + cofre.ang; });
  }
  const hitCofre = () => (cofre && !cofre.aberto ? [cofre.h] : []);      // aberto, o clique vai para o dinheiro la dentro

  // estante falsa do deposito do bar: esconde a passagem para a sala reservada
  const estante = (() => {
    const o = ctx.cena.getObjectByName('I_Estante_Secreta'); if (!o) return null;
    o.updateWorldMatrix(true, false);
    const col = new THREE.Mesh(new THREE.BoxGeometry(.4, 2.15, 1.25), invisivel());
    o.getWorldPosition(col.position); col.position.y += 1.07; col.userData.estante = true; col.geometry.computeBoundsTree(); scene.add(col); col.updateMatrixWorld(true);
    return { o, z0: o.position.z, col, aberta: false };
  })();
  function moverEstante(aberta, seg = 1.4) {
    if (!estante) return Promise.resolve();
    const cols = ctx.colisao(), i = cols.indexOf(estante.col), a0 = estante.o.position.z, alvo = estante.z0 - (aberta ? 1.12 : 0);
    estante.aberta = aberta; estante.col.position.z = alvo; estante.col.updateMatrixWorld(true);
    if (i < 0) cols.push(estante.col);
    if (seg > .3 && !window.__som?.tocar('movel_arrastado', estante.col.position, false, { ini: .3, dur: 1.6 })) estouro(.5, 300, .35, .7);      // som de movel arrastado
    return suave(seg, e => { estante.o.position.z = a0 + (alvo - a0) * e; });
  }
  function emboscada() {                                      // o homem sentado no sofa da sala reservada reage assim que a estante abre (treino ou modo livre)
    const n = npcs.atirador; if (!n) return;
    setTimeout(() => {
      const u = n.userData; if ((A && A.fase === 'fim') || u.caido || u.ameaca || u.atordoado > performance.now() || !u.sentado) return;
      u.ameaca = true; u.atira = true; u.proxTiro = performance.now() + 600; u.semVirar = false; u.base = 'sentado_apontando'; animar(n, 'sentado_apontando', 1e6, .2);
      if (u.arma) u.arma.visible = true;
      if (S.ativo && A && !S.variacao.decisao.includes('_porte')) S.variacao.decisao += '_porte';      // passa a haver preso por arma de fogo
      sincAmeaca(); status();
      legenda('Alerta', 'Há um homem armado no sofá da sala e ele começou a atirar! Proteja-se na parede e reaja.', 6);
    }, 300);
  }
  function usarEstante() {
    if (!estante) return;
    if (S.ativo && A) {
      if (!A.salaSecreta) {
        // o deposito e a sala sao compartimentos fechados: mexer neles antes de uma entrada legitima e entrada irregular
        if (!A.entrada) { registrar('entrada_ilegal', 'sala reservada'); if (S.modo === 'treino') legenda('Instrutor', 'Você entrou em área fechada sem decidir a entrada de forma legítima (consentimento, mandado ou flagrante).', 7); }
        A.salaSecreta = true; registrar('localizar_sala_secreta'); moverEstante(true); S.variacao.sala = 'aberta'; emboscada();
        return legenda('Vistoria', 'As marcas no piso e a luz por baixo indicam uma passagem. A estante corre para o lado: há uma sala escondida.', 7);
      }
    }
    const abrir = !estante.aberta; moverEstante(abrir); if (abrir) emboscada();
  }

  const ITENS = { dinheiro_mesa: 'I_Dinheiro_Mesa', fichas: 'I_Fichas', caderno_apostas: 'I_Caderno_Apostas', notebook: 'I_Notebook', celular: 'I_Celular',
    caderno_contab: 'I_Caderno_Contabilidade', dinheiro_escondido: 'I_Dinheiro_Escondido', dvr: 'I_DVR_Cameras', dinheiro_sala: 'I_Dinheiro_Sala', dinheiro_cofre: 'I_Dinheiro_Cofre' };
  const itens = {}, hitsItem = [];
  for (const [k, nome] of Object.entries(ITENS)) {
    const o = ctx.cena.getObjectByName(nome); if (!o) continue;
    const h = new THREE.Mesh(new THREE.SphereGeometry(.17, 10, 8), invisivel());
    o.getWorldPosition(h.position); h.position.y += .04; h.userData.item = k; scene.add(h); h.updateMatrixWorld(true); itens[k] = { o, h }; hitsItem.push(h);
  }
  // maquinas: area de clique em cada uma e a fita de lacre (aparece quando forem relacionadas)
  const lacres = new THREE.Group(); lacres.visible = false; scene.add(lacres);
  {
    const cv = document.createElement('canvas'); cv.width = 512; cv.height = 64; const g = cv.getContext('2d');
    g.fillStyle = '#f2c81e'; g.fillRect(0, 0, 512, 64); g.fillStyle = '#111'; g.font = '700 40px Segoe UI, sans-serif'; g.textAlign = 'center';
    g.fillText('LACRADO · POLÍCIA', 256, 46);
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
    const mat = new THREE.MeshBasicMaterial({ map: tex, toneMapped: false });
    for (const [n, p] of Object.entries(PT)) {
      if (!/^Maquina_/.test(n)) continue;
      const h = new THREE.Mesh(new THREE.BoxGeometry(.62, 1.6, .62), invisivel());
      h.position.set(p.pos[0], p.pos[1] + .8, p.pos[2]); h.rotation.y = p.rz; h.userData.item = 'maquinas'; scene.add(h); h.updateMatrixWorld(true); hitsItem.push(h);
      const l = new THREE.Mesh(new THREE.PlaneGeometry(.58, .0725), mat);
      l.position.set(p.pos[0] + Math.sin(p.rz) * .292, p.pos[1] + .62, p.pos[2] + Math.cos(p.rz) * .292); l.rotation.y = p.rz; l.rotation.z = .12; lacres.add(l);
    }
  }
  const INFO_ITEM = {
    maquinas: 'Máquinas caça-níqueis: são o principal vestígio do jogo de azar (LCP art. 50). Relacionar, fotografar e lacrar; quem abre e examina é a perícia.',
    dinheiro_mesa: 'Dinheiro sobre a mesa de jogo: contar no local, na frente do responsável ou de testemunha, e lacrar em envelope numerado.',
    dinheiro_escondido: 'Caixa com maços de dinheiro guardada no escritório.',
    dinheiro_cofre: 'Maços de dinheiro guardados no cofre do escritório.',
    cofre: 'Cofre de aço do escritório, trancado com segredo.',
    dinheiro_sala: 'Bolsa com maços de dinheiro escondida atrás do bar da sala reservada.',
    estante: 'Estante do depósito do bar. Há marcas de arrasto no piso e uma fresta de luz colorida por baixo.',
    fichas: 'Fichas de aposta: indicam os valores em jogo.',
    caderno_apostas: 'Caderno com anotações de apostas e prêmios.',
    caderno_contab: 'Caderno de contabilidade: entradas, saídas e nomes.',
    notebook: 'Computador do escritório. O conteúdo só pode ser acessado com ordem judicial ou consentimento.',
    celular: 'Celular. Pode ser apreendido; o conteúdo só pode ser acessado com ordem judicial ou consentimento.',
    dvr: 'Gravador das câmeras de segurança do local: registra quem entrou, quem operava o caixa e a própria ação policial.'
  };

  /* ================= equipamento do policial: pistola e granada de efeito moral ================= */
  let AC = null;
  function estouro(dur, corte, vol, grave = 0) {              // som sintetico (enquanto nao houver gravacao em 06_Audio/brutos)
    try {
      AC = AC || new (window.AudioContext || window.webkitAudioContext)();
      const n = Math.floor(AC.sampleRate * dur), b = AC.createBuffer(1, n, AC.sampleRate), d = b.getChannelData(0);
      for (let i = 0; i < n; i++) { const t = i / n; d[i] = ((Math.random() * 2 - 1) * (1 - grave) + Math.sin(i / AC.sampleRate * 2 * Math.PI * 55) * grave) * Math.pow(1 - t, 3.2); }
      const s = AC.createBufferSource(); s.buffer = b;
      const f = AC.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = corte;
      const g = AC.createGain(); g.gain.value = S.mudo ? 0 : vol; s.connect(f).connect(g).connect(AC.destination); s.start();
    } catch (e) { }
  }
  function zumbido(seg) {
    try {
      AC = AC || new (window.AudioContext || window.webkitAudioContext)();
      const o = AC.createOscillator(), g = AC.createGain(); o.frequency.value = 3400;
      g.gain.setValueAtTime(.05, AC.currentTime); g.gain.exponentialRampToValueAtTime(.0005, AC.currentTime + seg);
      o.connect(g).connect(AC.destination); o.start(); o.stop(AC.currentTime + seg);
    } catch (e) { }
  }
  // som gravado; o sintetizado so entra quando NAO existe arquivo com esse nome (nunca no lugar de um que ainda esta carregando)
  const somOu = (n, sintetico) => window.__som?.tocar(n) || window.__somArquivos?.[n] || sintetico();
  const somTiro = () => somOu('tiro_pistola', () => estouro(.3, 3200, .9, .25));
  const somGranada = () => somOu('granada_efeito_moral', () => estouro(1.5, 1100, 1.0, .5));
  const somQuique = () => somOu('granada_quique', () => estouro(.06, 5000, .25));

  const gl = new GLTFLoader();
  const arma = new THREE.Group(); arma.visible = false;       // pistola na mao do policial
  // clarao do disparo: estrela de fogo na boca do cano (tres planos cruzados) e luz que ilumina o comodo por um instante
  const texFlash = (() => {
    const cv = document.createElement('canvas'); cv.width = cv.height = 128; const g = cv.getContext('2d');
    g.translate(64, 64);
    for (let k = 0; k < 7; k++) {                             // linguas de fogo
      g.rotate(Math.PI * 2 / 7 + (Math.random() - .5) * .3); const L = 34 + Math.random() * 28;
      const gr = g.createLinearGradient(0, 0, L, 0); gr.addColorStop(0, 'rgba(255,240,190,1)'); gr.addColorStop(.5, 'rgba(255,170,60,.8)'); gr.addColorStop(1, 'rgba(255,90,20,0)');
      g.fillStyle = gr; g.beginPath(); g.moveTo(0, -9); g.lineTo(L, 0); g.lineTo(0, 9); g.fill();
    }
    const gr = g.createRadialGradient(0, 0, 0, 0, 0, 30); gr.addColorStop(0, 'rgba(255,255,240,1)'); gr.addColorStop(.5, 'rgba(255,200,90,.7)'); gr.addColorStop(1, 'rgba(255,120,30,0)');
    g.fillStyle = gr; g.beginPath(); g.arc(0, 0, 30, 0, 7); g.fill();
    const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; return t;
  })();
  const matFlash = new THREE.MeshBasicMaterial({ map: texFlash, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false, fog: false, side: THREE.DoubleSide });
  function criarFlash(tam = .2) {
    const g = new THREE.Group(), geo = new THREE.PlaneGeometry(tam, tam);
    const a = new THREE.Mesh(geo, matFlash), b = new THREE.Mesh(geo, matFlash), c = new THREE.Mesh(geo, matFlash);
    b.rotation.y = Math.PI / 2; b.scale.x = 1.5; c.rotation.x = Math.PI / 2; c.scale.y = 1.5; g.add(a, b, c);
    const l = new THREE.PointLight(0xffc880, 0, 10, 2); g.add(l); g.userData.luz = l; g.visible = false; return g;
  }
  function acenderFlash(f) {
    f.rotation.z = Math.random() * 6.28; f.scale.setScalar(.75 + Math.random() * .6); f.visible = true; f.userData.luz.intensity = 9;
    setTimeout(() => { f.userData.luz.intensity = 3; }, 40); setTimeout(() => { f.visible = false; f.userData.luz.intensity = 0; }, 85);
    f.getWorldPosition(GT);
    const m = new THREE.Mesh(geoFum, new THREE.MeshBasicMaterial({ color: 0xbfbfbf, transparent: true, opacity: .22, depthWrite: false }));
    m.position.copy(GT); m.scale.setScalar(.04); scene.add(m); fumacas.push({ f: m, t: 0, v: new THREE.Vector3(0, .25, 0), s0: .04, cres: .22, vida: 1.1, op: .22 });
  }
  const clarao = criarFlash(); clarao.position.set(0, 0, -.2); arma.add(clarao);      // a boca do cano fica em (0, 0, -0,15)
  const luzTiro = clarao.userData.luz;
  // capsulas ejetadas e gotas de sangue: pequenas pecas com gravidade e vida curta
  const soltos = [], geoCaps = new THREE.CylinderGeometry(.0045, .0045, .019, 6), matCaps = new THREE.MeshBasicMaterial({ color: 0xb8923a });
  const geoGota = new THREE.SphereGeometry(.011, 5, 4), matGota = new THREE.MeshBasicMaterial({ color: 0x6a0505 });
  function capsula(arm) {
    const m = new THREE.Mesh(geoCaps, matCaps); arm.getWorldPosition(m.position); m.position.y += .015;
    const lado = new THREE.Vector3(1, 0, 0).applyQuaternion(arm.getWorldQuaternion(new THREE.Quaternion()));
    scene.add(m); soltos.push({ m, v: lado.multiplyScalar(1.6 + Math.random()).add(new THREE.Vector3(0, 1.8, 0)), t: 0, vida: 1.1, giro: 20 });
  }
  // sangue: respingo no ponto atingido, mancha na superficie atras e poca sob quem caiu
  const texSangue = (() => {
    const cv = document.createElement('canvas'); cv.width = cv.height = 128; const g = cv.getContext('2d');
    for (let k = 0; k < 26; k++) {
      const a = Math.random() * 6.28, d = Math.pow(Math.random(), 1.6) * 46, r = 4 + Math.random() * (k < 6 ? 22 : 8);
      g.fillStyle = `rgba(${95 + Math.random() * 40 | 0},4,4,${.75 + Math.random() * .25})`; g.beginPath(); g.arc(64 + Math.cos(a) * d, 64 + Math.sin(a) * d, r, 0, 7); g.fill();
    }
    const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; return t;
  })();
  const manchas = [], geoMancha = new THREE.PlaneGeometry(1, 1);
  function mancha(ponto, normal, raio) {
    const m = new THREE.Mesh(geoMancha, new THREE.MeshBasicMaterial({ map: texSangue, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -3, toneMapped: false, color: 0x9a9a9a }));
    m.position.copy(ponto).addScaledVector(normal, .007); m.lookAt(ponto.clone().add(normal)); m.rotateZ(Math.random() * 6.28); m.scale.setScalar(raio * 2);
    scene.add(m); manchas.push(m); if (manchas.length > 36) { const v = manchas.shift(); scene.remove(v); v.material.dispose(); }
    return m;
  }
  function limparSangue() { for (const m of manchas) { scene.remove(m); m.material.dispose(); } manchas.length = 0; }
  function sangue(p, dir) {
    for (let k = 0; k < 16; k++) {
      const m = new THREE.Mesh(geoGota, matGota); m.position.copy(p); m.scale.setScalar(.5 + Math.random());
      const v = dir.clone().multiplyScalar(.8 + Math.random() * 2.6).add(new THREE.Vector3((Math.random() - .5) * 1.6, Math.random() * 1.6, (Math.random() - .5) * 1.6));
      scene.add(m); soltos.push({ m, v, t: 0, vida: .55 + Math.random() * .3, giro: 0 });
    }
    rayG.set(p, GV.copy(dir).normalize()); rayG.far = 3.5;                 // mancha na parede ou no movel atras
    const h = rayG.intersectObjects(ctx.colisao(), false)[0];
    if (h?.face) mancha(h.point, GN.copy(h.face.normal).transformDirection(h.object.matrixWorld).clone(), .16 + Math.random() * .2);
  }
  function pocaSangue(n) {
    setTimeout(() => {
      const m = mancha(new THREE.Vector3(n.position.x + Math.sin(n.rotation.y) * 1.0, .152, n.position.z + Math.cos(n.rotation.y) * 1.0), new THREE.Vector3(0, 1, 0), .06);
      suave(6, e => { m.scale.setScalar(.12 + .95 * e); });
    }, 900);
  }
  let armaModelo = null, granadaModelo = null;
  const prep = raiz => { raiz.traverse(o => { if (o.isMesh) o.material = Array.isArray(o.material) ? o.material.map(m => ctx.iluminar(m.clone())) : ctx.iluminar(o.material.clone()); }); return raiz; };
  gl.loadAsync(HQ('modelos/arma.glb')).then(g => { armaModelo = prep(g.scene); arma.add(armaModelo.clone()); }).catch(() => { });
  gl.loadAsync(HQ('modelos/granada.glb')).then(g => { granadaModelo = prep(g.scene); }).catch(() => { });
  const controle = mao => (ctx.controles || []).find(c => c.userData.mao === mao);
  function sacar(on) {
    S.armaNaMao = on;
    const pai = renderer.xr.isPresenting ? (controle('right') || ctx.controles?.[0] || camera) : camera;
    pai.add(arma);
    if (pai === camera) { arma.position.set(.17, -.13, -.38); arma.rotation.set(0, 0, 0); } else { arma.position.set(0, 0, -.02); arma.rotation.set(0, 0, 0); }      // no Quest o cano coincide com o raio do controle
    arma.visible = on; mostrarControle('right', !on); status();
  }
  // no Quest, o modelo do controle some enquanto a mao segura a arma ou a granada
  function mostrarControle(mao, visivel) {
    const i = (ctx.controles || []).findIndex(c => c.userData.mao === mao);
    for (const [k, g] of (ctx.grips || []).entries()) if (g.userData.mao === mao || (g.userData.mao === undefined && k === i)) g.visible = visivel;
    if (i >= 0 && mao === 'left' && ctx.controles[i].userData.linha) ctx.controles[i].userData.linha.visible = visivel;
    S.controles = { ...(S.controles || {}), [mao]: visivel };
  }
  // granada na mao esquerda: X pega; segurar o gatilho esquerdo puxa o pino; soltar no fim do movimento arremessa
  const granadaMao = new THREE.Group(); granadaMao.visible = false; let granadaMaoPronta = false;
  const amostras = [], AM = new THREE.Vector3();
  function pegarGranada(on) {
    if (on && S.ativo && S.granadas <= 0) return legenda('Equipamento', 'Não há mais granadas.', 2.5);
    if (on && !granadaModelo) return;
    if (!granadaMaoPronta && granadaModelo) { granadaMao.add(granadaModelo.clone()); granadaMaoPronta = true; }
    const pai = renderer.xr.isPresenting ? (controle('left') || camera) : camera;
    pai.add(granadaMao); granadaMao.position.set(pai === camera ? -.2 : 0, pai === camera ? -.2 : -.01, pai === camera ? -.45 : -.04);
    S.granadaNaMao = on; S.granadaArmada = false; granadaMao.visible = on; amostras.length = 0; mostrarControle('left', !on); status();
    if (on) dica('Granada na mão esquerda. Segure o gatilho esquerdo, faça o movimento e solte para arremessar.', 6);
  }
  function soltar(c) {                                        // gatilho solto
    if (!S.granadaNaMao || !S.granadaArmada || c?.userData.mao !== 'left') return;
    const agora = performance.now(), rec = amostras.filter(a => agora - a.t < 130);
    const v = new THREE.Vector3();
    if (rec.length >= 2) { const a = rec[0], b = rec[rec.length - 1]; v.copy(b.p).sub(a.p).multiplyScalar(1000 / Math.max(16, b.t - a.t)); }
    v.multiplyScalar(1.35); if (v.length() > 15) v.setLength(15);            // um pouco de ajuda: sem o peso real, o braco freia antes
    granadaMao.getWorldPosition(AM);
    pegarGranada(false); lancarGranada(AM.clone(), v.clone().normalize(), v);
  }
  // marcas de tiro nas paredes
  const marcas = [], geoMarca = new THREE.CircleGeometry(.014, 10), matMarca = new THREE.MeshBasicMaterial({ color: 0x050505 });
  function marcar(h) {
    const m = marcas.length >= 40 ? marcas.shift() : new THREE.Mesh(geoMarca, matMarca);
    const n = h.face.normal.clone().transformDirection(h.object.matrixWorld);
    m.position.copy(h.point).addScaledVector(n, .004); m.lookAt(h.point.clone().add(n)); scene.add(m); marcas.push(m);
  }
  let ultimoTiro = 0;
  const CARREGADOR = 15, MIRA = new THREE.Vector3(), BOCA = new THREE.Vector3();
  function recarregar() {
    if (S.recarregando || !S.armaNaMao || (S.municao ?? CARREGADOR) >= CARREGADOR) return;
    S.recarregando = true; status();
    const som = window.__som, seg = Math.min(4, (som?.tem('recarregar_pistola') && som.duracao('recarregar_pistola')) || 1.6);
    if (!som?.tocar('recarregar_pistola')) estouro(.08, 2500, .3);
    const rx = arma.rotation.x, rz = arma.rotation.z;         // a arma inclina enquanto troca o carregador
    suave(Math.min(.35, seg / 3), e => { arma.rotation.x = rx + .5 * e; arma.rotation.z = rz + .35 * e; });
    setTimeout(() => suave(.3, e => { arma.rotation.x = rx + .5 * (1 - e); arma.rotation.z = rz + .35 * (1 - e); }), Math.max(300, seg * 1000 - 320));
    setTimeout(() => { S.municao = CARREGADOR; S.recarregando = false; status(); }, seg * 1000);
  }
  function disparar(ray) {
    const agora = performance.now(); if (agora - ultimoTiro < 280 || S.recarregando) return true; ultimoTiro = agora;
    if ((S.municao ?? CARREGADOR) <= 0) { estouro(.03, 5000, .25); recarregar(); return true; }      // clique seco e recarga
    S.municao = (S.municao ?? CARREGADOR) - 1;
    // o tiro sai da boca do cano. No computador a arma gira para o ponto clicado; no Quest vale para onde o cano aponta
    if (arma.parent === camera) {
      const h0 = ray.intersectObjects(ctx.colisao(), false)[0];
      MIRA.copy(h0 ? h0.point : ray.ray.origin.clone().addScaledVector(ray.ray.direction, 30));
      arma.lookAt(MIRA); arma.rotateY(Math.PI); arma.updateMatrixWorld(true);
      clarao.getWorldPosition(BOCA); ray.set(BOCA, MIRA.clone().sub(BOCA).normalize());
    } else {
      arma.updateMatrixWorld(true); clarao.getWorldPosition(BOCA);
      ray.set(BOCA, MIRA.set(0, 0, -1).applyQuaternion(arma.getWorldQuaternion(new THREE.Quaternion())).normalize());
    }
    somTiro(); acenderFlash(clarao); capsula(arma); status(); const rx = arma.rotation.x; arma.rotation.x = rx + .22;
    setTimeout(() => { arma.rotation.x = rx; }, 130);
    const pessoas = Object.values(npcs).filter(n => n.visible && !n.userData.caido);
    const hn = ray.intersectObjects(pessoas.map(n => n.userData.hit), false)[0];
    const hp = ray.intersectObjects(ctx.colisao(), false)[0];
    // quem esta sentado fica dentro da caixa de colisao do sofa: o tiro vale se a pessoa estiver logo atras da borda do movel
    const alvoN = hn && pessoas.find(p => p.userData.hit === hn.object), folga = alvoN?.userData.sentado ? .9 : 0;
    if (hn && (!hp || hn.distance < hp.distance + folga)) {
      const n = alvoN, k = n.userData.chave;
      if (S.ativo && A) {
        if (n.userData.ameaca) { registrar(k === 'atirador' ? 'resposta_sala' : 'resposta_proporcional', 'disparo'); if (ameacando().length <= 1) legenda('Instrutor', 'Agressão armada atual: o disparo foi resposta legítima. Agora, socorro imediato e comunicação.', 6); }
        else registrar('disparo_injustificado', n.userData.nome);
        A.ferido = n; S.variacao.ferido = 'sim';
      }
      sangue(hn.point, ray.ray.direction); cair(n); sincAmeaca();
    } else {
      if (hp?.face) marcar(hp);
      if (S.ativo && A) registrar('disparo_sem_alvo');
    }
    return true;
  }
  function cair(n) {
    const u = n.userData; u.caido = true; u.rota = []; u.destino = null; u.semVirar = true; u.aoChegar = null;
    const lado = u.sentado ? 1 : -1; if (u.sentado) { u.sentado = false; n.position.y = .15; }      // sentado: tomba para a frente, no chao
    u.ameaca = false; u.atira = false;
    if (u.arma?.visible) { u.arma.visible = false; armaChao(n.position, u.chave); }
    pocaSangue(n);
    const y0 = n.position.y, r0 = n.rotation.x;
    suave(.7, e => { n.rotation.x = r0 + (lado * Math.PI / 2 - r0) * e; n.position.y = y0 + .12 * e; });
  }
  // granada de efeito moral: arremesso em arco, quique no chao e nas paredes, estouro com clarao depois de 2,2 s
  const granadas = [], rayG = new THREE.Raycaster(); rayG.firstHitOnly = true;
  const GV = new THREE.Vector3(), GN = new THREE.Vector3(), GT = new THREE.Vector3();
  function lancarGranada(origem, dir, vel = null) {          // vel = velocidade real da mao (Quest); sem ela, arremesso padrao
    if (!granadaModelo) return;
    if (S.ativo && S.granadas <= 0) return legenda('Equipamento', 'Não há mais granadas.', 2.5);
    const g = granadaModelo.clone(); g.position.copy(origem); if (!vel) g.position.addScaledVector(dir, .25); scene.add(g);
    granadas.push({ g, v: vel ? vel.clone() : dir.clone().multiplyScalar(8).add(new THREE.Vector3(0, 2.4, 0)), t: 0, parada: false, giro: 9 + Math.random() * 6 });
    if (S.ativo) { S.granadas--; status(); }
  }
  function fisicaGranadas(dt) {
    for (let i = granadas.length - 1; i >= 0; i--) {
      const o = granadas[i]; o.t += dt;
      if (!o.parada) {
        o.v.y -= 9.8 * dt;
        let resto = dt, n = 0;
        while (resto > 1e-4 && n++ < 3) {
          const vel = o.v.length(); if (vel < .02) break;
          const passo = vel * resto; rayG.set(o.g.position, GV.copy(o.v).normalize()); rayG.far = passo + .06;
          const h = rayG.intersectObjects(ctx.colisao(), false)[0];
          if (!h || !h.face) { o.g.position.addScaledVector(o.v, resto); break; }
          const livre = Math.max(0, h.distance - .06); o.g.position.addScaledVector(GV, livre);
          GN.copy(h.face.normal).transformDirection(h.object.matrixWorld); if (GN.dot(o.v) > 0) GN.negate();
          const vn = o.v.dot(GN); GT.copy(o.v).addScaledVector(GN, -vn);          // componente tangente
          if (-vn > 1.3) somQuique();
          o.v.copy(GT.multiplyScalar(.7)).addScaledVector(GN, -vn * .42);        // perde energia a cada quique
          if (GN.y > .7 && o.v.length() < .7) { o.parada = true; o.v.set(0, 0, 0); break; }
          resto *= 1 - livre / Math.max(passo, 1e-5);
        }
        const giro = Math.min(1, o.v.length() / 3) * o.giro * dt; o.g.rotation.x += giro; o.g.rotation.z += giro * .6;
        if (o.g.position.y < -3) { scene.remove(o.g); granadas.splice(i, 1); continue; }
      }
      if (o.t > 2.2) { detonar(o.g.position.clone()); scene.remove(o.g); granadas.splice(i, 1); }
    }
  }
  const veu = new THREE.Mesh(new THREE.PlaneGeometry(4, 4), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthTest: false, toneMapped: false, fog: false }));
  veu.position.z = -.3; veu.renderOrder = 1005; veu.visible = false; camera.add(veu);
  const luzGranada = new THREE.PointLight(0xffffff, 0, 22, 1.6); scene.add(luzGranada);
  const fumacas = [], geoFum = new THREE.SphereGeometry(.5, 12, 8);
  function visto(de, ate) {                                   // ha linha de visada entre dois pontos?
    GV.copy(ate).sub(de); const d = GV.length(); rayG.set(de, GV.normalize()); rayG.far = d - .15;
    return !rayG.intersectObjects(ctx.colisao(), false)[0];
  }
  function detonar(pos) {
    somGranada(); pos.y += .25;
    luzGranada.position.copy(pos); luzGranada.intensity = 900; suave(.5, e => { luzGranada.intensity = 900 * (1 - e); });
    for (let k = 0; k < 6; k++) {
      const f = new THREE.Mesh(geoFum, new THREE.MeshBasicMaterial({ color: 0xcfcfcf, transparent: true, opacity: .35, depthWrite: false }));
      f.position.copy(pos).add(new THREE.Vector3((Math.random() - .5) * .8, Math.random() * .5, (Math.random() - .5) * .8)); f.scale.setScalar(.3);
      scene.add(f); fumacas.push({ f, t: 0, v: new THREE.Vector3((Math.random() - .5) * .3, .25 + Math.random() * .2, (Math.random() - .5) * .3) });
    }
    // efeito no policial: clarao e zumbido, mais fortes de perto, de frente e com visada direta
    camera.getWorldPosition(V); const d = V.distanceTo(pos);
    if (d < 12 && visto(pos, V)) {
      camera.getWorldDirection(V2); const frente = Math.max(.35, V2.dot(GT.copy(pos).sub(V).normalize()) * .5 + .5);
      const k = Math.min(1, (1 - d / 12) * 1.5) * frente, seg = 1.5 + 4 * k;
      veu.visible = true; veu.material.opacity = k; suave(seg, e => { veu.material.opacity = k * (1 - e) * (1 - e); if (e >= 1) veu.visible = false; });
      zumbido(seg + 1);
    }
    // efeito nas pessoas
    let alguem = false; const ameaca = !!A?.ameaca;
    for (const n of Object.values(npcs)) {
      const u = n.userData; if (!n.visible || u.caido || /^(parceiro|apoio)$/.test(u.chave)) continue;
      GT.copy(n.position).setY(n.position.y + 1.4);
      const dg = GT.distanceTo(pos);                        // de perto o estrondo atinge mesmo sem visada (granada sob uma mesa)
      if (dg > 7 || (dg > 3.5 && !visto(GN.copy(pos).setY(pos.y + .8), GT))) continue;
      alguem = true; u.rota = []; u.destino = null; u.aoChegar = null; u.atordoado = performance.now() + 7000;
      animar(n, u.acoes?.nervoso ? 'nervoso' : 'parada', 7, .2);
      if (u.ameaca) { if (u.chave === 'atirador') registrar('resposta_sala', 'granada'); renderNPC(n, true); }
      if (u.fugindo) { u.fugindo = false; u.reunido = false; }
    }
    sincAmeaca();
    if (S.ativo && A) {
      if (ameaca && !A.ameaca) { registrar('resposta_proporcional', 'granada'); legenda('Instrutor', 'O agressor foi atordoado e largou a arma, sem disparo. Algeme e recolha a arma.', 6); }
      else if (alguem) registrar('granada_desproporcional');
    }
  }
  function efeitos(dt) {
    fisicaGranadas(dt);
    for (let i = fumacas.length - 1; i >= 0; i--) {
      const o = fumacas[i], vida = o.vida ?? 5; o.t += dt; o.f.position.addScaledVector(o.v, dt); o.f.scale.setScalar((o.s0 ?? .3) + o.t * (o.cres ?? .55)); o.f.material.opacity = (o.op ?? .35) * Math.max(0, 1 - o.t / vida);
      if (o.t > vida) { scene.remove(o.f); o.f.material.dispose(); fumacas.splice(i, 1); }
    }
    for (let i = soltos.length - 1; i >= 0; i--) {
      const o = soltos[i]; o.t += dt; o.v.y -= 9.8 * dt; o.m.position.addScaledVector(o.v, dt); if (o.giro) o.m.rotation.x += o.giro * dt;
      if (o.m.position.y < .16) { o.m.position.y = .16; o.v.set(0, 0, 0); }
      if (o.t > o.vida) { scene.remove(o.m); soltos.splice(i, 1); }
    }
  }
  // armas dos agressores (o mesmo modelo): na mao quando apontam; no chao depois que largam
  const armaNPC = new THREE.Group(), armaNPC2 = new THREE.Group(), armaNPC3 = new THREE.Group(), armaSolta = new THREE.Group(), armaSolta2 = new THREE.Group(), armaSolta3 = new THREE.Group();
  const ARMAS_NPC = [armaNPC, armaNPC2, armaNPC3, armaSolta, armaSolta2, armaSolta3];
  for (const g of ARMAS_NPC) { g.visible = false; scene.add(g); }
  for (const g of [armaNPC, armaNPC2, armaNPC3]) { const f = criarFlash(.24); f.position.set(0, 0, -.2); g.add(f); g.userData.flash = f; }
  gl.loadAsync(HQ('modelos/arma.glb')).then(g => { for (const a of ARMAS_NPC) a.add(prep(g.scene.clone())); }).catch(() => { });
  const hitArma = new THREE.Mesh(new THREE.SphereGeometry(.2, 8, 6), invisivel()); hitArma.userData.item = 'arma'; armaSolta.add(hitArma);
  function armaChao(p, chave) {
    const g = chave === 'seguranca_2' ? armaSolta2 : chave === 'atirador' ? armaSolta3 : armaSolta;
    g.position.set(p.x + .35, .17, p.z + .2); g.rotation.set(0, 1, Math.PI / 2); g.visible = true; g.updateMatrixWorld(true);
  }
  function seguirArmaNPC() {
    for (const n of Object.values(npcs)) {
      const g = n.userData.arma; if (!g?.visible) continue;
      const mao = n.userData.modelo?.getObjectByName('Bip01_R_Hand'); if (!mao) continue;
      mao.getWorldPosition(g.position); camera.getWorldPosition(GT);
      g.lookAt(GT); g.rotateY(Math.PI); g.translateZ(-.05); g.translateY(.075);      // a mao segura a empunhadura, abaixo do cano
    }
  }
  const ameacando = () => Object.values(npcs).filter(n => n.userData.ameaca && !n.userData.caido);
  function sincAmeaca() { if (A) A.ameaca = ameacando().length > 0; }
  function veuVermelho(k = .55, seg = 1.6) {
    veu.material.color.set(0xff2020); veu.visible = true; veu.material.opacity = k;
    suave(seg, e => { veu.material.opacity = k * (1 - e); if (e >= 1) { veu.visible = false; veu.material.color.set(0xffffff); } });
  }
  function policialAtingido() {
    S.vida = (S.vida ?? 3) - 1; veuVermelho(); registrar('atingido');
    if (S.vida <= 0) {
      legenda('Instrutor', S.ativo ? 'Você foi gravemente ferido. O parceiro e o apoio assumem. Ocorrência encerrada.' : 'Você foi gravemente ferido. No modo livre nada é registrado.', 7);
      if (!S.ativo) S.vida = 3;
      for (const n of ameacando()) renderNPC(n, true);
      setTimeout(finalizar, 4500);
    } else legenda('Alerta', `Você foi atingido (${S.vida} de 3). Proteja-se atrás da parede e reaja.`, 4);
  }
  function tiroInimigo(n) {
    const g = n.userData.arma; if (!g) return;
    somTiro(); if (g.userData.flash) acenderFlash(g.userData.flash); capsula(g);
    const de = g.position.clone(); camera.getWorldPosition(GT); const alvo = GT.clone();
    if (visto(de, alvo) && Math.random() < .3) return policialAtingido();
    GV.copy(alvo).sub(de).normalize(); GV.x += (Math.random() - .5) * .3; GV.y += (Math.random() - .5) * .25; GV.z += (Math.random() - .5) * .3;
    rayG.set(de, GV.normalize()); rayG.far = 30; const h = rayG.intersectObjects(ctx.colisao(), false)[0]; if (h?.face) marcar(h);
  }
  function confronto() {                                      // agressores que atiram: um disparo a cada 1,5 a 2,8 s
    if (A && A.fase === 'fim') return; const agora = performance.now();
    for (const n of ameacando()) {
      const u = n.userData; if (!u.atira || u.destino || u.rota?.length || u.atordoado > agora) continue;
      if (agora > u.proxTiro) { u.proxTiro = agora + 1500 + Math.random() * 1300; tiroInimigo(n); }
    }
  }

  /* ================= variacoes ================= */
  function derivar(v) {
    v.entra = (v.indicios === 'visiveis' || v.consentimento === 'franqueia') ? 'sim' : 'nao';
    if (v.entra === 'nao') { v.seguranca = 'desarmado'; v.fuga = 'colaboram'; v.suborno = 'nao'; }
    if (v.responsavel === 'ausente') v.suborno = 'nao';
    v.arma = v.seguranca !== 'desarmado' ? 'sim' : 'nao';
    v.ferido = 'nao';
    v.decisao = 'tco' + (v.suborno === 'sim' ? '_corrupcao' : '') + (v.arma === 'sim' ? '_porte' : '');
    return v;
  }
  function sortear() {
    const forc = Object.fromEntries((new URLSearchParams(location.search).get('v') || '').split(',').filter(Boolean).map(p => p.split(':')));
    const v = {};
    for (const [k, ops] of Object.entries(CEN.variacoes)) v[k] = forc[k] && ops.includes(forc[k]) ? forc[k] : ops[Math.floor(Math.random() * ops.length)];
    return derivar(v);
  }

  /* ================= personagens ================= */
  // chave, modelo, nome, posicao na planta (x, y), para onde olha (dx, dy), voz, altura
  const ELENCO = [
    ['atendente', 'atendente', 'Funcionária', [4.6, 3.0], [-1, 0], 'f', 1.66],
    ['seguranca', 'seguranca', 'Segurança', [-2.7, 7.25], [-1, 0], 'm', 1.8],
    ['responsavel', 'responsavel', 'Responsável', [1.25, 10.9], [-1, 0], 'm', 1.78],
    ['apostador_1', 'apostador_a', 'Apostador', [-2.1, 11.74], [0, 1], 'm', 1.78],      // sentado, jogando na segunda maquina
    ['apostador_2', 'apostador_b', 'Apostador', [-1.75, 9.45], [-1, .3], 'm', 1.78],
    ['apostador_3', 'apostador_c', 'Apostadora', [-.25, 7.25], [1, 1], 'f', 1.68],      // sentada na mesa de carteado
    ['seguranca_2', 'seguranca_2', 'Homem armado', [-4.9, 10.6], [0, -1], 'm', 1.8],
    ['atirador', 'atirador', 'Homem no sofá', [9.6, 6.72], [0, 1], 'm', 1.8],      // sentado no sofa da parede sul da sala reservada
    ['parceiro', 'pm_parceiro', 'Policial parceiro', [4.2, -1.0], [-.5, .3], 'm', 1.8],
    ['apoio', 'pm_apoio', 'Policial de apoio', [-7.0, 12.4], [0, 1], 'm', 1.8],
  ];
  const ALTURA_SENTADO = alt => .15 + .56 - .925 * (alt / 1.78);      // abaixa o modelo ate o quadril ficar na altura do assento do sofa
  const DESTINO_CONTENCAO = { apostador_1: [[-1.5, 11.0], [-1.45, 6.7]], apostador_2: [[-1.9, 8.2], [-2.3, 6.75]], apostador_3: [[1.3, 6.7]], seguranca: [[-.5, 6.7]], responsavel: [[1.9, 9.2], [1.95, 7.6]] };
  const FUGA = [[1.85, 12.3], [1.85, 13.7], [-3.6, 15.1], [-7.0, 15.1], [-7.0, 1.0], [-7.0, -1.2], [-17.0, -1.2]];
  function limparNPCs() { Object.values(npcs).forEach(n => scene.remove(n)); for (const k in npcs) delete npcs[k]; }
  function criarNPCs(v) {
    limparNPCs(); livreSaiu = false;
    for (const [chave, papel, nome, [x, y], [dx, dy], voz, alt] of ELENCO) {
      if (chave === 'responsavel' && v.responsavel === 'ausente') continue;
      if (chave === 'seguranca_2' && v.seguranca !== 'confronto') continue;
      const n = personagem(papel, nome, chave.startsWith('p') || chave === 'apoio' ? 0x1b2a4a : 0x3d4045, alt);
      n.userData.modelo?.traverse(o => { if (o.isMesh) o.material = Array.isArray(o.material) ? o.material.map(m => ctx.iluminar(m.clone())) : ctx.iluminar(o.material.clone()); });
      Object.assign(n.userData, { chave, voz, fig: true, giroBase: olharPara(dx, dy), altura: alt });
      n.position.copy(B(x, y)); n.rotation.y = n.userData.giroBase; scene.add(n); npcs[chave] = n;
    }
    if (npcs.apoio) npcs.apoio.visible = false;
    for (const g of ARMAS_NPC) g.visible = false;
    if (npcs.atirador) { const a = npcs.atirador, u = a.userData; u.arma = armaNPC3; u.sentado = true; u.semVirar = true; u.fig = false; u.base = 'sentado_parado'; animar(a, 'sentado_parado', 1e6, 0); a.position.y = ALTURA_SENTADO(u.altura); }
    for (const k of ['apostador_1', 'apostador_3']) { const j = npcs[k], u = j?.userData; if (!j) continue; u.sentado = true; u.jogando = true; u.semVirar = true; u.fig = false; u.base = 'sentado_jogando'; animar(j, 'sentado_jogando', 1e6, 0); j.position.y = ALTURA_SENTADO(u.altura) + .05; }
    if (npcs.seguranca) npcs.seguranca.userData.arma = armaNPC;
    if (npcs.seguranca_2) npcs.seguranca_2.userData.arma = armaNPC2;
  }
  // o apostador que joga sentado levanta (fica em pe atras da cadeira) e tenta sair pela porta dos fundos, andando.
  // So para quando o policial aponta a arma para ele (ver miraNoApostador, no quadro).
  const SAIDA_JOGADOR = [[-.9, 11.0], [-.9, 9.25], [1.6, 9.25], [1.7, 11.6]];      // contorna as cadeiras e a mesa de roleta
  let livreSaiu = false;
  const EM_PE = { apostador_1: [-2.1, 11.15], apostador_3: [-.7, 6.8] };      // onde cada um fica ao levantar (atras da cadeira)
  function levantar(n) { const u = n.userData; if (!u.sentado) return; u.sentado = false; u.jogando = false; u.semVirar = false; u.fig = true; u.base = 'parada'; n.position.copy(B(...(EM_PE[u.chave] || [-2.1, 11.15]))); animar(n, 'parada', 1e6, .2); }
  // a mulher da mesa de cartas puxa as fichas para o colo quando a policia se anuncia; devolve quando o policial manda
  function esconderFichas() {
    const n = npcs.apostador_3, u = n?.userData; if (!A || !n || !u.sentado || u.caido || !itens.fichas || A.apreendidos?.has('fichas')) return;
    itens.fichas.o.visible = false; A.fichasEscondidas = true; u.escondeu = true;
    setTimeout(() => { if (A && A.fichasEscondidas && S.modo === 'treino') legenda('Instrutor', 'Repare na mesa de cartas: as fichas sumiram. Alguém guardou.', 6); }, 9000);
  }
  function tentarSair() {
    const n = npcs.apostador_1, u = n?.userData; if (!n || u.saindo || u.parouArma || u.caido || u.fugiu || u.algemado || u.atordoado > performance.now()) return;
    levantar(n); u.saindo = true; u.fugindo = true; u.tMira = 0; moverPorta('fundos', 1, .4);
    if (A && A.apoio) rota(n, [...SAIDA_JOGADOR, ...FUGA.slice(0, 3)], 1.5, 'andando', () => {                 // a equipe de apoio contem no quintal e traz de volta
      u.saindo = false; u.fugindo = false; registrar('fuga_contida');
      setTimeout(() => rota(n, [[1.85, 13.7], [1.85, 12.3], ...DESTINO_CONTENCAO.apostador_1.slice(-1)], 1.3, 'andando', () => { u.reunido = true; conferirPessoas(); }), 1500);
    });
    else rota(n, [...SAIDA_JOGADOR, ...(A ? FUGA : FUGA.slice(0, 3))], 1.5, 'andando', () => { n.visible = false; u.fugiu = true; u.saindo = false; u.fugindo = false; if (A && !A.fugiram) { A.fugiram = true; registrar('apostadores_fugiram'); } conferirPessoas(); });
    legenda('Alerta', 'O homem que jogava na máquina levantou e está indo para a porta dos fundos. Aponte para ele e aperte o gatilho para dar a ordem de parar.', 5);
  }
  function ordemVerbal(n) {                                   // "Parado! Polícia!": a resposta proporcional para quem só está indo embora
    const u = n?.userData; if (!u?.saindo) return;
    u.saindo = false; u.fugindo = false; u.parouOrdem = true; u.rota = null; u.destino = null; u.base = u.acoes?.nervoso ? 'nervoso' : 'parada'; animar(n, u.base, 1e6, .3);
    camera.getWorldPosition(P1); n.rotation.y = Math.atan2(P1.x - n.position.x, P1.z - n.position.z); u.giroBase = n.rotation.y;
    legenda('Você', 'Parado! Polícia! Fique onde está.', 2.5); registrar('ordem_verbal_saida');
    setTimeout(() => diz(n, 'Tá bom, tá bom… eu só ia embora.'), 1200); conferirPessoas();
  }
  const P1 = new THREE.Vector3(), D1 = new THREE.Vector3(), T1 = new THREE.Vector3();
  function miraNoApostador(dt) {
    const n = npcs.apostador_1, u = n?.userData; if (!u?.saindo || !n.visible) return;
    let naMira = false;
    if (S.armaNaMao && arma?.visible) {
      arma.getWorldPosition(P1); arma.getWorldDirection(D1).negate();                  // o cano aponta para -Z da arma
      T1.copy(n.position); T1.y += 1.15; T1.sub(P1); const dist = T1.length();
      naMira = dist < 14 && D1.angleTo(T1) < .14;
    }
    u.tMira = naMira ? (u.tMira || 0) + dt : 0;
    if (u.tMira > .3) {
      u.saindo = false; u.fugindo = false; u.parouArma = true; u.rota = null; u.destino = null; u.base = 'rendido'; animar(n, 'rendido', 1e6, .25);
      n.rotation.y = Math.atan2(P1.x - n.position.x, P1.z - n.position.z); u.giroBase = n.rotation.y;
      legenda('Apostador', 'Calma! Não atira, eu paro!', 4); if (!ameacando().length) registrar('arma_sem_ameaca'); conferirPessoas();
    }
  }
  const rota = (n, pts, vel, anim, aoChegar) => {
    const u = n.userData; u.rota = pts.map(([x, y]) => B(x, y)); u.destino = null; u.vel = vel; u.aoChegar = () => { animar(n, u.base || 'parada', 1e6, .3); aoChegar?.(); };
    animar(n, u.acoes?.[anim] ? anim : 'andando', 1e6, .25);
  };
  const diz = (n, texto, gesto = 'falando') => n ? dizer(n, n.userData.nome, { texto, gesto }, n.userData.voz) : Promise.resolve();
  const pessoas = () => ['seguranca', 'apostador_1', 'apostador_2', 'apostador_3'].map(k => npcs[k]).filter(n => n && n.visible && !n.userData.fugiu);
  const apostadores = () => pessoas().filter(n => /^apostador/.test(n.userData.chave));
  function conferirPessoas() {
    if (!A) return;
    const livres = pessoas().filter(n => !n.userData.caido && !n.userData.algemado);
    if (livres.length && livres.every(n => n.userData.reunido)) registrar('reunir_pessoas');
    const ap = apostadores(); if (ap.length && ap.every(n => n.userData.qualificado)) registrar('qualificar_apostadores');
    status();
  }

  /* ================= paineis de opcoes ================= */
  const fechar = () => dialogo.esconder();
  function dica(texto, seg = 6) { if (S.modo !== 'avaliacao' && S.ativo) legenda('Dica do instrutor', texto, seg); }
  function painelOpc(tag, titulo, lista, aoEscolher, texto = '', voltar = true) {
    fecharPaineis();
    dialogo.mostrar({ tag, titulo, texto, botoes: [...lista.map(op => ({ label: op.fala, acao: () => {
      fechar();
      if (op.acao) registrar(op.acao);
      if (op.tambem) registrar(op.tambem);
      if (op.erro) registrar(op.erro);
      if (op.falha) registrar(op.falha);
      if (op.feedback && S.modo === 'treino') setTimeout(() => legenda('Instrutor', op.feedback, 7), 2400);
      aoEscolher?.(op);
    } })), ...(voltar ? [{ label: 'Voltar', acao: fechar }] : [])] });
  }

  /* ================= fluxo da ocorrencia ================= */
  function novaOcorrencia(v, cap) {
    S.variacao = v; S.feitos = new Map(); S.granadas = 2; S.vida = 3; S.municao = CARREGADOR; S.recarregando = false; limparSangue();
    A = { n: HIST.length + 1, fase: 'chegada', titulo: cap?.titulo || `Ocorrência ${HIST.length + 1}` };
    criarNPCs(v); sacar(false); pegarGranada(false);
    for (const it of Object.values(itens)) it.o.visible = true;
    lacres.visible = false; moverEstante(false, .1); moverCofre(false, .1);
    moverPorta('salao', v.indicios === 'visiveis' ? .13 : 0, .1); moverPorta('escritorio', 0, .1); moverPorta('fundos', 0, .1);
    rig.position.set(3.0, .15, 1.2); ctx.setYaw(1.34);
    const abrir = () => { radio(CEN.radio.inicio).then(() => { if (!A?.entrada) dica('Fale com o parceiro (ao lado da viatura) e use o menu (T ou botão Y/B) para falar no rádio.'); }); };
    if (cap) { fecharPaineis(); menu.mostrar({ tag: 'Modo história', titulo: cap.titulo, texto: cap.texto, longe: 1.3, botoes: [{ label: 'Começar', acao: () => { menu.esconder(); abrir(); } }] }); }
    else abrir();
    status();
  }
  function falarRadio(tipo) {
    fecharPaineis();
    if (tipo === 'chegada') { A.chegada = true; registrar('comunicar_chegada'); radio(CEN.radio.chegada); }
    if (tipo === 'apoio') {
      A.apoio = true; registrar('pedir_apoio');
      radio(CEN.radio.apoio).then(() => { if (npcs.apoio) { npcs.apoio.visible = true; npcs.apoio.position.copy(B(-7, -1)); rota(npcs.apoio, [[-7, 12.4]], 1.6, 'andando'); } });
    }
    status();
  }
  function menuParceiro() {
    const D = CEN.dialogos, p = npcs.parceiro;
    if (A.plano) return diz(p, CEN.equipe.pm_parceiro);
    painelOpc('Parceiro', 'Como vamos entrar?', D.parceiro, op => {
      A.plano = true; A.parceiroJunto = !!op.acao;
      if (op.acao) diz(p, D.resposta_parceiro).then(() => { rota(p, [[-2, -1], [-1.6, 1.6]], 1.5, 'andando'); if (!A.apoio) dica('Peça apoio pelo rádio para cobrir os fundos (menu).'); });
    });
  }
  function menuAtendente() {
    const D = CEN.dialogos, v = S.variacao, a = npcs.atendente;
    if (!A.abriu) return painelOpc('Funcionária do bar', 'Primeiro contato', D.abertura, () => { A.abriu = true; diz(a, D.resposta_abertura, 'nervoso'); });
    const ops = [];
    if (!A.perguntou) ops.push({ label: D.pergunta_fundos, acao: () => { fechar(); A.perguntou = true; diz(a, D.resposta_fundos[v.consentimento]); } });
    if (!A.pediu) ops.push({ label: D.pedido_consentimento, acao: () => { fechar(); A.pediu = true; registrar('pedir_consentimento'); A.consentiu = v.consentimento === 'franqueia'; diz(a, D.resposta_consentimento[v.consentimento]); } });
    if (A.entrou && v.responsavel === 'ausente' && !A.funcionaria) ops.push({ label: 'Perguntar pelo dono do local', acao: () => painelOpc('Funcionária do bar', 'Dono ausente', D.funcionaria, op => { A.funcionaria = true; if (op.acao) diz(a, D.resposta_funcionaria); }) });
    if (A.entrou && v.responsavel === 'ausente' && A.escritorio === undefined) ops.push({ label: 'Perguntar pela chave do escritório', acao: () => { fechar(); A.semChave = true; diz(a, 'A chave fica com o dono. Eu não tenho.'); } });
    fecharPaineis();
    dialogo.mostrar({ tag: 'Funcionária do bar', titulo: 'Conversa', botoes: [...ops, { label: 'Encerrar conversa', acao: fechar }] });
  }
  function menuPortaSalao() {
    const D = CEN.dialogos, v = S.variacao;
    if (A.decidiuEntrada) { if (A.entrada) moverPorta('salao', portas.salao.frac > .5 ? 0 : 1); return; }
    registrar('observar_indicios');
    painelOpc('Porta “PRIVATIVO”', 'O que você percebe', D.decisao_entrada, op => {
      A.decidiuEntrada = true;
      const certo = v.indicios === 'visiveis' ? 'flagrante' : v.consentimento === 'franqueia' ? 'consentimento' : 'nao_entrar';
      const licito = op.id === 'flagrante' ? v.indicios === 'visiveis' : op.id === 'consentimento' ? !!A.consentiu : op.id === 'nao_entrar';
      if (op.id === 'nao_entrar') {
        if (certo === 'nao_entrar') { registrar('decisao_entrada'); registrar('encaminhar_denuncia'); } else { registrar('deixou_de_agir'); v.entra = 'nao'; }
        if (S.modo === 'treino') legenda('Instrutor', (certo === 'nao_entrar' ? 'Correto. ' : 'Aqui cabia entrar: ') + D.decisao_entrada_explicacao[certo], 8);
        A.entrada = false; radio(CEN.radio.sem_entrada); setTimeout(finalizar, S.modo === 'treino' ? 9000 : 6000); return status();
      }
      if (licito) registrar('decisao_entrada'); else { registrar('entrada_ilegal', op.id); v.entra = 'sim'; }
      if (S.modo === 'treino') legenda('Instrutor', (licito ? 'Correto. ' : 'Entrada irregular. O correto: ') + D.decisao_entrada_explicacao[licito ? op.id : certo], 8);
      A.entrada = true; moverPorta('salao', 1);
      if (A.parceiroJunto && npcs.parceiro) rota(npcs.parceiro, [[-4.75, 5.2], [-4.75, 7.2], [-2.9, 6.55]], 1.6, 'andando');
      status();
    }, CEN.observacao_porta[v.indicios] + (A.pediu ? (A.consentiu ? '\nA funcionária autorizou a entrada.' : '\nA funcionária não autorizou a entrada.') : ''));
  }
  function aoEntrarNoSalao() {
    A.entrou = true; A.fase = 'salao';
    painelOpc('Salão de jogos', 'Você entrou no salão', CEN.dialogos.anuncio, () => { A.anunciou = true; reacoes(); }, 'Há pessoas jogando nas máquinas e na mesa.', false);
  }
  function renderNPC(s, largou) {                             // a pessoa se rende; se estava com a arma na mao, ela vai ao chao
    if (!s) return; const u = s.userData;
    if (u.sentado) { u.sentado = false; s.position.y = .15; }
    u.ameaca = false; u.atira = false; u.base = 'rendido'; animar(s, 'rendido', 1e6, .3); u.reunido = true;
    if (u.chave === 'seguranca' && A) A.rendeu = true;
    if (largou && u.arma?.visible) { u.arma.visible = false; armaChao(s.position, u.chave); }
    sincAmeaca(); status();
  }
  const renderSeguranca = largou => renderNPC(npcs.seguranca, largou);
  function reacoes() {
    const v = S.variacao, s = npcs.seguranca;
    for (const n of apostadores()) { if (n.userData.jogando) continue; animar(n, 'rendido', 6, .3); n.userData.base = n.userData.acoes?.nervoso ? 'nervoso' : 'parada'; }
    setTimeout(() => { if (A) tentarSair(); }, 900);
    setTimeout(esconderFichas, 1600);
    setTimeout(() => { const r = npcs.responsavel; if (A && r && r.visible && !r.userData.caido && !ameacando().length) diz(r, CEN.dialogos.reclamacao_responsavel, 'irritado'); }, 3200);
    if (npcs.responsavel) npcs.responsavel.userData.base = 'irritado', animar(npcs.responsavel, 'irritado', 1e6, .4);
    if (v.fuga === 'tentam_sair') setTimeout(() => {
      if (!A) return; moverPorta('fundos', 1, .4);
      for (const k of ['apostador_2']) {
        const n = npcs[k]; if (!n || n.userData.atordoado > performance.now()) continue;
        n.userData.fugindo = true;
        if (A.apoio) rota(n, FUGA.slice(0, 3), 3.4, 'correndo', () => {                 // a equipe de apoio contem no quintal e traz de volta
          n.userData.fugindo = false; registrar('fuga_contida');
          setTimeout(() => rota(n, [[1.85, 13.7], [1.85, 12.3], ...DESTINO_CONTENCAO[k].slice(-1)], 1.3, 'andando', () => { n.userData.reunido = true; conferirPessoas(); }), 1500);
        });
        else rota(n, FUGA, 3.4, 'correndo', () => { n.visible = false; n.userData.fugiu = true; n.userData.fugindo = false; if (!A.fugiram) { A.fugiram = true; registrar('apostadores_fugiram'); } conferirPessoas(); });
      }
      legenda('Alerta', A.apoio ? 'Outro apostador corre para os fundos. A equipe de apoio está lá.' : 'Outro apostador corre para a porta dos fundos!', 4);
    }, 1400);
    if (v.seguranca === 'armado_rende') setTimeout(() => { A && legenda('Alerta', 'O homem perto da entrada leva a mão à cintura: há um volume sob a camisa. Fale com ele.', 6); }, 1200);
    if (v.seguranca === 'armado_reage') setTimeout(() => {
      if (!A || !s || s.userData.caido || s.userData.atordoado > performance.now()) return;
      s.userData.ameaca = true; sincAmeaca(); s.userData.base = 'apontando'; animar(s, 'apontando', 1e6, .25); armaNPC.visible = true; s.userData.semVirar = false;
      legenda('Alerta', 'O homem perto da entrada sacou uma arma e aponta para você!', 5);
      A.tAmeaca = setTimeout(() => {
        if (!A?.ameaca) return;
        somTiro(); acenderFlash(armaNPC.userData.flash); veuVermelho(); registrar('atingido');
        legenda('Instrutor', 'Você foi atingido. Diante de agressão armada atual, a reação imediata é legítima. O parceiro rendeu o agressor.', 8);
        renderSeguranca(true);
      }, 6500);
    }, 1800);
    else if (s && v.seguranca === 'desarmado') { animar(s, 'rendido', 3, .3); }
    if (v.seguranca === 'confronto') setTimeout(() => {       // confronto: o seguranca atira e um segundo homem armado sai do deposito
      if (!A || !s) return;
      const armar = (n, atraso) => {
        const u = n.userData; if (u.caido || u.atordoado > performance.now()) return;
        u.ameaca = true; u.atira = true; u.proxTiro = performance.now() + atraso; u.base = 'apontando'; animar(n, 'apontando', 1e6, .25);
        if (u.arma) u.arma.visible = true; u.semVirar = false; sincAmeaca(); status();
      };
      armar(s, 2200); legenda('Alerta', 'O homem perto da entrada sacou uma arma e vai atirar! Proteja-se e reaja.', 5);
      const s2 = npcs.seguranca_2;
      if (s2) setTimeout(() => {
        if (!A || A.fase === 'fim' || s2.userData.caido) return;
        rota(s2, [[-4.75, 8.9], [-4.75, 7.3], [-3.0, 7.5]], 2.8, 'correndo', () => { armar(s2, 900); legenda('Alerta', 'Um segundo homem armado veio do depósito!', 4); });
      }, 5200);
    }, 1500);
  }
  function menuSeguranca() {
    const D = CEN.dialogos, v = S.variacao, s = npcs.seguranca, u = s.userData;
    if (u.ameaca) return legenda('Alerta', 'Ele não obedece e mantém a arma apontada para você.', 3);
    if (u.caido && !A.socorro) return painelOpc('Ferido', 'Homem baleado', D.socorro, op => { if (op.acao) { A.socorro = true; radio(CEN.radio.socorro); } });
    if (v.arma === 'sim' && !A.rendeu && !u.caido) return painelOpc('Segurança', 'Homem com volume na cintura', D.armado, op => {
      if (op.acao) { diz(s, D.resposta_armado, 'nervoso'); renderSeguranca(false); armaChao(s.position); dica('Ele obedeceu. Recolha a arma e algeme (fale com ele de novo).'); }
      else dica('Para atirar, saque a arma (tecla Q ou botão A). Avalie: ele está atacando alguém?');
    });
    if (v.arma === 'sim' && !A.algemou) return painelOpc('Segurança', 'Homem que estava armado', D.pos_arma, op => {
      A.algemou = true; armaSolta.visible = false; armaSolta2.visible = false;
      if (op.acao) { window.__som?.tocar('algemas', s.position.clone().setY(1.1)); u.algemado = true; if (!u.caido) { u.base = 'algemado'; animar(s, 'algemado', 1e6, .4); } legenda('Apreensão', 'Arma recolhida, desmuniciada e lacrada. Homem algemado; a justificativa vai para o registro.', 5); }
      conferirPessoas();
    });
    if (v.arma === 'sim') return legenda('Segurança', 'Preso em flagrante por porte ilegal de arma, aguardando a condução.', 3);
    menuPessoa(s);
  }
  function menuPessoa(n) {
    const D = CEN.dialogos, u = n.userData;
    if (!A.anunciou) return;
    if (u.atordoado > performance.now()) return legenda(u.nome, 'Está desorientado pelo estouro. Aguarde alguns segundos.', 3);
    const lista = [...(u.escondeu && A.fichasEscondidas ? [D.devolver_fichas] : []), ...D.apostador.filter(o => !(o.id === 'reunir' && u.reunido) && !(o.id === 'qualificar' && u.qualificado))];
    painelOpc(u.nome, 'O que fazer', lista, op => {
      if (op.id === 'devolver') { A.fichasEscondidas = false; diz(n, D.resposta_apostador.devolver).then(() => { if (itens.fichas && !A.apreendidos?.has('fichas')) itens.fichas.o.visible = true; registrar('fichas_recuperadas'); status(); }); }
      else if (op.id === 'reunir') { diz(n, D.resposta_apostador.reunir).then(() => { levantar(n); rota(n, DESTINO_CONTENCAO[u.chave], 1.2, 'andando', () => { u.reunido = true; u.giroBase = olharPara(0, 1); conferirPessoas(); }); }); }
      else if (op.id === 'qualificar') { u.qualificado = true; diz(n, D.resposta_apostador.qualificar); conferirPessoas(); }
      else if (op.id === 'algemar') { registrar('algemas_indevidas', u.nome); if (S.modo === 'treino') legenda('Instrutor', 'Ele colabora: não há resistência, risco de fuga nem perigo (Súmula Vinculante 11).', 6); }
      else if (op.id === 'revistar') { registrar('revista_sem_suspeita', u.nome); if (S.modo === 'treino') legenda('Instrutor', 'Busca pessoal exige fundada suspeita em relação àquela pessoa (CPP art. 244).', 6); }
    });
  }
  function menuResponsavel() {
    const D = CEN.dialogos, v = S.variacao, r = npcs.responsavel, R = D.responsavel;
    if (!A.anunciou) return;
    const ops = [];
    if (!A.quem) ops.push({ label: R.quem, acao: () => { fechar(); A.quem = true; registrar('identificar_responsavel'); diz(r, R.resposta_quem, 'irritado').then(() => { if (v.suborno === 'sim') setTimeout(oferta, 1200); }); } });
    if (A.quem && !A.direitos) ops.push({ label: R.direitos, acao: () => { fechar(); A.direitos = true; registrar('informar_direitos'); diz(r, R.resposta_direitos); } });
    if (v.suborno === 'sim' && A.ofertou && !A.suborno) ops.push({ label: 'Responder à oferta de dinheiro', acao: respostaOferta });
    if (!r.userData.reunido) ops.push({ label: 'Peço que fique junto à parede, com as mãos visíveis.', acao: () => { fechar(); rota(r, DESTINO_CONTENCAO.responsavel, 1.2, 'andando', () => { r.userData.reunido = true; r.userData.giroBase = olharPara(-1, 0); }); } });
    fecharPaineis();
    dialogo.mostrar({ tag: 'Responsável', titulo: 'Conversa', botoes: [...ops, { label: 'Encerrar conversa', acao: fechar }] });
  }
  function oferta() { if (!A || A.ofertou) return; A.ofertou = true; diz(npcs.responsavel, CEN.dialogos.suborno_oferta).then(respostaOferta); }
  function respostaOferta() {
    painelOpc('Responsável', 'Ele ofereceu dinheiro', CEN.dialogos.suborno, op => {
      A.suborno = true; const r = npcs.responsavel;
      if (op.acao) { r.userData.algemado = false; legenda('Flagrante', 'Voz de prisão por corrupção ativa. O parceiro é testemunha; o dinheiro oferecido será apreendido.', 6); }
    }, '', false);
  }
  function apreender(k, texto) { if (itens[k]) itens[k].o.visible = false; A.apreendidos = A.apreendidos || new Set(); A.apreendidos.add(k); legenda('Apreensão', texto, 4); conferirApreensao(); }
  function conferirApreensao() {
    const a = A.apreendidos || new Set();
    if (a.has('fichas') && a.has('caderno_apostas')) registrar('apreender_anotacoes');
    if (a.has('celular') && a.has('notebook') && a.has('dvr')) registrar('apreender_eletronicos');
    status();
  }
  function usarItem(k) {
    const D = CEN.dialogos;
    if (!A.entrou) return legenda('Vestígio', INFO_ITEM[k] || '', 5);
    if (A.apreendidos?.has(k)) return;
    if (k === 'fichas' && A.fichasEscondidas) return legenda('Vestígio', 'As fichas não estão mais na mesa. Alguém guardou.', 4);
    if (k === 'arma') return menuSeguranca();
    if (k === 'maquinas') {
      if (A.maquinas) return legenda('Apreensão', `${CFG.maquinas || 8} máquinas relacionadas e lacradas.`, 3);
      return painelOpc('Vestígio', 'Máquinas caça-níqueis', D.maquinas, op => { A.maquinas = true; if (op.acao) { lacres.visible = true; legenda('Apreensão', `${CFG.maquinas || 8} máquinas fotografadas, relacionadas e lacradas. Mais duas, desligadas, no depósito.`, 5); } status(); });
    }
    if (/^dinheiro/.test(k)) return painelOpc('Vestígio', 'Dinheiro', D.dinheiro, op => {
      if (op.acao && k === 'dinheiro_sala') registrar('apreender_dinheiro_secreto');
      if (op.acao && k === 'dinheiro_cofre') registrar('apreender_dinheiro_cofre');
      apreender(k, op.acao ? 'Dinheiro contado na frente de testemunha e lacrado. Lacre nº ' + (417000 + Math.floor(Math.random() * 900)) + '.' : 'Dinheiro recolhido sem contagem.');
    }, INFO_ITEM[k]);
    if (/^(notebook|celular)$/.test(k)) return painelOpc('Vestígio', k === 'celular' ? 'Celular' : 'Computador', D.eletronico, op => {
      if (op.ok) apreender(k, 'Aparelho apreendido sem acesso ao conteúdo e lacrado.');
      else if (S.modo === 'treino') legenda('Instrutor', 'O conteúdo de celular e computador é protegido: só com ordem judicial ou consentimento.', 7);
    }, INFO_ITEM[k]);
    apreender(k, { fichas: 'Fichas arrecadadas e lacradas.', caderno_apostas: 'Caderno de apostas arrecadado e lacrado.', caderno_contab: 'Caderno de contabilidade arrecadado e lacrado.', dvr: 'Gravador das câmeras apreendido e lacrado.' }[k] || 'Item arrecadado.');
  }
  // cofre trancado: pedir a quem sabe o segredo que abra (e contar o dinheiro na frente dele), lacrar fechado se nao ha quem
  // abra, ou forcar (erro). Mesmo desenho da porta do escritorio.
  function menuCofre() {
    const D = CEN.dialogos, v = S.variacao, r = npcs.responsavel;
    if (!A.entrou) return legenda('Vestígio', INFO_ITEM.cofre, 5);
    if (A.cofre === 'aberto') return;
    if (A.cofre) return legenda('Cofre', 'Cofre lacrado fechado e relacionado para apreensão. A autoridade policial foi informada.', 4);
    const presente = v.responsavel === 'presente' && r && r.visible && !r.userData.caido;
    painelOpc('Cofre', 'O cofre do escritório está trancado', D.cofre, op => {
      if (op.id === 'pedir') {
        if (presente) { registrar('cofre_correto'); A.cofre = 'aberto'; diz(r, D.resposta_cofre).then(() => moverCofre(true)); }
        else legenda('Cofre', 'Ninguém no local sabe o segredo: só o dono.', 4);
      } else if (op.id === 'lacrar') {
        if (!presente) registrar('cofre_correto'); else penalidade(-2, 'Lacrar o cofre fechado com o responsável no local e podendo abrir', 'O responsável estava no local: peça que abra e conte o dinheiro na frente dele.');
        A.cofre = 'lacrado'; legenda('Apreensão', 'Cofre lacrado fechado e relacionado. A abertura fica para a autoridade policial, com ordem judicial e perícia.', 6);
      } else { registrar('forcar_cofre'); A.cofre = 'aberto'; moverCofre(true, .5); estouro(.25, 900, .6, .6); }
      status();
    }, presente ? 'O responsável está no local.' : 'O dono não está no local.');
  }
  function menuEscritorio() {
    const D = CEN.dialogos, v = S.variacao;
    if (!A.entrou) return;
    if (A.escritorio === 'aberto') return moverPorta('escritorio', portas.escritorio.frac > .5 ? 0 : 1);
    if (A.escritorio) return legenda('Escritório', 'Cômodo fechado e preservado. A autoridade policial foi informada.', 3);
    painelOpc('Escritório', 'A porta “GERÊNCIA” está trancada', D.escritorio, op => {
      const presente = v.responsavel === 'presente';
      if (op.id === 'pedir') {
        if (presente) { registrar('escritorio_correto'); A.escritorio = 'aberto'; diz(npcs.responsavel, D.resposta_chave).then(() => moverPorta('escritorio', 1)); }
        else { legenda('Escritório', 'Ninguém no local tem a chave: ela fica com o dono.', 4); }
      } else if (op.id === 'preservar') {
        if (!presente) registrar('escritorio_correto'); else penalidade(-2, 'Deixar de arrecadar o que havia no escritório, com o responsável presente e a chave disponível', 'O responsável estava no local e podia abrir: peça a chave e registre.');
        A.escritorio = 'preservado';
      } else { registrar('arrombar_escritorio'); A.escritorio = 'aberto'; moverPorta('escritorio', 1, .3); estouro(.25, 900, .6, .6); }
      status();
    }, v.responsavel === 'presente' ? 'O responsável está no salão.' : 'O dono não está no local.');
  }
  function decidirFinal() {
    const D = CEN.dialogos, v = S.variacao;
    painelOpc('Rádio · encerramento', 'Enquadramento da ocorrência', D.decisao, op => {
      A.decidiu = true;
      if (op.id === v.decisao) registrar('enquadramento_correto');
      else if (op.id === 'prender_todos') registrar('prisao_indevida');
      else if (op.id === 'liberar') registrar('liberar_sem_registro');
      else registrar('enquadramento_errado', op.id);
      if (S.modo === 'treino') legenda('Instrutor', (op.id === v.decisao ? 'Correto. ' : 'O correto aqui: ') + D.decisao_explicacao[v.decisao], 8);
      const depois = () => painelOpc('Encerramento', 'Registro', D.registro, () => { radio(CEN.radio.final); setTimeout(finalizar, 5000); }, '', false);
      setTimeout(() => v.responsavel === 'presente' ? painelOpc('Condução', 'Responsável pelo local', D.algemas, depois, 'Ele acompanhou a ação sem resistir.', false) : depois(), S.modo === 'treino' ? 4200 : 400);
    }, 'Resumo: ' + [v.responsavel === 'presente' ? 'responsável identificado' : 'dono ausente', v.arma === 'sim' ? 'um homem estava armado' : 'ninguém armado', v.suborno === 'sim' ? 'houve oferta de dinheiro' : 'sem oferta de dinheiro'].join(' · '));
  }
  function finalizar() {
    if (!A || A.fase === 'fim') return;
    A.fase = 'fim'; clearTimeout(A.tAmeaca); fecharPaineis();
    if (A.ferido && !A.socorro) registrar('omissao_socorro');
    sacar(false); status(); setTimeout(concluir, 1500);
  }
  function resumo() {                                         // pontos da ocorrencia atual, por fase
    const fases = [];
    for (const f of CEN.fases) {
      let fp = 0, fo = 0; const its = [];
      for (const a of f.acoes || []) {
        if (!cond(a.condicao)) continue;
        fp += a.pontos; const ok = S.feitos.has(a.id); if (ok) fo += a.pontos;
        its.push({ texto: a.texto, ok, pontos: ok ? a.pontos : 0, base: a.base, atendimento: A.n });
      }
      fases.push({ nome: f.nome, obtidos: fo, possiveis: fp, itens: its });
    }
    return { n: A.n, titulo: A.titulo, variacao: { ...S.variacao }, fases };
  }
  function concluir() {
    if (!A) return;
    HIST.push(resumo()); A = null;
    if (!S.ativo) return;
    if (S.fila.length) { const prox = S.fila.shift(); setTimeout(() => novaOcorrencia(derivar({ ...prox.variacao }), S.historia ? prox : null), 1200); }
    else encerrar();
  }

  /* ================= inicio, menu e relatorio ================= */
  function aviso() {
    fecharPaineis();
    menu.mostrar({
      tag: 'Treinamento · conteúdo sensível · versão ' + (window.__versao || '?'), titulo: 'Cassino clandestino',
      texto: 'Você é policial militar e atende uma denúncia de jogo de azar nos fundos de um bar. O treinamento simula abordagem, uso da força (arma de fogo e granada de efeito moral), apreensão e condução.\n\n' +
        'Há cenas de confronto armado, com disparos e sangue.\n' +
        'Computador: clique fala/usa · T menu · Q saca ou guarda a arma (com ela na mão, o clique dispara) · R recarrega · E lança granada · K checklist.\n' +
        'Quest: gatilho usa/clica · A saca a arma (gatilho direito dispara, apertar o analógico direito recarrega) · X pega a granada na mão esquerda (segure o gatilho esquerdo, faça o movimento e solte) · Y ou B abre o menu · grip liga a lanterna.',
      botoes: [
        { label: 'Modo história (4 ocorrências guiadas)', acao: () => comecar('historia') },
        { label: 'Modo treino (objetivos e dicas na tela)', acao: () => comecar('treino') },
        { label: 'Modo avaliação (sem dicas)', acao: () => comecar('avaliacao') },
        { label: 'Treino de confronto armado (direto na entrada do salão)', acao: () => comecar('confronto') },
        { label: S.voz === false ? 'Voz sintética: desligada (só legendas)' : 'Voz sintética: ligada', acao: () => { S.voz = S.voz === false; aviso(); } },
        { label: 'Cancelar', acao: () => menu.esconder() }
      ]
    });
  }
  async function comecar(modo) {
    fecharPaineis();
    let carregou = false; modelosProntos.then(() => { carregou = true; });
    await new Promise(r => setTimeout(r, 0));
    if (!carregou) {
      menu.mostrar({ tag: 'Treinamento', titulo: 'Carregando personagens…', texto: 'Aguarde alguns segundos.', botoes: [] });
      await Promise.race([modelosProntos, new Promise(r => setTimeout(r, 30000))]);
      menu.esconder();
    }
    HIST.length = 0;
    Object.assign(S, { ativo: true, inicio: performance.now(), fim: 0, erros: [], graves: [], log: [], historia: modo === 'historia', modo: modo === 'avaliacao' ? 'avaliacao' : 'treino' });
    S.fila = S.historia ? CEN.historia.slice(1) : [];
    if (ctx.hotspots) ctx.hotspots.visible = false;
    document.getElementById('relatorioHTML')?.setAttribute('hidden', '');
    if (modo === 'confronto') {                             // pula a chegada: comeca no corredor, com a entrada ja decidida
      novaOcorrencia(derivar({ indicios: 'visiveis', consentimento: 'nega', seguranca: 'confronto', fuga: 'colaboram', responsavel: 'presente', suborno: 'nao' }), null);
      for (const id of ['comunicar_chegada', 'pedir_apoio', 'planejar_parceiro', 'identificar_se', 'observar_indicios', 'decisao_entrada']) registrar(id);
      Object.assign(A, { titulo: 'Treino de confronto armado', chegada: true, apoio: true, plano: true, parceiroJunto: true, parceiroNoBar: true, abriu: true, decidiuEntrada: true, entrada: true });
      moverPorta('salao', 1, .1); if (npcs.apoio) npcs.apoio.visible = true; if (npcs.parceiro) npcs.parceiro.position.copy(B(-4.75, 5.0));
      rig.position.set(-4.75, .15, -6.9); ctx.setYaw(-Math.PI / 2); sacar(true);
      dica('Você está no corredor, com a arma na mão. O salão fica à sua frente. Use a parede como proteção.', 7);
      return;
    }
    novaOcorrencia(S.historia ? derivar({ ...CEN.historia[0].variacao }) : sortear(), S.historia ? CEN.historia[0] : null);
  }
  function abrirMenu() {
    if (!S.ativo) return aviso();
    fecharPaineis();
    const b = [];
    if (A && !A.chegada) b.push({ label: 'Rádio: informar a chegada ao local', acao: () => falarRadio('chegada') });
    if (A && !A.apoio && !A.entrou) b.push({ label: 'Rádio: pedir apoio para cobrir os fundos', acao: () => falarRadio('apoio') });
    if (A?.ferido && !A.socorro) b.push({ label: 'Rádio: pedir socorro médico e comunicar o disparo', acao: () => { fecharPaineis(); A.socorro = true; registrar('socorro'); radio(CEN.radio.socorro); } });
    if (A?.entrou && !A.decidiu) b.push({ label: 'Rádio: enquadramento e condução (encerrar a ocorrência)', acao: decidirFinal });
    if (npcs.apostador_1?.userData.saindo) b.unshift({ label: 'Ordenar: "Parado! Polícia!"', acao: () => { menu.esconder(); ordemVerbal(npcs.apostador_1); } });
    if (S.armaNaMao) b.push({ label: `Recarregar a arma (${S.municao ?? CARREGADOR}/${CARREGADOR})`, acao: () => { menu.esconder(); recarregar(); } });
    b.push({ label: S.armaNaMao ? 'Guardar a arma no coldre' : 'Sacar a arma', acao: () => { sacar(!S.armaNaMao); menu.esconder(); } },
      { label: renderer.xr.isPresenting ? (S.granadaNaMao ? 'Guardar a granada' : `Pegar granada de efeito moral (${S.granadas ?? 2})`) : `Lançar granada de efeito moral (${S.granadas ?? 2})`, acao: () => { menu.esconder(); renderer.xr.isPresenting ? pegarGranada(!S.granadaNaMao) : arremessar(); } },
      { label: 'Checklist desta ocorrência', acao: abrirChecklist },
      { label: 'Lanterna (liga/desliga)', acao: () => { ctx.setLanterna(!ctx.lanternaLigada(), camera); menu.esconder(); } },
      { label: 'Encerrar e ver o relatório', cor: 'rgba(240,80,64,.22)', acao: encerrar },
      { label: 'Fechar', acao: () => menu.esconder() });
    menu.mostrar({ tag: 'Menu', titulo: 'Cassino clandestino', texto: `Tempo: ${fmt(tempo())} · ${A ? A.titulo : 'aguardando'}`, botoes: b });
  }
  function abrirChecklist() {
    fecharPaineis();
    const linhas = CEN.fases.map(f => `${f.nome}: ` + (f.acoes || []).filter(a => cond(a.condicao)).map(a => (S.feitos.has(a.id) ? '✓ ' : '· ') + a.texto).join(' | ')).join('\n');
    menu.mostrar({ tag: 'Checklist', titulo: 'Checklist da ocorrência', texto: (S.modo === 'avaliacao' ? 'No modo avaliação o checklist só aparece no relatório.' : linhas) + `\n\nTempo: ${fmt(tempo())}`, botoes: [{ label: 'Fechar', acao: () => menu.esconder() }], longe: 1.3 });
  }
  function encerrar() {
    if (!S.ativo) return;
    if (A) { clearTimeout(A.tAmeaca); if (A.ferido && !A.socorro) registrar('omissao_socorro'); HIST.push(resumo()); A = null; }
    S.fila = []; S.fim = performance.now(); S.ativo = false; fecharPaineis(); sacar(false); status();
    mostrarRelatorio(relatorio());
  }
  function relatorio() {
    let possiveis = 0, obtidos = 0; const fases = [];
    CEN.fases.forEach((f, i) => {
      const fr = { nome: f.nome, obtidos: 0, possiveis: 0, itens: [] };
      for (const h of HIST) { const x = h.fases[i]; fr.obtidos += x.obtidos; fr.possiveis += x.possiveis; fr.itens.push(...x.itens); }
      possiveis += fr.possiveis; obtidos += fr.obtidos; fases.push(fr);
    });
    const desc = S.erros.reduce((s, e) => s + e.pontos, 0) + S.graves.reduce((s, e) => s + e.pontos, 0);
    const nota = possiveis ? Math.max(0, Math.round((obtidos + desc) / possiveis * 100)) : 0;
    const aprovado = nota >= CEN.aprovacao.pontos_minimos && !(CEN.aprovacao.sem_falha_grave && S.graves.length);
    return { cenario: CEN.id, data: new Date().toISOString(), tempo: fmt(tempo()), modo: S.historia ? 'historia' : S.modo, nota, aprovado, obtidos, descontos: desc, possiveis,
      atendimentos: HIST.map(h => ({ n: h.n, titulo: h.titulo, variacao: h.variacao })), fases, erros: S.erros, falhas_graves: S.graves, linha_do_tempo: S.log };
  }
  function mostrarRelatorio(r) {
    const varios = r.atendimentos.length > 1, at = e => varios ? ` [ocorr. ${e.atendimento}]` : '';
    const txtFases = r.fases.map(f => `${f.nome}: ${f.obtidos}/${f.possiveis}`).join('\n');
    const txtErros = [...r.falhas_graves.map(g => '⚠ FALHA GRAVE: ' + g.texto + (g.base ? ` (${g.base})` : '') + at(g)), ...r.erros.map(e => `• ${e.texto} (${e.pontos})${e.feedback ? ' — ' + e.feedback : ''}` + at(e))].join('\n') || 'Nenhum erro registrado.';
    menu.mostrar({
      tag: 'Relatório', titulo: `Nota ${r.nota}/100 · ${r.aprovado ? 'APROVADO' : 'NÃO APROVADO'}`,
      texto: `Tempo: ${r.tempo} · Ocorrências: ${r.atendimentos.length}\n\n${txtFases}\n\n${txtErros}`,
      botoes: [{ label: 'Novo treinamento (outras variações)', acao: () => { fecharPaineis(); cenaExploracao(); aviso(); } }, { label: 'Fechar', acao: () => { menu.esconder(); cenaExploracao(); } }], longe: 1.4
    });
    const el = document.getElementById('relatorioHTML');
    if (el) {
      const nomeVar = v => `indícios: ${v.indicios} · consentimento: ${v.consentimento} · segurança: ${v.seguranca} · fuga: ${v.fuga} · responsável: ${v.responsavel} · suborno: ${v.suborno}`;
      const leis = Object.entries(CEN.base_legal).filter(([k]) => k !== '_nota').map(([k, t]) => `<li><b>${k}</b> — ${t}</li>`).join('');
      el.innerHTML = `<h2>Nota ${r.nota}/100 — ${r.aprovado ? 'aprovado' : 'não aprovado'}</h2>
        <p>Tempo ${r.tempo} · modo ${r.modo}</p>
        <ul>${r.atendimentos.map(a => `<li>${a.titulo} — <em>${nomeVar(a.variacao)}</em></li>`).join('')}</ul>
        ${r.fases.map(f => `<h3>${f.nome} <small>${f.obtidos}/${f.possiveis}</small></h3><ul>${f.itens.map(i => `<li class="${i.ok ? 'ok' : 'nao'}">${i.ok ? '✓' : '✗'} ${i.texto}${varios ? ` [ocorr. ${i.atendimento}]` : ''}${i.base ? ` <em>(${i.base})</em>` : ''}</li>`).join('')}</ul>`).join('')}
        <h3>Erros e falhas graves</h3><ul>${txtErros.split('\n').map(l => `<li>${l}</li>`).join('')}</ul>
        <h3>Base legal</h3><ul>${leis}</ul>
        <p><em>Rascunho para validação com instrutores da instituição. Os itens marcados “validar” dependem de norma interna.</em></p>
        <p><button type="button" id="baixarRel">Baixar relatório (JSON)</button> <button type="button" id="fecharRel">Fechar</button></p>`;
      el.hidden = false;
      document.getElementById('baixarRel').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' })); a.download = `relatorio_${r.cenario}_${Date.now()}.json`; a.click(); };
      document.getElementById('fecharRel').onclick = () => el.hidden = true;
    }
  }

  /* ================= modo exploracao (antes de iniciar): cena livre, personagens respondem ================= */
  function cenaExploracao() {
    S.variacao = derivar({ ...CEN.historia[0].variacao }); criarNPCs(S.variacao); S.vida = 3; S.municao = CARREGADOR; limparSangue();
    for (const it of Object.values(itens)) it.o.visible = true;
    lacres.visible = false; moverEstante(false, .1); moverCofre(false, .1); moverPorta('salao', 1, .1); moverPorta('escritorio', 1, .1); moverPorta('fundos', 0, .1);
  }
  function explorar(ray) {
    const hi = ray.intersectObjects([...hitsItem.filter(h => h.userData.item !== 'dinheiro_cofre' || cofre?.aberto), ...hitCofre(), ...(estante ? [estante.col] : []), ...Object.values(portas).map(p => p.col)], false)[0];
    const hn = ray.intersectObjects(Object.values(npcs).filter(n => n.visible).map(n => n.userData.hit), false)[0];
    if (hn && hn.distance < 6 && (!hi || hn.distance < hi.distance)) {
      const n = Object.values(npcs).find(p => p.userData.hit === hn.object), k = n.userData.chave, E = CEN.exploracao;
      diz(n, k === 'parceiro' ? CEN.equipe.pm_parceiro : k === 'apoio' ? CEN.equipe.pm_apoio : E[k] || E.apostador, n.userData.sentado ? null : 'falando'); return true;
    }
    if (hi && hi.distance < 4.5) {
      if (hi.object.userData.estante) usarEstante();
      else if (hi.object.userData.cofre) moverCofre(true);
      else if (hi.object.userData.porta) { const k = hi.object.userData.porta; moverPorta(k, portas[k].frac > .5 ? 0 : 1); }
      else legenda('Vestígio', INFO_ITEM[hi.object.userData.item], 6);
      return true;
    }
    return false;
  }

  /* ================= clique / gatilho ================= */
  function usar(ray, c) {
    for (const p of paineis) if (p.clique(ray)) return true;
    if (S.granadaNaMao && c?.userData.mao === 'left') { S.granadaArmada = true; window.__som?.tocar('algemas', null, false, { vol: .3 }); legenda('Granada', 'Pino puxado. Solte o gatilho no fim do movimento.', 2.5); return true; }
    if (S.armaNaMao && (!c || c.userData.mao !== 'left')) return disparar(ray);
    { const sj = npcs.apostador_1; if (sj?.userData.saindo && sj.visible) { const h = ray.intersectObject(sj.userData.hit, false)[0]; if (h && h.distance < 14) { ordemVerbal(sj); return true; } } }      // apontar e clicar nele, mesmo de longe
    if (!S.ativo) return explorar(ray);
    if (!A || A.fase === 'fim') return false;
    const hn = ray.intersectObjects(Object.values(npcs).filter(n => n.visible).map(n => n.userData.hit), false)[0];
    const hi = ray.intersectObjects([...hitsItem.filter(h => h.userData.item !== 'dinheiro_cofre' || cofre?.aberto), ...hitCofre(), hitArma, ...(estante ? [estante.col] : []), ...Object.values(portas).filter(p => p.frac <= .5 || p === portas.salao || p === portas.escritorio || p === portas.fundos).map(p => p.col)], false)[0];
    if (hn && hn.distance < 5 && (!hi || hn.distance < hi.distance)) {
      const n = Object.values(npcs).find(p => p.userData.hit === hn.object), k = n.userData.chave;
      if (n.userData.caido) painelOpc('Ferido', 'Pessoa baleada', CEN.dialogos.socorro, op => { if (op.acao) { A.socorro = true; radio(CEN.radio.socorro); } });
      else if (k === 'parceiro') menuParceiro();
      else if (k === 'apoio') diz(n, CEN.equipe.pm_apoio);
      else if (k === 'atendente') menuAtendente();
      else if (k === 'seguranca') (A.anunciou ? menuSeguranca() : null);
      else if (k === 'atirador') (n.userData.ameaca ? legenda('Homem armado', 'Ele não obedece e continua atirando.', 3) : A.salaSecreta ? legenda('Homem do sofá', 'Rendido e desarmado. Preso em flagrante, aguardando a condução.', 3) : null);
      else if (k === 'seguranca_2') legenda('Homem armado', n.userData.ameaca ? 'Ele não obedece e continua atirando.' : 'Rendido e desarmado. Preso em flagrante, aguardando a condução.', 3);
      else if (k === 'responsavel') menuResponsavel();
      else menuPessoa(n);
      return true;
    }
    if (hi && hi.distance < 4) {
      const u = hi.object.userData;
      if (u.estante) usarEstante();
      else if (u.cofre) menuCofre();
      else if (u.porta === 'salao') menuPortaSalao();
      else if (u.porta === 'escritorio') menuEscritorio();
      else if (u.porta === 'fundos') { if (A.entrou) moverPorta('fundos', portas.fundos.frac > .5 ? 0 : 1); }
      else if (u.item === 'arma') { if (armaSolta.visible) menuSeguranca(); else return false; }
      else usarItem(u.item);
      return true;
    }
    return false;
  }
  function arremessar(c) {
    const o = new THREE.Vector3(), d = new THREE.Vector3(), fonte = (c && renderer.xr.isPresenting) ? c : camera;
    fonte.getWorldPosition(o); fonte.getWorldDirection(d); if (fonte !== camera) d.negate();
    if (fonte === camera) o.y -= .15;
    lancarGranada(o, d);
  }
  function botao(mao) { if (mao === 'right') sacar(!S.armaNaMao); else if (renderer.xr.isPresenting) pegarGranada(!S.granadaNaMao); else arremessar(); }

  /* ================= objetivos (modo treino) e status ================= */
  function objetivos() {
    const L = [], v = S.variacao;
    if (!A) return ['Aguarde a próxima ocorrência'];
    if (A.fase === 'fim') return ['Ocorrência concluída'];
    if (A.ameaca) return ['Agressão armada: proteja-se e reaja com o meio necessário (arma ou granada)', `Sua condição: ${S.vida ?? 3} de 3`];
    if (A.ferido && !A.socorro) L.push('Peça socorro médico pelo rádio (menu)');
    if (!A.entrou) {
      if (!A.chegada) L.push('Informe a chegada pelo rádio (menu)');
      if (!A.plano) L.push('Combine a entrada com o parceiro');
      if (!A.apoio) L.push('Peça apoio para cobrir os fundos (menu)');
      if (!A.abriu) L.push('Entre no bar e fale com a funcionária');
      else if (!A.decidiuEntrada) L.push('Observe a porta “PRIVATIVO” e decida se pode entrar');
      else if (A.entrada) L.push('Entre no salão pelos fundos do bar');
      else L.push('Ocorrência registrada sem entrada');
    } else {
      if (!A.anunciou) L.push('Anuncie a presença policial');
      if (v.arma === 'sim' && !A.rendeu && !npcs.seguranca?.userData.caido) L.push('Fale com o homem perto da entrada');
      else if (v.arma === 'sim' && !A.algemou) L.push('Recolha a arma e algeme quem estava armado');
      if (!S.feitos.has('reunir_pessoas')) L.push('Reúna as pessoas junto à parede');
      if (!S.feitos.has('qualificar_apostadores')) L.push('Qualifique os apostadores');
      if (!S.feitos.has('identificar_responsavel')) L.push(v.responsavel === 'presente' ? 'Identifique o responsável' : 'Pergunte pelo dono à funcionária do bar');
      if (!A.maquinas) L.push('Relacione e lacre as máquinas');
      if (!A.apreendidos?.has('dinheiro_mesa')) L.push('Apreenda o dinheiro da mesa');
      if (!A.escritorio) L.push('Decida o que fazer com o escritório trancado');
      if (!A.salaSecreta) L.push('Vistorie todos os cômodos, inclusive o depósito do bar');
      else if (!A.apreendidos?.has('dinheiro_sala')) L.push('Procure dinheiro na sala reservada');
      if (!A.decidiu) L.push('Encerre pelo rádio: enquadramento e condução (menu)');
    }
    return L.slice(0, 6);
  }
  function status() {
    const el = document.getElementById('statusTrein'); if (!el) return;
    el.hidden = !S.ativo || S.modo === 'treino';
    el.innerHTML = `<b>${A ? A.titulo : 'Cassino clandestino'}</b> · ${fmt(tempo())}<br>Na mão: ${S.armaNaMao ? (S.recarregando ? 'arma (recarregando…)' : `arma · ${S.municao ?? CARREGADOR}/${CARREGADOR}`) : 'nada'} · granadas: ${S.granadas ?? 2}`;
    mostrarObjetivos();
  }

  /* ================= quadro ================= */
  let ultimo = performance.now();
  function quadro() {
    const agora = performance.now(), dt = Math.min(.1, (agora - ultimo) / 1000); ultimo = agora;
    if (agora > legAte) { leg.visible = false; const hl = document.getElementById('legendaHTML'); if (hl && !hl.hidden) hl.hidden = true; }
    efeitos(dt); confronto();
    if (renderer.xr.isPresenting) for (const g of ctx.grips || []) { const quer = !((g.userData.mao === 'right' && S.armaNaMao) || (g.userData.mao === 'left' && S.granadaNaMao)); if (g.visible !== quer) g.visible = quer; }
    if (S.granadaNaMao && granadaMao.parent !== camera) {      // guarda as ultimas posicoes da mao para medir a velocidade do arremesso
      granadaMao.getWorldPosition(AM); amostras.push({ p: AM.clone(), t: agora }); if (amostras.length > 12) amostras.shift();
    }
    camera.getWorldPosition(V); camera.getWorldDirection(V2);
    if (S.ativo && A && A.entrada && !A.entrou && noSalao(V)) aoEntrarNoSalao();
    if (S.ativo && A && !A.parceiroNoBar && A.parceiroJunto && noBar(V) && !A.decidiuEntrada && npcs.parceiro && !npcs.parceiro.userData.rota?.length && !npcs.parceiro.userData.destino) { A.parceiroNoBar = true; rota(npcs.parceiro, [[-3.6, 4.6]], 1.5, 'andando'); }
    for (const n of Object.values(npcs)) {
      const u = n.userData;
      u.mixer?.update(dt);
      animarRosto(n, dt, agora);
      if (!u.caido) olhar(n, dt, V);
      ajustarAreaClique(n);
      moverNPC(n, dt);
      camera.getWorldPosition(V);
      if (u.caido) continue;
      const encarar = u.ameaca || (u.real && !u.destino && !u.semVirar && !u.rota?.length && V.distanceTo(n.position) < 3.2 && (S.ativo ? (A?.anunciou || !/^apostador|seguranca|responsavel/.test(u.chave)) : true));
      if (encarar) { let d = Math.atan2(V.x - n.position.x, V.z - n.position.z) - n.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d)); n.rotation.y += d * Math.min(1, dt * (A?.ameaca ? 6 : 2.5)); }
      else if (u.fig && !u.fala && !u.destino && !u.rota?.length) { let d = u.giroBase - n.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d)); n.rotation.y += d * Math.min(1, dt * 1.2); }
    }
    miraNoApostador(dt);
    if (!S.ativo && !livreSaiu && noSalao(V) && npcs.apostador_1?.userData.real) { livreSaiu = true; setTimeout(tentarSair, 1200); }      // modo livre: reage quando o policial entra no salao
    seguirArmaNPC();
    if (Math.floor(agora / 500) !== Math.floor((agora - dt * 1000) / 500)) {        // sons que saem dos comodos fechados
      const som = window.__som;
      if (som?.nivel) {
        const silencio = S.ativo && A && S.variacao.indicios === 'nenhum' && !A.entrou;      // nessa variacao nao se ouve nada do bar
        som.nivel('maquinas_caca_niquel', portas.salao?.frac > .5 ? 1 : silencio ? 0 : .3);
        som.nivel('musica_sala_reservada', estante?.aberta ? 1 : .2);
      }
    }
    if (S.ativo && Math.floor(agora / 1000) !== Math.floor((agora - dt * 1000) / 1000)) status();
  }

  /* ================= entradas ================= */
  addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.repeat) return;
    if (e.code === 'KeyT') abrirMenu();
    if (e.code === 'KeyK' && S.ativo) abrirChecklist();
    if (e.code === 'KeyQ') sacar(!S.armaNaMao);
    if (e.code === 'KeyE') arremessar();
    if (e.code === 'KeyR') recarregar();
  });
  const bt = document.createElement('button'); bt.type = 'button'; bt.textContent = 'Iniciar treinamento'; bt.id = 'bTrein';
  bt.onclick = aviso; document.getElementById('acoes')?.prepend(bt);
  modelosProntos.then(() => { if (!S.ativo) cenaExploracao(); });

  window.__trein = {
    clique: ray => usar(ray), gatilho: (ray, c) => usar(ray, c), botao, recarregar, soltar,
    apontar, painelAberto: () => paineis.some(p => p.mesh.visible),
    menu: abrirMenu, quadro, estado: S, relatorio,
    // acesso para testes automatizados e para o instrutor
    _t: { comecar, encerrar, objetivos, sortear, derivar, novaOcorrencia, npcs, portas, moverPorta, itens, usarItem, sacar, disparar, lancarGranada, detonar, granadas, arremessar, falarRadio, menuParceiro, menuAtendente, menuPortaSalao, menuSeguranca, menuPessoa, menuResponsavel, menuEscritorio, decidirFinal, finalizar, reacoes, aoEntrarNoSalao, usar, arma, armaNPC, armaSolta, lacres, B, armaNPC2, armaSolta2, armaNPC3, armaSolta3, emboscada, ameacando, tiroInimigo, policialAtingido, sangue, manchas, soltos, recarregar, clarao, pegarGranada, soltar, granadaMao, amostras, mostrarControle, estante, moverEstante, usarEstante,
      ocorrencia: () => A, historico: HIST, botoes: () => (dialogo.mesh.visible ? dialogo : menu).botoes, painel: () => (dialogo.mesh.visible ? dialogo : menu.mesh.visible ? menu : null) }
  };
  return window.__trein;
}
