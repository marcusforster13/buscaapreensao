// Busca e Apreensao - o mandado de busca e apreensao que o aluno segura e le.
// Uma folha A4 desenhada num canvas (texto gerado a cada rodada a partir da variacao sorteada). No Quest, o botao X poe ou tira
// o mandado da mao esquerda (ele fica na frente do controle, inclinado para leitura); no computador, a tecla V mostra ou esconde
// o mandado na frente da camera. Nomes, numeros e o juizo sao ficticios; sem brasao oficial.
import * as THREE from 'three';

const NOMES = ['Carlos Eduardo Mendes da Silva', 'Ricardo Alves Pereira', 'Marcos Vinícius Rocha', 'Anderson Luiz Batista', 'Fábio Henrique Moura', 'Rodrigo Teixeira Lima'];
const VARAS = ['1ª', '7ª', '12ª', '19ª', '23ª', '31ª', '37ª'];
const JUIZES = ['Dra. Helena Duarte Campos', 'Dr. Paulo Roberto Siqueira', 'Dra. Mariana Lopes Viana', 'Dr. Eduardo Nogueira Faria'];
const sorteio = (a, r = Math.random) => a[Math.floor(r() * a.length)];
const dois = n => String(n).padStart(2, '0');

// Monta o texto do mandado. v (variacao): endereco = correto | apto_errado | bloco_errado; dados = autoriza | nao_autoriza;
// validade = valido | vencido. O endereco REAL do alvo e sempre Rua das Acacias, 120, Bloco B, apto 302.
export function textoMandado(v = {}, semente = Math.random) {
  const hoje = new Date(); const exp = new Date(hoje); exp.setDate(hoje.getDate() - (v.validade === 'vencido' ? 40 : 3));
  const prazo = 30, vence = new Date(exp); vence.setDate(exp.getDate() + prazo);
  const data = d => `${dois(d.getDate())}/${dois(d.getMonth() + 1)}/${d.getFullYear()}`;
  const apto = v.endereco === 'apto_errado' ? '203' : '302', bloco = v.endereco === 'bloco_errado' ? 'A' : 'B';
  const nome = v.nome || sorteio(NOMES, semente);
  const proc = `${String(Math.floor(semente() * 9e6) + 1e6).padStart(7, '0')}-${dois(Math.floor(semente() * 99))}.${hoje.getFullYear()}.8.19.0001`;
  return {
    nome, apto, bloco, processo: proc, expedido: data(exp), vence: data(vence), vencido: v.validade === 'vencido', dados: v.dados !== 'nao_autoriza',
    vara: sorteio(VARAS, semente), juiz: sorteio(JUIZES, semente),
    endereco: `Rua das Acácias, nº 120, Bloco ${bloco}, apartamento ${apto}, Rio de Janeiro/RJ`,
    objeto: 'aparelhos de telefonia celular, computadores, notebooks, tablets, mídias de armazenamento (pen drives, HDs, cartões de memória) e documentos, cadernos, anotações, cartões bancários e comprovantes relacionados à prática, em tese, do crime de estelionato (Código Penal, art. 171), apurado no inquérito policial em referência',
  };
}

function quebrar(g, texto, x, y, larg, alt) {
  let linha = '';
  for (const p of texto.split(' ')) {
    const t = linha ? linha + ' ' + p : p;
    if (g.measureText(t).width > larg && linha) { g.fillText(linha, x, y); y += alt; linha = p; } else linha = t;
  }
  if (linha) g.fillText(linha, x, y);
  return y + alt;
}

