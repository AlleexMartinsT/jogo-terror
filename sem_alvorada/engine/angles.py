"""Aritmética de ângulos (radianos)."""
import math


def wrap(angle):
    """Leva o ângulo para (-pi, pi]."""
    return (angle + math.pi) % (2 * math.pi) - math.pi


def difference(target, current):
    """Menor giro com sinal que leva `current` até `target`."""
    return wrap(target - current)


def clamp(value, low, high):
    return max(low, min(high, value))
