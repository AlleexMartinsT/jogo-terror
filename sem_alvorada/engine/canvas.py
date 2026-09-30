"""Superfície de desenho 2D do HUD.

`Canvas` só GRAVA operações (retângulos e textos, origem no canto inferior esquerdo, y para cima).
O HUD e as telas desenham nela sem saber de GPU, então dá para testar sem janela.
`GpuCanvas` reproduz as operações num draw handler POST_PIXEL usando `gpu` e `blf`.
"""
import os

# Paleta de papel envelhecido. Nada colorido demais: só o vermelho apagado dos avisos.
PAPER = (0.86, 0.80, 0.66, 1.0)
PAPER_DIM = (0.60, 0.56, 0.46, 1.0)
INK = (0.16, 0.11, 0.07, 1.0)
WARNING = (0.66, 0.24, 0.18, 1.0)
SHADE = (0.02, 0.02, 0.018, 1.0)

MONO_ADVANCE = 0.602          # largura de um caractere do DejaVu Sans Mono, em em


def with_alpha(color, alpha):
    return (color[0], color[1], color[2], color[3] * alpha)


class Canvas:
    """Grava operações de desenho. Subclasses sabem desenhá-las de verdade."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.ops = []

    @property
    def scale(self):
        """Fator relativo a uma janela de 720 px de altura; tudo no HUD é medido em múltiplos disso."""
        return self.height / 720.0

    def rect(self, x, y, w, h, color):
        if color[3] > 0.003 and w > 0 and h > 0:
            self.ops.append(("rect", x, y, w, h, color))

    def text(self, x, y, string, size, color, align="left"):
        """`y` é a linha de base. `align`: left | center | right."""
        if string and color[3] > 0.003:
            width = self.text_width(string, size)
            origin = x - width / 2 if align == "center" else x - width if align == "right" else x
            self.ops.append(("text", origin, y, string, size, color))

    def text_width(self, string, size):
        return len(string) * size * MONO_ADVANCE

    def outline(self, x, y, w, h, thickness, color):
        self.rect(x, y, w, thickness, color)
        self.rect(x, y + h - thickness, w, thickness, color)
        self.rect(x, y, thickness, h, color)
        self.rect(x + w - thickness, y, thickness, h, color)

    def wrapped(self, x, y, string, size, color, max_width, leading=1.35, align="left"):
        """Escreve `string` quebrando em linhas de até `max_width`; devolve a altura usada."""
        lines = wrap_text(self, string, size, max_width)
        for index, line in enumerate(lines):
            self.text(x, y - index * size * leading, line, size, color, align)
        return len(lines) * size * leading

    def clear(self):
        self.ops.clear()


def wrap_text(canvas, string, size, max_width):
    """Quebra por palavras respeitando as quebras de linha existentes."""
    lines = []
    for paragraph in string.split("\n"):
        current = ""
        for word in paragraph.split(" "):
            trial = f"{current} {word}".strip() if current else word
            if current and canvas.text_width(trial, size) > max_width:
                lines.append(current)
                current = word
            else:
                current = trial
        lines.append(current)
    return lines


# --------------------------------------------------------------------------
# GPU
# --------------------------------------------------------------------------
def load_hud_font():
    """DejaVu Sans Mono que acompanha o Blender (é o visual de máquina de escrever); 0 se falhar."""
    try:
        import blf
        import bpy
        folder = bpy.utils.system_resource("DATAFILES", path="fonts")
        path = os.path.join(folder, "DejaVuSansMono.woff2")
        if os.path.exists(path):
            font_id = blf.load(path)
            if font_id >= 0:
                return font_id
    except (ImportError, RuntimeError, TypeError):
        pass
    return 0


class GpuCanvas(Canvas):
    """Canvas que se desenha com gpu/blf. Só use dentro de um draw handler (precisa do contexto de GPU)."""

    def __init__(self, width, height, font_id):
        super().__init__(width, height)
        self.font_id = font_id
        self.failed = None

    def text_width(self, string, size):
        import blf
        blf.size(self.font_id, size)
        return blf.dimensions(self.font_id, string)[0]

    def flush(self):
        """Desenha tudo o que foi gravado, na ordem: retângulos vizinhos viram um único lote."""
        import gpu
        gpu.state.blend_set("ALPHA")
        run = []
        for op in self.ops:
            if op[0] == "rect":
                run.append(op)
                continue
            self._draw_rects(run)
            run = []
            self._draw_text(op)
        self._draw_rects(run)
        gpu.state.blend_set("NONE")
        self.ops.clear()

    def _draw_rects(self, rects):
        if not rects:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        positions, colors, indices = [], [], []
        for _kind, x, y, w, h, color in rects:
            base = len(positions)
            positions += [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            colors += [tuple(color)] * 4
            indices += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        shader = gpu.shader.from_builtin("FLAT_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": positions, "color": colors}, indices=indices)
        batch.draw(shader)

    def _draw_text(self, op):
        import blf
        _kind, x, y, string, size, color = op
        blf.size(self.font_id, size)
        blf.color(self.font_id, *color)
        blf.enable(self.font_id, blf.SHADOW)
        blf.shadow(self.font_id, 3, 0.0, 0.0, 0.0, 0.85 * color[3])
        blf.shadow_offset(self.font_id, 1, -1)
        blf.position(self.font_id, x, y, 0)
        blf.draw(self.font_id, string)
        blf.disable(self.font_id, blf.SHADOW)