export function desenharMandado(cv, m) {
  const g = cv.getContext('2d'), W = cv.width, H = cv.height, M = 90, L = W - 2 * M;
  g.fillStyle = '#fbfaf6'; g.fillRect(0, 0, W, H);
  g.fillStyle = '#1a1a1a'; g.textAlign = 'center';
  g.font = '700 30px "Times New Roman", serif'; g.fillText('PODER JUDICIÁRIO DO ESTADO DO RIO DE JANEIRO', W / 2, 110);
  g.font = '400 26px "Times New Roman", serif'; g.fillText(`Juízo de Direito da ${m.vara} Vara Criminal da Comarca da Capital`, W / 2, 150);
  g.strokeStyle = '#333'; g.lineWidth = 2; g.beginPath(); g.moveTo(M, 175); g.lineTo(W - M, 175); g.stroke();
  g.font = '700 38px "Times New Roman", serif'; g.fillText('MANDADO DE BUSCA E APREENSÃO DOMICILIAR', W / 2, 240);
  g.textAlign = 'left'; g.font = '400 25px "Times New Roman", serif'; let y = 300;
  g.fillText(`Processo nº ${m.processo}`, M, y); y += 34; g.fillText('Classe: Medidas Cautelares — Pedido de Busca e Apreensão Criminal', M, y); y += 50;
  g.font = '400 27px "Times New Roman", serif'; const lh = 37;
  y = quebrar(g, `O(A) MM. Juiz(a) de Direito, na forma da lei, MANDA a qualquer autoridade policial ou seus agentes que, em cumprimento a este, dirijam-se ao endereço abaixo e procedam à BUSCA E APREENSÃO DOMICILIAR, observadas as formalidades dos arts. 240 a 250 do Código de Processo Penal.`, M, y, L, lh) + 14;
  g.font = '700 27px "Times New Roman", serif'; g.fillText('ENDEREÇO:', M, y); y += lh; g.font = '400 27px "Times New Roman", serif';
  y = quebrar(g, m.endereco, M + 30, y, L - 30, lh) + 10;
  g.font = '700 27px "Times New Roman", serif'; g.fillText('MORADOR / INVESTIGADO:', M, y); y += lh; g.font = '400 27px "Times New Roman", serif';
  y = quebrar(g, m.nome, M + 30, y, L - 30, lh) + 10;
  g.font = '700 27px "Times New Roman", serif'; g.fillText('FINALIDADE (o que se procura):', M, y); y += lh; g.font = '400 27px "Times New Roman", serif';
  y = quebrar(g, `Apreender ${m.objeto}.`, M + 30, y, L - 30, lh) + 10;
  g.font = '700 27px "Times New Roman", serif'; g.fillText('DADOS DOS APARELHOS:', M, y); y += lh; g.font = '400 27px "Times New Roman", serif';
  y = quebrar(g, m.dados ? 'Fica AUTORIZADO o acesso ao conteúdo dos aparelhos e mídias apreendidos (dados armazenados, mensagens e arquivos), para extração e perícia.'
    : 'Autorizada somente a APREENSÃO dos aparelhos. O acesso ao seu conteúdo (dados, mensagens e arquivos) dependerá de nova decisão judicial.', M + 30, y, L - 30, lh) + 10;
  g.font = '700 27px "Times New Roman", serif'; g.fillText('CUMPRIMENTO:', M, y); y += lh; g.font = '400 27px "Times New Roman", serif';
  y = quebrar(g, 'A diligência será realizada durante o dia (Constituição, art. 5º, XI; CPP, art. 245), vedado o início antes das 5h ou depois das 21h (Lei 13.869/2019, art. 22, § 1º, III). Antes de entrar, os executores mostrarão e lerão este mandado ao morador. Ao final, lavrar-se-á auto circunstanciado, assinado por duas testemunhas presenciais (CPP, art. 245, § 7º).', M + 30, y, L - 30, lh) + 10;
  g.font = '700 27px "Times New Roman", serif'; g.fillText(`Expedido em ${m.expedido}.   Validade: 30 dias (até ${m.vence}).`, M, y); y += 70;
  g.font = 'italic 400 30px "Times New Roman", serif'; g.textAlign = 'center'; g.fillText(m.juiz, W / 2, y); y += 34;
  g.font = '400 25px "Times New Roman", serif'; g.fillText('Juiz(a) de Direito', W / 2, y); y += 32;
  g.font = '400 20px "Courier New", monospace'; g.fillStyle = '#555'; g.fillText(`Documento assinado eletronicamente — código ${m.processo.slice(0, 7)}-${m.processo.slice(-4)}`, W / 2, y);
  g.fillStyle = '#9a9a9a'; g.font = '400 18px Consolas, monospace'; g.fillText('Documento fictício para treinamento', W / 2, H - 40);
}

export function iniciarMandado(ctx) {
  const { scene, camera, renderer, controles } = ctx;
  const cv = document.createElement('canvas'); cv.width = 1240; cv.height = 1754;
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  const folha = new THREE.Group();
  const papel = new THREE.Mesh(new THREE.PlaneGeometry(.26, .368), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false, side: THREE.DoubleSide }));
  const prancheta = new THREE.Mesh(new THREE.BoxGeometry(.29, .4, .008), new THREE.MeshStandardMaterial({ color: 0x6b4a2e, roughness: .7 }));
  prancheta.position.z = -.006; const presilha = new THREE.Mesh(new THREE.BoxGeometry(.1, .03, .02), new THREE.MeshStandardMaterial({ color: 0x9a9c9e, metalness: .4, roughness: .35 }));
  presilha.position.set(0, .19, .004); folha.add(prancheta, papel, presilha); folha.visible = false; scene.add(folha);
  let atual = null, naMao = false;
  function gerar(variacao = {}) { atual = textoMandado(variacao); desenharMandado(cv, atual); tex.needsUpdate = true; return atual; }
  gerar({});
  function mao() { return controles.find(c => c.userData.mao === 'left') || controles[0]; }
  function mostrar(sim) {
    naMao = sim; folha.visible = sim;
    if (!sim) { folha.removeFromParent(); scene.add(folha); return; }
    if (renderer.xr.isPresenting) {                    // na mao esquerda, inclinado para o rosto
      const c = mao(); c.add(folha); folha.position.set(.02, .1, -.12); folha.rotation.set(-1.05, 0, 0); folha.scale.setScalar(1.15);
    } else {                                           // no computador: na frente da camera, grande o bastante para ler
      camera.add(folha); folha.position.set(0, -.02, -.42); folha.rotation.set(0, 0, 0); folha.scale.setScalar(1);
    }
  }
  addEventListener('keydown', e => { if (e.code === 'KeyV' && e.target.tagName !== 'INPUT') mostrar(!naMao); });
  const api = { gerar, mostrar, get dados() { return atual; }, get naMao() { return naMao; }, botao(m) { if (m === 'left') { mostrar(!naMao); return true; } return false; } };
  window.__mandado = api;
  return api;
}
