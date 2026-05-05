"""
CNC Pro - Processador de Imagens
Pré-processamento e otimização de imagens para usinagem CNC
"""

import logging
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class InfoImagem:
    """Informações da imagem processada"""
    dimensoes_px: Tuple[int, int]
    dimensoes_mm: Tuple[float, float]
    resolucao_passos_mm: float
    pixels_ativos: int
    percentual_area: float
    brilho_medio: float
    contraste_medio: float


class ProcessadorImagem:
    """Pré-processador de imagens para CNC"""
    
    def __init__(self):
        self.imagem_original = None
        self.imagem_processada = None
        self.info = None
    
    def carregar_imagem(self, caminho: str) -> bool:
        """
        Carrega imagem do arquivo
        
        Args:
            caminho: Caminho do arquivo de imagem
            
        Returns:
            True se sucesso, False caso contrário
        """
        try:
            self.imagem_original = Image.open(caminho)
            logger.info(f"Imagem carregada: {caminho}")
            logger.info(f"Modo: {self.imagem_original.mode}, Tamanho: {self.imagem_original.size}")
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar imagem: {e}")
            return False
    
    def processar_para_cnc(self, 
                          largura_mm: float, 
                          altura_mm: float, 
                          resolucao_passos_mm: float,
                          limiar: int = 128,
                          inverter: bool = False,
                          suavizar: bool = False,
                          aumentar_contraste: bool = False) -> np.ndarray:
        """
        Processa imagem para usinagem CNC
        
        Args:
            largura_mm: Largura final em mm
            altura_mm: Altura final em mm
            resolucao_passos_mm: Resolução em passos por mm
            limiar: Valor de limiar (0-255)
            inverter: Inverter cores
            suavizar: Aplicar suavização
            aumentar_contraste: Aumentar contraste
            
        Returns:
            Array numpy binário (True=cortar, False=não cortar)
        """
        if self.imagem_original is None:
            raise ValueError("Nenhuma imagem carregada")
        
        # Converte para escala de cinza
        img = self.imagem_original.convert('L')
        
        # Calcula dimensões em pixels
        largura_px = max(1, int(largura_mm * resolucao_passos_mm))
        altura_px = max(1, int(altura_mm * resolucao_passos_mm))
        
        logger.info(f"Redimensionando: {img.size} -> {largura_px} x {altura_px} pixels")
        
        # Redimensiona
        img = img.resize((largura_px, altura_px), Image.Resampling.LANCZOS)
        
        # Aumenta contraste se necessário
        if aumentar_contraste:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)
            logger.info("Contraste aumentado")
        
        # Suaviza se necessário
        if suavizar:
            img = img.filter(ImageFilter.GaussianBlur(radius=1.0))
            logger.info("Suavização aplicada")
        
        # Converte para array
        pixels = np.array(img, dtype=np.uint8)
        
        # Inverte cores se necessário
        if inverter:
            pixels = 255 - pixels
            logger.info("Cores invertidas")
        
        # Aplica limiar
        binario = pixels < limiar
        
        # Coleta informações
        pixels_ativos = np.sum(binario)
        percentual = (pixels_ativos / (largura_px * altura_px)) * 100
        
        self.info = InfoImagem(
            dimensoes_px=(largura_px, altura_px),
            dimensoes_mm=(largura_mm, altura_mm),
            resolucao_passos_mm=resolucao_passos_mm,
            pixels_ativos=int(pixels_ativos),
            percentual_area=percentual,
            brilho_medio=float(np.mean(pixels)),
            contraste_medio=float(np.std(pixels))
        )
        
        self.imagem_processada = binario
        
        logger.info(f"Processamento concluído: {percentual:.1f}% da área será usinada")
        
        return binario
    
    def get_info(self) -> Optional[Dict]:
        """Retorna informações da última imagem processada"""
        if self.info is None:
            return None
        
        return {
            'dimensoes_px': self.info.dimensoes_px,
            'dimensoes_mm': self.info.dimensoes_mm,
            'resolucao_passos_mm': self.info.resolucao_passos_mm,
            'pixels_ativos': self.info.pixels_ativos,
            'percentual_area': round(self.info.percentual_area, 2),
            'brilho_medio': round(self.info.brilho_medio, 1),
            'contraste_medio': round(self.info.contraste_medio, 1)
        }
    
    def gerar_preview(self, tamanho_max: int = 400) -> Image.Image:
        """
        Gera preview da imagem processada para exibição
        
        Args:
            tamanho_max: Tamanho máximo (largura ou altura)
            
        Returns:
            Imagem PIL para exibição
        """
        if self.imagem_processada is None:
            return None
        
        # Converte binário para imagem
        img_preview = Image.fromarray(self.imagem_processada.astype(np.uint8) * 255)
        
        # Redimensiona para preview
        img_preview.thumbnail((tamanho_max, tamanho_max), Image.Resampling.LANCZOS)
        
        return img_preview
    
    def salvar_preview(self, caminho: str) -> bool:
        """Salva preview da imagem processada"""
        try:
            preview = self.gerar_preview()
            if preview:
                preview.save(caminho)
                logger.info(f"Preview salvo: {caminho}")
                return True
        except Exception as e:
            logger.error(f"Erro ao salvar preview: {e}")
        return False