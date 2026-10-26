"""Puntos de entrada de audiotrans y practice: ejecutan su script de bash con el Python del paquete."""
import os
import sys

SH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sh")


def _ejecutar(nombre):
    # Los scripts llaman a los módulos con python -m audiotrans.<módulo>, con este mismo Python
    os.environ["AUDIOTRANS_PYTHON"] = sys.executable
    script = os.path.join(SH, nombre)
    os.execvp("bash", ["bash", script, *sys.argv[1:]])


def audiotrans():
    _ejecutar("audiotrans")


def practice():
    _ejecutar("practice")
