/*
  Monitoramento pelo instrutor (portal XPTO VR) — o mesmo arquivo nas 6 fases.
  So e carregado quando o endereco tem ?monitor=1 (aluno transmite) ou ?espectador=1 (tela do instrutor, dentro do portal).
  Sem esses parametros o treinamento funciona exatamente como antes: este arquivo nem e baixado.

  aluno      : conexao direta (WebRTC, PeerJS) com o codigo mostrado na tela; envia so DADOS (pose da cabeca, personagens,
               portas, estado do treinamento, painel aberto). Recebe do instrutor: mensagens e comandos (iniciar, pausar,
               retomar, encerrar, eventos). Se a conexao cair, o treino segue normalmente.
  espectador : recebe esses dados do portal (postMessage) e redesenha a cena: visao do aluno ou camera de ombro.

  ctx (do index.html): { scene, camera, rig, renderer, fase, modo, cenarios: [json...], modos: [[chave, nome]...] }
  O motor expoe window.__trein._mon (legenda, personagem, animar, menu, dialogo, relatorio, estado, ...).
*/
import * as THREE from 'three';

const ORIGENS_PORTAL = [/^https:\/\/portalxptovr(-[\w-]+)?\.vercel\.app$/, /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/];

export async function iniciar(ctx) {
  return ctx.modo === 'espectador' ? espectador(ctx) : aluno(ctx);
}

const motor = () => new Promise(res => { const t = () => window.__trein?._mon ? res(window.__trein) : setTimeout(t, 300); t(); });
const url = p => window.__h ? window.__h(p) : p;

