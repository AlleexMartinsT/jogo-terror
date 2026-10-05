"""Coerência entre ângulos dos renders 3D dos objetos (fase 4, agente 4): o mesmo instante em todas as câmeras.

    LIBGL_ALWAYS_SOFTWARE=1 python tests/test_objetos_3d.py

Monta o palco do Blender (out/integration/full.blend, Workbench), reproduz a gravação do jogo nos objetos reais e põe o modelo físico
como fantasma azul. Confere, no estilo de tests/test_movimento_ref.py:
    - a ponta da porta nos objetos do .blend está onde a gravação e o modelo mandam (a menos de 1 mm), e a projeção dela em cada
      câmera (planta, frente, jogador) cai no mesmo pixel que a projeção do dado (a menos de meio pixel);
    - renderizar as câmeras não mexe na pose (a pose é aplicada antes e não depende da câmera);
    - a marca laranja do jogo aparece na imagem onde a projeção diz, nas três câmeras;
    - o pêndulo do relógio e o carro, idem (posição 3D dos objetos x dado, e a projeção em cada câmera).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

BLEND = os.path.join(ROOT, "out", "integration", "full.blend")


class Palcos:
    """Um palco por cena, criado uma vez (abrir o .blend e gravar o jogo leva alguns segundos)."""
    _cache = {}

    @classmethod
    def obter(cls, nome):
        if nome not in cls._cache:
            cls._cache.clear()                                # abrir outro .blend invalida os objetos do palco anterior
            from tools.movimento_ref.fisica import cenas3d
            from tools.movimento_ref.fisica.render3d import Palco
            palco = Palco()
            fabrica = {"porta": lambda: cenas3d.CenaPorta(palco, "master_hall"),
                       "relogio": lambda: cenas3d.CenaRelogio(palco, inicio=8.0, duracao=4.0),
                       "carro": lambda: cenas3d.CenaCarro(palco)}[nome]
            cls._cache[nome] = (palco, fabrica())
        return cls._cache[nome]


def _mundo(obj):
    return obj.matrix_world.translation.copy()


def test_door_tip_matches_data_and_projects_to_the_same_pixel_in_every_camera():
    palco, cena = Palcos.obter("porta")
    pior_mm, pior_px = 0.0, 0.0
    for t in (0.5, 0.8, 1.8, 3.75, 6.3, 6.45, 6.6):
        dado_jogo, dado_modelo = cena.dados(t)
        cena.pose(t)
        for marca, dado in ((cena.marca_jogo, dado_jogo), (cena.marca_modelo, dado_modelo)):
            objeto = _mundo(marca)
            pior_mm = max(pior_mm, (objeto - dado).length * 1000.0)
            for nome, cam in cena.cameras.items():
                a, b = palco.projetar(cam, objeto), palco.projetar(cam, dado)
                assert a is not None and b is not None, (t, nome)
                assert 0.0 <= a[0] <= palco.largura and 0.0 <= a[1] <= palco.altura, f"a ponta saiu do quadro em {nome}, t={t}: {a}"
                pior_px = max(pior_px, abs(a[0] - b[0]), abs(a[1] - b[1]))
    assert pior_mm < 1.0, f"a ponta no .blend difere do dado em até {pior_mm:.3f} mm"
    assert pior_px < 0.5, f"a projeção da ponta difere do dado em até {pior_px:.3f} px"
    return f"ponta x dado {pior_mm:.1e} mm, projeção {pior_px:.1e} px"


def test_rendering_the_cameras_does_not_move_the_pose():
    palco, cena = Palcos.obter("porta")
    t = 3.75
    cena.pose(t)
    antes = (_mundo(cena.marca_jogo), _mundo(cena.marca_modelo), cena.pivo.rotation_euler.z, cena.pivo_modelo.rotation_euler.z)
    cena.imagens(t)                                           # pose + as três câmeras, uma a uma
    depois = (_mundo(cena.marca_jogo), _mundo(cena.marca_modelo), cena.pivo.rotation_euler.z, cena.pivo_modelo.rotation_euler.z)
    assert (antes[0] - depois[0]).length == 0.0 and (antes[1] - depois[1]).length == 0.0
    assert antes[2] == depois[2] and antes[3] == depois[3]
    # e a mesma posição 3D é a que as três câmeras enxergam: projeções de um único ponto, nenhuma com folga
    pontos = {nome: palco.projetar(cam, antes[0]) for nome, cam in cena.cameras.items()}
    assert all(p is not None for p in pontos.values()), pontos
    return "mesma pose antes e depois das 3 câmeras"


def test_orange_marker_is_where_the_projection_says_in_each_camera():
    """Renderiza cada câmera com e sem a marca laranja do jogo: a diferença entre as duas imagens é a marca, e o centro dela cai
    onde a projeção do dado manda (o fundo, a maçaneta de latão e o fantasma azul não atrapalham)."""
    palco, cena = Palcos.obter("porta")
    import numpy as np
    t = 0.8
    cena.pose(t)
    dado_jogo, _ = cena.dados(t)
    pior = 0.0
    for nome, cam in cena.cameras.items():
        px, py = palco.projetar(cam, dado_jogo)
        com = palco.render(cam).astype(int)
        cena.marca_jogo.hide_render = True
        sem = palco.render(cam).astype(int)
        cena.marca_jogo.hide_render = False
        diferenca = np.abs(com - sem).sum(axis=2) > 30
        assert diferenca.sum() >= 20, f"a marca laranja não aparece na câmera {nome}"
        ys, xs = np.nonzero(diferenca)
        perto = (np.abs(xs - px) < 25) & (np.abs(ys - py) < 25)
        assert perto.sum() >= 20, f"a diferença entre as imagens não está perto de ({px:.0f}, {py:.0f}) na câmera {nome}"
        centro = (xs[perto].mean(), ys[perto].mean())
        pior = max(pior, abs(centro[0] - px), abs(centro[1] - py))
    assert pior < 4.0, f"a marca laranja está a {pior:.1f} px do ponto projetado"
    return f"marca laranja a {pior:.1f} px da projeção, nas 3 câmeras"


def test_clock_bob_in_the_blend_matches_the_pendulum_model_and_projects_consistently():
    palco, cena = Palcos.obter("relogio")
    pior_mm, pior_px = 0.0, 0.0
    marcas = {"marca_jogo": cena.marca_jogo, "marca_modelo": cena.marca_modelo}
    for t in (8.3, 8.8, 9.3, 9.8, 10.3, 11.0):
        dado_jogo, dado_modelo = cena.dados(t)
        cena.pose(t)
        for nome_marca, dado in (("marca_jogo", dado_jogo), ("marca_modelo", dado_modelo)):
            objeto = _mundo(marcas[nome_marca])
            pior_mm = max(pior_mm, (objeto - dado).length * 1000.0)
            for nome, cam in cena.cameras.items():
                a, b = palco.projetar(cam, objeto), palco.projetar(cam, dado)
                assert a is not None and b is not None, (t, nome)
                pior_px = max(pior_px, abs(a[0] - b[0]), abs(a[1] - b[1]))
    assert pior_mm < 1.0, f"a lentilha no .blend difere do dado em até {pior_mm:.3f} mm"
    assert pior_px < 0.5, f"a projeção da lentilha difere do dado em até {pior_px:.3f} px"
    # o fantasma e o objeto real balançam para o mesmo lado: a diferença entre eles é bem menor que a amplitude
    dado_jogo, dado_modelo = cena.dados(9.3)
    assert (dado_jogo - dado_modelo).length < 0.2 * 1.024 * 0.0436, (dado_jogo, dado_modelo)
    return f"lentilha x dado {pior_mm:.1e} mm, projeção {pior_px:.1e} px"


def test_car_objects_match_the_recording_and_the_ghost_matches_the_model():
    palco, cena = Palcos.obter("carro")
    from tools.movimento_ref.fisica import carro as K
    pior_mm, pior_px, pior_roda_mm = 0.0, 0.0, 0.0
    for t in (7.8, 9.3, 11.0, 13.0, 15.0, 16.2):
        jogo, modelo, pitch_j, pitch_m = cena.dados(t)
        cena.pose(t)
        carro = _mundo(cena.carro)
        fantasma = _mundo(cena.casco)
        pior_mm = max(pior_mm, (carro - jogo).length * 1000.0, (fantasma - modelo).length * 1000.0)
        assert abs(cena.carro.rotation_euler.x - pitch_j) < 1e-6 and abs(cena.casco.rotation_euler.x - pitch_m) < 1e-6
        for nome, cam in cena.cameras.items():
            if nome == "dentro":
                continue
            for objeto, dado in ((carro, jogo), (fantasma, modelo)):
                a, b = palco.projetar(cam, objeto), palco.projetar(cam, dado)
                assert a is not None and b is not None, (t, nome)
                pior_px = max(pior_px, abs(a[0] - b[0]), abs(a[1] - b[1]))
        # as rodas do fantasma encostam no chão (raio 0,33 m sobre o terreno) e rolam o que o carro andou
        for nome, (eixo, sx, sy) in cena.rodas_modelo.items():
            esperado = K.RAIO_RODA + float(K.altura_do_chao(_mundo(eixo).y))
            pior_roda_mm = max(pior_roda_mm, abs(_mundo(eixo).z - esperado) * 1000.0)
            assert abs(eixo.rotation_euler.x - cena.percurso[cena._indice(t)] / K.RAIO_RODA) < 1e-4       # float32 do Blender
    assert pior_mm < 1.0, f"o carro no .blend difere do dado em até {pior_mm:.3f} mm"
    assert pior_px < 0.5, f"a projeção difere do dado em até {pior_px:.3f} px"
    assert pior_roda_mm < 1.0, pior_roda_mm
    return f"carro x dado {pior_mm:.1e} mm, projeção {pior_px:.1e} px"


def main():
    if not os.path.exists(BLEND):
        print(f"test_objetos_3d: pulado ({BLEND} não existe; rode a montagem integrada antes)")
        return 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    falhas = 0
    for fn in tests:
        try:
            nota = fn()
            print(f"  ok   {fn.__name__}" + (f"  ({nota})" if nota else ""))
        except Exception as erro:       # noqa: BLE001
            falhas += 1
            print(f"  FALHOU {fn.__name__}: {type(erro).__name__}: {erro}")
    print("test_objetos_3d: OK" if not falhas else f"test_objetos_3d: {falhas} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
