"""
CNC Pro - Interface Principal (PySide6)
Versão 3.0 - Com suporte a RELEVO 3D
"""

import sys
import json
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QProgressBar,
    QTabWidget, QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox,
    QComboBox, QCheckBox, QTextEdit, QStatusBar, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont

from src.core.gerador import GeradorGCode, ConfigGerador
from src.core.processador import ProcessadorImagem

logger = logging.getLogger(__name__)


class GeracaoThread(QThread):
    """Thread para gerar G-code sem travar a interface"""
    progress = Signal(int)
    log = Signal(str)
    finished = Signal(object, object)
    error = Signal(str)
    
    def __init__(self, gerador, imagem_array, config):
        super().__init__()
        self.gerador = gerador
        self.imagem_array = imagem_array
        self.config = config
    
    def run(self):
        try:
            self.log.emit("⚙️ Configurando...")
            self.gerador.config = self.config
            
            self.log.emit("🎨 Processando imagem para relevo 3D...")
            self.progress.emit(30)
            
            gcode = self.gerador.gerar_gcode(self.imagem_array)
            
            self.progress.emit(80)
            self.log.emit("📊 Gerando relatório...")
            
            relatorio = self.gerador.gerar_relatorio(gcode)
            
            self.progress.emit(100)
            self.finished.emit(gcode, relatorio)
            
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Janela principal do CNC Pro - Suporte a Relevo 3D"""
    
    def __init__(self):
        super().__init__()
        
        self.processador = ProcessadorImagem()
        self.gerador = GeradorGCode()
        self.imagem_atual = None
        self.imagem_array = None
        self.gcode_atual = None
        
        self.setWindowTitle("CNC Pro 3D - Gerador de Relevo Artístico")
        self.setMinimumSize(1400, 900)
        
        self.setStyleSheet(self._get_stylesheet())
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        config_panel = self._criar_painel_config()
        splitter.addWidget(config_panel)
        
        result_panel = self._criar_painel_resultado()
        splitter.addWidget(result_panel)
        
        splitter.setSizes([450, 950])
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("✅ Pronto - Carregue uma imagem para criar RELEVO 3D")
        
        self.loading_timer = QTimer()
        self.loading_timer.timeout.connect(self._update_loading)
        self.loading_dots = 0
    
    def _get_stylesheet(self) -> str:
        return """
        QMainWindow { background-color: #1e1e1e; }
        QWidget { background-color: #252526; color: #d4d4d4; font-family: 'Segoe UI'; font-size: 10pt; }
        QGroupBox { border: 1px solid #3e3e42; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QPushButton { background-color: #0e639c; border: none; border-radius: 4px; padding: 8px 16px; color: white; font-weight: bold; }
        QPushButton:hover { background-color: #1177bb; }
        QPushButton:disabled { background-color: #3e3e42; color: #6e6e6e; }
        QComboBox, QDoubleSpinBox, QSpinBox { background-color: #3c3c3c; border: 1px solid #3e3e42; border-radius: 3px; padding: 5px; }
        QTextEdit { background-color: #1e1e1e; border: 1px solid #3e3e42; border-radius: 4px; font-family: 'Courier New'; font-size: 9pt; }
        QProgressBar { border: 1px solid #3e3e42; border-radius: 3px; text-align: center; background-color: #3c3c3c; }
        QProgressBar::chunk { background-color: #0e639c; border-radius: 2px; }
        QTabWidget::pane { border: 1px solid #3e3e42; border-radius: 4px; background-color: #252526; }
        QTabBar::tab { background-color: #2d2d30; padding: 8px 16px; margin-right: 2px; }
        QTabBar::tab:selected { background-color: #0e639c; color: white; }
        """
    
    def _criar_painel_config(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Tab: Arquivo
        tab_arquivo = self._criar_tab_arquivo()
        tabs.addTab(tab_arquivo, "📁 Arquivo")
        
        # Tab: Dimensões
        tab_dimensoes = self._criar_tab_dimensoes()
        tabs.addTab(tab_dimensoes, "📏 Dimensões")
        
        # Tab: Ferramenta
        tab_ferramenta = self._criar_tab_ferramenta()
        tabs.addTab(tab_ferramenta, "🔧 Ferramenta")
        
        # Tab: Processamento
        tab_processamento = self._criar_tab_processamento()
        tabs.addTab(tab_processamento, "🎨 Processamento")
        
        # Tab: Config 3D
        tab_3d = self._criar_tab_3d()
        tabs.addTab(tab_3d, "🏔️ Configurações 3D")
        
        self.gerar_btn = QPushButton("🚀 GERAR RELEVO 3D")
        self.gerar_btn.setMinimumHeight(50)
        self.gerar_btn.clicked.connect(self._gerar_gcode)
        layout.addWidget(self.gerar_btn)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        self.status_imagem = QLabel("ℹ️ Nenhuma imagem carregada")
        self.status_imagem.setWordWrap(True)
        self.status_imagem.setStyleSheet("background-color: #2d2d30; padding: 8px; border-radius: 4px;")
        layout.addWidget(self.status_imagem)
        
        return widget
    
    def _criar_tab_arquivo(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.upload_label = QLabel("📸 Clique para selecionar uma imagem\n\nFormatos: PNG, JPG, JPEG, BMP\n\n🎨 Use imagens ESCALA DE CINZA para melhor resultado 3D")
        self.upload_label.setAlignment(Qt.AlignCenter)
        self.upload_label.setMinimumHeight(200)
        self.upload_label.setStyleSheet("""
            QLabel {
                background-color: #2d2d30;
                border: 2px dashed #3e3e42;
                border-radius: 10px;
                color: #6e6e6e;
                font-size: 11pt;
            }
            QLabel:hover { border-color: #0e639c; background-color: #3e3e42; }
        """)
        self.upload_label.mousePressEvent = self._selecionar_imagem
        layout.addWidget(self.upload_label)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMaximumHeight(250)
        self.preview_label.setStyleSheet("background-color: #1e1e1e; border-radius: 8px; padding: 5px;")
        self.preview_label.hide()
        layout.addWidget(self.preview_label)
        
        group_info = QGroupBox("Informações da Imagem")
        info_layout = QFormLayout(group_info)
        
        self.info_nome = QLabel("-")
        self.info_tamanho = QLabel("-")
        self.info_modo = QLabel("-")
        self.info_brilho = QLabel("-")
        
        info_layout.addRow("Arquivo:", self.info_nome)
        info_layout.addRow("Dimensões:", self.info_tamanho)
        info_layout.addRow("Modo:", self.info_modo)
        info_layout.addRow("Brilho médio:", self.info_brilho)
        
        layout.addWidget(group_info)
        layout.addStretch()
        return widget
    
    def _criar_tab_dimensoes(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)
        
        self.largura_spin = QDoubleSpinBox()
        self.largura_spin.setRange(10, 300)
        self.largura_spin.setValue(100)
        self.largura_spin.setSuffix(" mm")
        layout.addRow("Largura (X):", self.largura_spin)
        
        self.altura_spin = QDoubleSpinBox()
        self.altura_spin.setRange(10, 300)
        self.altura_spin.setValue(100)
        self.altura_spin.setSuffix(" mm")
        layout.addRow("Altura (Y):", self.altura_spin)
        
        self.profundidade_spin = QDoubleSpinBox()
        self.profundidade_spin.setRange(0.5, 20)
        self.profundidade_spin.setValue(3)
        self.profundidade_spin.setSuffix(" mm")
        layout.addRow("Profundidade máxima:", self.profundidade_spin)
        
        return widget
    
    def _criar_tab_ferramenta(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)
        
        self.diametro_spin = QDoubleSpinBox()
        self.diametro_spin.setRange(0.1, 10)
        self.diametro_spin.setValue(3.175)
        self.diametro_spin.setSuffix(" mm")
        layout.addRow("Diâmetro da ferramenta:", self.diametro_spin)
        
        self.velocidade_corte_spin = QDoubleSpinBox()
        self.velocidade_corte_spin.setRange(100, 5000)
        self.velocidade_corte_spin.setValue(600)
        self.velocidade_corte_spin.setSuffix(" mm/min")
        layout.addRow("Velocidade para 3D:", self.velocidade_corte_spin)
        
        self.passo_corte_spin = QDoubleSpinBox()
        self.passo_corte_spin.setRange(0.1, 5)
        self.passo_corte_spin.setValue(0.5)
        self.passo_corte_spin.setSuffix(" mm")
        layout.addRow("Profundidade por passe:", self.passo_corte_spin)
        
        self.altura_seguranca_spin = QDoubleSpinBox()
        self.altura_seguranca_spin.setRange(1, 20)
        self.altura_seguranca_spin.setValue(5)
        self.altura_seguranca_spin.setSuffix(" mm")
        layout.addRow("Altura de segurança:", self.altura_seguranca_spin)
        
        return widget
    
    def _c