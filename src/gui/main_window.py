"""
CNC Pro - Interface Principal (PySide6)
Design profissional com tema escuro
Versão 3.0 - Corrigida
"""

import sys
import json
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow, 
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout,
    QPushButton, 
    QLabel, 
    QFileDialog, 
    QMessageBox,
    QProgressBar, 
    QTabWidget, 
    QGroupBox, 
    QFormLayout,
    QDoubleSpinBox, 
    QSpinBox, 
    QComboBox, 
    QCheckBox,
    QTextEdit, 
    QStatusBar, 
    QSplitter
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
        self.gerar_btn = QPushButton("🚀 GERAR G-CODE")
        self.gerar_btn.setMinimumHeight(50)
        self.gerar_btn.clicked.connect(self._gerar_gcode)
        layout.addWidget(self.gerar_btn)
        
        # Barra de progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Status da imagem
        self.status_imagem = QLabel("ℹ️ Nenhuma imagem carregada")
        self.status_imagem.setWordWrap(True)
        self.status_imagem.setStyleSheet("background-color: #2d2d30; padding: 8px; border-radius: 4px;")
        layout.addWidget(self.status_imagem)
        
        return widget
    
    def _criar_tab_arquivo(self) -> QWidget:
        """Tab de seleção de arquivo"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Área de upload
        self.upload_label = QLabel("📸 Clique para selecionar uma imagem\n\nFormatos: PNG, JPG, JPEG, BMP")
        self.upload_label.setAlignment(Qt.AlignCenter)
        self.upload_label.setMinimumHeight(200)
        self.upload_label.setStyleSheet("""
            QLabel {
                background-color: #2d2d30;
                border: 2px dashed #3e3e42;
                border-radius: 10px;
                color: #6e6e6e;
                font-size: 12pt;
            }
            QLabel:hover {
                border-color: #0e639c;
                background-color: #3e3e42;
            }
        """)
        self.upload_label.mousePressEvent = self._selecionar_imagem
        layout.addWidget(self.upload_label)
        
        # Preview da imagem
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMaximumHeight(250)
        self.preview_label.setStyleSheet("background-color: #1e1e1e; border-radius: 8px; padding: 5px;")
        self.preview_label.hide()
        layout.addWidget(self.preview_label)
        
        # Informações da imagem
        group_info = QGroupBox("Informações da Imagem")
        info_layout = QFormLayout(group_info)
        
        self.info_nome = QLabel("-")
        self.info_tamanho = QLabel("-")
        self.info_modo = QLabel("-")
        
        info_layout.addRow("Arquivo:", self.info_nome)
        info_layout.addRow("Dimensões:", self.info_tamanho)
        info_layout.addRow("Modo:", self.info_modo)
        
        layout.addWidget(group_info)
        
        layout.addStretch()
        return widget
    
    def _criar_tab_dimensoes(self) -> QWidget:
        """Tab de dimensões da peça"""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)
        
        self.largura_spin = QDoubleSpinBox()
        self.largura_spin.setRange(1, 1000)
        self.largura_spin.setValue(100)
        self.largura_spin.setSuffix(" mm")
        layout.addRow("Largura (X):", self.largura_spin)
        
        self.altura_spin = QDoubleSpinBox()
        self.altura_spin.setRange(1, 1000)
        self.altura_spin.setValue(100)
        self.altura_spin.setSuffix(" mm")
        layout.addRow("Altura (Y):", self.altura_spin)
        
        self.profundidade_spin = QDoubleSpinBox()
        self.profundidade_spin.setRange(0.1, 50)
        self.profundidade_spin.setValue(3)
        self.profundidade_spin.setSuffix(" mm")
        layout.addRow("Profundidade (Z):", self.profundidade_spin)
        
        self.resolucao_spin = QDoubleSpinBox()
        self.resolucao_spin.setRange(5, 50)
        self.resolucao_spin.setValue(15)
        self.resolucao_spin.setSuffix(" passos/mm")
        layout.addRow("Resolução:", self.resolucao_spin)
        
        return widget
    
    def _criar_tab_ferramenta(self) -> QWidget:
        """Tab de configurações da ferramenta"""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)
        
        self.diametro_spin = QDoubleSpinBox()
        self.diametro_spin.setRange(0.1, 10)
        self.diametro_spin.setValue(3.175)
        self.diametro_spin.setSuffix(" mm")
        layout.addRow("Diâmetro da ferramenta:", self.diametro_spin)
        
        self.velocidade_corte_spin = QDoubleSpinBox()
        self.velocidade_corte_spin.setRange(10, 5000)
        self.velocidade_corte_spin.setValue(800)
        self.velocidade_corte_spin.setSuffix(" mm/min")
        layout.addRow("Velocidade de corte:", self.velocidade_corte_spin)
        
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
    
    def _criar_tab_processamento(self) -> QWidget:
        """Tab de processamento de imagem"""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)
        
        self.estrategia_combo = QComboBox()
        self.estrategia_combo.addItems([
            "Pocket (Escavação completa)",
            "Profile (Apenas contorno)",
            "Zig-Zag (Varredura linear)"
        ])
        layout.addRow("Estratégia de usinagem:", self.estrategia_combo)
        
        self.limiar_spin = QSpinBox()
        self.limiar_spin.setRange(0, 255)
        self.limiar_spin.setValue(128)
        layout.addRow("Limiar (0-255):", self.limiar_spin)
        
        self.inverter_check = QCheckBox("Inverter cores (decalque)")
        layout.addRow("", self.inverter_check)
        
        self.suavizar_check = QCheckBox("Suavizar imagem")
        layout.addRow("", self.suavizar_check)
        
        self.contraste_check = QCheckBox("Aumentar contraste")
        layout.addRow("", self.contraste_check)
        
        return widget
    
    def _criar_painel_resultado(self) -> QWidget:
        """Cria painel de resultados (G-code e estatísticas)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Tabs para organizar resultados
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Tab: G-code
        tab_gcode = QWidget()
        gcode_layout = QVBoxLayout(tab_gcode)
        
        self.gcode_text = QTextEdit()
        self.gcode_text.setFont(QFont("Courier New", 9))
        self.gcode_text.setReadOnly(True)
        gcode_layout.addWidget(self.gcode_text)
        
        tabs.addTab(tab_gcode, "📝 G-code Gerado")
        
        # Tab: Estatísticas
        tab_stats = QWidget()
        stats_layout = QVBoxLayout(tab_stats)
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setFont(QFont("Segoe UI", 10))
        stats_layout.addWidget(self.stats_text)
        
        tabs.addTab(tab_stats, "📊 Estatísticas")
        
        # Botões de ação
        btn_layout = QHBoxLayout()
        
        self.salvar_btn = QPushButton("💾 Salvar G-code")
        self.salvar_btn.setEnabled(False)
        self.salvar_btn.clicked.connect(self._salvar_gcode)
        btn_layout.addWidget(self.salvar_btn)
        
        self.copiar_btn = QPushButton("📋 Copiar")
        self.copiar_btn.setEnabled(False)
        self.copiar_btn.clicked.connect(self._copiar_gcode)
        btn_layout.addWidget(self.copiar_btn)
        
        self.limpar_btn = QPushButton("🗑️ Limpar")
        self.limpar_btn.clicked.connect(self._limpar)
        btn_layout.addWidget(self.limpar_btn)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def _selecionar_imagem(self, event):
        """Seleciona imagem via diálogo"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Imagem", "images",
            "Imagens (*.png *.jpg *.jpeg *.bmp)"
        )
        
        if file_path:
            self._carregar_imagem(file_path)
    
    def _carregar_imagem(self, path: str):
        """Carrega e processa imagem"""
        if self.processador.carregar_imagem(path):
            self.imagem_atual = path
            
            # Atualiza preview
            pixmap = QPixmap(path)
            scaled = pixmap.scaled(300, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
            self.preview_label.show()
            self.upload_label.hide()
            
            # Atualiza informações
            nome = Path(path).name
            img = self.processador.imagem_original
            self.info_nome.setText(nome)
            self.info_tamanho.setText(f"{img.width} x {img.height} px")
            self.info_modo.setText(img.mode)
            
            self.status_imagem.setText(f"✅ Imagem carregada: {nome}")
            self.status_bar.showMessage(f"Imagem carregada: {nome}")
            
            logger.info(f"Imagem carregada: {path}")
    
    def _gerar_gcode(self):
        """Inicia geração de G-code"""
        if self.imagem_atual is None:
            QMessageBox.warning(self, "Aviso", "Carregue uma imagem primeiro!")
            return
        
        # Mapeia estratégia
        estrategias = {
            "Pocket (Escavação completa)": "pocket",
            "Profile (Apenas contorno)": "profile",
            "Zig-Zag (Varredura linear)": "zigzag"
        }
        
        # Prepara configuração
        config = ConfigGerador(
            largura_mm=self.largura_spin.value(),
            altura_mm=self.altura_spin.value(),
            profundidade_mm=self.profundidade_spin.value(),
            resolucao_passos_mm=self.resolucao_spin.value(),
            profundidade_max_passe=self.passo_corte_spin.value(),
            velocidade_corte=self.velocidade_corte_spin.value(),
            velocidade_rapida=3500.0,
            altura_seguranca_z=self.altura_seguranca_spin.value(),
            diametro_ferramenta=self.diametro_spin.value(),
            limiar_preto_branco=self.limiar_spin.value(),
            estrategia=estrategias[self.estrategia_combo.currentText()],
            inverter_cores=self.inverter_check.isChecked(),
            suavizar_imagem=self.suavizar_check.isChecked()
        )
        
        # Processa imagem
        try:
            self.status_bar.showMessage("🔄 Processando imagem...")
            imagem_array = self.processador.processar_para_cnc(
                largura_mm=config.largura_mm,
                altura_mm=config.altura_mm,
                resolucao_passos_mm=config.resolucao_passos_mm,
                limiar=config.limiar_preto_branco,
                inverter=config.inverter_cores,
                suavizar=config.suavizar_imagem,
                aumentar_contraste=self.contraste_check.isChecked()
            )
            
            # Exibe informações do processamento
            info = self.processador.get_info()
            self.status_imagem.setText(
                f"📊 Área a usinar: {info['percentual_area']:.1f}% "
                f"({info['pixels_ativos']:,} pixels)\n"
                f"🎨 Brilho médio: {info['brilho_medio']:.0f} | "
                f"Contraste: {info['contraste_medio']:.0f}"
            )
            
            # Inicia thread de geração
            self.thread = GeracaoThread(self.gerador, imagem_array, config)
            self.thread.progress.connect(self._atualizar_progresso)
            self.thread.log.connect(self._atualizar_log)
            self.thread.finished.connect(self._geracao_concluida)
            self.thread.error.connect(self._geracao_erro)
            
            self.gerar_btn.setEnabled(False)
            self.progress_bar.show()
            self.progress_bar.setValue(0)
            self.status_bar.showMessage("🔄 Gerando G-code...")
            
            self.loading_dots = 0
            self.loading_timer.start(500)
            
            self.thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao processar imagem:\n{e}")
            logger.error(f"Erro no processamento: {e}", exc_info=True)
    
    def _atualizar_progresso(self, valor: int):
        """Atualiza barra de progresso"""
        self.progress_bar.setValue(valor)
    
    def _atualizar_log(self, mensagem: str):
        """Atualiza log na status bar"""
        self.status_bar.showMessage(mensagem)
    
    def _update_loading(self):
        """Atualiza animação de loading"""
        self.loading_dots = (self.loading_dots + 1) % 4
        dots = "." * self.loading_dots
        self.status_bar.showMessage(f"🔄 Gerando G-code{dots.ljust(3)}")
    
    def _geracao_concluida(self, gcode, relatorio):
        """Geração concluída com sucesso"""
        self.loading_timer.stop()
        self.gcode_atual = gcode
        self.gcode_text.setText('\n'.join(gcode))
        
        # Exibe estatísticas
        stats_text = f"""
        📊 RELATÓRIO DE USINAGEM
        {'=' * 50}
        
        📄 INFORMAÇÕES GERAIS:
        • Total de linhas do G-code: {relatorio['total_linhas']:,}
        • Movimentos de corte (G1): {relatorio['movimentos_corte']:,}
        • Movimentos rápidos (G0): {relatorio['movimentos_rapidos']:,}
        
        📏 DIMENSÕES:
        • Profundidade máxima: {relatorio['profundidade_max_mm']:.2f} mm
        • Área de usinagem: {relatorio['area_usinada_mm2']:.1f} mm²
        
        ⏱️ TEMPO ESTIMADO:
        • Distância aproximada: {relatorio['distancia_aproximada_mm']:,.0f} mm
        • Tempo de usinagem: {relatorio['tempo_estimado_min']:.1f} minutos
        
        🔧 CONFIGURAÇÕES:
        • Velocidade de corte: {self.velocidade_corte_spin.value():.0f} mm/min
        • Profundidade por passe: {self.passo_corte_spin.value():.2f} mm
        • Resolução: {self.resolucao_spin.value():.0f} passos/mm
        """
        
        self.stats_text.setText(stats_text)
        
        self.gerar_btn.setEnabled(True)
        self.progress_bar.hide()
        self.salvar_btn.setEnabled(True)
        self.copiar_btn.setEnabled(True)
        
        self.status_bar.showMessage(f"✅ G-code gerado! {relatorio['total_linhas']:,} linhas")
        
        QMessageBox.information(
            self, "Sucesso",
            f"✅ G-code gerado com sucesso!\n\n"
            f"📊 Total de linhas: {relatorio['total_linhas']:,}\n"
            f"⏱️ Tempo estimado: {relatorio['tempo_estimado_min']:.1f} minutos\n"
            f"📏 Profundidade: {relatorio['profundidade_max_mm']:.2f} mm"
        )
        
        logger.info(f"G-code gerado: {relatorio['total_linhas']} linhas")
    
    def _geracao_erro(self, erro):
        """Erro na geração"""
        self.loading_timer.stop()
        self.gerar_btn.setEnabled(True)
        self.progress_bar.hide()
        self.status_bar.showMessage("❌ Erro na geração")
        
        QMessageBox.critical(self, "Erro", f"❌ Falha ao gerar G-code:\n{erro}")
        logger.error(f"Erro na geração: {erro}")
    
    def _salvar_gcode(self):
        """Salva G-code em arquivo"""
        if not self.gcode_atual:
            return
        
        nome_base = Path(self.imagem_atual).stem if self.imagem_atual else "projeto"
        from datetime import datetime
        nome_sugerido = f"{nome_base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.nc"
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar G-code",
            str(Path("output") / nome_sugerido),
            "Arquivos G-code (*.nc *.gcode);;Todos os arquivos (*.*)"
        )
        
        if path:
            if self.gerador.salvar_gcode(self.gcode_atual, path):
                QMessageBox.information(self, "Sucesso", f"✅ G-code salvo em:\n{path}")
                self.status_bar.showMessage(f"💾 Salvo: {Path(path).name}")
            else:
                QMessageBox.warning(self, "Erro", "❌ Erro ao salvar arquivo")
    
    def _copiar_gcode(self):
        """Copia G-code para área de transferência"""
        if not self.gcode_atual:
            return
        
        clipboard = QApplication.clipboard()
        clipboard.setText('\n'.join(self.gcode_atual))
        self.status_bar.showMessage("📋 G-code copiado para área de transferência")
    
    def _limpar(self):
        """Limpa todos os resultados"""
        self.gcode_atual = None
        self.gcode_text.clear()
        self.stats_text.clear()
        self.salvar_btn.setEnabled(False)
        self.copiar_btn.setEnabled(False)
        self.status_bar.showMessage("🗑️ Resultados limpos")