# Busca e Apreensão: treinamento em realidade virtual

Cumprimento de mandado de busca e apreensão em um apartamento, no Rio de Janeiro, de dia. O jogador é policial militar
em apoio à equipe que cumpre o mandado. Quarto treinamento da série (depois de "A Casa em Silêncio", "Operação Lei Seca"
e "Cassino clandestino"), com a mesma arquitetura.

## Etapas

1. **Cenário e peças que abrem** (feito): portaria, corredor do 3º andar, apartamento 302 completo e sala do vizinho 301.
   Gavetas, armários, geladeira, forno, tampas e portas abrem de verdade.
2. Mandado na mão (documento que muda a cada rodada), personagens, variações, modos e relatório.
3. Peças remodeladas pelo autor, vozes e ajustes.

## Pastas

| Pasta | Conteúdo |
|---|---|
| `01_Cena_Render_Cycles/` | `busca.py` (**gera a cena inteira**), `busca.blend` (resultado, não editar à mão), `modelos/` |
| `02_Cena_VR_Otimizada/` | `otimizar_para_vr.py`: junta os estáticos, gera a colisão |
| `04_ThreeJS/` | `pipeline_threejs.py` (bake e exportação), `texturas_cc0/`, `hdri/`, `web/` (o site) |
| `05_Treinamento/` | `BASE_LEGAL.md` (pesquisa e pontos a validar), `_base_cassino/` (motor do projeto anterior, para adaptar) |
| `06_Audio/`, `07_Personagens/` | sons e conversor de personagens (avatares em `Downloads\leiseca\07_Personagens\rocketbox`) |

## Como refazer

```
.\atualizar_tudo.ps1 recriar alta
python carimbar_versao.py
```

## Peças que abrem

Em `busca.py`, a classe `Movel` cria o casco do móvel (peças `Mv_*`), as gavetas (`gaveta`), as portas (`folha`) e as
tampas (`tampa`). Cada peça que abre é uma raiz `A_*` com as propriedades `abre`, `curso` ou `ang`, e `eixo`. O pipeline
grava essas propriedades em `cena.json` e o site (`web/abrir.js`) move as peças:

- computador: clique abre ou fecha;
- Quest: apontar e segurar o gatilho; a peça acompanha a mão. Um toque rápido abre ou fecha de uma vez.

As peças que abrem ficam fora do bake: o interior dos móveis recebe a luz do cômodo, e cada peça usa a luz medida no
piso à sua frente.
