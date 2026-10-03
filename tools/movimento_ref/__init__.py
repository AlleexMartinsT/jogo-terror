"""Movimento de referência: compara o movimento do jogo com mocap real (CMU), com números e imagens.

ESTADO: MARCO 1 PRONTO (gravador, métricas, gráficos e teste). Marco 2 (retarget, palco 3D, vídeo, cenários) em andamento.

Guia de uso (rode tudo com LIBGL_ALWAYS_SOFTWARE=1; detalhes no topo de cada módulo):
  1. Real:   clip = cmu.carregar("07_01"); real = movimento.movimento_de_mocap(clip)       # Movimento: [T, 20 juntas, 3]
  2. Jogo:   jogo = grava.montar_jogo(palco=True)      # só corpo e piso (3 s); sem palco=True abre out/estado_f3.blend (13 s)
             rec = grava.gravar(jogo, grava.roteiro_de_texto("andar 5; parar 1; correr 3"), ossos="armadura")
             mov = rec.movimento_do_passo(0)           # miolo do trecho "andar", sem a aceleração inicial -> Movimento
  3. Medir:  r = metricas.medir_tudo(mov, "zeni")      # r.v = escalares (cadência, passo, apoio, deslize...), r.curvas = % do ciclo
  4. Tabela: linhas = metricas.comparar_metricas(real_r.v, r.v); print(metricas.tabela_texto(linhas))   # valor, dif., tolerância
  5. Figura: graficos.painel_curvas(real_r, r, "out/f4_N/curvas.png"); graficos.painel_tabela(linhas, "out/f4_N/tabela.png")
  6. Disco:  rec.salvar("out/f4_N/x.npz"); grava.Gravacao.carregar("out/f4_N/x.npz")   # grave uma vez, meça muitas
  Linha de comando do gravador: python -m tools.movimento_ref.grava "andar 6; correr 3" --palco --saida out/f4_N/x.npz
  Roteiro: andar S | correr S | parar S | agachar S | agachado S | virar GRAUS S [parado] | olhar GRAUS S (S = segundos);
           em Python: Passo(duracao, mover, lado, correr, agachar, giro, arfagem, entradas={"interact": True}, ao_iniciar=fn(jogo)).
  Método dos eventos: "zeni" para caminhada, "altura" para corrida, "auto" decide pelo número de Froude (acima de ~2,4 m/s
  vira corrida: o jogo que "anda" a 2,6 m/s precisa de metodo="zeni" explícito). Mãos: metricas.perfil_mao / detectar_alcances / ajuste_jerk_minimo. Cabeça: velocidade_angular_cabeca.
  Mocap: cmu.REFERENCIAS (id e motivo de cada clipe). Medidas de referência e tolerâncias: metricas.CAMPOS_MARCHA.

Módulos: bvh, cmu (mocap) | movimento (formato comum) | metricas | graficos | grava (precisa de bpy) | tests/test_movimento_ref.py.
Coisas puras (movimento, metricas, graficos, bvh, cmu) rodam em qualquer Python com numpy e matplotlib; só `grava` importa bpy.
"""
