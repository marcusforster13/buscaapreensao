
  /* =====================================================================================================================
     BUSCA E APREENSAO - logica do cumprimento do mandado (o que vem acima e a base do motor do cassino: paineis, falas,
     personagens, rosto, olhar e objetivos)
     ===================================================================================================================== */
  const ABRIR = () => window.__abrir, MANDADO = () => window.__mandado;
  const B = (x, y, z = .15) => new THREE.Vector3(x, z, -y);                 // planta do Blender (X, Y) -> cena web
  const Z3 = 6.45, B3 = (x, y) => B(x, y, Z3);
  const olharPara = (dx, dy) => Math.atan2(dx, -dy);
  const suave = (seg, passo) => new Promise(fim => {
    const t0 = performance.now();
    const tic = () => { const k = Math.min(1, (performance.now() - t0) / (seg * 1000)); passo(k * k * (3 - 2 * k)); k < 1 ? setTimeout(tic, 16) : fim(); };
    tic();
  });
  const invisivel = () => new THREE.MeshBasicMaterial({ visible: false });
  const noApto = p => p.y > Z3 - .5 && p.x > -1.05 && p.x < 8.05 && -p.z > 1.62 && -p.z < 9.05;
  const andar3 = p => p.y > Z3 - .5;

  /* ================= itens: carregados do site (modelos/*.glb) ou feitos aqui; ficam dentro das gavetas e armarios ================= */
  const gl = new GLTFLoader();
  const MOD = {};
  for (const n of ['celular', 'notebook', 'arma']) gl.loadAsync(HQ('modelos/' + n + '.glb')).then(g => { MOD[n] = g.scene; g.scene.traverse(o => { if (o.isMesh) o.material = [].concat(o.material).map(m => ctx.iluminar(m.clone()))[0]; }); }).catch(() => { });
  const matSimples = (cor, r = .7) => ctx.iluminar(new THREE.MeshStandardMaterial({ color: cor, roughness: r }));
  function caixa(l, a, p, cor) { return new THREE.Mesh(new THREE.BoxGeometry(l, a, p), matSimples(cor)); }
  function feitoAqui(tipo) {
    const g = new THREE.Group();
    if (tipo === 'celular') { const c = caixa(.075, .009, .155, 0x15161a); g.add(c); const t = caixa(.068, .002, .145, 0x0b1a2a); t.position.y = .0055; g.add(t); }
    else if (tipo === 'notebook') { const b = caixa(.34, .022, .24, 0x2b2d31); g.add(b); const t = caixa(.34, .012, .24, 0x34373c); t.position.y = .017; g.add(t); }
    else if (tipo === 'documentos') { const p = caixa(.25, .03, .33, 0x6b4a2e); g.add(p); for (let k = 0; k < 3; k++) { const f = caixa(.21, .003, .29, 0xf3efe4); f.position.set(.005 * k, .017 + k * .003, .005 * k); f.rotation.y = .05 * k; g.add(f); } }
    else if (tipo === 'cartoes') { for (let k = 0; k < 4; k++) { const c = caixa(.086, .002, .054, [0x1f4fb8, 0xc0261e, 0x111111, 0xd9a514][k]); c.position.set(k * .02, k * .003, k * .01); c.rotation.y = k * .3; g.add(c); } }
    else if (tipo === 'droga') { for (let k = 0; k < 3; k++) { const t = caixa(.2, .05, .1, 0x9a8a5a); t.position.set(0, .025 + k * .052, 0); t.rotation.y = k * .2; g.add(t); } }
    else if (tipo === 'dinheiro') { for (let k = 0; k < 6; k++) { const m = caixa(.15, .02, .07, k % 2 ? 0x6f9a7a : 0x5d86a8); m.position.set((k % 2) * .16 - .08, .01 + Math.floor(k / 2) * .021, 0); g.add(m); } }
    else if (tipo === 'doc_terceiro') { const e = caixa(.24, .006, .17, 0xe9dfc4); g.add(e); const r = caixa(.05, .004, .03, 0x1c3f8a); r.position.set(.06, .005, -.04); g.add(r); }
    return g;
  }
  function modeloItem(tipo) {
    const base = tipo === 'arma' ? MOD.arma : tipo === 'celular' ? MOD.celular : tipo === 'notebook' ? MOD.notebook : null;
    if (!base) return feitoAqui(tipo);
    const m = base.clone(); const bb = new THREE.Box3().setFromObject(m), s = bb.getSize(new THREE.Vector3());
    const alvo = { celular: .155, notebook: .34, arma: .2 }[tipo]; m.scale.setScalar(alvo / Math.max(s.x, s.z, s.y));
    const g = new THREE.Group(); g.add(m); return g;
  }
  // onde cada coisa pode estar: [peca que abre (ou null: em cima de um movel), posicao local x, y, z] - coordenadas do site
  const LUGARES = {
    vista_mesa: [null, ...B3(4.75, 3.05).toArray().map((v, i) => i === 1 ? Z3 + .78 : v)],
    vista_mesa2: [null, ...B3(5.05, 3.4).toArray().map((v, i) => i === 1 ? Z3 + .78 : v)],
    vista_rack: [null, ...B3(6.0, 1.95).toArray().map((v, i) => i === 1 ? Z3 + .56 : v)],
    criado_b2: ['A_Gav_Criado_B_2', 0, .03, -.16], criado_a1: ['A_Gav_Criado_A_1', 0, .03, -.15],
    gr_gaveta_1: ['A_Gav_Guarda_Roupa_Casal_1', 0, .03, -.24], gr_gaveta_3: ['A_Gav_Guarda_Roupa_Casal_5', 0, .03, -.24],
    rack_gaveta: ['A_Gav_Rack_TV_3', 0, .03, -.15], bancada_gaveta: ['A_Gav_Bancada_4', 0, .03, -.2],
  };
  const itens = {};          // tipo -> { o, tipo, lugar, apreendido, fotografado, lacrado, isolado }
  const hitsItem = [];
  function limparItens() { for (const it of Object.values(itens)) it.o.removeFromParent(); for (const k in itens) delete itens[k]; hitsItem.length = 0; }
  function porItem(tipo, lugar) {
    const L = LUGARES[lugar]; if (!L) return;
    const o = modeloItem(tipo); o.name = 'Item_' + tipo; o.rotation.y = Math.random() * .6 - .3;
    if (L[0]) { const raiz = ctx.cena.getObjectByName(L[0]); if (!raiz) return; raiz.add(o); o.position.set(L[1], L[2], L[3]); }
    else { scene.add(o); o.position.set(L[1], L[2], L[3]); }
    const hit = new THREE.Mesh(new THREE.BoxGeometry(.3, .16, .3), invisivel()); hit.userData.item = tipo; o.add(hit); hitsItem.push(hit);
    itens[tipo] = { o, tipo, lugar, dentro: !!L[0], raiz: L[0] };
  }
  const NOME_ITEM = { celular: 'Celular', notebook: 'Notebook', documentos: 'Pasta de documentos', cartoes: 'Cartões bancários', arma: 'Arma de fogo (revólver)', droga: 'Tabletes de droga', dinheiro: 'Maços de dinheiro', doc_terceiro: 'Documentos de outra pessoa' };
  const DO_MANDADO = new Set(['celular', 'notebook', 'documentos', 'cartoes']);
  function distribuirItens(v) {
    limparItens();
    if (v.objeto === 'a_vista') { porItem('celular', 'vista_mesa'); porItem('notebook', 'vista_mesa2'); porItem('documentos', 'vista_rack'); porItem('cartoes', 'criado_a1'); }
    else if (v.objeto === 'escondido') { porItem('celular', 'gr_gaveta_3'); porItem('notebook', 'gr_gaveta_1'); porItem('documentos', 'criado_b2'); porItem('cartoes', 'rack_gaveta'); }
    if (v.extra === 'arma') porItem('arma', 'gr_gaveta_3');
    else if (v.extra === 'droga') porItem('droga', 'criado_a1');
    else if (v.extra === 'dinheiro') porItem('dinheiro', 'bancada_gaveta');
    else if (v.extra === 'documentos_terceiro') porItem('doc_terceiro', 'bancada_gaveta');
  }
  const lacres = new THREE.Group(); scene.add(lacres);
  function saco(tipo) {                                       // item lacrado: saco plastico com etiqueta, em cima da mesa de jantar
    const n = lacres.children.length, s = caixa(.24, .06, .32, 0xd8dde2); s.material.transparent = true; s.material.opacity = .85;
    const et = caixa(.08, .004, .05, 0xc0261e); et.position.set(.06, .032, .1); s.add(et);
    s.position.copy(B3(4.45 + (n % 3) * .27, 2.75 + Math.floor(n / 3) * .35)); s.position.y = Z3 + .79 + .03; lacres.add(s);
  }

  /* ================= arma de fogo e arma de choque (no coldre; o treinamento observa se e quando o aluno usa) ================= */
  const arma = new THREE.Group(), choque = new THREE.Group(); arma.visible = choque.visible = false;
  gl.loadAsync(HQ('modelos/arma.glb')).then(g => { g.scene.traverse(o => { if (o.isMesh) o.material = ctx.iluminar([].concat(o.material)[0].clone()); }); arma.add(g.scene); }).catch(() => { });
  {      // arma de choque (modelo generico, sem marca): corpo amarelo, cartucho preto na frente, cabo emborrachado, guarda-mato e gatilho
    const am = new THREE.MeshStandardMaterial({ color: 0xe8c215, roughness: .45 }), pr = new THREE.MeshStandardMaterial({ color: 0x18191b, roughness: .7 }), cz = new THREE.MeshStandardMaterial({ color: 0x3a3c40, roughness: .5, metalness: .3 });
    const peca = (geo, m, x, y, z, rx = 0) => { const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); o.rotation.x = rx; choque.add(o); return o; };
    peca(new THREE.BoxGeometry(.036, .052, .15), am, 0, 0, -.02);                       // corpo
    peca(new THREE.BoxGeometry(.03, .016, .12), pr, 0, .033, -.025);                    // trilho de cima
    peca(new THREE.BoxGeometry(.04, .058, .045), pr, 0, -.002, -.115);                  // cartucho
    peca(new THREE.BoxGeometry(.03, .03, .004), cz, 0, .004, -.1385);                   // boca do cartucho
    peca(new THREE.BoxGeometry(.032, .11, .042), pr, 0, -.075, .035, -.28);             // cabo, inclinado
    peca(new THREE.BoxGeometry(.006, .03, .045), pr, 0, -.04, -.03);                    // guarda-mato
    peca(new THREE.BoxGeometry(.008, .022, .008), am, 0, -.034, -.012);                 // gatilho
    peca(new THREE.BoxGeometry(.012, .006, .012), new THREE.MeshBasicMaterial({ color: 0x40ff60 }), 0, .044, .03);      // led de carga
  }
  const luzTiro = new THREE.PointLight(0xffc880, 0, 8, 2); scene.add(luzTiro);
  const controleMao = mao => (ctx.controles || []).find(c => c.userData.mao === mao);
  function empunhar(qual) {                                  // qual: null | 'arma' | 'choque'
    S.naMao = qual;
    for (const [obj, k] of [[arma, 'arma'], [choque, 'choque']]) {
      const pai = renderer.xr.isPresenting ? (controleMao('right') || camera) : camera;
      pai.add(obj); obj.visible = qual === k;
      if (pai === camera) { obj.position.set(.17, -.13, -.38); obj.rotation.set(0, 0, 0); } else { obj.position.set(0, 0, -.02); obj.rotation.set(0, 0, 0); }
    }
    if (qual === 'arma' && A?.entrou !== undefined) A.sacou = true;
    for (const g of ctx.grips || []) if (g.userData.mao === 'right') g.visible = !qual;
    status();
  }
  function ameacaReal() { return Object.values(npcs).some(n => n.visible && n.userData.armado && !n.userData.caido); }      // so agressor armado justifica arma de fogo (Lei 13.060/2014); destruir prova nao
  function disparar(ray) {
    const fonte = arma.visible ? arma : choque, tiro = fonte === arma;
    const o = new THREE.Vector3(), d = new THREE.Vector3();
    if (fonte.parent === camera) { o.copy(ray.ray.origin); d.copy(ray.ray.direction); }
    else { fonte.getWorldPosition(o); d.set(0, 0, -1).applyQuaternion(fonte.getWorldQuaternion(new THREE.Quaternion())); }
    const r = new THREE.Raycaster(o, d, 0, tiro ? 40 : 7);
    const hn = r.intersectObjects(Object.values(npcs).filter(n => n.visible).map(n => n.userData.hit), false)[0];
    if (tiro) {
      window.__som?.tocar('tiro_pistola'); luzTiro.position.copy(o); luzTiro.intensity = 9; setTimeout(() => luzTiro.intensity = 0, 70);
      if (!ameacaReal()) registrar('disparo_sem_ameaca');
      if (hn) { const n = Object.values(npcs).find(p => p.userData.hit === hn.object); cair(n); }
    } else {
      window.__som?.tocar('radio_chiado');
      if (hn) {
        const n = Object.values(npcs).find(p => p.userData.hit === hn.object);
        if (!n.userData.agressivo) registrar('choque_sem_motivo'); else if (A?.conduta && !A.condutaResolvida) registrar('impedir_destruicao');      // resistencia ativa: arma de choque e forca menos letal
        atordoar(n);
      }
    }
    return true;
  }
  function cair(n) { const u = n.userData; if (u.caido) return; u.caido = true; u.agressivo = false; suave(.5, e => { n.rotation.x = -Math.PI / 2 * e; n.position.y = u.y0 + .15 * e; }); legenda('Instrutor', 'Pessoa atingida. Peça socorro imediato.', 5); }
  function atordoar(n) {
    const u = n.userData; u.agressivo = false; u.contido = true; animar(n, 'rendido', 1e6, .2); u.base = 'rendido';
    legenda(u.nome, 'Aaai! Tá bom, tá bom!', 3); if (A) { A.contido = true; resolverConduta('contido'); }
  }

  /* ================= variacoes ================= */
  function derivar(v) {
    if (v.morador === 'ausente') { v.vulneraveis = 'nenhum'; v.conduta = 'nenhuma'; }
    if (v.vulneraveis !== 'nenhum' && v.conduta === 'destruir') v.conduta = 'nenhuma';
    return v;
  }
  function sortear() {
    const forc = Object.fromEntries((new URLSearchParams(location.search).get('v') || '').split(',').filter(Boolean).map(p => p.split(':')));
    const v = {};
    for (const [k, ops] of Object.entries(CEN.variacoes)) v[k] = forc[k] && ops.includes(forc[k]) ? forc[k] : ops[Math.floor(Math.random() * ops.length)];
    return derivar(v);
  }
  const RESUMO_V = v => [
    v.endereco === 'correto' ? 'mandado com o endereço certo' : v.endereco === 'apto_errado' ? 'mandado com o apartamento 203' : 'mandado do Bloco A',
    v.horario === 'madrugada' ? 'equipe pronta às 4h30' : 'de dia', v.validade === 'vencido' ? 'mandado vencido' : null,
    { colabora: 'morador colabora', recusa: 'morador se recusa a abrir', ausente: 'ninguém em casa' }[v.morador],
    { nenhum: null, mulher: 'só a esposa em casa', idoso_acamado: 'idoso acamado' }[v.vulneraveis],
    { a_vista: 'objeto à vista', escondido: 'objeto escondido', ausente: 'objeto não está lá' }[v.objeto],
    v.extra !== 'nenhum' ? 'achado fora do mandado: ' + v.extra.replace('_', ' ') : null, v.inquilino === 'quarto_trancado' ? 'quarto do inquilino trancado' : null,
    v.dados === 'autoriza' ? 'mandado autoriza o acesso aos dados' : 'mandado não autoriza o acesso aos dados',
    v.conduta !== 'nenhuma' ? 'conduta do morador: ' + v.conduta.replace('_', ' ') : null, v.vizinho === 'sai_corredor' ? 'vizinha curiosa' : null,
  ].filter(Boolean).join(' · ');

  /* ================= personagens ================= */
  // chave, modelo, nome, onde fica (x, y, andar), para onde olha (dx, dy), voz, altura
  const ELENCO = [
    ['civil', 'policial_civil', 'Inspetor Souza (Polícia Civil)', [-1.9, -3.5, 0], [-.4, -1], 'm', 1.8],
    // (o parceiro e o apoio da PM foram tirados a pedido do usuario: a equipe e o aluno e o inspetor)
    ['porteiro', 'porteiro', 'Porteiro', [-.1, -2.6, 0], [-1, 0], 'm', 1.75],
    ['morador', 'morador', 'Morador', [3.95, 2.35, 3], [0, -1], 'm', 1.78],      // perto da porta de entrada, fora da mesa de jantar
    ['mulher', 'mulher', 'Moradora', [6.4, 4.4, 3], [0, -1], 'f', 1.66],
    ['idoso', 'idoso', 'Seu Antônio (idoso)', [6.1, 7.5, 3], [0, -1], 'm', 1.7],
    ['vizinha', 'vizinha', 'Vizinha do 301', [-2.95, 2.6, 3], [0, -1], 'f', 1.66],
  ];
  const NA_PORTA = [3.95, 2.25];                              // morador atende na porta (por dentro)
  function limparNPCs() { Object.values(npcs).forEach(n => scene.remove(n)); for (const k in npcs) delete npcs[k]; }
  function criarNPCs(v) {
    limparNPCs();
    for (const [chave, papel, nome, [x, y, andar], [dx, dy], voz, alt] of ELENCO) {
      if (chave === 'morador' && v.morador === 'ausente') continue;
      if (chave === 'mulher' && v.vulneraveis !== 'mulher') continue;
      if (chave === 'idoso' && v.vulneraveis !== 'idoso_acamado') continue;
      if (chave === 'vizinha' && v.vizinho !== 'sai_corredor') continue;
      const n = personagem(papel, nome, /parceiro|apoio/.test(chave) ? 0x1b2a4a : 0x3d4045, alt);
      n.userData.modelo?.traverse(o => { if (o.isMesh) o.material = Array.isArray(o.material) ? o.material.map(m => ctx.iluminar(m.clone())) : ctx.iluminar(o.material.clone()); });
      const p = andar === 3 ? B3(x, y) : B(x, y);
      Object.assign(n.userData, { chave, voz, fig: true, giroBase: olharPara(dx, dy), altura: alt, y0: p.y });
      n.position.copy(p); n.rotation.y = n.userData.giroBase; scene.add(n); npcs[chave] = n;
    }
    // quem esta no apartamento so aparece quando a porta abre; o morador "colabora" vem atender
    for (const k of ['morador', 'mulher', 'idoso']) if (npcs[k]) npcs[k].visible = false;
    if (npcs.vizinha) npcs.vizinha.visible = false;
    if (npcs.idoso) { const u = npcs.idoso.userData; u.sentado = true; u.semVirar = true; u.base = 'sentado_parado'; animar(npcs.idoso, 'sentado_parado', 1e6, 0); npcs.idoso.position.y = Z3 - .22; }
  }
  const rota = (n, pts, vel, anim, aoChegar, andar = null) => {
    const u = n.userData, z = andar === null ? n.position.y : andar; u.rota = pts.map(([x, y]) => B(x, y, z)); u.destino = null; u.vel = vel;
    u.aoChegar = () => { animar(n, u.base || 'parada', 1e6, .3); aoChegar?.(); };
    animar(n, u.acoes?.[anim] ? anim : 'andando', 1e6, .25);
  };
  const diz = (n, texto, gesto = 'falando') => n ? dizer(n, n.userData.nome, { texto, gesto }, n.userData.voz) : Promise.resolve();
  const civil = () => npcs.civil, parceiro = () => npcs.parceiro;
  // a equipe acompanha o aluno quando ele troca de andar (elevador ou escada)
  function equipeNoAndar(z) {
    const pos3 = { civil: [-4.6, .95], parceiro: [-4.0, .5], apoio: [-5.2, .55] }, pos0 = { civil: [-4.6, -.3], parceiro: [-4.0, -.8], apoio: [-5.2, -1.2] };
    for (const k of ['civil', 'parceiro', 'apoio']) {
      const n = npcs[k]; if (!n || n.userData.posicionado) continue; const [x, y] = (z > 3 ? pos3 : pos0)[k];
      n.userData.rota = null; n.userData.destino = null; n.position.copy(B(x, y, z > 3 ? Z3 : .15)); n.rotation.y = olharPara(1, 0); n.userData.giroBase = n.rotation.y;
    }
  }

  /* ================= paineis de opcoes ================= */
  const fechar = () => dialogo.esconder();
  function dica(texto, seg = 6) { if (S.modo !== 'avaliacao' && S.ativo) legenda('Dica do instrutor', texto, seg); }
  function painelOpc(tag, titulo, lista, aoEscolher, texto = '', voltar = true) {
    fecharPaineis();
    dialogo.mostrar({ tag, titulo, texto, botoes: [...lista.map(op => ({ label: op.fala, acao: () => {
      fechar();
      for (const k of ['acao', 'tambem', 'erro', 'falha']) if (op[k]) registrar(op[k]);
      if (op.feedback && S.modo === 'treino') setTimeout(() => legenda('Instrutor', op.feedback, 7), 2400);
      aoEscolher?.(op);
    } })), ...(voltar ? [{ label: 'Voltar', acao: fechar }] : [])] });
  }

  /* ================= fluxo ================= */
  function novaOcorrencia(v, cap) {
    S.variacao = v; S.feitos = new Map(); empunhar(null);
    A = { n: HIST.length + 1, fase: 'portaria', titulo: cap?.titulo || `Cumprimento ${HIST.length + 1}`, aberturas: new Set(), danos: [], indevidos: [], testemunhas: new Set() };
    A.hora = v.horario === 'madrugada' ? '04:30' : '08:40';
    criarNPCs(v); distribuirItens(v); lacres.clear();
    MANDADO()?.gerar({ endereco: v.endereco, dados: v.dados, validade: v.validade }); MANDADO()?.mostrar(false);
    const ab = ABRIR(); ab?.fecharTudo();
    for (const nome of ['A_Passagem_Apto_302', 'A_Passagem_Apto_301']) ab?.trancar(nome, true);
    ab?.trancar('A_Passagem_Quarto_2', v.inquilino === 'quarto_trancado');
    ctx.ambiente?.(v.horario === 'madrugada' ? 'madrugada' : 'dia');
    rig.position.set(-2.7, .15, 4.6); ctx.setYaw(0);
    const comecar_ = () => {
      diz(civil(), `Bom dia. ${v.horario === 'madrugada' ? 'São quatro e meia, a equipe está pronta.' : 'Equipe pronta.'} O mandado está com você: leia antes de subirmos.`)
        .then(() => dica('Aperte X (ou a tecla V) para ler o mandado. Converse com o inspetor e com o porteiro.', 7));
    };
    if (cap) { fecharPaineis(); menu.mostrar({ tag: 'Modo história', titulo: cap.titulo, texto: cap.texto, longe: 1.3, botoes: [{ label: 'Começar', acao: () => { menu.esconder(); comecar_(); } }] }); }
    else comecar_();
    status();
  }
  // leitura do mandado: abrir o documento por alguns segundos conta como leitura
  let tLeitura = 0;
  function acompanharLeitura(dt) {
    if (!A || !MANDADO()?.naMao) return;
    tLeitura += dt; if (tLeitura > 2.5 && !S.feitos.has('ler_mandado')) { registrar('ler_mandado'); A.leu = true; }
  }

  /* ---------- inspetor (responsavel) ---------- */
  function menuCivil() {
    const v = S.variacao, ops = [];
    if (A.fase === 'portaria') {
      ops.push({ fala: 'Conferi o endereço: bloco, número e nome batem com o local.', id: 'confere' });
      ops.push({ fala: 'Inspetor, o mandado não bate com o endereço: o número ou o bloco está diferente.', id: 'diverge' });
      ops.push({ fala: 'Conferi a data: o mandado está dentro da validade.', id: 'valido' });
      ops.push({ fala: 'Inspetor, o mandado está vencido.', id: 'vencido' });
      if (v.horario === 'madrugada' && !A.esperou) ops.push({ fala: 'Ainda não são cinco horas. Vamos aguardar.', id: 'esperar' });
      ops.push({ fala: 'Tudo certo. Vamos subir.', id: 'subir' });
    } else if (A.fase === 'busca' || A.fase === 'auto') {
      ops.push({ fala: 'Inspetor, terminei a busca. Vamos lavrar o auto com duas testemunhas.', id: 'auto' });
      ops.push({ fala: 'Pode encerrar, não precisa de auto.', id: 'sem_auto' });
    } else ops.push({ fala: 'Aguardando o senhor.', id: 'nada' });
    painelOpc('Inspetor Souza · Polícia Civil', 'Responsável pelo cumprimento', ops, op => {
      if (op.id === 'confere') {
        registrar('conferir_endereco');
        if (v.endereco !== 'correto') { registrar('subir_sem_ler', 'endereço divergente não percebido'); diz(civil(), 'Tem certeza? Confira de novo o número e o bloco.'); }
        else diz(civil(), 'Ótimo.');
      } else if (op.id === 'diverge') {
        if (v.endereco !== 'correto') { registrar('conferir_endereco'); registrar('apontar_divergencia'); diz(civil(), 'Bem visto. Com o endereço errado não podemos entrar. Vou comunicar o juízo e pedir a correção do mandado.').then(() => encerrarSemEntrada('Mandado com endereço divergente: cumprimento suspenso e juízo comunicado.')); }
        else { penalidade(-2, 'Apontou divergência de endereço que não existia'); diz(civil(), 'Confira de novo: o endereço bate, é o Bloco B, apartamento 302.'); }
      } else if (op.id === 'valido') {
        if (v.validade === 'vencido') { penalidade(-3, 'Disse que o mandado estava válido, mas estava vencido'); diz(civil(), 'Olhe a data de novo.'); }
        else { registrar('conferir_validade'); diz(civil(), 'Certo.'); }
      } else if (op.id === 'vencido') {
        if (v.validade === 'vencido') { registrar('conferir_validade'); diz(civil(), 'É verdade, passou da validade. Não cumprimos; vou pedir um novo mandado.').then(() => encerrarSemEntrada('Mandado vencido: cumprimento suspenso.')); }
        else { penalidade(-2, 'Disse que o mandado estava vencido sem estar'); diz(civil(), 'Não, está dentro do prazo.'); }
      } else if (op.id === 'esperar') {
        registrar('aguardar_horario'); A.esperou = true; A.hora = '05:05'; ctx.ambiente?.('dia');
        diz(civil(), 'Certo. Vamos esperar dar cinco horas.').then(() => legenda('', 'Meia hora depois: 05h05.', 3));
      } else if (op.id === 'subir') {
        if (!A.leu) registrar('subir_sem_ler');
        A.fase = 'corredor'; diz(civil(), 'Vamos de elevador.').then(() => dica('Chame o elevador (botão ao lado da porta), entre e aperte o painel. No andar, bata do lado da porta, fora da linha dela.', 7));
      } else if (op.id === 'auto') lavrarAuto();
      else if (op.id === 'sem_auto') { registrar('sem_auto'); finalizar(); }
    }, `Agora: ${A.hora}. ${A.fase === 'portaria' ? 'Leia o mandado (X ou V) e confira com o local.' : ''}`);
  }
  function encerrarSemEntrada(motivo) { A.semEntrada = motivo; legenda('Encerramento', motivo, 6); setTimeout(finalizar, 3500); }

  /* ---------- porteiro ---------- */
  function menuPorteiro() {
    painelOpc('Portaria', 'Porteiro', [
      { fala: 'Bom dia. Polícia. Precisamos subir; por favor, não avise nenhum morador.', acao: 'porteiro_discreto', id: 'discreto' },
      { fala: 'Avise o morador do 302 que a polícia está subindo.', erro: 'porteiro_avisa', id: 'avisa' },
      { fala: 'Quem mora no 302, Bloco B?', id: 'quem' },
      ...(A.precisaTestemunha ? [{ fala: 'O senhor pode subir e acompanhar a busca como testemunha?', id: 'testemunha' }] : []),
    ], op => {
      const p = npcs.porteiro;
      if (op.id === 'discreto') diz(p, 'Pode deixar, doutor. Elevador é ali à esquerda.');
      else if (op.id === 'avisa') { A.avisado = true; diz(p, 'Tá bom, vou interfonar.'); }
      else if (op.id === 'quem') diz(p, S.variacao.morador === 'ausente' ? 'É o seu Carlos. Saiu cedo, não voltou ainda.' : 'O seu Carlos. Tá em casa, subiu ontem à noite.');
      else if (op.id === 'testemunha') chamarTestemunha('porteiro');
    });
  }
  function chamarTestemunha(quem) {
    A.testemunhas.add(quem); const n = npcs[quem];
    if (n) { n.visible = true; n.position.copy(B3(quem === 'porteiro' ? 3.2 : 2.4, .8)); n.userData.giroBase = olharPara(0, 1); n.rotation.y = n.userData.giroBase; n.userData.posicionado = true; }
    legenda(quem === 'porteiro' ? 'Porteiro' : 'Vizinha', 'Tudo bem, eu acompanho.', 3);
    if (A.precisaTestemunha && !A.entrou) { registrar('chamar_testemunha_ausente'); dica('Com a testemunha presente, a porta pode ser aberta à força (chaveiro ou arrombamento), com o mínimo de dano.', 6); }
  }

  /* ---------- apoio ---------- */
  function menuApoio() {
    painelOpc('Equipe', 'Policial de apoio', [
      { fala: 'Cubra a escada: ninguém desce nem sobe.', id: 'escada' },
      { fala: 'Fique no corredor, fora da linha da porta.', id: 'corredor' },
      { fala: 'Fique aqui comigo.', id: 'junto' },
    ], op => {
      const n = npcs.apoio; if (!n) return; n.userData.posicionado = op.id !== 'junto';
      if (op.id === 'escada') { registrar('apoio_escada'); ABRIR()?.abrir('A_Passagem_Escada', 1); rota(n, [[-5.55, .3], [-5.6, -.9]], 1.5, 'andando', () => { n.userData.giroBase = olharPara(0, 1); }, Z3); diz(n, 'Escada coberta.'); }
      else if (op.id === 'corredor') { registrar('apoio_corredor'); rota(n, [[5.5, .5]], 1.5, 'andando', () => { n.userData.giroBase = olharPara(-1, 0); }, Z3); diz(n, 'Fico aqui, fora da linha da porta.'); }
      else diz(n, 'Certo.');
    });
  }

  function menuParceiro() {
    const n = parceiro();
    if (A.fase === 'busca' || A.fase === 'auto') return diz(n, 'Eu fico de olho no morador enquanto você procura.');
    painelOpc('Equipe', 'Policial parceiro', [
      { fala: 'Fique ao lado da porta do 302, fora da linha de tiro.', id: 'porta' },
      { fala: 'Vem comigo.', id: 'junto' }], op => {
      if (op.id === 'porta') { registrar('apoio_corredor'); n.userData.posicionado = true; rota(n, [[4.75, .45]], 1.4, 'andando', () => { n.userData.giroBase = olharPara(-1, 0); }, Z3); diz(n, 'Fico aqui, encostado na parede.'); }
      else { n.userData.posicionado = false; diz(n, 'Tô contigo.'); }
    });
  }

  /* ---------- vizinha curiosa ---------- */
  function vizinhaSai() {
    const n = npcs.vizinha; if (!n || n.userData.saiu) return; n.userData.saiu = true;
    const ab = ABRIR(); ab?.trancar('A_Passagem_Apto_301', false); ab?.abrir('A_Passagem_Apto_301', .7);
    n.visible = true; n.position.copy(B3(-2.95, 2.4)); rota(n, [[-2.95, 1.2]], 1.0, 'andando', () => { n.userData.giroBase = olharPara(1, 0); diz(n, 'Ué, o que tá acontecendo aqui? É com o vizinho do 302?'); }, Z3);
  }
  function menuVizinha() {
    painelOpc('Corredor', 'Vizinha do 301', [
      { fala: 'Polícia, senhora. Por favor, volte para dentro e feche a porta.', acao: 'orientar_vizinho', id: 'volta' },
      { fala: 'A senhora pode acompanhar a busca como testemunha?', acao: 'orientar_vizinho', id: 'test' },
      { fala: 'É o 302 mesmo. Ele está sendo investigado por estelionato.', id: 'conta' },
    ], op => {
      const n = npcs.vizinha;
      if (op.id === 'volta') { rota(n, [[-2.95, 2.4]], 1.0, 'andando', () => { n.visible = false; ABRIR()?.abrir('A_Passagem_Apto_301', 0); }, Z3); diz(n, 'Tá bom, desculpa.'); }
      else if (op.id === 'test') chamarTestemunha('vizinha');
      else { penalidade(-3, 'Expôs a investigação a uma vizinha'); diz(n, 'Nossa! Eu sabia que tinha alguma coisa errada.'); }
    });
  }

  /* ---------- portas do corredor ---------- */
  function menuPorta(qual) {
    const v = S.variacao;
    if (qual === '301') {
      return painelOpc('Corredor', 'Porta do apartamento 301', [
        { fala: 'Bater e anunciar: "Polícia! Temos um mandado de busca!"', id: 'bater' },
        { fala: 'Conferir o número antes', id: 'conferir' }], op => {
        if (op.id === 'bater') { registrar('porta_errada'); legenda('Morador do 301', 'Aqui não, moço! Deve ser outro apartamento.', 4); }
        else { registrar('conferir_porta'); legenda('Você', 'Esta é a 301. O mandado é para outra porta.', 3); }
      });
    }
    if (A.entrou) return;
    const ops = [];
    if (!A.bateu) {
      ops.push({ fala: 'Bater e anunciar: "Polícia! Temos um mandado de busca e apreensão!"', id: 'bater' });
      ops.push({ fala: 'Tocar a campainha sem se identificar', id: 'campainha' });
      ops.push({ fala: 'Forçar a porta e entrar de surpresa', id: 'forcar' });
    } else if (A.recusou || A.ausente) {
      if (A.recusou && !A.leuEmVoz) ops.push({ fala: 'Ler o mandado em voz alta pela porta e intimar a abrir', id: 'ler_porta' });
      if (A.ausente && !A.testemunhas.size) ops.push({ fala: 'Pedir ao porteiro que suba para acompanhar como testemunha', id: 'chamar_porteiro' });
      ops.push({ fala: 'Abrir a porta à força, com o mínimo de dano', id: 'arrombar' });
      ops.push({ fala: 'Insistir: bater de novo', id: 'insistir' });
    }
    painelOpc('Corredor', `Porta do apartamento 302`, ops, op => {
      if (op.id === 'bater') bater(true);
      else if (op.id === 'campainha') { bater(false); }
      else if (op.id === 'forcar') { registrar('arrombar_sem_recusa'); registrar('entrar_sem_anunciar'); entrar(true); }
      else if (op.id === 'ler_porta') { A.leuEmVoz = true; registrar('mostrar_ler'); registrar('intimar_abrir'); legenda('Você', 'Senhor Carlos, temos mandado judicial de busca e apreensão para este apartamento. Abra a porta.', 5); setTimeout(() => legenda('Morador (por trás da porta)', 'Não abro! Chama o meu advogado!', 4), 5200); }
      else if (op.id === 'chamar_porteiro') { A.precisaTestemunha = true; chamarTestemunha('porteiro'); }
      else if (op.id === 'arrombar') {
        if (A.ausente && !A.testemunhas.size) registrar('entrar_ausente_sem_testemunha');
        if (A.recusou && !A.leuEmVoz) registrar('arrombar_sem_recusa');
        if (A.recusou) registrar('arrombar_apos_recusa');
        window.__som?.tocar('porta_abrindo'); A.danos.push('Porta de entrada forçada (fechadura danificada)'); entrar(true);
      } else if (op.id === 'insistir') legenda('', A.ausente ? 'Ninguém responde.' : 'O morador continua se recusando a abrir.', 3);
    });
  }
  function bater(anunciou) {
    const v = S.variacao; A.bateu = true; A.fase = 'entrada';
    camera.getWorldPosition(V); if (Math.abs(V.x - 3.95) > .45) registrar('fora_linha_porta');      // porta do 302: de x 3,5 a 4,4; ao lado = fora da linha de tiro
    else dica('Você bateu bem na frente da porta. O certo é ficar ao lado, encostado na parede, fora da linha dela.', 6);
    if (anunciou) registrar('bater_anunciar');
    if (A.hora < '05:00') registrar('cumprir_madrugada');
    if (v.endereco !== 'correto') registrar('cumprir_endereco_errado');
    if (v.validade === 'vencido') registrar('cumprir_vencido');
    registrar('conferir_porta');
    window.__som?.tocar('porta_abrindo');
    if (v.morador === 'ausente') { A.ausente = true; A.precisaTestemunha = true; setTimeout(() => legenda('', 'Ninguém responde. O apartamento parece vazio.', 4), 1500); dica('Ninguém em casa: antes de entrar, chame um vizinho ou o porteiro para acompanhar (CPP, art. 245, § 4º).', 7); return; }
    if (v.morador === 'recusa' && !A.avisado) { A.recusou = true; setTimeout(() => legenda('Morador (por trás da porta)', anunciou ? 'Polícia? Não vou abrir nada! Vocês não vão entrar aqui!' : 'Quem é? Não tô esperando ninguém.', 4), 1500); return; }
    // o morador abre a porta
    setTimeout(() => {
      const ab = ABRIR(); ab?.trancar('A_Passagem_Apto_302', false); ab?.abrir('A_Passagem_Apto_302', .55);
      const n = npcs.morador; if (!n) return; n.visible = true; n.position.copy(B3(...NA_PORTA)); n.userData.giroBase = olharPara(0, -1); n.rotation.y = n.userData.giroBase;
      diz(n, anunciou ? 'Polícia? O que é que vocês querem?' : 'Pois não?').then(menuMoradorPorta);
      if (v.vulneraveis === 'mulher') { npcs.mulher.visible = true; setTimeout(() => legenda('Moradora (lá dentro)', 'Carlos? Quem é a essa hora?', 4), 2500); }
      if (v.vulneraveis === 'idoso_acamado' && npcs.idoso) npcs.idoso.visible = true;
    }, 1800);
  }
  function menuMoradorPorta() {
    painelOpc('Porta do 302', 'Morador', [
      { fala: 'Mostrar e ler o mandado: "Temos mandado de busca e apreensão para este endereço. O senhor precisa nos deixar entrar."', id: 'ler' },
      { fala: 'Entrar logo, sem explicar', id: 'direto' },
      { fala: 'Mandar o morador virar de costas e algemá-lo', id: 'algemar' },
    ], op => {
      const n = npcs.morador;
      if (op.id === 'ler') { registrar('mostrar_ler'); registrar('intimar_abrir'); MANDADO()?.mostrar(true); diz(n, 'Tá… pode entrar. Mas eu quero ver tudo o que vocês fizerem.').then(() => { MANDADO()?.mostrar(false); entrar(false); }); }
      else if (op.id === 'direto') { registrar('entrar_sem_anunciar'); entrar(false); }
      else { registrar('algemar_sem_motivo'); n.userData.algemado = true; animar(n, 'algemado', 1e6, .3); n.userData.base = 'algemado'; entrar(false); }
    }, false);
  }
  function entrar(forcado) {
    A.entrou = true; A.fase = 'busca'; const ab = ABRIR(); ab?.trancar('A_Passagem_Apto_302', false); ab?.abrir('A_Passagem_Apto_302', 1);
    const v = S.variacao, n = npcs.morador;
    if (v.morador === 'recusa' && n) { n.visible = true; n.position.copy(B3(3.95, 2.75)); n.userData.giroBase = olharPara(0, -1); animar(n, n.userData.acoes?.irritado ? 'irritado' : 'parada', 1e6, .2); n.userData.base = n.userData.acoes?.irritado ? 'irritado' : 'parada'; }
    if (v.vulneraveis === 'mulher') npcs.mulher.visible = true;
    if (v.vulneraveis === 'idoso_acamado' && npcs.idoso) npcs.idoso.visible = true;
    // a equipe entra junto
    if (npcs.civil) rota(npcs.civil, [[3.95, 1.0], [3.95, 2.6], [4.0, 3.6]], 1.3, 'andando', null, Z3);
    if (npcs.parceiro) rota(npcs.parceiro, [[3.95, 1.0], [3.95, 2.4]], 1.3, 'andando', null, Z3);
    dica('Fale com o morador e com quem está em casa. Depois procure: gavetas, armários e portas abrem com o gatilho (ou clique).', 7);
    if (v.conduta !== 'nenhuma' && n) setTimeout(condutaMorador, 14000);
  }

  /* ---------- quem esta em casa ---------- */
  function menuMorador() {
    const n = npcs.morador, u = n.userData, v = S.variacao;
    if (A.conduta && !A.condutaResolvida) return menuConduta();
    painelOpc('Apartamento 302', 'Morador', [
      { fala: 'O senhor vai acompanhar a busca, cômodo por cômodo.', acao: 'morador_acompanha', id: 'acomp' },
      { fala: 'Onde estão o celular, o computador e os documentos?', id: 'onde' },
      { fala: 'De quem é o quarto trancado?', id: 'quarto' },
      { fala: 'Revistar o morador', id: 'revistar' },
      { fala: u.algemado ? 'Tirar as algemas' : 'Algemar o morador', id: 'algemas' },
      { fala: 'Qual é a senha do celular? Vou ver as mensagens.', id: 'senha' },
    ], op => {
      if (op.id === 'acomp') { A.acompanha = true; diz(n, 'Tá bom, eu vou junto.'); }
      else if (op.id === 'onde') diz(n, v.objeto === 'ausente' ? 'Celular eu não tenho mais, perdi semana passada. Computador nunca tive.' : v.objeto === 'a_vista' ? 'Tá tudo aí na sala, ué. Não tenho nada a esconder.' : 'Não sei do que o senhor está falando.');
      else if (op.id === 'quarto') diz(n, v.inquilino === 'quarto_trancado' ? 'É do inquilino, o Rafael. Ele aluga o quarto. Tá trabalhando, a chave fica com ele.' : 'Que quarto? Tá tudo aberto.');
      else if (op.id === 'revistar') { if (!n.userData.agressivo) registrar('revistar_sem_motivo'); diz(n, 'Ei! Pra que isso?'); }
      else if (op.id === 'algemas') { if (u.algemado) { u.algemado = false; u.base = 'parada'; animar(n, 'parada', 1e6, .3); } else { if (!u.agressivo && !A.condutaGrave) registrar('algemar_sem_motivo'); u.algemado = true; u.base = 'algemado'; animar(n, 'algemado', 1e6, .3); } }
      else if (op.id === 'senha') { if (v.dados === 'nao_autoriza') registrar('acessar_celular'); else penalidade(-1, 'Pediu a senha para ler no local: a análise do conteúdo é feita pela perícia'); diz(n, 'Não vou dar senha nenhuma! Quero o meu advogado.'); }
    });
  }
  function menuFamilia(n) {
    const k = n.userData.chave;
    painelOpc('Apartamento 302', n.userData.nome, [
      { fala: 'Calma, senhora. É uma busca com mandado judicial. Fique aqui na sala, longe da busca, por favor.', acao: 'cuidado_vulneraveis', id: 'calma' },
      { fala: 'Todo mundo de mãos na cabeça, contra a parede!', id: 'parede' },
    ].filter(o => k !== 'idoso' || o.id !== 'parede').concat(k === 'idoso' ? [{ fala: 'Seu Antônio, fique tranquilo, vamos procurar sem incomodar o senhor.', acao: 'cuidado_vulneraveis', id: 'idoso' }] : []), op => {
      if (op.id === 'parede') { penalidade(-5, 'Tratou a família como suspeita sem motivo (mãos na cabeça, contra a parede)'); diz(n, 'Pelo amor de Deus, eu não fiz nada!'); }
      else diz(n, k === 'idoso' ? 'Obrigado, meu filho. Eu não levanto daqui.' : 'Tá… tá bom. Eu fico aqui sentada.');
    });
  }

  /* ---------- conduta do morador durante a busca ---------- */
  function condutaMorador() {
    if (!A || A.fase !== 'busca' || A.conduta) return;
    const v = S.variacao, n = npcs.morador; if (!n || n.userData.algemado) return;
    A.conduta = v.conduta; const u = n.userData;
    if (v.conduta === 'suborno') { diz(n, 'Ô, doutor… vamos resolver isso aqui entre a gente? Tenho cinco mil aqui, ninguém precisa saber.'); return menuConduta(); }
    if (v.conduta === 'filma_advogado') { diz(n, 'Eu vou filmar tudo, tá? E já liguei pro meu advogado, ele tá vindo.'); animar(n, 'falando', 6); return; }
    // tenta se livrar da prova: vai para a janela, para o banheiro ou quebra o notebook
    const alvo = { jogar_janela: [[6.8, 3.0], [7.75, 3.6]], jogar_vaso: [[2.45, 3.3], [1.2, 3.0], [.5, 2.2]], destruir: [[4.4, 2.3], [5.6, 2.3]] }[v.conduta];      // ao lado da mesa de jantar (antes ia para dentro dela)
    u.agressivo = v.conduta === 'destruir'; A.prazoConduta = performance.now() + 7000;
    legenda('Alerta', { jogar_janela: 'O morador pegou alguma coisa e foi para a janela!', jogar_vaso: 'O morador correu para o banheiro com alguma coisa na mão!', destruir: 'O morador está tentando quebrar o notebook!' }[v.conduta], 4);
    rota(n, alvo, 2.0, 'correndo', null, Z3);
  }
  function menuConduta() {
    const v = S.variacao, n = npcs.morador;
    if (A.conduta === 'suborno') return painelOpc('Apartamento 302', 'O morador oferece dinheiro', [
      { fala: 'Recusar: "O senhor está oferecendo vantagem a um policial. Isso é crime." e avisar o inspetor', acao: 'recusar_suborno', id: 'recusa' },
      { fala: 'Aceitar e encerrar a busca', falha: 'aceitar_suborno', id: 'aceita' }], op => { A.condutaResolvida = true; diz(n, op.id === 'recusa' ? 'Calma, era brincadeira…' : 'Valeu, doutor.'); if (op.id === 'recusa') diz(civil(), 'Ouvi. O senhor vai ser autuado também por corrupção ativa.'); }, '', false);
    if (A.conduta === 'filma_advogado') return painelOpc('Apartamento 302', 'O morador filma e chama o advogado', [
      { fala: 'Pode filmar. O advogado pode acompanhar quando chegar; a busca continua.', acao: 'permitir_filmar', id: 'ok' },
      { fala: 'Tomar o celular da mão dele: "Aqui ninguém filma!"', erro: 'filmagem_impedida', id: 'toma' }], op => { A.condutaResolvida = true; diz(n, op.id === 'ok' ? 'Tá bom.' : 'Ei! Isso é abuso!'); }, '', false);
    painelOpc('Alerta', 'Conter o morador', [
      { fala: 'Ordem verbal firme: "Pare! Solte isso!" e segurar o braço dele', acao: 'impedir_destruicao', id: 'conter' },
      { fala: 'Algemar depois de contê-lo (houve resistência)', acao: 'impedir_destruicao', id: 'algemar' },
      { fala: 'Deixar: não é problema meu', id: 'deixar' }], op => resolverConduta(op.id), '', false);
  }
  function resolverConduta(como) {
    const n = npcs.morador, u = n?.userData; if (!A || !n || A.condutaResolvida) return;
    A.condutaResolvida = true; u.rota = null; u.destino = null;
    if (como === 'deixar') {
      u.agressivo = false; const c = A.conduta;
      const alvo = (c === 'destruir' ? ['notebook', 'celular'] : ['celular', 'notebook']).map(k => itens[k]).find(it => it && !it.apreendido);
      if (!alvo) return;
      if (c === 'jogar_janela') {                 // cai na calcadinha do jardim lateral, embaixo da janela da sala: da para descer e buscar
        scene.attach(alvo.o); alvo.o.position.copy(B(8.55, 3.3)); alvo.o.position.y = .17; alvo.o.rotation.set(0, Math.random() * 3, 0); alvo.o.visible = true; alvo.jogado = true;
        legenda('Alerta', 'O morador jogou o ' + NOME_ITEM[alvo.tipo].toLowerCase() + ' pela janela! Caiu no jardim lateral do prédio.', 5);
        dica('Desça (elevador e portaria), saia pela calçada e entre pelo portão do jardim lateral. Fotografe onde caiu e apreenda.', 9);
      } else { A.provaPerdida = true; alvo.o.visible = false; alvo.perdido = true; legenda('', c === 'destruir' ? 'O notebook foi destruído.' : 'O celular foi descartado no vaso sanitário.', 4); }
      return;
    }
    A.condutaGrave = true; u.agressivo = false; u.base = como === 'algemar' ? 'algemado' : 'nervoso'; if (como === 'algemar') u.algemado = true; animar(n, u.base, 1e6, .3);
    diz(n, 'Tá bom, tá bom! Me solta!');
  }

  /* ---------- quarto do inquilino ---------- */
  function menuQuartoInquilino() {
    painelOpc('Apartamento 302', 'Quarto trancado', [
      { fala: 'Perguntar ao morador de quem é o quarto', id: 'perg' },
      { fala: 'Consultar o inspetor: o quarto é de outra pessoa, que não está no mandado', acao: 'inquilino_correto', id: 'consulta' },
      { fala: 'Arrombar a porta do quarto', erro: 'arrombar_quarto_inquilino', id: 'arromba' },
    ], op => {
      if (op.id === 'perg') diz(npcs.morador, 'É do inquilino, o Rafael. Ele aluga o quarto. A chave tá com ele.');
      else if (op.id === 'consulta') diz(civil(), 'Bem lembrado. O cômodo dele tem proteção própria. Não entramos; registro no auto e comunico o juízo.');
      else { A.danos.push('Porta do quarto do inquilino arrombada'); ABRIR()?.trancar('A_Passagem_Quarto_2', false); ABRIR()?.abrir('A_Passagem_Quarto_2', 1); window.__som?.tocar('porta_abrindo'); }
    });
  }

  /* ---------- itens ---------- */
  function menuItem(tipo) {
    const it = itens[tipo], v = S.variacao, doMandado = DO_MANDADO.has(tipo); if (!it || it.apreendido) return;
    const ops = [];
    if (!it.fotografado) ops.push({ fala: 'Fotografar no lugar onde foi encontrado', id: 'foto' });
    if (tipo === 'celular' || tipo === 'notebook') {
      ops.push({ fala: tipo === 'celular' ? 'Colocar em modo avião e desligar, sem mexer no conteúdo' : 'Desligar sem mexer no conteúdo', id: 'isolar' });
      ops.push({ fala: tipo === 'celular' ? 'Desbloquear e olhar as mensagens' : 'Abrir e olhar os arquivos', id: 'acessar' });
    }
    if (doMandado) ops.push({ fala: 'Apreender: relacionar, embalar e lacrar com número', id: 'apreender' });
    else if (tipo === 'arma' || tipo === 'droga') { ops.push({ fala: 'Não mexer e chamar o inspetor: é flagrante', id: 'flagrante' }); ops.push({ fala: 'Deixar onde está', id: 'ignorar' }); }
    else { ops.push({ fala: 'Só registrar no auto (não está no mandado e não é crime aparente)', id: 'registrar' }); ops.push({ fala: 'Apreender também', id: 'apreender_extra' }); }
    painelOpc('Achado', NOME_ITEM[tipo], ops, op => {
      if (op.id === 'foto') { it.fotografado = true; A.fotos = (A.fotos || 0) + 1; window.__som?.tocar('radio_bip'); legenda('', 'Foto registrada.', 1.5); if (A.fotos >= 2) registrar('fotografar_local'); return menuItem(tipo); }
      if (op.id === 'isolar') { it.isolado = true; registrar('celular_sem_acesso'); return menuItem(tipo); }
      if (op.id === 'acessar') { if (v.dados === 'nao_autoriza') registrar('acessar_celular'); else penalidade(-1, 'Acessou o conteúdo no local: mesmo autorizado, a análise é da perícia'); return; }
      if (op.id === 'apreender') { apreender(it); if (!A.acompanha && !A.testemunhas.size) dica('A busca deve ser acompanhada pelo morador ou por testemunhas.', 5); return; }
      if (op.id === 'flagrante') { registrar('fora_mandado_correto'); A.flagrante = tipo; diz(civil(), tipo === 'arma' ? 'Arma sem registro? Flagrante. Vou apreender e conduzir.' : 'Isso é droga. Flagrante: apreendo e conduzo.'); apreender(it, false); return; }
      if (op.id === 'ignorar') { registrar('ignorar_flagrante'); return; }
      if (op.id === 'registrar') { registrar('fora_mandado_correto'); it.registrado = true; legenda('', 'Anotado para o auto.', 2); return; }
      if (op.id === 'apreender_extra') { registrar('apreender_fora_mandado'); A.indevidos.push(NOME_ITEM[tipo]); apreender(it, false); }
    });
  }
  function apreender(it, doMandado = true) {
    it.apreendido = true; it.o.removeFromParent(); saco(it.tipo); window.__som?.tocar('algemas');
    A.apreendidos = (A.apreendidos || 0) + 1; registrar('relacionar_itens'); registrar('lacrar');
    if (doMandado && DO_MANDADO.has(it.tipo)) registrar('achar_objeto');
    legenda('Apreensão', `${NOME_ITEM[it.tipo]}: embalado e lacrado (lacre nº ${String(48210 + A.apreendidos)}).`, 3);
    status();
  }
  function lavrarAuto() {
    if (A.testemunhas.size < 2) {
      return painelOpc('Auto circunstanciado', 'Faltam testemunhas', [
        ...(!A.testemunhas.has('porteiro') ? [{ fala: 'Chamar o porteiro para assinar', id: 'porteiro' }] : []),
        ...(!A.testemunhas.has('vizinha') ? [{ fala: 'Chamar a vizinha do 301 para assinar', id: 'vizinha' }] : []),
        { fala: 'Lavrar sem testemunhas', id: 'sem' }], op => {
        if (op.id === 'sem') { penalidade(-6, 'Auto lavrado sem as duas testemunhas'); concluirAuto(); }
        else { A.testemunhas.add(op.id); if (op.id === 'vizinha' && !npcs.vizinha) { legenda('', 'A vizinha do 301 sobe para assinar.', 2); } else chamarTestemunha(op.id); lavrarAuto(); }
      }, 'O auto precisa de duas testemunhas presenciais (CPP, art. 245, § 7º).', false);
    }
    concluirAuto();
  }
  function concluirAuto() {
    registrar('lavrar_auto'); A.fase = 'auto';
    painelOpc('Auto circunstanciado', 'Encerramento', [
      { fala: 'Informar o morador do que foi apreendido e entregar a cópia do auto', acao: 'informar_morador', id: 'info' },
      { fala: 'Encerrar sem informar', id: 'nao' }], () => { diz(civil(), 'Auto lavrado. Vamos encerrar.'); setTimeout(finalizar, 3000); }, `Itens apreendidos: ${A.apreendidos || 0}. Danos: ${A.danos.length ? A.danos.join('; ') : 'nenhum'}.`, false);
  }

  /* ---------- busca: o que o aluno abre conta como lugar procurado ---------- */
  const ouvinteAbrir = (p, alvo) => {
    if (!A || alvo < .5) return;
    if (!A.entrou && /Gav_|Fol_|Tam_/.test(p.nome) && noApto(p.o.getWorldPosition(new THREE.Vector3()))) return;
    A.aberturas.add(p.nome);
    if (A.aberturas.size >= 6 && !S.feitos.has('buscar_onde_cabe')) registrar('buscar_onde_cabe');
    if (/Lavadora|Fogao|Vaso/.test(p.nome)) { A.estranhos = (A.estranhos || 0) + 1; if (A.estranhos === 2) registrar('revirar_onde_nao_cabe'); }
  };

  /* ================= fim, resumo, relatorio ================= */
  function finalizar() {
    if (!A || A.fase === 'fim') return;
    if (A.entrou) {
      if (!S.feitos.has('lavrar_auto') && !A.semEntrada) registrar('sem_auto');
      if (A.acompanha || A.testemunhas.size) registrar('morador_acompanha');
      if (!A.danos.length) registrar('sem_dano');
      for (const it of Object.values(itens)) if (DO_MANDADO.has(it.tipo) && !it.apreendido && !it.perdido) A.naoAchados = (A.naoAchados || 0) + 1;
      if (Object.values(itens).some(it => it.jogado && !it.apreendido)) registrar('prova_arremessada_nao_recuperada');
    }
    A.fase = 'fim'; fecharPaineis(); empunhar(null); MANDADO()?.mostrar(false); status(); setTimeout(concluir, 1500);
  }
  function resumo() {
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
    return { n: A.n, titulo: A.titulo, variacao: { ...S.variacao }, fases, danos: [...A.danos], indevidos: [...A.indevidos], semEntrada: A.semEntrada || null };
  }
  function concluir() {
    if (!A) return;
    HIST.push(resumo()); A = null;
    if (!S.ativo) return;
    if (S.fila.length) { const prox = S.fila.shift(); setTimeout(() => novaOcorrencia(derivar({ ...prox.variacao }), S.historia ? prox : null), 1200); }
    else encerrar();
  }
  function aviso() {
    fecharPaineis();
    menu.mostrar({
      tag: 'Treinamento · versão ' + (window.__versao || '?'), titulo: 'Busca e Apreensão',
      texto: 'Você é policial militar e apoia o cumprimento de um mandado de busca e apreensão num apartamento. O responsável é o inspetor da Polícia Civil; você é avaliado pelo que confere, propõe e faz.\n\n' +
        'Computador: clique fala/usa/abre · V lê o mandado · T menu · Q saca a arma · Z arma de choque · K checklist.\n' +
        'Quest: gatilho fala/usa/abre (segure para puxar gavetas) · X segura o mandado · A saca a arma · Y ou B abre o menu.',
      botoes: [
        { label: 'Modo história (5 cumprimentos guiados)', acao: () => comecar('historia') },
        { label: 'Modo treino (objetivos e dicas)', acao: () => comecar('treino') },
        { label: 'Modo avaliação (sem dicas)', acao: () => comecar('avaliacao') },
        { label: S.voz === false ? 'Voz sintética: desligada (só legendas)' : 'Voz sintética: ligada', acao: () => { S.voz = S.voz === false; aviso(); } },
        { label: 'Cancelar', acao: () => menu.esconder() }
      ]
    });
  }
  async function comecar(modo) {
    fecharPaineis();
    let carregou = false; modelosProntos.then(() => { carregou = true; });
    await new Promise(r => setTimeout(r, 0));
    if (!carregou) {      // no Quest os personagens (~50 MB) podem levar mais de um minuto na primeira vez; depois ficam guardados
      const msg = () => menu.mostrar({ tag: 'Treinamento', titulo: 'Carregando personagens…', texto: `${Object.keys(modelos).length} de ${window.__totalPersonagens || '?'} prontos. Na primeira vez pode levar um ou dois minutos.`, botoes: [] });
      msg(); const tm = setInterval(msg, 1500);
      await Promise.race([modelosProntos, new Promise(r => setTimeout(r, 120000))]); clearInterval(tm); menu.esconder();
    }
    HIST.length = 0;
    Object.assign(S, { ativo: true, inicio: performance.now(), fim: 0, erros: [], graves: [], log: [], historia: modo === 'historia', modo: modo === 'avaliacao' ? 'avaliacao' : 'treino' });
    S.fila = S.historia ? CEN.historia.slice(1) : [];
    if (ctx.hotspots) ctx.hotspots.visible = false;
    document.getElementById('relatorioHTML')?.setAttribute('hidden', '');
    novaOcorrencia(S.historia ? derivar({ ...CEN.historia[0].variacao }) : sortear(), S.historia ? CEN.historia[0] : null);
  }
  function abrirMenu() {
    if (!S.ativo) return aviso();
    fecharPaineis();
    const b = [
      { label: MANDADO()?.naMao ? 'Guardar o mandado' : 'Ler o mandado', acao: () => { menu.esconder(); MANDADO()?.mostrar(!MANDADO()?.naMao); } },
      { label: S.naMao === 'arma' ? 'Guardar a arma no coldre' : 'Sacar a arma de fogo', acao: () => { empunhar(S.naMao === 'arma' ? null : 'arma'); menu.esconder(); } },
      { label: S.naMao === 'choque' ? 'Guardar a arma de choque' : 'Sacar a arma de choque', acao: () => { empunhar(S.naMao === 'choque' ? null : 'choque'); menu.esconder(); } },
      { label: 'Checklist deste cumprimento', acao: abrirChecklist },
      { label: 'Encerrar e ver o relatório', cor: 'rgba(240,80,64,.22)', acao: encerrar },
      { label: 'Fechar', acao: () => menu.esconder() }];
    menu.mostrar({ tag: 'Menu', titulo: 'Busca e Apreensão', texto: `Tempo: ${fmt(tempo())} · ${A ? A.titulo + ' · ' + A.hora : 'aguardando'}`, botoes: b });
  }
  function abrirChecklist() {
    fecharPaineis();
    const linhas = CEN.fases.map(f => `${f.nome}: ` + (f.acoes || []).filter(a => cond(a.condicao)).map(a => (S.feitos.has(a.id) ? '✓ ' : '· ') + a.texto).join(' | ')).join('\n');
    menu.mostrar({ tag: 'Checklist', titulo: 'Checklist do cumprimento', texto: (S.modo === 'avaliacao' ? 'No modo avaliação o checklist só aparece no relatório.' : linhas) + `\n\nTempo: ${fmt(tempo())}`, botoes: [{ label: 'Fechar', acao: () => menu.esconder() }], longe: 1.3 });
  }
  function encerrar() {
    if (!S.ativo) return;
    if (A) { HIST.push(resumo()); A = null; }
    S.fila = []; S.fim = performance.now(); S.ativo = false; fecharPaineis(); empunhar(null); status();
    mostrarRelatorio(relatorio());
  }
  function relatorio() {
    let possiveis = 0, obtidos = 0; const fases = [];
    CEN.fases.forEach((f, i) => {
      const fr = { nome: f.nome, obtidos: 0, possiveis: 0, itens: [] };
      for (const h of HIST) { const x = h.fases[i]; fr.obtidos += x.obtidos; fr.possiveis += x.possiveis; fr.itens.push(...x.itens); }
      possiveis += fr.possiveis; obtidos += fr.obtidos; fases.push(fr);
    });
    const desc = S.erros.reduce((s, e) => s + e.pontos, 0) + S.graves.reduce((s, e) => s + (e.pontos || 0), 0);
    const nota = possiveis ? Math.max(0, Math.min(100, Math.round((obtidos + desc) / possiveis * 100))) : 0;
    const aprovado = nota >= CEN.aprovacao.pontos_minimos && !(CEN.aprovacao.sem_falha_grave && S.graves.length);
    return { cenario: CEN.id, data: new Date().toISOString(), tempo: fmt(tempo()), modo: S.historia ? 'historia' : S.modo, nota, aprovado, obtidos, descontos: desc, possiveis,
      atendimentos: HIST.map(h => ({ n: h.n, titulo: h.titulo, variacao: h.variacao, danos: h.danos, indevidos: h.indevidos, semEntrada: h.semEntrada })), fases, erros: S.erros, falhas_graves: S.graves, linha_do_tempo: S.log };
  }
  function mostrarRelatorio(r) {
    const varios = r.atendimentos.length > 1, at = e => varios ? ` [cumpr. ${e.atendimento}]` : '';
    const danos = r.atendimentos.flatMap(a => a.danos.map(d => d + (varios ? ` [cumpr. ${a.n}]` : '')));
    const indev = r.atendimentos.flatMap(a => a.indevidos.map(d => d + (varios ? ` [cumpr. ${a.n}]` : '')));
    const txtFases = r.fases.map(f => `${f.nome}: ${f.obtidos}/${f.possiveis}`).join('\n');
    const txtErros = [...r.falhas_graves.map(g => '⚠ FALHA GRAVE: ' + g.texto + (g.base ? ` (${g.base})` : '') + at(g)), ...r.erros.map(e => `• ${e.texto} (${e.pontos})${e.feedback ? ' — ' + e.feedback : ''}` + at(e))].join('\n') || 'Nenhum erro registrado.';
    menu.mostrar({
      tag: 'Relatório', titulo: `Nota ${r.nota}/100 · ${r.aprovado ? 'APROVADO' : 'NÃO APROVADO'}`,
      texto: `Tempo: ${r.tempo} · Cumprimentos: ${r.atendimentos.length}\n\n${txtFases}\n\nDanos causados: ${danos.join('; ') || 'nenhum'}\nApreendido sem autorização: ${indev.join('; ') || 'nada'}\n\n${txtErros}`,
      botoes: [{ label: 'Novo treinamento (outras variações)', acao: () => { fecharPaineis(); aviso(); } }, { label: 'Fechar', acao: () => menu.esconder() }], longe: 1.4
    });
    const el = document.getElementById('relatorioHTML');
    if (el) {
      const leis = Object.entries(CEN.base_legal).filter(([k]) => k !== '_nota').map(([k, t]) => `<li><b>${k}</b> — ${t}</li>`).join('');
      el.innerHTML = `<h2>Nota ${r.nota}/100 — ${r.aprovado ? 'aprovado' : 'não aprovado'}</h2>
        <p>Tempo ${r.tempo} · modo ${r.modo}</p>
        <ul>${r.atendimentos.map(a => `<li>${a.titulo} — <em>${RESUMO_V(a.variacao)}</em>${a.semEntrada ? ` — <b>${a.semEntrada}</b>` : ''}</li>`).join('')}</ul>
        ${r.fases.map(f => `<h3>${f.nome} <small>${f.obtidos}/${f.possiveis}</small></h3><ul>${f.itens.map(i => `<li class="${i.ok ? 'ok' : 'nao'}">${i.ok ? '✓' : '✗'} ${i.texto}${varios ? ` [cumpr. ${i.atendimento}]` : ''}${i.base ? ` <em>(${i.base})</em>` : ''}</li>`).join('')}</ul>`).join('')}
        <h3>Danos causados</h3><ul>${(danos.length ? danos : ['Nenhum']).map(d => `<li>${d}</li>`).join('')}</ul>
        <h3>Apreendido sem autorização do mandado</h3><ul>${(indev.length ? indev : ['Nada']).map(d => `<li>${d}</li>`).join('')}</ul>
        <h3>Erros e falhas graves</h3><ul>${txtErros.split('\n').map(l => `<li>${l}</li>`).join('')}</ul>
        <h3>Base legal</h3><ul>${leis}</ul>
        <p><em>Rascunho para validação com os instrutores. Os itens marcados “validar” dependem de norma interna e de conferência das decisões citadas.</em></p>
        <p><button type="button" id="baixarRel">Baixar relatório (JSON)</button> <button type="button" id="fecharRel">Fechar</button></p>`;
      el.hidden = false;
      document.getElementById('baixarRel').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' })); a.download = `relatorio_${r.cenario}_${Date.now()}.json`; a.click(); };
      document.getElementById('fecharRel').onclick = () => el.hidden = true;
    }
  }

  /* ================= clique / gatilho ================= */
  const npcDoHit = obj => Object.values(npcs).find(p => p.userData.hit === obj);
  function portaDoRaio(ray) {
    const ab = ABRIR(); if (!ab) return null;
    const ms = ab.pecas.filter(p => /Apto_30[12]|Quarto_2/.test(p.nome)).flatMap(p => p.ms);
    const h = ray.intersectObjects(ms, false)[0]; if (!h || h.distance > 3.2) return null;
    return h.object.userData.peca;
  }
  function usar(ray, c) {
    for (const p of paineis) if (p.clique(ray)) return true;
    if (S.naMao && (!c || c.userData.mao !== 'left')) return disparar(ray);
    if (!S.ativo || !A || A.fase === 'fim') return false;
    const hn = ray.intersectObjects(Object.values(npcs).filter(n => n.visible).map(n => n.userData.hit), false)[0];
    const hi = ray.intersectObjects(hitsItem.filter(h => h.parent?.visible !== false), false)[0];
    if (hn && hn.distance < 5 && (!hi || hn.distance < hi.distance)) {
      const n = npcDoHit(hn.object), k = n.userData.chave;
      if (n.userData.caido) { legenda('Instrutor', 'Pessoa ferida: peça socorro imediato.', 4); return true; }
      if (k === 'civil') menuCivil(); else if (k === 'porteiro') menuPorteiro(); else if (k === 'apoio') menuApoio(); else if (k === 'parceiro') menuParceiro();
      else if (k === 'vizinha') menuVizinha(); else if (k === 'morador') menuMorador(); else menuFamilia(n);
      return true;
    }
    if (hi && hi.distance < 3) { if (A.fase !== 'busca' && A.fase !== 'auto') return false; menuItem(hi.object.userData.item); return true; }
    const p = portaDoRaio(ray);
    if (p) {
      if (p.nome === 'A_Passagem_Apto_302' && !A.entrou) { menuPorta('302'); return true; }
      if (p.nome === 'A_Passagem_Apto_301' && p.trancada) { menuPorta('301'); return true; }
      if (p.nome === 'A_Passagem_Quarto_2' && p.trancada) { menuQuartoInquilino(); return true; }
    }
    return false;
  }
  function botao(mao) { if (mao === 'right') empunhar(S.naMao === 'arma' ? null : 'arma'); }

  /* ================= objetivos (modo treino) e status ================= */
  function objetivos() {
    const L = [], v = S.variacao;
    if (!A) return ['Aguarde o próximo cumprimento'];
    if (A.fase === 'fim') return ['Cumprimento concluído'];
    if (A.fase === 'portaria') { if (!A.leu) L.push('Leia o mandado (X ou V)'); L.push('Confira endereço, bloco, apartamento e validade com o inspetor'); if (v.horario === 'madrugada' && !A.esperou) L.push(`Agora são ${A.hora}`); L.push('Fale com o porteiro'); L.push('Quando estiver tudo certo, combine a subida com o inspetor'); }
    else if (!A.entrou) { L.push('Vá até a porta certa e bata do lado dela, fora da linha da porta'); L.push('Anuncie-se: polícia, mandado de busca'); if (A.recusou) L.push('O morador se recusa: leia o mandado e decida'); if (A.ausente) L.push('Ninguém em casa: chame uma testemunha antes de entrar'); }
    else { if (!A.acompanha && !A.testemunhas.size) L.push('Peça ao morador que acompanhe a busca'); L.push('Procure só onde o que o mandado pede poderia estar'); L.push('Fotografe, isole e lacre o que encontrar'); if (v.inquilino === 'quarto_trancado') L.push('Há um quarto trancado: descubra de quem é'); L.push('No fim, fale com o inspetor para lavrar o auto'); }
    return L.slice(0, 6);
  }
  function status() {
    const el = document.getElementById('statusTrein'); if (!el) return;
    el.hidden = !S.ativo || S.modo === 'treino';
    el.innerHTML = `<b>${A ? A.titulo : 'Busca e Apreensão'}</b> · ${fmt(tempo())}${A ? ' · ' + A.hora : ''}<br>Na mão: ${S.naMao === 'arma' ? 'arma de fogo' : S.naMao === 'choque' ? 'arma de choque' : MANDADO()?.naMao ? 'mandado' : 'nada'} · apreendidos: ${A?.apreendidos || 0}`;
    mostrarObjetivos();
  }

  /* ================= quadro ================= */
  let ultimo = performance.now(), ultimoAndar = 0; const rayMira = new THREE.Raycaster();
  function quadro() {
    const agora = performance.now(), dt = Math.min(.1, (agora - ultimo) / 1000); ultimo = agora;
    if (agora > legAte) { leg.visible = false; const hl = document.getElementById('legendaHTML'); if (hl && !hl.hidden) hl.hidden = true; }
    camera.getWorldPosition(V); camera.getWorldDirection(V2);
    acompanharLeitura(dt);
    if (S.naMao === 'arma' && A && !A.apontou && !ameacaReal()) {      // arma apontada para uma pessoa que nao ameaca ninguem
      rayMira.set(V, V2); rayMira.far = 8; const h = rayMira.intersectObjects(Object.values(npcs).filter(n => n.visible && !n.userData.caido).map(n => n.userData.hit), false)[0];
      if (h) { A.apontou = true; registrar('arma_apontada_sem_ameaca'); }
    }
    const andar = andar3(V) ? 3 : 0;
    if (S.ativo && A && andar !== ultimoAndar) { equipeNoAndar(andar === 3 ? 6.45 : .15); if (andar === 3 && A.fase === 'portaria') { if (!A.leu) registrar('subir_sem_ler'); A.fase = 'corredor'; } if (andar === 3) setTimeout(vizinhaSai, 6000); }
    ultimoAndar = andar;
    if (S.ativo && A && A.prazoConduta && !A.condutaResolvida && agora > A.prazoConduta) { A.prazoConduta = 0; resolverConduta('deixar'); }
    for (const n of Object.values(npcs)) {
      const u = n.userData; if (!n.visible) continue;
      u.mixer?.update(dt); animarRosto(n, dt, agora);
      if (!u.caido) olhar(n, dt, V);
      ajustarAreaClique(n); moverNPC(n, dt);
      camera.getWorldPosition(V);
      if (u.caido) continue;
      const encarar = u.real && !u.destino && !u.semVirar && !u.rota?.length && V.distanceTo(n.position) < 3.2;
      if (encarar) { let d = Math.atan2(V.x - n.position.x, V.z - n.position.z) - n.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d)); n.rotation.y += d * Math.min(1, dt * 2.5); }
      else if (u.fig && !u.fala && !u.destino && !u.rota?.length) { let d = u.giroBase - n.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d)); n.rotation.y += d * Math.min(1, dt * 1.2); }
    }
    if (S.ativo && Math.floor(agora / 1000) !== Math.floor((agora - dt * 1000) / 1000)) status();
    if (Math.floor(agora / 400) !== Math.floor((agora - dt * 1000) / 400)) luzDosPersonagens();
  }
  // cada personagem recebe a luz do lugar onde esta (lida no lightmap do piso em volta): no corredor fica mais escuro, perto da
  // janela mais claro. Sem isso todos tinham a mesma luz uniforme e pareciam recortados do cenario.
  const PL = new THREE.Vector3(), FR = new THREE.Vector3();
  function luzDosPersonagens() {
    const ab = ABRIR(); if (!ab?.luzLocal) return;
    for (const n of Object.values(npcs)) {
      if (!n.visible) continue; const u = n.userData;
      PL.copy(n.position); PL.y += .02; FR.set(Math.sin(n.rotation.y), 0, Math.cos(n.rotation.y));
      const L = ab.luzLocal(PL, FR); if (L == null) continue;
      const alvo = Math.min(3.2, Math.max(.35, L * Math.PI * 1.15));
      u.luz = u.luz == null ? alvo : u.luz + (alvo - u.luz) * .35;
      const env = ab.dentro ? .05 : .5;      // dentro dos comodos, sem a luz do ceu (como as paredes)
      u.modelo?.traverse(o => { if (o.isMesh) for (const m of [].concat(o.material)) { if (m.lightMap) m.lightMapIntensity = u.luz; m.envMapIntensity = env; if (env < .2 && scene.environment && m.envMap !== scene.environment) { m.envMap = scene.environment; m.needsUpdate = true; } } });
    }
  }

  /* ================= entradas ================= */
  addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.repeat) return;
    if (e.code === 'KeyT') abrirMenu();
    if (e.code === 'KeyK' && S.ativo) abrirChecklist();
    if (e.code === 'KeyQ') empunhar(S.naMao === 'arma' ? null : 'arma');
    if (e.code === 'KeyZ') empunhar(S.naMao === 'choque' ? null : 'choque');
  });
  const bt = document.createElement('button'); bt.type = 'button'; bt.textContent = 'Iniciar treinamento'; bt.id = 'bTrein';
  bt.onclick = aviso; document.getElementById('acoes')?.prepend(bt);
  const esperaAbrir = setInterval(() => { if (ABRIR()) { ABRIR().ouvintes.push(ouvinteAbrir); clearInterval(esperaAbrir); } }, 300);
  setTimeout(() => { if (!S.ativo) aviso(); }, 1200);
  renderer.xr.addEventListener('sessionstart', () => setTimeout(() => { if (!S.ativo) aviso(); }, 1500));

  window.__trein = {
    clique: ray => usar(ray), gatilho: (ray, c) => usar(ray, c), botao, soltar: () => false,
    apontar, painelAberto: () => paineis.some(p => p.mesh.visible),
    menu: abrirMenu, quadro, estado: S, relatorio,
    _t: { comecar, encerrar, objetivos, sortear, derivar, novaOcorrencia, npcs, itens, menuCivil, menuPorteiro, menuApoio, menuParceiro, menuVizinha, menuFamilia, menuConduta, relatorio, menuPorta, menuMorador, menuItem, menuQuartoInquilino, lavrarAuto, finalizar, bater, entrar, usar, empunhar, disparar, condutaMorador, resolverConduta, B, B3,
      ocorrencia: () => A, historico: HIST, botoes: () => (dialogo.mesh.visible ? dialogo : menu).botoes, painel: () => (dialogo.mesh.visible ? dialogo : menu.mesh.visible ? menu : null) }
  };
  return window.__trein;
}
