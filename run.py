#!/usr/bin/env python3
"""
CNC Pro - Gerador de G-code Profissional (Offline)
Versão Desktop - Sem limitações de tempo, tamanho ou internet

Uso: python run.py
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Configura logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

log_filename = LOG_DIR / f"cnc_pro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def setup_environment():
    """Cria diretórios necessários"""
    dirs = ['images', 'output', 'logs']
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
        logger.info(f"Diretório verificado/criado: {d}")


def main():
    """Função principal"""
    try:
        setup_environment()
        
        # Adiciona src ao path
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        
        from PySide6.QtWidgets import QApplication
        from src.gui.main_window import MainWindow
        
        # Configura Qt para High DPI
        os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
        os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
        
        app = QApplication(sys.argv)
        app.setApplicationName("CNC Pro")
        app.setOrganizationName("CNC Pro")
        
        # Aplica estilo global
        app.setStyle('Fusion')
        
        window = MainWindow()
        window.show()
        
        logger.info("Aplicação CNC Pro iniciada com sucesso")
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Erro fatal ao iniciar aplicação: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()