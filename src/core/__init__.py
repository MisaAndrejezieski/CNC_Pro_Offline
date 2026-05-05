"""Módulo core do CNC Pro"""

from .gerador import GeradorGCode
from .processador import ProcessadorImagem

__all__ = ['GeradorGCode', 'ProcessadorImagem']