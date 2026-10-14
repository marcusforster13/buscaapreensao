// Busca e Apreensao - pecas que abrem: gavetas, portas de armario, portas dos comodos, tampas e o elevador.
// A cena traz uma raiz A_* para cada peca (na dobradica ou na frente da gaveta) e o cena.json diz como ela se move:
//   gaveta: desliza "curso" metros para a frente;  porta: gira "ang" radianos no eixo vertical (ou no eixo "x", deitado).
// No computador, um clique abre ou fecha. No Quest, apontar e apertar o gatilho segura a peca: ela acompanha o movimento
// da mao (puxar a gaveta, girar a porta); um toque rapido no gatilho abre ou fecha de uma vez.
import * as THREE from 'three';

export function iniciarAbrir(ctx) {
  const { scene, camera, rig, renderer, cena, CFG, estaticos, lmTex } = ctx;
  const PI = Math.PI, clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const V = new THREE.Vector3(), V2 = new THREE.Vector3(), Q = new THREE.Quaternion();
  const semCeu = t => { t.envMapIntensity = CFG.env_interior ?? .05; if (scene.environment && t.envMap !== scene.environment) { t.envMap = scene.environment; t.needsUpdate = true; } };      // dentro dos comodos: reflexo fraco, sem a luz do ceu
  const invisivel = () => new THREE.MeshBasicMaterial({ visible: false });
  scene.updateMatrixWorld(true);

  /* ---------- luz do comodo: le o lightmap do piso perto da peca (as pecas que abrem nao tem luz pre-calculada) ---------- */
  const rc = new THREE.Raycaster(); rc.firstHitOnly = true;
  const BAIXO = new THREE.Vector3(0, -1, 0), telas = new Map();
  const ta = new THREE.Vector3(), tb = new THREE.Vector3(), tc = new THREE.Vector3(), bar = new THREE.Vector3(), pl = new THREE.Vector3();
  function pixels(tex) {
    if (!telas.has(tex)) {
      const im = tex.image, c = document.createElement('canvas'); c.width = im.width; c.height = im.height;
      const g = c.getContext('2d', { willReadFrequently: true }); g.drawImage(im, 0, 0); telas.set(tex, { g, w: im.width, h: im.height });
    }
    return telas.get(tex);
  }
  let ultimoDentro = false;      // o ultimo piso lido e de dentro de um comodo (ali o ceu nao ilumina: ver index.html)
  function luzNoPiso(p) {
    rc.set(V2.set(p.x, p.y, p.z), BAIXO); rc.far = 3.5;
    const h = rc.intersectObjects(estaticos, false)[0]; if (!h || !h.face) return null;
    const geo = h.object.geometry, uv1 = geo.attributes.uv1, pos = geo.attributes.position; if (!uv1) return null;
    let lm = null, o = h.object; while (o && !lm) { lm = CFG.lightmaps[o.name]; o = o.parent; }
    let q = h.object; ultimoDentro = false; while (q) { if (/^(03|04|05|06|07|10|11|12)_/.test(q.name)) ultimoDentro = true; q = q.parent; }
    if (!lm || !lmTex[lm.lm]) return null;
    ta.fromBufferAttribute(pos, h.face.a); tb.fromBufferAttribute(pos, h.face.b); tc.fromBufferAttribute(pos, h.face.c);
    THREE.Triangle.getBarycoord(h.object.worldToLocal(pl.copy(h.point)), ta, tb, tc, bar);
    const u = uv1.getX(h.face.a) * bar.x + uv1.getX(h.face.b) * bar.y + uv1.getX(h.face.c) * bar.z;
    const v = uv1.getY(h.face.a) * bar.x + uv1.getY(h.face.b) * bar.y + uv1.getY(h.face.c) * bar.z;
    const t = pixels(lmTex[lm.lm]), d = t.g.getImageData(clamp(Math.floor(u * t.w), 0, t.w - 1), clamp(Math.floor(v * t.h), 0, t.h - 1), 1, 1).data;
    return Math.pow((d[0] + d[1] + d[2]) / 765, 2.2) * lm.max * (lm.ganho ?? 1) * (ultimoDentro ? CFG.interior_site ?? .85 : 1);      // mesmo ajuste do interior em index.html
  }
  function luzLocal(centro, frente) {          // media de tres pontos do piso a frente da peca, sem os extremos (mancha de sol, sombra do movel)
    const vs = [];
    for (const k of [.35, .65, .95]) { const l = luzNoPiso(V.copy(centro).addScaledVector(frente, k).setY(centro.y + .6)); if (l != null) vs.push(l); }
    if (!vs.length) return null;
    vs.sort((a, b) => a - b); return clamp(vs[Math.floor(vs.length / 2)], .08, .9);
  }

  /* ---------- pecas ---------- */
  const pecas = [], malhas = [];
  const EIXOS = { x: new THREE.Vector3(1, 0, 0), y: new THREE.Vector3(0, 1, 0) };
  for (const [nome, d] of Object.entries(CFG.abre || {})) {
    const o = cena.getObjectByName(nome); if (!o) continue;
    o.updateWorldMatrix(true, true);
    const p = { nome, o, tipo: d.tipo, f: 0, alvo: 0, pos0: o.position.clone(), q0: o.quaternion.clone(), ms: [], trancada: false, tranca: !!d.tranca };
    const qW = o.getWorldQuaternion(new THREE.Quaternion()), pW = o.getWorldPosition(new THREE.Vector3());
    const caixa = new THREE.Box3(), inv = new THREE.Matrix4().copy(o.matrixWorld).invert(), bb = new THREE.Box3();
    o.traverse(m => {
      if (!m.isMesh) return;
      m.geometry.computeBoundsTree(); m.geometry.computeBoundingBox(); m.userData.peca = p; p.ms.push(m); malhas.push(m);
      caixa.union(bb.copy(m.geometry.boundingBox).applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, m.matrixWorld)));
    });
    if (!p.ms.length) continue;
    const meio = caixa.getCenter(new THREE.Vector3());
    if (d.tipo === 'gaveta') {
      p.curso = d.curso; p.dirL = new THREE.Vector3(0, 0, 1).applyQuaternion(o.quaternion);      // frente do movel no espaco do pai
      p.dirW = new THREE.Vector3(0, 0, 1).applyQuaternion(qW);
    } else {
      p.ang = d.ang; p.eixo = EIXOS[d.eixo === 'x' ? 'x' : 'y']; p.eixoW = p.eixo.clone().applyQuaternion(qW);
      // braco: da dobradica ate a borda livre (no espaco da peca), para converter o movimento da mao em giro
      p.braco = meio.clone().multiplyScalar(2).projectOnPlane(p.eixo); p.raio = Math.max(.25, p.braco.length());
    }
    // luz do comodo
    const frente = d.tipo === 'gaveta' ? p.dirW : new THREE.Vector3(0, 0, 1).applyQuaternion(qW).setY(0).normalize();
    const centroW = meio.clone().applyMatrix4(o.matrixWorld); centroW.y = pW.y;
    // portas de comodo e folhas do elevador: luz dos dois lados (a folha 2 do elevador esta girada e olharia para dentro da cabine)
    const ambos = d.colide || /^A_Elevador_/.test(nome);
    let L = luzLocal(centroW, frente); const L2 = ambos ? luzLocal(centroW, frente.clone().negate()) : null;
    if (L != null && L2 != null) L = /^A_Elevador_/.test(nome) ? Math.max(L, L2) : (L + L2) / 2; else if (L == null) L = L2;      // no elevador vale o lado do hall
    if (L != null) for (const m of p.ms) for (const mt of [].concat(m.material)) { mt.lightMapIntensity = L * PI * 1.1; mt.userData.luzBase = mt.lightMapIntensity; if (ultimoDentro) semCeu(mt); }
    // portas dos comodos: enquanto fechadas, uma caixa invisivel entra na colisao
    if (d.colide) {
      const larg = d.larg || .88, col = new THREE.Mesh(new THREE.BoxGeometry(larg, 2.1, .12), invisivel());
      col.position.copy(pW).addScaledVector(V.set(1, 0, 0).applyQuaternion(qW), larg / 2); col.position.y += 1.05;
      col.quaternion.copy(qW); col.geometry.computeBoundsTree(); scene.add(col); col.updateMatrixWorld(true); p.col = col; ctx.colisao().push(col);
    }
    p.som = d.tipo === 'gaveta' ? 'movel_arrastado' : (d.colide ? 'porta_abrindo' : null);
    pecas.push(p);
  }

  function aplicar(p) {
    if (p.tipo === 'gaveta') p.o.position.copy(p.pos0).addScaledVector(p.dirL, p.curso * p.f);
    else p.o.quaternion.copy(p.q0).multiply(Q.setFromAxisAngle(p.eixo, p.ang * p.f));
    if (p.col) {
      const cols = ctx.colisao(), i = cols.indexOf(p.col);
      if (p.f > .5) { if (i >= 0) cols.splice(i, 1); } else if (i < 0) cols.push(p.col);
    }
  }
  function som(p) { if (p.som) { p.o.getWorldPosition(V); window.__som?.tocar(p.som, V.clone()); } }
  function alternar(p) {
    if (p.trancada) { aviso('Trancada', 'Esta porta está trancada.'); return; }
    p.alvo = p.f > .5 ? 0 : 1; som(p); ouvintes.forEach(fn => fn(p, p.alvo));
  }
  const ouvintes = [];          // o motor do treinamento registra aqui o que foi aberto (onde o aluno procurou)
  function aviso(t, m) { const el = document.getElementById('legendaHTML'); if (!el) return; el.hidden = false; el.innerHTML = `<b>${t}</b> · ${m}`; clearTimeout(aviso.t); aviso.t = setTimeout(() => el.hidden = true, 3500); }

  /* ---------- apontar: a peca mais proxima no raio, se nao houver parede ou movel na frente ---------- */
  const ALCANCE = 3.2;
  function alvoDe(ray) {
    const far0 = ray.far; ray.far = ALCANCE; ray.firstHitOnly = true;
    const h = ray.intersectObjects(malhas, false)[0], hE = h && ray.intersectObjects(estaticos, false)[0];
    ray.far = far0;
    if (!h || (hE && hE.distance < h.distance - .03)) return null;
    return h;
  }
  const realce = new Map();          // controle (ou 'mouse') -> peca realcada
  function realcar(chave, p) {
    const antes = realce.get(chave); if (antes === p) return;
    realce.set(chave, p);
    for (const q of [antes, p]) {
      if (!q) continue; const on = [...realce.values()].includes(q);
      for (const m of q.ms) for (const mt of [].concat(m.material)) { if (mt.emissive) { mt.emissive.setHex(on ? 0x3a2a10 : 0x000000); mt.emissiveIntensity = on ? 1 : (mt.userData.emi0 ?? 1); } }
    }
  }

  /* ---------- elevador: o botao de fora abre as portas; o painel de dentro fecha, muda de andar e abre de novo ---------- */
  const elev = [], ANDARES = ['Terreo', 'Andar_3'];
  const folhas = k => pecas.filter(p => p.nome.startsWith('A_Elevador_' + k + '_'));
  const portasElev = (k, f) => { for (const p of folhas(k)) { if (p.alvo !== f) { p.alvo = f; } } if (folhas(k).length) window.__som?.tocar('porta_abrindo'); };
  ANDARES.forEach((k, i) => {
    const fora = CFG.pontos?.['Elevador_' + k], dentro = CFG.pontos?.['Cabine_' + k]; if (!fora || !dentro) return;
    const chamar = new THREE.Mesh(new THREE.BoxGeometry(.3, .5, .4), invisivel());            // botao de chamada, ao lado da porta
    chamar.position.set(fora.pos[0] - .62, fora.pos[1] + 1.15, fora.pos[2] - .62); chamar.userData.elevador = { tipo: 'chamar', k };
    const painel = new THREE.Mesh(new THREE.BoxGeometry(.45, .8, .25), invisivel());          // botoeira dentro da cabine
    painel.position.set(dentro.pos[0] + .52, dentro.pos[1] + 1.2, dentro.pos[2] - .62); painel.userData.elevador = { tipo: 'painel', k, outro: ANDARES[1 - i] };
    for (const h of [chamar, painel]) { scene.add(h); h.updateMatrixWorld(true); elev.push(h); }
  });
  let viajando = false;
  function usarElevador(h) {
    const u = h.userData.elevador;
    if (u.tipo === 'chamar') { const aberta = folhas(u.k).some(p => p.alvo > .5); portasElev(u.k, aberta ? 0 : 1); if (!aberta) aviso('Elevador', 'Entre e aperte o painel de botões.'); return; }
    if (viajando) return; viajando = true;
    const de = CFG.pontos['Cabine_' + u.k], para = CFG.pontos['Cabine_' + u.outro];
    portasElev(u.k, 0);
    setTimeout(() => {
      rig.position.x += para.pos[0] - de.pos[0]; rig.position.z += para.pos[2] - de.pos[2]; rig.position.y += para.pos[1] - de.pos[1];
      aviso('Elevador', u.outro === 'Terreo' ? 'Térreo: portaria.' : '3º andar.');
      setTimeout(() => { portasElev(u.outro, 1); viajando = false; }, 900);
    }, 1300);
  }
  function elevadorNoRaio(ray) { const far0 = ray.far; ray.far = 2.5; const h = ray.intersectObjects(elev, false)[0]; ray.far = far0; return h; }

  /* ---------- computador: clique ---------- */
  function clique(ray) {
    const h = alvoDe(ray);
    if (h) { alternar(h.object.userData.peca); return true; }
    const e = elevadorNoRaio(ray); if (e) { usarElevador(e.object); return true; }
    return false;
  }

  /* ---------- Quest: segurar com o gatilho ---------- */
  const maos = new Map();          // controle -> { p, ult, andou, t0 }
  function pegar(ray, c) {
    const h = alvoDe(ray);
    if (!h) { const e = elevadorNoRaio(ray); if (e) { usarElevador(e.object); return true; } return false; }
    const p = h.object.userData.peca;
    if (p.trancada) { aviso('Trancada', 'Esta porta está trancada.'); return true; }
    maos.set(c, { p, ult: c.getWorldPosition(new THREE.Vector3()), andou: 0, t0: performance.now(), f0: p.f });
    p.alvo = p.f; return true;
  }
  function soltar(c) {
    const m = maos.get(c); if (!m) return false; maos.delete(c);
    const p = m.p;
    if (m.andou < .03 && performance.now() - m.t0 < 600) { p.f = m.f0; alternar(p); }      // toque rapido: abre ou fecha de uma vez
    else { p.alvo = p.f < .08 ? 0 : p.f; if (Math.abs(p.f - m.f0) > .1) { som(p); ouvintes.forEach(fn => fn(p, p.alvo)); } }
    return true;
  }
  const tang = new THREE.Vector3(), mao = new THREE.Vector3(), dm = new THREE.Vector3();
  function arrastar() {
    for (const [c, m] of maos) {
      const p = m.p; c.getWorldPosition(mao); dm.subVectors(mao, m.ult); m.ult.copy(mao); m.andou += dm.length();
      if (p.tipo === 'gaveta') p.f = clamp(p.f + dm.dot(p.dirW) / p.curso, 0, 1);
      else {
        // direcao em que a borda livre anda agora: eixo x braco (no mundo), no sentido de abrir
        p.o.getWorldQuaternion(Q); tang.copy(p.braco).applyQuaternion(Q); tang.crossVectors(V.copy(p.eixo).applyQuaternion(Q), tang).normalize().multiplyScalar(Math.sign(p.ang));
        p.f = clamp(p.f + dm.dot(tang) / (p.raio * Math.abs(p.ang)), 0, 1);
      }
      p.alvo = p.f; aplicar(p);
    }
  }

  /* ---------- a cada quadro ---------- */
  let tAnt = performance.now();
  function quadro(raios) {
    const agora = performance.now(), dt = Math.min(.05, (agora - tAnt) / 1000); tAnt = agora;
    arrastar();
    for (const p of pecas) {
      if (p.f === p.alvo) continue;
      const passo = dt * (p.tipo === 'gaveta' ? 2.6 : 2.0), d = p.alvo - p.f;
      p.f = Math.abs(d) <= passo ? p.alvo : p.f + Math.sign(d) * passo; aplicar(p);
    }
    if (raios) raios.forEach((r, i) => { const m = maos.get(r.controle); realcar(i, m ? m.p : (r.ray ? alvoDe(r.ray)?.object.userData.peca : null) || null); });
  }
  function apontarMouse(ray) { realcar('mouse', alvoDe(ray)?.object.userData.peca || null); }

  // miudezas sem lightmap (objetos sobre os moveis, quadros, itens soltos; juntos em poucas malhas que cobrem o predio todo):
  // cada vertice recebe, como cor, a luz da superficie logo abaixo dele (lida no lightmap, em celulas de 30 cm). Os que ficam
  // dentro dos comodos perdem a luz do ceu, como as paredes.
  const comLm = estaticos.filter(o => o.geometry.attributes.uv1), salvo = estaticos.slice();
  estaticos.length = 0; estaticos.push(...comLm);
  const cel = new Map(), VW = new THREE.Vector3();
  function luzCelula(p) {
    const k = Math.floor(p.x / .3) + ',' + Math.floor(p.y / .5) + ',' + Math.floor(p.z / .3);
    if (!cel.has(k)) { const l = luzNoPiso(V.set(p.x, p.y + .25, p.z)); cel.set(k, l == null ? null : [clamp(l, .08, .9), ultimoDentro]); }
    return cel.get(k);
  }
  cena.traverse(m => {
    if (!m.isMesh || m.userData.peca || !/14_Miudos/.test(m.parent?.name + m.name)) return;
    const mts = [].concat(m.material); if (!mts.every(t => t.lightMap?.image?.width === 1)) return;
    const pos = m.geometry.attributes.position, cor = new Float32Array(pos.count * 3); let dentro = 0;
    for (let i = 0; i < pos.count; i++) {
      VW.fromBufferAttribute(pos, i).applyMatrix4(m.matrixWorld);
      const c = luzCelula(VW), l = c ? c[0] : .6; if (c && c[1]) dentro++;
      cor[i * 3] = cor[i * 3 + 1] = cor[i * 3 + 2] = l / .9;
    }
    m.geometry.setAttribute('color', new THREE.BufferAttribute(cor, 3));
    for (const t of mts) { t.vertexColors = true; t.lightMapIntensity = .9 * PI * 1.1; t.needsUpdate = true; if (dentro > pos.count / 2) semCeu(t); }
  });
  estaticos.length = 0; estaticos.push(...salvo);

  const api = {
    clique, pegar, soltar, quadro, apontarMouse, pecas, ouvintes, aviso, luzLocal, get dentro() { return ultimoDentro; },
    segurando: c => maos.has(c),
    abrir(nome, f = 1, jaAgora = false) { const p = pecas.find(q => q.nome === nome); if (!p) return; p.alvo = f; if (jaAgora) { p.f = f; aplicar(p); } },
    trancar(nome, sim = true) { const p = pecas.find(q => q.nome === nome); if (p) p.trancada = sim; },
    fecharTudo() { for (const p of pecas) { p.alvo = p.f = 0; aplicar(p); } },
    get abertas() { return pecas.filter(p => p.f > .5).map(p => p.nome); },
  };
  window.__abrir = api;
  return api;
}
