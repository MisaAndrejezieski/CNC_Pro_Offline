"""
CNC Pro - Interface Principal (PySide6)
Design profissional com tema escuro
"""

import sys
import json
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QProgressBar, QTabWidget, QGroupBox, QFormLayout,
    QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox,
    QTextEdit, QStatusBar, QSplitter, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont, QIcon

from src.core.gerador import GeradorGCode, ConfigGerador
from src.core.processador import ProcessadorImagem

logger = logging.getLogger(__name__)


class GeracaoThread(QThread):
    """Thread para gerar G-code sem travar a interface"""
    progress = Signal(int)
    log = Signal(str)
    finished = Signal(object, object)  # gcode, relatorio
    error = Signal(str)
    
    def __init__(self, gerador, imagem_array, config):
        super().__init__()
        self.gerador = gerador
        self.imagem_array = imagem_array
        self.config = config
    
    def run(self):
        try:
            self.log.emit("⚙️ Configurando gerador...")
            self.gerador.config = self.config
            
            self.log.emit("🔄 Gerando G-code...")
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
    """Janela principal do CNC Pro"""
    
    def __init__(self):
        super().__init__()
        
        # Componentes
        self.processador = ProcessadorImagem()
        self.gerador = GeradorGCode()
        self.imagem_atual = None
        self.imagem_array = None
        self.gcode_atual = None
        
        self.setWindowTitle("CNC Pro - Gerador de G-code Profissional")
        self.setMinimumSize(1300, 800)
        
        # Aplica estilo escuro
        self.setStyleSheet(self._get_stylesheet())
        
        # Widget central
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Painel de configuração
        config_panel = self._criar_painel_config()
        splitter.addWidget(config_panel)
        
        # Painel de resultados
        result_panel = self._criar_painel_resultado()
        splitter.addWidget(result_panel)
        
        splitter.setSizes([450, 850])
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("✅ Pronto - Carregue uma imagem para começar")
        
        # Timer para animação
        self.loading_timer = QTimer()
        self.loading_timer.timeout.connect(self._update_loading)
        self.loading_dots = 0
    
    def _get_stylesheet(self) -> str:
        """Retorna o stylesheet para tema escuro profissional"""
        return """
        QMainWindow {
            background-color: #1e1e1e;
        }
        QWidget {
            background-color: #252526;
            color: #d4d4d4;
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            font-size: 10pt;
        }
        QGroupBox {
            border: 1px solid #3e3e42;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QPushButton {
            background-color: #0e639c;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            color: white;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1177bb;
        }
        QPushButton:disabled {
            background-color: #3e3e42;
            color: #6e6e6e;
        }
        QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
            background-color: #3c3c3c;
            border: 1px solid #3e3e42;
            border-radius: 3px;
            padding: 5px;
            color: #d4d4d4;
        }
        QTextEdit {
            background-color: #1e1e1e;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 10pt;
        }
        QProgressBar {
            border: 1px solid #3e3e42;
            border-radius: 3px;
            text-align: center;
            background-color: #3c3c3c;
        }
        QProgressBar::chunk {
            background-color: #0e639c;
            border-radius: 2px;
        }
        QTabWidget::pane {
            border: 1px solid #3e3e42;
            border-radius: 4px;
            background-color: #252526;
        }
        QTabBar::tab {
            background-color: #2d2d30;
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background-color: #0e639c;
            color: white;
        }
        QLabel[error="true"] {
            color: #f48771;
        }
        QLabel[success="true"] {
            color: #6a9955;
        }
        """
    
    def _criar_painel_config(self) -> QWidget:
        """Cria painel de configuração"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Tab widget para organizar configurações
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
        tabs.addTab(tab_processamento, "⚙️ Processamento")
        
        # Botão Gerar