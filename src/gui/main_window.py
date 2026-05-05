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
    
    def _criar_tab_processamento(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)
        
        self.estrategia_combo = QComboBox()
        self.estrategia_combo.addItems([
            "🎨 RELEVO 3D (Gray Scale) - RECOMENDADO",
            "🕳️ Pocket (Escavação completa) - 2.5D",
            "📐 Profile (Apenas contorno) - 2.5D",
            "〰️ Zig-Zag (Varredura) - 2.5D"
        ])
        layout.addRow("Estratégia de usinagem:", self.estrategia_combo)
        
        self.resolucao_spin = QDoubleSpinBox()
        self.resolucao_spin.setRange(5, 30)
        self.resolucao_spin.setValue(12)
        self.resolucao_spin.setSuffix(" passos/mm")
        layout.addRow("Resolução (12 recomendado):", self.resolucao_spin)
        
        self.limiar_spin = QSpinBox()
        self.limiar_spin.setRange(0, 255)
        self.limiar_spin.setValue(128)
        layout.addRow("Limiar para 2.5D:", self.limiar_spin)
        
        self.inverter_check = QCheckBox("Inverter cores (decalque)")
        layout.addRow("", self.inverter_check)
        
        self.suavizar_check = QCheckBox("Suavizar imagem (recomendado para 3D)")
        self.suavizar_check.setChecked(True)
        layout.addRow("", self.suavizar_check)
        
        self.contraste_check = QCheckBox("Aumentar contraste (melhora relevo)")
        self.contraste_check.setChecked(True)
        layout.addRow("", self.contraste_check)
        
        return widget
    
    def _criar_tab_3d(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)
        
        self.qualidade_3d_combo = QComboBox()
        self.qualidade_3d_combo.addItems([
            "⚡ Rápido (menos detalhes, arquivo menor)",
            "🎨 Normal (equilíbrio) - RECOMENDADO",
            "✨ Alta qualidade (mais detalhes, arquivo maior)"
        ])
        self.qualidade_3d_combo.setCurrentIndex(1)
        layout.addRow("Qualidade do relevo 3D:", self.qualidade_3d_combo)
        
        self.profundidade_min_spin = QDoubleSpinBox()
        self.profundidade_min_spin.setRange(0, 5)
        self.profundidade_min_spin.setValue(0)
        self.profundidade_min_spin.setSuffix(" mm")
        layout.addRow("Profundidade mínima:", self.profundidade_min_spin)
        
        self.profundidade_max_spin = QDoubleSpinBox()
        self.profundidade_max_spin.setRange(0.5, 20)
        self.profundidade_max_spin.setValue(3)
        self.profundidade_max_spin.setSuffix(" mm")
        layout.addRow("Profundidade máxima:", self.profundidade_max_spin)
        
        info_label = QLabel("💡 Dicas para RELEVO 3D:\n"
                           "• Use imagens em escala de cinza\n"
                           "• Resolução: 10-15 passos/mm\n"
                           "• Velocidade: 400-600 mm/min\n"
                           "• Ferramenta ponta fina (0.5-1mm)\n"
                           "• Faça testes pequenos primeiro")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("background-color: #2d2d30; padding: 10px; border-radius: 5px;")
        layout.addRow("", info_label)
        
        return widget
    
    def _criar_painel_resultado(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        tab_gcode = QWidget()
        gcode_layout = QVBoxLayout(tab_gcode)
        self.gcode_text = QTextEdit()
        self.gcode_text.setFont(QFont("Courier New", 9))
        self.gcode_text.setReadOnly(True)
        gcode_layout.addWidget(self.gcode_text)
        tabs.addTab(tab_gcode, "📝 G-code do Relevo 3D")
        
        tab_stats = QWidget()
        stats_layout = QVBoxLayout(tab_stats)
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setFont(QFont("Segoe UI", 10))
        stats_layout.addWidget(self.stats_text)
        tabs.addTab(tab_stats, "📊 Estatísticas")
        
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
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Imagem", "images",
            "Imagens (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self._carregar_imagem(file_path)
    
    def _carregar_imagem(self, path: str):
        if self.processador.carregar_imagem(path):
            self.imagem_atual = path
            
            pixmap = QPixmap(path)
            scaled = pixmap.scaled(300, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
            self.preview_label.show()
            self.upload_label.hide()
            
            nome = Path(path).name
            img = self.processador.imagem_original
            self.info_nome.setText(nome)
            self.info_tamanho.setText(f"{img.width} x {img.height} px")
            self.info_modo.setText(img.mode)
            
            # Calcula brilho médio
            img_array = np.array(img.convert('L'))
            brilho_medio = np.mean(img_array)
            self.info_brilho.setText(f"{brilho_medio:.1f} / 255")
            
            self.status_imagem.setText(f"✅ Imagem carregada: {nome} | Brilho médio: {brilho_medio:.0f}")
            self.status_bar.showMessage(f"Imagem carregada: {nome}")
            
            logger.info(f"Imagem carregada: {path}")
    
    def _gerar_gcode(self):
        if self.imagem_atual is None:
            QMessageBox.warning(self, "Aviso", "Carregue uma imagem primeiro!")
            return
        
        # Mapeia estratégia
        estrategia_texto = self.estrategia_combo.currentText()
        if "RELEVO 3D" in estrategia_texto:
            estrategia = "relief_3d"
        elif "Pocket" in estrategia_texto:
            estrategia = "pocket"
        elif "Profile" in estrategia_texto:
            estrategia = "profile"
        else:
            estrategia = "zigzag"
        
        # Mapeia qualidade
        qualidade_texto = self.qualidade_3d_combo.currentText()
        if "Rápido" in qualidade_texto:
            qualidade = 3
        elif "Normal" in qualidade_texto:
            qualidade = 1
        else:
            qualidade = 1
        
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
            estrategia=estrategia,
            inverter_cores=self.inverter_check.isChecked(),
            suavizar_imagem=self.suavizar_check.isChecked(),
            qualidade_3d=qualidade,
            profundidade_maxima_mm=self.profundidade_max_spin.value(),
            profundidade_minima_mm=self.profundidade_min_spin.value()
        )
        
        try:
            self.status_bar.showMessage("🔄 Processando imagem para relevo 3D...")
            imagem_array = self.processador.processar_para_cnc(
                largura_mm=config.largura_mm,
                altura_mm=config.altura_mm,
                resolucao_passos_mm=config.resolucao_passos_mm,
                limiar=config.limiar_preto_branco,
                inverter=config.inverter_cores,
                suavizar=config.suavizar_imagem,
                aumentar_contraste=self.contraste_check.isChecked()
            )
            
            info = self.processador.get_info()
            self.status_imagem.setText(
                f"🎨 Iniciando RELEVO 3D...\n"
                f"📊 Área: {info['percentual_area']:.1f}% | "
                f"🎨 Brilho: {info['brilho_medio']:.0f}"
            )
            
            self.thread = GeracaoThread(self.gerador, imagem_array, config)
            self.thread.progress.connect(self._atualizar_progresso)
            self.thread.log.connect(self._atualizar_log)
            self.thread.finished.connect(self._geracao_concluida)
            self.thread.error.connect(self._geracao_erro)
            
            self.gerar_btn.setEnabled(False)
            self.progress_bar.show()
            self.progress_bar.setValue(0)
            self.status_bar.showMessage("🎨 Gerando relevo 3D...")
            
            self.loading_dots = 0
            self.loading_timer.start(500)
            
            self.thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao processar imagem:\n{e}")
            logger.error(f"Erro no processamento: {e}", exc_info=True)
    
    def _atualizar_progresso(self, valor: int):
        self.progress_bar.setValue(valor)
    
    def _atualizar_log(self, mensagem: str):
        self.status_bar.showMessage(mensagem)
    
    def _update_loading(self):
        self.loading_dots = (self.loading_dots + 1) % 4
        dots = "." * self.loading_dots
        self.status_bar.showMessage(f"🎨 Criando relevo 3D{dots.ljust(3)}")
    
    def _geracao_concluida(self, gcode, relatorio):
        self.loading_timer.stop()
        self.gcode_atual = gcode
        self.gcode_text.setText('\n'.join(gcode))
        
        estrategia_nome = "🎨 RELEVO 3D (Gray Scale Relief)" if relatorio['estrategia'] == "relief_3d" else relatorio['estrategia']
        
        stats_text = f"""
        {'=' * 60}
        🎨 RELATÓRIO DO RELEVO ARTÍSTICO 3D
        {'=' * 60}
        
        📊 INFORMAÇÕES GERAIS:
        • Estratégia: {estrategia_nome}
        • Total de linhas: {relatorio['total_linhas']:,}
        • Tamanho aproximado: {relatorio['total_linhas'] * 30 / 1024:.1f} KB
        
        🔧 CONFIGURAÇÕES:
        • Resolução: {relatorio['resolucao']} passos/mm
        • Profundidade máxima: {relatorio['profundidade_max_mm']:.2f} mm
        
        ⏱️ TEMPO ESTIMADO PARA USINAGEM:
        • Distância percorrida: {relatorio['distancia_aproximada_mm']:,.0f} mm
        • Tempo aproximado: {relatorio['tempo_estimado_min']:.1f} minutos ({relatorio['tempo_estimado_min']/60:.1f} horas)
        
        💡 DICAS PARA O RELEVO 3D:
        • Use ferramenta de ponta fina (0.5-1mm)
        • Velocidade recomendada: 400-600 mm/min
        • Faça um teste pequeno primeiro
        • Use madeira macia para testes
        """
        
        self.stats_text.setText(stats_text)
        
        self.gerar_btn.setEnabled(True)
        self.progress_bar.hide()
        self.salvar_btn.setEnabled(True)
        self.copiar_btn.setEnabled(True)
        
        self.status_bar.showMessage(f"✅ Relevo 3D gerado! {relatorio['total_linhas']:,} linhas | Tempo estimado: {relatorio['tempo_estimado_min']:.1f} min")
        
        QMessageBox.information(
            self, "Sucesso",
            f"✅ RELEVO 3D gerado com sucesso!\n\n"
            f"🎨 Total de linhas: {relatorio['total_linhas']:,}\n"
            f"⏱️ Tempo estimado: {relatorio['tempo_estimado_min']:.1f} minutos\n"
            f"📏 Profundidade máxima: {relatorio['profundidade_max_mm']:.2f} mm\n\n"
            f"💡 Dica: Use velocidade de corte entre 400-600 mm/min para melhor acabamento 3D"
        )
        
        logger.info(f"Relevo 3D gerado: {relatorio['total_linhas']} linhas")
    
    def _geracao_erro(self, erro):
        self.loading_timer.stop()
        self.gerar_btn.setEnabled(True)
        self.progress_bar.hide()
        self.status_bar.showMessage("❌ Erro na geração do relevo 3D")
        
        QMessageBox.critical(self, "Erro", f"❌ Falha ao gerar relevo 3D:\n{erro}")
        logger.error(f"Erro na geração: {erro}")
    
    def _salvar_gcode(self):
        if not self.gcode_atual:
            return
        
        nome_base = Path(self.imagem_atual).stem if self.imagem_atual else "relevo_3d"
        from datetime import datetime
        nome_sugerido = f"{nome_base}_3d_{datetime.now().strftime('%Y%m%d_%H%M%S')}.nc"
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar G-code do Relevo 3D",
            str(Path("output") / nome_sugerido),
            "Arquivos G-code (*.nc *.gcode);;Todos os arquivos (*.*)"
        )
        
        if path:
            if self.gerador.salvar_gcode(self.gcode_atual, path):
                QMessageBox.information(self, "Sucesso", f"✅ G-code do relevo 3D salvo em:\n{path}")
                self.status_bar.showMessage(f"💾 Salvo: {Path(path).name}")
            else:
                QMessageBox.warning(self, "Erro", "❌ Erro ao salvar arquivo")
    
    def _copiar_gcode(self):
        if not self.gcode_atual:
            return
        
        clipboard = QApplication.clipboard()
        clipboard.setText('\n'.join(self.gcode_atual))
        self.status_bar.showMessage("📋 G-code copiado para área de transferência")
    
    def _limpar(self):
        self.gcode_atual = None
        self.gcode_text.clear()
        self.stats_text.clear()
        self.salvar_btn.setEnabled(False)
        self.copiar_btn.setEnabled(False)
        self.status_bar.showMessage("🗑️ Resultados limpos")


# Ponto de entrada para teste direto
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())