/* ====================================================================== aluno */
async function aluno({ camera, scene, renderer, rig, fase, cenarios = [], modos = [] }) {
  const { Peer } = await import('https://cdn.jsdelivr.net/npm/peerjs@1.5.4/+esm');
  const T = await motor(), M = T._mon, S = M.estado;

  // catalogo das acoes de cada cenario (c = indice do cenario: 0 = principal, 1 = missao extra)
  const catalogo = {}, nomesVar = {}; let variacoes = {};
  for (const [c, arq] of cenarios.entries()) {
    try {
      const j = await fetch(url(arq)).then(r => r.json());
      Object.assign(nomesVar, j.nomes_variacao || {}); if (c === 0) variacoes = j.variacoes || {};
      for (const f of j.fases || []) for (const [lista, tipo] of [['acoes', 'acao'], ['erros', 'erro'], ['falhas_graves', 'grave']])
        for (const a of f[lista] || []) if (!catalogo[a.id] || c === 0) catalogo[a.id] = { texto: a.texto, pontos: a.pontos, base: a.base || '', tipo, fase: f.nome || f.id, c };
    } catch (e) { }
  }

  // o que o aluno tem aberto na frente dele (menus e dialogos 3D)
  for (const p of [M.menu, M.dialogo]) {
    if (!p?.mostrar) continue;
    const mo = p.mostrar.bind(p), es = p.esconder?.bind(p);
    p.mostrar = d => { p.__mon = { tag: d?.tag || '', titulo: d?.titulo || '', texto: String(d?.texto || '').slice(0, 900), botoes: (d?.botoes || []).map(b => b.label).slice(0, 12) }; return mo(d); };
    if (es) p.esconder = (...a) => { p.__mon = null; return es(...a); };
  }
  const telaAtual = () => { for (const p of [M.dialogo, M.menu]) if (p?.mesh?.visible && p.__mon) return p.__mon; return null; };

  // selo na tela (2D) com o codigo
  const selo = document.createElement('div');
  selo.style.cssText = 'position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:9999;font:600 15px Segoe UI,sans-serif;color:#e8edf7;background:rgba(5,7,15,.85);border:1px solid #00d4e6;border-radius:999px;padding:8px 18px;letter-spacing:.04em;pointer-events:none';
  document.body.append(selo);
  const conexoes = new Set();
  let codigo = '', peer = null;
  const atualizarSelo = () => selo.innerHTML = `<span style="color:#ff5a5a">●</span> Monitoramento · código <b style="color:#5cf0ff;letter-spacing:.15em">${codigo}</b> · ${conexoes.size ? 'instrutor conectado' : 'aguardando instrutor'}`;
  const avisarVR = (t, s = 7, quem = 'Monitoramento') => { try { M.legenda(quem, t, s); } catch (e) { } };

  function abrir() {
    codigo = String(Math.floor(10000 + Math.random() * 90000));
    peer = new Peer('xptovr-' + codigo, { debug: 0 });
    peer.on('open', () => { atualizarSelo(); avisarVR(`Código para o instrutor: ${codigo}`, 10); });
    peer.on('error', e => { if (e.type === 'unavailable-id') { peer.destroy(); abrir(); } else console.warn('monitor:', e.type); });
    peer.on('disconnected', () => { try { peer.reconnect(); } catch (e) { } });
    peer.on('connection', c => {
      c.on('open', () => {
        conexoes.add(c); atualizarSelo(); avisarVR('Instrutor conectado.', 4);
        c.send({ tipo: 'ola', fase, titulo: document.title, url: location.origin + location.pathname, catalogo, nomesVar, variacoes, modos });
        enviarEstado(true);
      });
      c.on('data', m => {
        if (m?.tipo === 'mensagem' && typeof m.texto === 'string') avisarVR(m.texto.slice(0, 220), Math.min(14, 4 + m.texto.length / 18), m.como === 'central' ? 'Central (rádio)' : 'Instrutor');
        else if (m?.tipo === 'comando') comando(m);
      });
      c.on('close', () => { conexoes.delete(c); atualizarSelo(); });
    });
  }
  abrir();
  renderer.xr.addEventListener('sessionstart', () => setTimeout(() => avisarVR(conexoes.size ? 'Monitoramento ativo.' : `Código para o instrutor: ${codigo}`, 8), 1500));

  /* ---------- controles do instrutor ---------- */
  let pausado = false, tPausa = 0, posPausa = null;
  const veuP = new THREE.Mesh(new THREE.PlaneGeometry(4, 4), new THREE.MeshBasicMaterial({ color: 0x02040a, transparent: true, opacity: .82, depthTest: false, toneMapped: false, fog: false }));
  const tcv = document.createElement('canvas'); tcv.width = 1024; tcv.height = 256;
  { const g = tcv.getContext('2d'); g.textAlign = 'center'; g.fillStyle = '#5cf0ff'; g.font = '600 38px Segoe UI, sans-serif'; g.fillText('TREINO PAUSADO PELO INSTRUTOR', 512, 110); g.fillStyle = '#c3cbdb'; g.font = '30px Segoe UI, sans-serif'; g.fillText('Aguarde. O treino continua de onde parou.', 512, 170); }
  const texP = new THREE.CanvasTexture(tcv); texP.colorSpace = THREE.SRGBColorSpace;
  const txtP = new THREE.Mesh(new THREE.PlaneGeometry(.64, .16), new THREE.MeshBasicMaterial({ map: texP, transparent: true, depthTest: false, toneMapped: false, fog: false }));
  // texto a 80 cm: confortavel no Quest
  veuP.position.z = -.29; txtP.position.z = -.8;
  veuP.renderOrder = 2000; txtP.renderOrder = 2001; veuP.visible = txtP.visible = false; camera.add(veuP, txtP);
  // embrulha a interacao do jogo: pausado, nada anda e nenhum clique vale
  const quadroOrig = T.quadro;
  T.quadro = (...a) => { if (!pausado) return quadroOrig?.(...a); };
  for (const k of ['clique', 'gatilho', 'botao', 'recarregar', 'menu']) { const f = T[k]; if (typeof f === 'function') T[k] = (...a) => pausado ? true : f(...a); }
  const antes = scene.onBeforeRender;
  scene.onBeforeRender = (...a) => { antes?.(...a); if (pausado && posPausa) { rig.position.copy(posPausa); rig.updateMatrixWorld(true); } };
  function pausar(sim) {
    if (sim === pausado) return;
    pausado = sim; veuP.visible = txtP.visible = sim;
    if (sim) { tPausa = performance.now(); posPausa = rig.position.clone(); try { speechSynthesis.pause(); } catch (e) { } }
    else {
      const d = performance.now() - tPausa; posPausa = null;
      if (S.inicio) S.inicio += d; const A = M.ocorrencia?.(); if (A) { if (A.t0) A.t0 += d; if (A.tAmeaca) A.tAmeaca += d; }
      const C = S.crise?.estado; if (C?.t0) C.t0 += d;
      try { speechSynthesis.resume(); } catch (e) { } avisarVR('Treino retomado.', 3, 'Instrutor');
    }
    enviarEstado(true);
  }
  // eventos que o instrutor pode disparar (so onde o motor tem a funcao)
  function eventos() {
    const A = M.ocorrencia?.(), lst = [];
    if (fase === 'ciep' && T._t.comecarFilmar) lst.push({ id: 'filmar', label: 'Responsável começa a filmar', ok: !!(S.ativo && A && !A.filmando && !A.ameacaAtiva) });
    if (fase === 'ciep' && T._t.escalar) lst.push({ id: 'disparos', label: 'Antecipar a ameaça (disparos no corredor)', ok: !!(S.ativo && A && S.variacao?.origem === 'ameaca_real' && !A.ameacaAtiva), so: 'só na variação de ameaça real' });
    return lst;
  }
  function comando(m) {
    try {
      const emCurso = S.ativo || (S.crise && !S.crise.estado?.fim);
      if (m.acao === 'iniciar' && !emCurso && modos.some(([k]) => k === m.modo)) {
        const v = Object.entries(m.variacao || {}).filter(([k, x]) => variacoes[k]?.includes(x)).map(([k, x]) => `${k}:${x}`).join(',');
        const u = new URL(location.href); v ? u.searchParams.set('v', v) : u.searchParams.delete('v'); history.replaceState(null, '', u);
        pausar(false);
        if (m.modo.startsWith('crise:') && M.iniciarCrise) { const [, papel, modo] = m.modo.split(':'); M.iniciarCrise(papel, modo); setTimeout(() => avisarVR('O instrutor abriu a Missão Sala 201. Toque em Começar.', 6, 'Instrutor'), 2500); }
        else { T._t.comecar(m.modo === 'unico' ? undefined : m.modo); setTimeout(() => avisarVR('O instrutor iniciou o treinamento.', 4, 'Instrutor'), 800); }
      }
      else if (m.acao === 'pausar') pausar(true);
      else if (m.acao === 'retomar') pausar(false);
      else if (m.acao === 'encerrar') {
        pausar(false);
        if (S.crise && !S.crise.estado?.fim) S.crise.relatorio?.();
        else if (S.ativo) T._t.encerrar();
      }
      else if (m.acao === 'evento') {
        const e = eventos().find(x => x.id === m.id && x.ok); if (!e) return;
        if (e.id === 'filmar') T._t.comecarFilmar(); else if (e.id === 'disparos') T._t.escalar('disparos');
      }
    } catch (er) { console.warn('monitor comando:', er); }
    setTimeout(() => enviarEstado(true), 300);
  }

  const enviar = m => { for (const c of conexoes) if (c.open) try { c.send(m); } catch (e) { } };

  // pose da cabeca: 20 por segundo
  const P = new THREE.Vector3(), Q = new THREE.Quaternion();
  const r3 = v => Math.round(v * 1000) / 1000;
  setInterval(() => {
    if (!conexoes.size) return;
    const cam = renderer.xr.isPresenting ? renderer.xr.getCamera() : camera;
    cam.getWorldPosition(P); cam.getWorldQuaternion(Q);
    enviar({ tipo: 'pose', p: [r3(P.x), r3(P.y), r3(P.z)], q: [r3(Q.x), r3(Q.y), r3(Q.z), r3(Q.w)], vr: renderer.xr.isPresenting, arma: !!(S.armaNaMao || S.naMao === 'arma') });
  }, 50);

  // personagens e portas: 10 por segundo
  setInterval(() => {
    if (!conexoes.size) return;
    const lista = [];
    for (const n of scene.children) {
      if (!n.name?.startsWith('NPC_') || !n.visible || !n.userData?.real) continue;
      const u = n.userData;
      lista.push({ k: n.uuid, papel: u.papel, nome: u.nome, alt: r3(u.hit?.scale?.y || 1.7), p: [r3(n.position.x), r3(n.position.y), r3(n.position.z)], r: r3(n.rotation.y), a: u.pose || u.atual?.getClip?.().name?.replace(/\.\d+$/, '') || 'parada' });
    }
    const portas = {}; for (const [k, p] of Object.entries(M.portas || {})) if (p?.o) portas[k] = r3(p.o.rotation.y);
    enviar({ tipo: 'npcs', lista, portas });
  }, 100);

  // estado do treinamento: 2 por segundo (e na hora em que algo e registrado)
  let assinatura = '', fimEnviado = 0;
  function enviarEstado(forcar) {
    if (!conexoes.size) return;
    const C = S.crise?.estado, emCrise = !!(S.crise && C);
    const fonte = emCrise ? C : S, agora = pausado ? tPausa : performance.now();
    const t = emCrise ? ((C.fim ? (C.tFim ||= agora) : agora) - C.t0) / 1000 : S.inicio ? ((S.fim || agora) - S.inicio) / 1000 : 0;
    const tl = telaAtual();
    const ass = [fonte.log?.length, S.fim, C?.fim, C?.fase, C?.tensao, C?.vinculo, pausado, JSON.stringify(tl)].join('|');
    if (!forcar && ass === assinatura) { enviar({ tipo: 'relogio', ativo: emCrise ? !C.fim : S.ativo, pausado, t, eventos: eventos() }); return; }
    assinatura = ass;
    const A = emCrise ? null : M.ocorrencia?.();
    const est = {
      tipo: 'estado', cenario: emCrise ? 1 : 0, ativo: emCrise ? !C.fim : S.ativo, pausado, eventos: eventos(), t, tela: tl,
      modo: emCrise ? C.modo : S.historia ? 'historia' : S.modo, variacao: emCrise ? C.v : S.variacao,
      ocorrencia: emCrise ? { titulo: 'Missão Sala 201 · ' + (C.papel || ''), fatos: Object.keys(C.fatos || {}) } : A ? { titulo: A.titulo, n: A.n, fatos: A.fatos || [] } : null,
      crise: emCrise ? { fase: C.fase, tensao: Math.round(C.tensao), vinculo: Math.round(C.vinculo), refens: C.refens, resultado: C.resultado || '', papel: C.papel } : null,
      feitos: [...(fonte.feitos || new Map()).entries()], erros: (fonte.erros || []).map(e => ({ id: e.id, texto: e.texto, pontos: e.pontos, t: e.t })),
      graves: (fonte.graves || []).map(g => ({ id: g.id, texto: g.texto, pontos: g.pontos, base: g.base, t: g.t })), log: (fonte.log || []).slice(-200)
    };
    if (!emCrise && S.fim && S.fim !== fimEnviado) { fimEnviado = S.fim; try { est.relatorio = (M.relatorio || T.relatorio)?.(); } catch (e) { } }
    enviar(est);
  }
  setInterval(() => enviarEstado(false), 500);
}

