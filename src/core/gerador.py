"""
CNC Pro - Gerador de G-code (Núcleo)
Versão 3.0 - Suporte a Relevo 3D (Gray Scale Relief)
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
    POCKET = "pocket"      # Escavação completa (2.5D)
    PROFILE = "profile"    # Apenas contorno (2.5D)
    ZIGZAG = "zigzag"      # Varredura linear (2.5D)
    RELIEF_3D = "relief_3d"  # Relevo 3D (Gray Scale) - NOVO!


@dataclass
class ConfigGerador:
    """Configurações do gerador"""
    # Dimensões e resolução
    largura_mm: float = 100.0
    altura_mm: float = 100.0
    profundidade_mm: float = 3.0
    resolucao_passos_mm: float = 10.0  # Reduzido para 3D
    
    # Corte
    profundidade_max_passe: float = 0.5
    velocidade_corte: float = 600.0  # Mais lento para 3D
    velocidade_rapida: float = 3500.0
    altura_seguranca_z: float = 5.0
    
    # Ferramenta
    diametro_ferramenta: float = 3.175
    sobreposicao: float = 0.4
    
    # Processamento
    limiar_preto_branco: int = 128
    estrategia: str = "relief_3d"  # Padrão agora é 3D!
    inverter_cores: bool = False
    suavizar_imagem: bool = True  # Importante para 3D
    blur_radius: float = 1.0
    
    # Controle de qualidade 3D
    qualidade_3d: int = 1  # 1=normal, 2=alta, 3=extra (usa step)
    profundidade_maxima_mm: float = 3.0
    profundidade_minima_mm: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConfigGerador':
        return cls(**{k: v for k, v in data.items() 
                     if k in cls.__dataclass_fields__})


class GeradorGCode:
    """
    Gerador profissional de G-code
    Suporte a relevo 3D (gray scale relief)
    """
    
    def __init__(self, config: Optional[ConfigGerador] = None):
        self.config = config or ConfigGerador()
        self.passo_mm = 1.0 / self.config.resolucao_passos_mm
        
        # Mapeamento de qualidade para step de pixel
        self.qualidade_step = {
            1: 1,      # Normal: todos os pixels
            2: 2,      # Alta: 1 a cada 2 pixels
            3: 3,      # Extra: 1 a cada 3 pixels
        }
        
        logger.info(f"Gerador inicializado: {self.config.resolucao_passos_mm} passos/mm")
        logger.info(f"Estratégia: {self.config.estrategia}")
    
    def _validar_parametros(self):
        """Valida e ajusta parâmetros para evitar G-codes gigantes"""
        
        # Limita resolução para 3D (máximo 20 passos/mm)
        if self.config.estrategia == "relief_3d" and self.config.resolucao_passos_mm > 20:
            logger.warning(f"Resolução {self.config.resolucao_passos_mm} é muito alta para 3D! Reduzindo para 15 passos/mm")
            self.config.resolucao_passos_mm = 15
            self.passo_mm = 1.0 / self.config.resolucao_passos_mm
        
        # Limita dimensões para 3D
        max_dim = 300 if self.config.estrategia == "relief_3d" else 500
        if self.config.largura_mm > max_dim:
            logger.warning(f"Largura {self.config.largura_mm}mm é muito grande! Reduzindo para {max_dim}mm")
            self.config.largura_mm = max_dim
        
        if self.config.altura_mm > max_dim:
            logger.warning(f"Altura {self.config.altura_mm}mm é muito grande! Reduzindo para {max_dim}mm")
            self.config.altura_mm = max_dim
        
        # Calcula total de pixels e alerta
        total_pixels = int((self.config.largura_mm * self.config.resolucao_passos_mm) * 
                          (self.config.altura_mm * self.config.resolucao_passos_mm))
        
        if total_pixels > 2_000_000:  # 2 milhões de pixels
            logger.warning(f"⚠️ Total de pixels: {total_pixels:,.0f} é MUITO ALTO para 3D!")
            logger.warning(f"💡 O arquivo G-code será muito grande. Considere reduzir resolução ou dimensões.")
            
            if self.config.estrategia == "relief_3d":
                nova_resolucao = int((1_000_000 / (self.config.largura_mm * self.config.altura_mm)) ** 0.5)
                nova_resolucao = max(5, min(nova_resolucao, 12))
                logger.warning(f"💡 Sugestão: use resolução de {nova_resolucao} passos/mm para 3D")
    
    def gerar_gcode(self, imagem_array: np.ndarray) -> List[str]:
        """
        Gera G-code baseado na estratégia selecionada
        """
        if self.config.estrategia == "relief_3d":
            return self.gerar_gcode_relief_3d(imagem_array)
        elif self.config.estrategia == "profile":
            return self.gerar_gcode_profile(imagem_array)
        elif self.config.estrategia == "zigzag":
            return self.gerar_gcode_zigzag(imagem_array)
        else:
            return self.gerar_gcode_pocket(imagem_array)
    
    def gerar_gcode_relief_3d(self, imagem_array: np.ndarray) -> List[str]:
        """
        Gera G-code para RELEVO 3D (entalhe artístico)
        A profundidade varia conforme o brilho do pixel (gray scale)
        
        Como funciona:
        - Preto (0) = profundidade máxima (escava mais fundo)
        - Branco (255) = profundidade 0 (não corta)
        - Tons de cinza (1-254) = profundidades intermediárias
        """
        try:
            self._validar_parametros()
            
            altura_px, largura_px = imagem_array.shape
            passo_x = self.config.largura_mm / largura_px
            passo_y = self.config.altura_mm / altura_px
            profundidade_max = self.config.profundidade_mm
            
            # Pulos de qualidade (otimização)
            step = self.qualidade_step.get(self.config.qualidade_3d, 1)
            
            # Calcula número de pontos
            pontos_x = largura_px // step
            pontos_y = altura_px // step
            total_pontos = pontos_x * pontos_y
            
            logger.info(f"🎨 Gerando RELEVO 3D (Gray Scale Relief)")
            logger.info(f"📐 Dimensões: {largura_px} x {altura_px} pixels")
            logger.info(f"🔍 Resolução: {self.config.resolucao_passos_mm} passos/mm")
            logger.info(f"📏 Passo XY: {passo_x:.3f} x {passo_y:.3f} mm")
            logger.info(f"⚙️ Qualidade: step={step} | Pontos a gerar: {total_pontos:,}")
            logger.info(f"🎨 Profundidade máxima: {profundidade_max} mm")
            
            gcode = []
            gcode.extend(self._gerar_cabecalho())
            gcode.append(f"F{self.config.velocidade_corte:.1f} ; Velocidade de corte para relevo 3D")
            gcode.append("")
            
            pontos_gerados = 0
            z_max = 0
            z_min = 0
            
            # ========== GERANDO RELEVO 3D ==========
            # Estratégia: varredura tipo "raster" para melhor acabamento
            for y in range(0, altura_px, step):
                y_mm = y * passo_y
                
                # Alterna direção a cada linha para otimizar (zig-zag)
                if (y // step) % 2 == 0:
                    x_range = range(0, largura_px, step)
                else:
                    x_range = range(largura_px - 1, -1, -step)
                
                for x in x_range:
                    brilho = imagem_array[y, x]
                    
                    # Converte brilho (0-255) para profundidade (0 até profundidade_max)
                    # Fórmula: profundidade = (1 - brilho/255) * profundidade_max
                    profundidade = (255 - brilho) / 255 * profundidade_max
                    
                    if profundidade > 0.01:  # Só gera ponto se profundidade significativa
                        x_mm = x * passo_x
                        z = -profundidade
                        
                        if z < z_min:
                            z_min = z
                        if z > z_max:
                            z_max = z
                        
                        gcode.append(f"G1 X{x_mm:.3f} Y{y_mm:.3f} Z{z:.3f}")
                        pontos_gerados += 1
                    
                    # Pequeno progresso para não travar
                    if pontos_gerados % 10000 == 0 and pontos_gerados > 0:
                        logger.info(f"⏳ Gerando relevo... {pontos_gerados:,} pontos processados")
            
            gcode.extend(self._gerar_rodape())
            
            logger.info(f"✅ RELEVO 3D gerado com sucesso!")
            logger.info(f"📊 Pontos gerados: {pontos_gerados:,}")
            logger.info(f"📏 Profundidade máxima: {abs(z_min):.2f} mm")
            logger.info(f"📏 Profundidade mínima: {abs(z_max):.2f} mm")
            
            return gcode
            
        except Exception as e:
            logger.error(f"Erro ao gerar relevo 3D: {e}", exc_info=True)
            raise
    
    def gerar_gcode_pocket(self, imagem_array: np.ndarray) -> List[str]:
        """Estratégia Pocket - Escavação completa (2.5D)"""
        altura_px, largura_px = imagem_array.shape
        
        # Aplica limiar
        imagem_binaria = imagem_array < self.config.limiar_preto_branco
        
        # Calcula passes
        num_passes, incremento = self._calcular_passes()
        
        gcode = []
        gcode.extend(self._gerar_cabecalho())
        
        logger.info(f"🕳️ Gerando POCKET (escavação completa): {num_passes} passes")
        
        for passe in range(1, num_passes + 1):
            z_atual = -(incremento * passe)
            gcode.append(f"(Passe {passe}/{num_passes} - Profundidade: {z_atual:.3f} mm)")
            gcode.append(f"F{self.config.velocidade_corte:.1f}")
            
            em_corte = False
            
            for y in range(altura_px):
                y_mm = y * self.passo_mm
                
                if y % 2 == 0:
                    for x in range(largura_px):
                        if imagem_binaria[y, x]:
                            x_mm = x * self.passo_mm
                            if not em_corte:
                                gcode.append(f"G0 X{x_mm:.3f} Y{y_mm:.3f}")
                                gcode.append(f"G1 Z{z_atual:.3f}")
                                em_corte = True
                            else:
                                gcode.append(f"G1 X{x_mm:.3f} Y{y_mm:.3f}")
                        elif em_corte:
                            gcode.append(f"G0 Z{self.config.altura_seguranca_z:.3f}")
                            em_corte = False
                else:
                    for x in range(largura_px - 1, -1, -1):
                        if imagem_binaria[y, x]:
                            x_mm = x * self.passo_mm
                            if not em_corte:
                                gcode.append(f"G0 X{x_mm:.3f} Y{y_mm:.3f}")
                                gcode.append(f"G1 Z{z_atual:.3f}")
                                em_corte = True
                            else:
                                gcode.append(f"G1 X{x_mm:.3f} Y{y_mm:.3f}")
                        elif em_corte:
                            gcode.append(f"G0 Z{self.config.altura_seguranca_z:.3f}")
                            em_corte = False
            
            if em_corte:
                gcode.append(f"G0 Z{self.config.altura_seguranca_z:.3f}")
        
        gcode.extend(self._gerar_rodape())
        return gcode
    
    def gerar_gcode_profile(self, imagem_array: np.ndarray) -> List[str]:
        """Estratégia Profile - Apenas contorno (2.5D)"""
        altura_px, largura_px = imagem_array.shape
        imagem_binaria = imagem_array < self.config.limiar_preto_branco
        
        # Encontra pixels de borda
        bordas = []
        for y in range(altura_px):
            for x in range(largura_px):
                if imagem_binaria[y, x]:
                    is_borda = False
                    if y == 0 or y == altura_px - 1 or x == 0 or x == largura_px - 1:
                        is_borda = True
                    else:
                        if (not imagem_binaria[y-1, x] or not imagem_binaria[y+1, x] or
                            not imagem_binaria[y, x-1] or not imagem_binaria[y, x+1]):
                            is_borda = True
                    
                    if is_borda:
                        bordas.append((x * self.passo_mm, y * self.passo_mm))
        
        num_passes, incremento = self._calcular_passes()
        
        gcode = []
        gcode.extend(self._gerar_cabecalho())
        
        logger.info(f"📐 Gerando PROFILE (contorno): {len(bordas)} pontos de borda, {num_passes} passes")
        
        if bordas:
            for passe in range(1, num_passes + 1):
                z_atual = -(incremento * passe)
                gcode.append(f"(Passe {passe}/{num_passes} - Profundidade: {z_atual:.3f} mm)")
                gcode.append(f"F{self.config.velocidade_corte:.1f}")
                
                gcode.append(f"G1 X{bordas[0][0]:.3f} Y{bordas[0][1]:.3f} Z{z_atual:.3f}")
                for x, y in bordas[1:]:
                    gcode.append(f"G1 X{x:.3f} Y{y:.3f}")
                
                gcode.append(f"G0 Z{self.config.altura_seguranca_z:.3f}")
        
        gcode.extend(self._gerar_rodape())
        return gcode
    
    def gerar_gcode_zigzag(self, imagem_array: np.ndarray) -> List[str]:
        """Estratégia Zig-Zag - Varredura linear (2.5D)"""
        altura_px, largura_px = imagem_array.shape
        imagem_binaria = imagem_array < self.config.limiar_preto_branco
        num_passes, incremento = self._calcular_passes()
        
        gcode = []
        gcode.extend(self._gerar_cabecalho())
        
        logger.info(f"〰️ Gerando ZIG-ZAG (varredura linear): {num_passes} passes")
        
        for passe in range(1, num_passes + 1):
            z_atual = -(incremento * passe)
            gcode.append(f"(Passe {passe}/{num_passes} - Profundidade: {z_atual:.3f} mm)")
            gcode.append(f"F{self.config.velocidade_corte:.1f}")
            
            for y in range(altura_px):
                y_mm = y * self.passo_mm
                
                if y % 2 == 0:
                    for x in range(largura_px):
                        if imagem_binaria[y, x]:
                            x_mm = x * self.passo_mm
                            gcode.append(f"G1 X{x_mm:.3f} Y{y_mm:.3f} Z{z_atual:.3f}")
                else:
                    for x in range(largura_px - 1, -1, -1):
                        if imagem_binaria[y, x]:
                            x_mm = x * self.passo_mm
                            gcode.append(f"G1 X{x_mm:.3f} Y{y_mm:.3f} Z{z_atual:.3f}")
            
            gcode.append(f"G0 Z{self.config.altura_seguranca_z:.3f}")
        
        gcode.extend(self._gerar_rodape())
        return gcode
    
    def _calcular_passes(self) -> Tuple[int, float]:
        """Calcula número de passes e incremento por passe"""
        profundidade_abs = abs(self.config.profundidade_mm)
        num_passes = max(1, int(np.ceil(profundidade_abs / self.config.profundidade_max_passe)))
        incremento = profundidade_abs / num_passes
        return num_passes, incremento
    
    def _gerar_cabecalho(self) -> List[str]:
        """Gera cabeçalho do G-code com informações detalhadas"""
        estrategia_nome = {
            "pocket": "Pocket (Escavação completa)",
            "profile": "Profile (Contorno)",
            "zigzag": "Zig-Zag (Varredura)",
            "relief_3d": "RELEVO 3D (Gray Scale Relief)"
        }.get(self.config.estrategia, self.config.estrategia)
        
        return [
            "(CNC Pro - G-code Gerado Automaticamente)",
            f"(Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
            f"(Arquivo: {datetime.now().strftime('%Y%m%d_%H%M%S')}.nc)",
            f"(Dimensões X: {self.config.largura_mm:.2f} mm)",
            f"(Dimensões Y: {self.config.altura_mm:.2f} mm)",
            f"(Profundidade Z: {self.config.profundidade_mm:.2f} mm)",
            f"(Resolução: {self.config.resolucao_passos_mm:.1f} passos/mm)",
            f"(Estratégia: {estrategia_nome})",
            f"(Ferramenta: {self.config.diametro_ferramenta:.2f} mm)",
            f"(Velocidade corte: {self.config.velocidade_corte:.0f} mm/min)",
            "",
            "G90 ; Coordenadas absolutas",
            "G21 ; Unidades em milímetros",
            "G17 ; Plano XY",
            f"M3 S10000 ; Liga spindle",
            f"G0 Z{self.config.altura_seguranca_z:.3f} F{self.config.velocidade_rapida:.1f} ; Altura de segurança",
            "G0 X0 Y0 ; Ponto inicial",
            ""
        ]
    
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
            logger.info(f"💾 G-code salvo: {path} ({len(gcode):,} linhas)")
            
            # Mostra tamanho do arquivo
            tamanho_kb = path.stat().st_size / 1024
            logger.info(f"📦 Tamanho do arquivo: {tamanho_kb:.1f} KB")
            
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar G-code: {e}")
            return False
    
    def gerar_relatorio(self, gcode: List[str]) -> Dict:
        """Gera relatório estatístico do G-code"""
        movimentos_corte = len([l for l in gcode if l.startswith('G1')])
        movimentos_rapidos = len([l for l in gcode if l.startswith('G0')])
        
        distancia_total = movimentos_corte * self.passo_mm * 1.5
        
        return {
            'total_linhas': len(gcode),
            'movimentos_corte': movimentos_corte,
            'movimentos_rapidos': movimentos_rapidos,
            'distancia_aproximada_mm': distancia_total,
            'tempo_estimado_min': distancia_total / self.config.velocidade_corte * 60,
            'profundidade_max_mm': self.config.profundidade_mm,
            'area_usinada_mm2': self.config.largura_mm * self.config.altura_mm,
            'estrategia': self.config.estrategia,
            'resolucao': self.config.resolucao_passos_mm
        }