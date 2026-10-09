"""Movimento de referência: compara o movimento do jogo com mocap real (CMU), com números, imagens e vídeo.

ESTADO: MARCO 1 PRONTO (gravador, métricas, gráficos, teste). MARCO 2 PRONTO (retarget, palco, comparar, cenários).

Guia de uso (rode tudo com LIBGL_ALWAYS_SOFTWARE=1; detalhes no topo de cada módulo):
  1. Real:   clip = cmu.carregar("07_01"); real = movimento.movimento_de_mocap(clip)       # Movimento: [T, 21 juntas, 3]
  2. Jogo:   jogo = grava.montar_jogo(palco=True)      # só corpo e piso (3 s); sem palco=True abre out/estado_completo_<versão do Blender>.blend (13 s)
             rec = grava.gravar(jogo, grava.roteiro_de_texto("andar 5; parar 1; correr 3"), ossos="armadura")
             mov = rec.movimento_do_passo(0)           # miolo do trecho "andar", sem a aceleração inicial -> Movimento
  3. Medir:  r = metricas.medir_tudo(mov, "zeni")      # r.v = escalares (cadência, passo, apoio, deslize...), r.curvas = % do ciclo
  4. Tabela: linhas = metricas.comparar_metricas(real_r.v, r.v); print(metricas.tabela_texto(linhas))   # valor, dif., tolerância
  5. Figura: graficos.painel_curvas(real_r, r, "out/f4_N/curvas.png"); graficos.painel_tabela(linhas, "out/f4_N/tabela.png")
  6. Disco:  rec.salvar("out/f4_N/x.npz"); grava.Gravacao.carregar("out/f4_N/x.npz")   # grave uma vez, meça muitas
  7. TUDO:   python -m tools.movimento_ref.comparar <cenario> --vistas frente,lado,topo,primeira --saida out/f4_N/<cenario>
             gera video.mp4 ([real | jogo] em cada vista, 30 quadros/s), folha_contato.png, curvas.png, tabela.png/.txt, apoios.png;
             --lista mostra os cenários; --folha-retarget 07_01 confere o retarget (mocap em linhas sobre o Daniel).
  8. Cenário novo: subclasse de cenarios.Cenario (marcha) ou CenarioAlcance (mão) em cenarios/locomocao.py, maos.py ou objetos.py,
             com @registrar; veja cenarios/base.py (ganchos) e cenarios/exemplo.py ("andar" e "alcance_exemplo"). Gesto sem corpo
             (porta, pêndulo): sobrescreva Cenario.executar e use comparar.escrever_mp4 / grade / rotular.
  Roteiro do jogo: andar S | correr S | parar S | agachar S | agachado S | virar GRAUS S [parado] | olhar GRAUS S (S = segundos);
           em Python: grava.Passo(duracao, mover, lado, correr, agachar, giro, arfagem, entradas={"interact": True},
           ao_iniciar=fn(jogo), por_quadro=fn(jogo, t, k)); por_quadro roda antes de CADA tick (guia mãos, alvos, luzes).
  Método dos eventos: "zeni" para caminhada, "altura" para corrida, "auto" decide pelo número de Froude (acima de ~2,4 m/s
  vira corrida: o jogo que "anda" depressa precisa de metodo="zeni" explícito). Mãos: metricas.perfil_mao / detectar_alcances /
  ajuste_jerk_minimo. Cabeça: velocidade_angular_cabeca, fases_do_ponto_baixo_por_passo. Retarget: retarget.retargetar(clip,
  bracos="direcao"|"ik"); limites no topo de retarget.py. Palco: palco.Palco(640, 360); vistas frente, lado, costas, topo,
  tres_quartos, primeira_pessoa.
  Mocap: cmu.REFERENCIAS (um clipe por gesto), cmu.GRUPOS (12 clipes de andar e 3 de correr para a faixa +-1 desvio),
  python -m tools.movimento_ref.referencias (tabela MEDIDA de todos os clipes). Tolerâncias: metricas.CAMPOS_MARCHA.

Módulos: bvh, cmu (mocap) | movimento (formato comum) | metricas | graficos | grava (precisa de bpy) | retarget, palco, comparar,
cenarios/ (precisam de bpy) | referencias | tests/test_movimento_ref.py.
Coisas puras (movimento, metricas, graficos, bvh, cmu) rodam em qualquer Python com numpy e matplotlib.
"""
