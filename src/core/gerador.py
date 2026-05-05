"""
CNC Pro - Gerador de G-code (Núcleo)
Processa imagens e gera código G-code otimizado
"""

import logging
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class EstrategiaUsinagem(Enum):
    """Estratégias de usinagem disponíveis"""
    POCKET = "pocket"      # Escavação completa
    PROFILE = "profile"    # Apenas contorno
    ZIGZAG = "zigzag"      # Varredura linear
    CONTOUR = "contour"    # Segue o perímetro


@dataclass
class ConfigGerador:
    """Configurações do gerador"""
    # Dimensões e resolução
    largura_mm: float = 100.0
    altura_mm: float = 100.0
    profundidade_mm: float = 3.0
    resolucao_passos_mm: float = 15.0
    
    # Corte
    profundidade_max_passe: float = 0.5
    velocidade_corte: float = 800.0
    velocidade_rapida: float = 3500.0
    altura_seguranca_z: float = 5.0
    
    # Ferramenta
    diametro_ferramenta: float = 3.175
    sobreposicao: float = 0.4
    
    # Processamento
    limiar_preto_branco: int = 128
    estrategia: str = "pocket"
    inverter_cores: bool = False
    suavizar_imagem: bool = False
    blur_radius: float = 1.0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConfigGerador':
        return cls(**{k: v for k, v in data.items() 
                     if k in cls.__dataclass_fields__})


