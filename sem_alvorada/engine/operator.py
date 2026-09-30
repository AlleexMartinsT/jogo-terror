"""Operador modal `sa.play`: a janela do jogo. A lógica está em `session.PlaySession`."""
import bpy
from bpy.props import BoolProperty, EnumProperty

from .session import PlaySession
from .windowing import find_view3d


class SA_OT_play(bpy.types.Operator):
    """Joga SEM ALVORADA nesta janela (Esc pausa; um segundo Esc sai)"""
    bl_idname = "sa.play"
    bl_label = "Jogar SEM ALVORADA"
    bl_options = {"REGISTER"}

    quality: EnumProperty(name="Qualidade", default="medium",
                          items=[("low", "Baixa", ""), ("medium", "Média", ""), ("high", "Alta", "")])
    skip_intro: BoolProperty(name="Pular abertura", default=False)
    debug: BoolProperty(name="Depuração", default=False)

    def invoke(self, context, event):
        found = find_view3d(context.window_manager)
        if found is None:
            self.report({"ERROR"}, "SEM ALVORADA precisa de um editor 3D aberto.")
            return {"CANCELLED"}
        window, area, _region = found
        self.session = PlaySession(context, self.quality, self.skip_intro, self.debug)
        try:
            self.session.start(window, area)
        except Exception as error:      # noqa: BLE001 - se não deu para começar, devolve a interface
            self.session.finish()
            self.report({"ERROR"}, f"Não foi possível iniciar o jogo: {error}")
            raise
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if self.session.handle_event(event):
            return {"RUNNING_MODAL"}
        return {"FINISHED"}

    def cancel(self, context):
        self.session.finish()


def register():
    if hasattr(bpy.types, SA_OT_play.__name__):
        bpy.utils.unregister_class(getattr(bpy.types, SA_OT_play.__name__))
    bpy.utils.register_class(SA_OT_play)


def unregister():
    bpy.utils.unregister_class(SA_OT_play)
