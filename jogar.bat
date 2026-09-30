@echo off
rem Abre o jogo no Blender. Se o blender.exe nao estiver no PATH:
rem   set BLENDER="C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
rem Argumentos extras vao para o jogo: jogar.bat --quality low --skip-intro
cd /d "%~dp0"
if "%BLENDER%"=="" set BLENDER=blender
"%BLENDER%" SemAlvorada.blend --python play.py -- %*