class GeradorGCode:
    """
    Gerador principal de G-code
    Processa imagens e gera comandos CNC
    """
    
    def __init__(self, config: Optional[ConfigGerador] = None):
        self.config = config or ConfigGerador()
        self.passo_mm = 1.0 / self.config.resolucao_passos_mm
        
        logger.info(f"Gerador inicializado: {self.config.resolucao_passos_mm} passos/mm")
        logger.info(f"Estratégia: {self.config.estrategia}")
        logger.info(f"Inverter cores: {self.config.inverter_cores}")
    
    def gerar_gcode(self, imagem_array: np.ndarray) -> List[str]:
        """
        Gera G-code a partir de um array numpy da imagem
        
        Args:
            imagem_array: Array numpy da imagem em escala de cinza (0-255)
            
        Returns:
            Lista de strings com comandos G-code
        """
        try:
            dimensoes_px = imagem_array.shape
            altura_px, largura_px = dimensoes_px
            
            logger.info(f"Processando imagem: {largura_px} x {altura_px} pixels")
            logger.info(f"Área total: {(largura_px * altura_px):,} pixels")
            
            # Aplica inversão se necessário
            if self.config.inverter_cores:
                imagem_array = 255 - imagem_array
                logger.info("Cores invertidas (decalque)")
            
            # Aplica limiar
            imagem_binaria = imagem_array < self.config.limiar_preto_branco
            
            # Calcula pixels ativos
            pixels_ativos = np.sum(imagem_binaria)
            percentual_area = (pixels_ativos / (largura_px * altura_px)) * 100
            logger.info(f"Área a ser usinada: {percentual_area:.1f}% ({pixels_ativos:,} pixels)")
            
            # Calcula passes
            num_passes, incremento = self._calcular_passes()
            logger.info(f"Total de passes: {num_passes} (incremento: {incremento:.3f}mm)")
            
            # Gera G-code
            gcode = []
            gcode.extend(self._gerar_cabecalho())
            
            if self.config.estrategia == "pocket":
                gcode.extend(self._gerar_pocket(imagem_binaria, num_passes, incremento))
            elif self.config.estrategia == "profile":
                gcode.extend(self._gerar_profile(imagem_binaria, num_passes, incremento))
            elif self.config.estrategia == "zigzag":
                gcode.extend(self._gerar_zigzag(imagem_binaria, num_passes, incremento))
            else:
                gcode.extend(self._gerar_pocket(imagem_binaria, num_passes, incremento))
            
            gcode.extend(self._gerar_rodape())
            
            logger.info(f"G-code gerado: {len(gcode):,} linhas")
            return gcode
            
        except Exception as e:
            logger.error(f"Erro ao gerar G-code: {e}", exc_info=True)
            raise
    
    def _calcular_passes(self) -> Tuple[int, float]:
        """Calcula número de passes e incremento por passe"""
        profundidade_abs = abs(self.config.profundidade_mm)
        num_passes = max(1, int(np.ceil(profundidade_abs / self.config.profundidade_max_passe)))
        incremento = profundidade_abs / num_passes
        return num_passes, incremento
    
    def _gerar_cabecalho(self) -> List[str]:
        """Gera cabeçalho do G-code com informações detalhadas"""
        return [
            "(CNC Pro - G-code Gerado Automaticamente)",
            f"(Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
            f"(Arquivo: {datetime.now().strftime('%Y%m%d_%H%M%S')}.nc)",
            f"(Dimensões X: {self.config.largura_mm:.2f} mm)",
            f"(Dimensões Y: {self.config.altura_mm:.2f} mm)",
            f"(Profundidade Z: {self.config.profundidade_mm:.2f} mm)",
            f"(Resolução: {self.config.resolucao_passos_mm:.1f} passos/mm)",
            f"(Estratégia: {self.config.estrategia.upper()})",
            f"(Ferramenta: {self.config.diametro_ferramenta:.2f} mm)",
            f"(Velocidade corte: {self.config.velocidade_corte:.0f} mm/min)",
            "",
            "G90 ; Coordenadas absolutas",
            "G21 ; Unidades em milímetros",
            "G17 ; Plano XY",
            f"M3 S10000 ; Liga spindle",
            f"G0 Z{self.config.altura_seguranca_z:.3f} F{self.config.velocidade_rapida:.1f}",
            "G0 X0 Y0 ; Ponto inicial",
            ""
        ]
    
    def _gerar_pocket(self, imagem: np.ndarray, num_passes: int, incremento: float) -> List[str]:
        """Estratégia Pocket - Escavação completa da área"""
        gcode = []
        altura_px, largura_px = imagem.shape
        
        logger.info("Gerando estratégia POCKET (escavação completa)")
        
        for passe in range(1, num_passes + 1):
            z_atual = -(incremento * passe)
            gcode.append(f"(Passe {passe}/{num_passes} - Profundidade: {z_atual:.3f} mm)")
            gcode.append(f"F{self.config.velocidade_corte:.1f}")
            
            em_corte = False
            linhas_escavadas = 0
            
            for y in range(altura_px):
                y_mm = y * self.passo_mm
                
                # Zig-zag para otimização
                if y % 2 == 0:
                    for x in range(largura_px):
                        if imagem[y, x]:
                            x_mm = x * self.passo_mm
                            if not em_corte:
                                gcode.append(f"G0 X{x_mm:.3f} Y{y_mm:.3f}")
                                gcode.append(f"G1 Z{z_atual:.3f}")
                                em_corte = True
                            else:
                                gcode.append(f"G1 X{x_mm:.3f} Y{y_mm:.3f}")
                            linhas_escavadas += 1
                        elif em_corte:
                            gcode.append(f"G0 Z{self.config.altura_seguranca_z:.3f}")
                            em_corte = False
                else:
                    for x in range(largura_px - 1, -1, -1):
                        if imagem[y, x]:
                            x_mm = x * self.passo_mm
                            if not em_corte:
                                gcode.append(f"G0 X{x_mm:.3f} Y{y_mm:.3f}")
                                gcode.append(f"G1 Z{z_atual:.3f}")
                                em_corte = True
                            else:
                                gcode.append(f"G1 X{x_mm:.3f} Y{y_mm:.3f}")
                            linhas_escavadas += 1
                        elif em_corte:
                            gcode.append(f"G0 Z{self.config.altura_seguranca_z:.3f}")
                            em_corte = False
            
            if em_corte:
                gcode.append(f"G0 Z{self.config.altura_seguranca_z:.3f}")
            
            logger.info(f"Passe {passe}: escavou {linhas_escavadas:,} pontos")
        
        return gcode
    
    def _gerar_profile(self, imagem: np.ndarray, num_passes: int, incremento: float) -> List[str]:
        """Estratégia Profile - Apenas o contorno"""
        gcode = []
        altura_px, largura_px = imagem.shape
        
        logger.info("Gerando estratégia PROFILE (apenas contorno)")
        
        # Encontra pixels de borda
        bordas = []
        for y in range(altura_px):
            for x in range(largura_px):
                if imagem[y, x]:
                    # Verifica se é borda (tem vizinho branco)
                    is_borda = False
                    if y == 0 or y == altura_px - 1 or x == 0 or x == largura_px - 1:
                        is_borda = True
                    else:
                        if (not imagem[y-1, x] or not imagem[y+1, x] or
                            not imagem[y, x-1] or not imagem[y, x+1]):
                            is_borda = True
                    
                    if is_borda:
                        bordas.append((x * self.passo_mm, y * self.passo_mm))
        
        logger.info(f"Encontrados {len(bordas)} pontos de borda")
        
        # Ordena bordas (algoritmo do vizinho mais próximo)
        if bordas:
            pontos_ordenados = [bordas[0]]
            restantes = bordas[1:]
            
            while restantes:
                ultimo = pontos_ordenados[-1]
                mais_proximo = min(restantes, 
                                  key=lambda p: (p[0] - ultimo[0])**2 + (p[1] - ultimo[1])**2)
                pontos_ordenados.append(mais_proximo)
                restantes.remove(mais_proximo)
            
            for passe in range(1, num_passes + 1):
                z_atual = -(incremento * passe)
                gcode.append(f"(Passe {passe}/{num_passes} - Profundidade: {z_atual:.3f} mm)")
                gcode.append(f"F{self.config.velocidade_corte:.1f}")
                
                gcode.append(f"G1 X{pontos_ordenados[0][0]:.3f} Y{pontos_ordenados[0][1]:.3f} Z{z_atual:.3f}")
                for x, y in pontos_ordenados[1:]:
                    gcode.append(f"G1 X{x:.3f} Y{y:.3f}")
                
                gcode.append(f"G0 Z{self.config.altura_seguranca_z:.3f}")
        
        return gcode
    
    def _gerar_zigzag(self, imagem: np.ndarray, num_passes: int, incremento: float) -> List[str]:
        """Estratégia Zig-Zag - Varredura linear"""
        gcode = []
        altura_px, largura_px = imagem.shape
        
        logger.info("Gerando estratégia ZIG-ZAG (varredura linear)")
        
        for passe in range(1, num_passes + 1):
            z_atual = -(incremento * passe)
            gcode.append(f"(Passe {passe}/{num_passes} - Profundidade: {z_atual:.3f} mm)")
            gcode.append(f"F{self.config.velocidade_corte:.1f}")
            
            linhas_cortadas = 0
            
            for y in range(altura_px):
                y_mm = y * self.passo_mm
                
                if y % 2 == 0:
                    for x in range(largura_px):
                        if imagem[y, x]:
                            x_mm = x * self.passo_mm
                            gcode.append(f"G1 X{x_mm:.3f} Y{y_mm:.3f} Z{z_atual:.3f}")
                            linhas_cortadas += 1
                else:
                    for x in range(largura_px - 1, -1, -1):
                        if imagem[y, x]:
                            x_mm = x * self.passo_mm
                            gcode.append(f"G1 X{x_mm:.3f} Y{y_mm:.3f} Z{z_atual:.3f}")
                            linhas_cortadas += 1
            
            gcode.append(f"G0 Z{self.config.altura_seguranca_z:.3f}")
            logger.info(f"Passe {passe}: cortou {linhas_cortadas:,} pontos")
        
        return gcode
    
    def _gerar_rodape(self) -> List[str]:
        """Gera rodapé do G-code"""
        return [
            "",
            "M5 ; Desliga spindle",
            f"G0 Z{self.config.altura_seguranca_z:.3f} ; Sobe ferramenta",
            "G0 X0 Y0 ; Retorna à origem",
            "M30 ; Fim do programa"
        ]
    
    def salvar_gcode(self, gcode: List[str], caminho: str) -> bool:
        """Salva G-code em arquivo"""
        try:
            path = Path(caminho)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('\n'.join(gcode), encoding='utf-8')
            logger.info(f"G-code salvo: {path} ({len(gcode):,} linhas)")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar G-code: {e}")
            return False
    
    def gerar_relatorio(self, gcode: List[str]) -> Dict:
        """Gera relatório estatístico do G-code"""
        # Análise básica
        movimentos_corte = len([l for l in gcode if l.startswith('G1')])
        movimentos_rapidos = len([l for l in gcode if l.startswith('G0')])
        
        # Cálculo de distância aproximada (simplificado)
        distancia_total = movimentos_corte * self.passo_mm * 2  # Estimativa
        
        return {
            'total_linhas': len(gcode),
            'movimentos_corte': movimentos_corte,
            'movimentos_rapidos': movimentos_rapidos,
            'distancia_aproximada_mm': distancia_total,
            'tempo_estimado_min': distancia_total / self.config.velocidade_corte,
            'profundidade_max_mm': self.config.profundidade_mm,
            'area_usinada_mm2': self.config.largura_mm * self.config.altura_mm
        }