/* ================================================================= espectador */
async function espectador({ camera, scene, renderer, rig, fase }) {
  // tela limpa: so a cena
  const canvas = renderer.domElement;
  const limpar = () => { for (const el of document.body.children) if (el !== canvas && !el.contains(canvas) && el.tagName !== 'SCRIPT') el.style.display = 'none'; };
  limpar(); setTimeout(limpar, 2000); setTimeout(limpar, 6000);
  window.__som?.mudo?.(true);

  const T = await motor(), M = T._mon;
  // paineis 3D do espectador nunca aparecem (o instrutor ve o painel do aluno no proprio monitor)
  for (const p of [M.menu, M.dialogo]) if (p?.mesh) { const mo = p.mostrar?.bind(p); if (mo) p.mostrar = d => { mo(d); p.mesh.visible = false; }; p.mesh.visible = false; }
  let uniformizar = null;
  if (fase === 'ciep') try { ({ uniformizar } = await import('./' + url('crise.js'))); } catch (e) { }

  // avatar do aluno (aparece na camera de ombro)
  const corpo = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color: 0x0a2a3a, emissive: 0x00d4e6, emissiveIntensity: .35, roughness: .5 });
  const tronco = new THREE.Mesh(new THREE.CapsuleGeometry(.22, .9, 6, 12), mat); tronco.position.y = -.85; corpo.add(tronco);
  const cabeca = new THREE.Mesh(new THREE.SphereGeometry(.13, 16, 12), mat); corpo.add(cabeca);
  const visor = new THREE.Mesh(new THREE.BoxGeometry(.2, .08, .08), new THREE.MeshBasicMaterial({ color: 0x5cf0ff })); visor.position.set(0, .01, -.12); cabeca.add(visor);
  const anel = new THREE.Mesh(new THREE.RingGeometry(.45, .52, 40), new THREE.MeshBasicMaterial({ color: 0x00d4e6, transparent: true, opacity: .8, side: THREE.DoubleSide }));
  anel.rotation.x = -Math.PI / 2; scene.add(anel); scene.add(corpo);

  let vista = 'aluno', alvoP = null, alvoQ = null, arma = false, armaMostrada = false, portas = {};
  const pos = new THREE.Vector3(), quat = new THREE.Quaternion(), E = new THREE.Euler(0, 0, 0, 'YXZ');
  const espelhos = new Map(); let listaNPC = [];

  addEventListener('message', ev => {
    if (!ORIGENS_PORTAL.some(r => r.test(ev.origin))) return;
    const m = ev.data; if (!m || typeof m !== 'object') return;
    if (m.tipo === 'pose') { alvoP = new THREE.Vector3(...m.p); alvoQ = new THREE.Quaternion(...m.q); arma = !!m.arma; }
    else if (m.tipo === 'npcs') { listaNPC = m.lista || []; portas = m.portas || {}; }
    else if (m.tipo === 'vista') vista = m.vista;
  });
  if (parent !== window) parent.postMessage({ tipo: 'espectador-pronto' }, '*');

  // espelha os personagens do aluno; esconde os que o espectador criou sozinho
  const criando = new Set();
  function sincronizar() {
    const vivos = new Set(listaNPC.map(n => n.k));
    for (const [k, e] of espelhos) if (!vivos.has(k)) { scene.remove(e.n); espelhos.delete(k); }
    for (const d of listaNPC) {
      const e = espelhos.get(d.k);
      if (e) { e.d = d; continue; }
      if (criando.has(d.k)) continue;
      criando.add(d.k);
      Promise.resolve(M.carregarPapeis?.(p => p === d.papel)).then(() => {
        const n = M.personagem(d.papel, d.nome, 0x3d4045, d.alt);
        n.name = 'ESP_' + d.nome; n.position.set(...d.p); n.rotation.y = d.r;
        if (/^refem_/.test(d.papel) && uniformizar) try { uniformizar(n, d.papel); } catch (er) { }
        scene.add(n); espelhos.set(d.k, { n, d, anim: null }); criando.delete(d.k);
      }).catch(() => criando.delete(d.k));
    }
    for (const n of scene.children) if (n.name?.startsWith('NPC_')) n.visible = false;
    for (const [k, y] of Object.entries(portas)) { const p = M.portas?.[k]; if (p?.o) p.o.rotation.y = y; }
    const querArma = arma && vista === 'aluno';
    if (M.sacar && querArma !== armaMostrada) { armaMostrada = querArma; try { M.sacar(querArma); } catch (er) { } }
  }
  setInterval(sincronizar, 150);

  const relogio = new THREE.Clock(), V = new THREE.Vector3(), atras = new THREE.Vector3();
  const anterior = scene.onBeforeRender;
  scene.onBeforeRender = (...args) => {
    anterior?.(...args);
    const dt = Math.min(relogio.getDelta(), .1), k = 1 - Math.exp(-dt * 14);
    for (const e of espelhos.values()) {
      const { n, d } = e;
      n.position.lerp(V.set(...d.p), k);
      let dr = d.r - n.rotation.y; dr = Math.atan2(Math.sin(dr), Math.cos(dr)); n.rotation.y += dr * k;
      if (e.anim !== d.a) { e.anim = d.a; try { M.animar(n, d.a, 1e6, .35); } catch (er) { } }
      n.userData.mixer?.update(dt);
      n.updateMatrixWorld(true);
    }
    if (!alvoP) return;
    pos.lerp(alvoP, k); quat.slerp(alvoQ, k);
    if (pos.lengthSq() === 0) { pos.copy(alvoP); quat.copy(alvoQ); }
    E.setFromQuaternion(quat);
    corpo.position.copy(pos); corpo.rotation.set(0, E.y, 0); cabeca.rotation.set(E.x, 0, 0);
    anel.position.set(pos.x, Math.max(0, pos.y - 1.58), pos.z);
    rig.rotation.set(0, 0, 0); rig.position.set(0, 0, 0);
    if (vista === 'aluno') {
      corpo.visible = false; anel.visible = false;
      camera.position.copy(pos); camera.quaternion.copy(quat);
    } else {
      corpo.visible = true; anel.visible = true;
      atras.set(Math.sin(E.y), 0, Math.cos(E.y)).multiplyScalar(2.2);
      camera.position.set(pos.x + atras.x, pos.y + .7, pos.z + atras.z);
      camera.lookAt(pos.x - atras.x * .8, pos.y - .25, pos.z - atras.z * .8);
    }
    rig.updateMatrixWorld(true); corpo.updateMatrixWorld(true); anel.updateMatrixWorld(true);
  };
}
