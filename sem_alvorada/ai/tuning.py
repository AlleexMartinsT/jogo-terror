"""Todos os números de percepção e comportamento da entidade, num só lugar.

Agressividade (0, 1, 2) escala vários deles por `per_level`: veja `BrainTuning.scaled`.
"""
from dataclasses import dataclass, field

from .. import conventions as C


@dataclass(frozen=True)
class BrainTuning:
    # ---- visão ----------------------------------------------------------
    fov_deg: float = 110.0              # cone de visão
    flash_range: float = C.FLASH_RANGE_VISION      # lanterna acesa apontada para ele
    dark_range: float = C.DARK_VISION_RANGE        # no escuro
    glow_range_factor: float = 1.4      # lanterna acesa mas apontada para outro lado: a luz vaza pelo cômodo
    flash_aim_deg: float = 28.0         # meio-ângulo em que a lanterna "aponta para ele" (spot 48/2 + folga)
    crouch_vision: float = 0.6          # agachado enxerga-se de menos longe
    still_vision: float = 0.7           # parado também
    run_vision: float = 1.25            # correr chama atenção
    still_speed: float = 0.15           # m/s abaixo disto o jogador está "parado"
    run_speed: float = 2.85             # m/s acima disto é "correndo" (no meio entre andar 1,7 e correr 4,0, como 3,6 entre 2,6 e 4,6)
    touch_range: float = 1.3            # colado nele, ignora o cone
    # ---- consciência (0..1) ---------------------------------------------
    gain_far: float = 0.35              # por segundo, jogador visível no limite do alcance
    gain_near: float = 1.4              # soma por segundo quando colado
    decay_per_s: float = 0.12
    chase_awareness: float = 0.6
    stalk_awareness: float = 0.25
    stalk_gain_factor: float = 0.3     # espreitando, a consciência sobe mais devagar
    presence_radius: float = 3.0        # no mesmo cômodo, perto, ele "sente" mesmo sem ver
    presence_gain: float = 0.15
    presence_cap: float = 0.45
    # ---- audição -----------------------------------------------------------
    chase_loudness: float = 0.55        # som efetivo desta força leva direto à perseguição
    chase_loudness_per_level: float = -0.08
    repeat_count: int = 3               # sons repetidos ...
    repeat_window: float = 4.0          # ... dentro desta janela ...
    repeat_min_loudness: float = 0.15   # ... cada um acima disto: perseguição
    hearing_bump: float = 0.6           # cada som novo do jogador soma isto x volume à consciência
    hearing_cap: float = 0.5            # ...mas o som sozinho nunca passa disto
    error_radius_max: float = 4.0       # erro de localização do som fraco (m); cai com o volume
    distract_min_loudness: float = 0.25 # evento ambiental precisa chegar com isto x peso
    ambient_weight: dict = field(default_factory=lambda: {
        "phone": 1.3, "glass": 1.3, "tv_burst": 1.0, "thud": 0.9, "clock_chime": 0.9, "creak": 0.5})
    # ---- movimento ---------------------------------------------------------
    speed_patrol: float = C.ENTITY_SPEED_PATROL
    speed_stalk: float = C.ENTITY_SPEED_STALK
    speed_chase: float = C.ENTITY_SPEED_CHASE
    speed_investigate_factor: float = 1.15
    patrol_speed_per_level: float = 0.15      # +15% por nível de agressividade
    chase_speed_per_level: float = 0.174      # +0,174 m/s por nível (era 0,20 com a perseguição a 4,1; mesma proporção)
    turn_rate_walk: float = 3.0               # rad/s
    turn_rate_chase: float = 6.0
    # ---- tempos --------------------------------------------------------------
    patrol_pause: tuple = (2.0, 5.0)
    investigate_linger: float = 3.0
    lose_time: float = 4.0                    # sem ver nem ouvir por isto: search
    lose_time_per_level: float = 1.5
    search_time: float = 8.0
    search_time_per_level: float = 2.0
    search_linger: float = 1.5
    stalk_give_up: float = 10.0
    stalk_cooldown: float = 6.0               # depois de desistir de espreitar, não espreita de novo por isto
    stalk_radius: float = 7.0
    stalk_quiet_level: float = 0.12           # ruído do jogador abaixo disto = quieto
    stalk_quiet_speed: float = 0.99     # entre agachar (0,8) e andar (1,7), na mesma posição que 1,5 entre 1,2 e 2,6
    attack_windup: float = 0.35
    attack_cancel_factor: float = 1.8         # jogador fugiu além disto x distância de morte: cancela
    replan_seconds: float = 0.35              # perseguição com o alvo à vista
    patrol_player_bias: float = 0.2           # chance por nível de patrulhar o cômodo do jogador
    # ---- drone ------------------------------------------------------------
    drone_near: float = 2.5
    drone_far: float = 16.0
    drone_smoothing: float = 1.5              # 1/s

    def scaled(self, base, per_level, aggression):
        return base + per_level * aggression
