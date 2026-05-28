import sys
import os
import json
import time
import re
import subprocess
import requests
from datetime import datetime

from PyQt6.QtCore import (
    Qt, QTimer, QSize, QRect, QPoint, QObject,
    QRunnable, QThreadPool, pyqtSignal, pyqtSlot
)
from PyQt6.QtGui import (
    QIcon, QPainter, QColor, QFont, QAction, QCursor
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QScrollArea, QDialog, QLineEdit,
    QComboBox, QSpinBox, QCheckBox, QSystemTrayIcon, QMenu, QFormLayout,
    QMessageBox, QSizePolicy
)

# --- Resolución de Rutas de Activos para PyInstaller ---
def get_asset_path(filename):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, 'assets', filename)

def get_config_path():
    if sys.platform == 'win32':
        base_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
    else:
        base_dir = os.path.expanduser('~/.config')
    config_dir = os.path.join(base_dir, 'montray')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'sites.json')

# --- Comprobaciones HTTP ---
def check_http(url, timeout_ms=5000):
    target_url = url.strip()
    if not target_url.lower().startswith(('http://', 'https://')):
        target_url = 'http://' + target_url
    
    start_time = time.time()
    try:
        response = requests.get(
            target_url,
            timeout=timeout_ms / 1000.0,
            headers={
                'User-Agent': 'MonTray/1.0 (Python)',
                'Cache-Control': 'no-cache'
            }
        )
        latency = int((time.time() - start_time) * 1000)
        
        if response.status_code >= 400:
            return {
                'online': True,
                'latency': latency,
                'error': f"Estado HTTP {response.status_code} {response.reason}",
                'warning': True
            }
        return {
            'online': True,
            'latency': latency,
            'error': None,
            'warning': False
        }
    except requests.exceptions.Timeout:
        return {'online': False, 'latency': None, 'error': 'Límite de tiempo excedido (Timeout)', 'warning': False}
    except requests.exceptions.ConnectionError:
        return {'online': False, 'latency': None, 'error': 'Servidor no encontrado (DNS/Red)', 'warning': False}
    except Exception as e:
        return {'online': False, 'latency': None, 'error': str(e), 'warning': False}

# --- Señales y Worker de Monitoreo No Bloqueante ---
class CheckResultSignals(QObject):
    finished = pyqtSignal(str, dict)

class CheckSiteWorker(QRunnable):
    def __init__(self, site_id, site_type, address, timeout_ms=5000):
        super().__init__()
        self.site_id = site_id
        self.site_type = site_type
        self.address = address
        self.timeout_ms = timeout_ms
        self.signals = CheckResultSignals()

    def run(self):
        if self.site_type == 'ping':
            result = self.ping_check()
        else:
            result = check_http(self.address, self.timeout_ms)
        self.signals.finished.emit(self.site_id, result)

    def ping_check(self):
        clean_addr = re.sub(r'[^a-zA-Z0-9.-]', '', self.address)
        timeout_sec = max(1, round(self.timeout_ms / 1000.0))
        
        start_time = time.time()
        try:
            if sys.platform == 'win32':
                # En Windows ping -n 1 -w timeoutMs
                cmd = f"ping -n 1 -w {self.timeout_ms} \"{clean_addr}\""
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.Popen(
                    cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    startupinfo=startupinfo, text=True, errors='ignore'
                )
            else:
                # En Linux ping -c 1 -W timeoutSec
                cmd = ["ping", "-c", "1", "-W", str(timeout_sec), clean_addr]
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, errors='ignore'
                )
            
            stdout, stderr = process.communicate()
            latency = int((time.time() - start_time) * 1000)
            
            if process.returncode == 0:
                # Expresión regular insensible a mayúsculas para time= o tiempo=
                match = re.search(r"(?:time|tiempo)[=<]\s*([\d.]+)\s*ms", stdout, re.IGNORECASE)
                if match:
                    parsed_latency = int(float(match.group(1)))
                    return {'online': True, 'latency': parsed_latency, 'error': None, 'warning': False}
                return {'online': True, 'latency': latency, 'error': None, 'warning': False}
            else:
                msg = 'Offline'
                stdout_lower = stdout.lower()
                if '100% packet loss' in stdout_lower or 'loss' in stdout_lower or 'inalcanzable' in stdout_lower or 'unreachable' in stdout_lower:
                    msg = 'Inalcanzable (100% packet loss)'
                elif 'dns' in stdout_lower or 'not find host' in stdout_lower or 'no pudo encontrar' in stdout_lower:
                    msg = 'Servidor no encontrado (DNS error)'
                return {'online': False, 'latency': None, 'error': msg, 'warning': False}
        except Exception as e:
            return {'online': False, 'latency': None, 'error': str(e), 'warning': False}

# --- Widget Personalizado para el Historial de Latencia ---
class LatencyHistoryWidget(QWidget):
    def __init__(self, history=None, parent=None):
        super().__init__(parent)
        self.history = history or []
        self.setMinimumHeight(42)
        self.setMaximumHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_history(self, history):
        self.history = history
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        max_bars = 20
        gap = 4
        bar_width = max(2, (w - (max_bars - 1) * gap) // max_bars)
        
        # Rellenar con vacíos si hay menos de 20 elementos en el historial
        padded = [{'empty': True}] * (max_bars - len(self.history)) + [{'empty': False, **item} for item in self.history]
        
        num_blocks = 20
        block_gap = 1
        block_height = max(1, (h - (num_blocks - 1) * block_gap) // num_blocks)
        
        for idx, item in enumerate(padded):
            x = idx * (bar_width + gap)
            
            if item.get('empty', True):
                # 20 bloques vacíos oscuros
                for j in range(num_blocks):
                    y = h - (j + 1) * (block_height + block_gap)
                    painter.fillRect(QRect(x, y, bar_width, block_height), QColor(255, 255, 255, 12))
            else:
                online = item.get('online', True)
                warning = item.get('warning', False)
                latency = item.get('latency')
                
                if not online:
                    # 20 bloques rojos (caído)
                    for j in range(num_blocks):
                        y = h - (j + 1) * (block_height + block_gap)
                        painter.fillRect(QRect(x, y, bar_width, block_height), QColor("#ef4444"))
                else:
                    # Latencia dinámica
                    max_latency = 1000
                    lat_val = latency if latency is not None else 0
                    active_blocks = max(1, min(20, round((lat_val / max_latency) * 20)))
                    
                    for j in range(num_blocks):
                        y = h - (j + 1) * (block_height + block_gap)
                        if j < active_blocks:
                            if j < 8:
                                color = QColor("#10b981") # Verde bajo
                            elif j < 14:
                                color = QColor("#f59e0b") # Amarillo medio
                            else:
                                color = QColor("#ef4444") # Rojo alto
                            painter.fillRect(QRect(x, y, bar_width, block_height), color)
                        else:
                            painter.fillRect(QRect(x, y, bar_width, block_height), QColor(255, 255, 255, 12))

# --- Diálogo: Agregar / Editar Sitio ---
class SiteDialog(QDialog):
    def __init__(self, parent=None, site_data=None):
        super().__init__(parent)
        self.site_data = site_data
        self.setWindowTitle("Agregar Sitio" if not site_data else "Editar Sitio")
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.txtName = QLineEdit(self)
        self.txtName.setPlaceholderText("Ej: Mi Servidor API, Blog Personal")
        
        self.cbType = QComboBox(self)
        self.cbType.addItems(["HTTP / HTTPS (Sitio Web / API)", "Ping / ICMP (IP o Hostname)"])
        
        self.txtAddress = QLineEdit(self)
        self.txtAddress.setPlaceholderText("Ej: https://miservidor.com o 192.168.1.1")
        
        self.spinInterval = QSpinBox(self)
        self.spinInterval.setMinimum(0)
        self.spinInterval.setMaximum(3600)
        self.spinInterval.setSpecialValueText("Predeterminado global")
        
        form_layout.addRow("Nombre descriptivo:", self.txtName)
        form_layout.addRow("Tipo de Monitoreo:", self.cbType)
        form_layout.addRow("Dirección / IP:", self.txtAddress)
        form_layout.addRow("Intervalo (segundos):", self.spinInterval)
        
        layout.addLayout(form_layout)
        
        # Botones
        btn_layout = QHBoxLayout()
        self.btnCancel = QPushButton("Cancelar", self)
        self.btnCancel.clicked.connect(self.reject)
        self.btnSave = QPushButton("Guardar", self)
        self.btnSave.setObjectName("btnPrimary")
        self.btnSave.clicked.connect(self.validate_and_save)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btnCancel)
        btn_layout.addWidget(self.btnSave)
        layout.addLayout(btn_layout)
        
        if self.site_data:
            self.txtName.setText(self.site_data.get('name', ''))
            self.cbType.setCurrentIndex(0 if self.site_data.get('type') == 'http' else 1)
            self.txtAddress.setText(self.site_data.get('address', ''))
            self.spinInterval.setValue(self.site_data.get('interval') or 0)

    def validate_and_save(self):
        if not self.txtName.text().strip() or not self.txtAddress.text().strip():
            QMessageBox.warning(self, "Campos requeridos", "Por favor, completa el nombre y la dirección.")
            return
        self.accept()

    def get_data(self):
        return {
            'name': self.txtName.text().strip(),
            'type': 'http' if self.cbType.currentIndex() == 0 else 'ping',
            'address': self.txtAddress.text().strip(),
            'interval': self.spinInterval.value() if self.spinInterval.value() > 0 else None
        }

# --- Diálogo: Ajustes Globales ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings_data=None):
        super().__init__(parent)
        self.settings_data = settings_data or {}
        self.setWindowTitle("Ajustes de MonTray")
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.spinGlobalInterval = QSpinBox(self)
        self.spinGlobalInterval.setMinimum(5)
        self.spinGlobalInterval.setMaximum(3600)
        self.spinGlobalInterval.setValue(self.settings_data.get('globalInterval', 30))
        
        self.chkNotifications = QCheckBox("Habilitar notificaciones de escritorio", self)
        self.chkNotifications.setChecked(self.settings_data.get('notificationsEnabled', True))
        
        self.chkStartMinimized = QCheckBox("Iniciar minimizado en la bandeja", self)
        self.chkStartMinimized.setChecked(self.settings_data.get('startMinimized', False))
        
        self.chkAutostart = QCheckBox("Iniciar con el sistema operativo (Autostart)", self)
        self.chkAutostart.setChecked(self.settings_data.get('autostart', False))
        
        form_layout.addRow("Intervalo global (segundos):", self.spinGlobalInterval)
        form_layout.addRow("", self.chkNotifications)
        form_layout.addRow("", self.chkStartMinimized)
        form_layout.addRow("", self.chkAutostart)
        
        layout.addLayout(form_layout)
        
        btn_layout = QHBoxLayout()
        self.btnCancel = QPushButton("Cancelar", self)
        self.btnCancel.clicked.connect(self.reject)
        self.btnApply = QPushButton("Aplicar cambios", self)
        self.btnApply.setObjectName("btnPrimary")
        self.btnApply.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btnCancel)
        btn_layout.addWidget(self.btnApply)
        layout.addLayout(btn_layout)

    def get_data(self):
        return {
            'globalInterval': self.spinGlobalInterval.value(),
            'notificationsEnabled': self.chkNotifications.isChecked(),
            'startMinimized': self.chkStartMinimized.isChecked(),
            'autostart': self.chkAutostart.isChecked()
        }

# --- Clase de Tarjeta de Monitor (SiteCard) ---
class SiteCard(QFrame):
    toggle_signal = pyqtSignal(str, bool)
    edit_signal = pyqtSignal(str)
    delete_signal = pyqtSignal(str)
    check_now_signal = pyqtSignal(str)

    def __init__(self, site, parent=None):
        super().__init__(parent)
        self.site = site
        self.setObjectName("siteCard")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        
        # Encabezado de la tarjeta (Nombre y Estado)
        header_layout = QHBoxLayout()
        self.lblName = QLabel(self.site['name'], self)
        self.lblName.setObjectName("siteName")
        
        self.lblBadge = QLabel(self)
        self.lblBadge.setObjectName("statusBadge")
        self.update_status_badge()
        
        header_layout.addWidget(self.lblName)
        header_layout.addStretch()
        header_layout.addWidget(self.lblBadge)
        layout.addLayout(header_layout)
        
        # Dirección
        self.lblAddress = QLabel(self.site['address'], self)
        self.lblAddress.setObjectName("siteAddress")
        layout.addWidget(self.lblAddress)
        
        # Historial (Gráfico personalizado)
        self.graph = LatencyHistoryWidget(self.site.get('history', []), self)
        layout.addWidget(self.graph)
        
        # Fila inferior: Stats e información
        footer_layout = QHBoxLayout()
        
        stat_text = "Sin chequeos"
        if self.site.get('lastCheck'):
            lat = f"{self.site['lastLatency']} ms" if self.site.get('lastLatency') is not None else "N/D"
            stat_text = f"Último: {lat}"
        
        self.lblStats = QLabel(stat_text, self)
        self.lblStats.setStyleSheet("color: #a0aec0; font-size: 11px;")
        footer_layout.addWidget(self.lblStats)
        
        # Detalle de error si hay
        self.lblError = QLabel(self)
        self.lblError.setStyleSheet("color: #fc8181; font-size: 10px; font-weight: bold;")
        self.lblError.setVisible(False)
        self.update_error_label()
        
        footer_layout.addStretch()
        
        # Acciones de control
        self.chkEnabled = QCheckBox(self)
        self.chkEnabled.setToolTip("Activar/Desactivar monitoreo")
        self.chkEnabled.setChecked(self.site.get('enabled', True))
        self.chkEnabled.toggled.connect(self.on_toggle)
        
        self.btnCheck = QPushButton("🔄", self)
        self.btnCheck.setFixedSize(26, 26)
        self.btnCheck.setToolTip("Verificar ahora")
        self.btnCheck.clicked.connect(self.on_check_now)
        
        self.btnEdit = QPushButton("⚙️", self)
        self.btnEdit.setFixedSize(26, 26)
        self.btnEdit.setToolTip("Editar sitio")
        self.btnEdit.clicked.connect(self.on_edit)
        
        self.btnDelete = QPushButton("🗑️", self)
        self.btnDelete.setFixedSize(26, 26)
        self.btnDelete.setObjectName("btnDangerAction")
        self.btnDelete.setStyleSheet("background-color: #ef4444; border: none; border-radius: 4px; color: white;")
        self.btnDelete.setToolTip("Eliminar sitio")
        self.btnDelete.clicked.connect(self.on_delete)
        
        footer_layout.addWidget(self.chkEnabled)
        footer_layout.addWidget(self.btnCheck)
        footer_layout.addWidget(self.btnEdit)
        footer_layout.addWidget(self.btnDelete)
        
        layout.addLayout(footer_layout)
        layout.addWidget(self.lblError)

    def update_data(self, site):
        self.site = site
        self.lblName.setText(site['name'])
        self.lblAddress.setText(site['address'])
        self.chkEnabled.setChecked(site.get('enabled', True))
        self.update_status_badge()
        self.update_error_label()
        self.graph.set_history(site.get('history', []))
        
        stat_text = "Sin chequeos"
        if self.site.get('lastCheck'):
            lat = f"{self.site['lastLatency']} ms" if self.site.get('lastLatency') is not None else "N/D"
            stat_text = f"Último: {lat}"
        self.lblStats.setText(stat_text)

    def update_status_badge(self):
        status = self.site.get('status', 'idle')
        self.lblBadge.setText(status.upper())
        self.lblBadge.setProperty("class", f"badge-{status}")
        self.lblBadge.setObjectName(f"badge-{status}")
        self.lblBadge.style().unpolish(self.lblBadge)
        self.lblBadge.style().polish(self.lblBadge)

    def update_error_label(self):
        err = self.site.get('lastError')
        if err and self.site.get('status') == 'offline':
            self.lblError.setText(err)
            self.lblError.setVisible(True)
        elif err and self.site.get('status') == 'warning':
            self.lblError.setText(err)
            self.lblError.setVisible(True)
        else:
            self.lblError.setVisible(False)

    def on_toggle(self, checked):
        self.toggle_signal.emit(self.site['id'], checked)

    def on_check_now(self):
        self.check_now_signal.emit(self.site['id'])

    def on_edit(self):
        self.edit_signal.emit(self.site['id'])

    def on_delete(self):
        self.delete_signal.emit(self.site['id'])

# --- Ventana Principal de la Aplicación (MainWindow) ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MonTray - Panel de Monitoreo")
        self.setMinimumSize(780, 560)
        self.resize(840, 600)
        
        self.config_path = get_config_path()
        self.config = {
            'settings': {
                'globalInterval': 30,
                'notificationsEnabled': True,
                'startMinimized': False,
                'autostart': False
            },
            'sites': []
        }
        self.timers = {}
        self.cards = {}
        self.is_monitoring_active = True
        self.thread_pool = QThreadPool.globalInstance()
        
        self.load_config()
        self.init_ui()
        self.init_tray()
        
        # Iniciar timers
        self.start_all_monitoring()
        
        # Aplicar autostart si aplica
        self.update_autostart(self.config['settings'].get('autostart', False))

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.config['settings'].update(loaded.get('settings', {}))
                    self.config['sites'] = loaded.get('sites', [])
            else:
                self.save_config()
        except Exception as e:
            print("Error al cargar configuración:", e)

    def save_config(self):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print("Error al guardar configuración:", e)

    def init_ui(self):
        # Widget Central
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # 1. Cabecera (Header)
        header_layout = QHBoxLayout()
        
        logo_label = QLabel(self)
        icon_path = get_asset_path('app-icon.png')
        if os.path.exists(icon_path):
            logo_label.setPixmap(QIcon(icon_path).pixmap(36, 36))
        header_layout.addWidget(logo_label)
        
        title_layout = QVBoxLayout()
        self.lblTitle = QLabel("MonTray", self)
        self.lblTitle.setStyleSheet("color: white; font-weight: bold; font-size: 18px;")
        self.lblSubtitle = QLabel("Inicializando monitores...", self)
        self.lblSubtitle.setStyleSheet("color: #a0aec0; font-size: 12px;")
        title_layout.addWidget(self.lblTitle)
        title_layout.addWidget(self.lblSubtitle)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch()
        
        # Botones de Cabecera
        self.btnCheckAll = QPushButton("🔄 Verificar ahora", self)
        self.btnCheckAll.clicked.connect(self.check_all_now)
        
        self.btnSettings = QPushButton("⚙️ Ajustes", self)
        self.btnSettings.clicked.connect(self.open_settings)
        
        self.btnNewSite = QPushButton("➕ Nuevo Sitio", self)
        self.btnNewSite.setObjectName("btnPrimary")
        self.btnNewSite.clicked.connect(self.open_add_site)
        
        header_layout.addWidget(self.btnCheckAll)
        header_layout.addWidget(self.btnSettings)
        header_layout.addWidget(self.btnNewSite)
        main_layout.addLayout(header_layout)
        
        # 2. Área de Contenido (Scroll Grid)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("mainScroll")
        
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("scrollAreaWidgetContents")
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setSpacing(12)
        
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll)
        
        # 3. Footer
        footer_layout = QHBoxLayout()
        lbl_dir = QLabel(f"Directorio de datos: {os.path.dirname(self.config_path)}", self)
        lbl_dir.setStyleSheet("color: #718096; font-size: 11px;")
        lbl_ver = QLabel("v1.0.0 (Python)", self)
        lbl_ver.setStyleSheet("color: #718096; font-size: 11px;")
        footer_layout.addWidget(lbl_dir)
        footer_layout.addStretch()
        footer_layout.addWidget(lbl_ver)
        main_layout.addLayout(footer_layout)
        
        self.render_cards()
        self.update_global_status()

    def render_cards(self):
        # Limpiar grid
        for card in self.cards.values():
            self.grid.removeWidget(card)
            card.deleteLater()
        self.cards.clear()
        
        # Agregar tarjetas
        cols = 2
        for idx, site in enumerate(self.config['sites']):
            card = SiteCard(site, self)
            card.toggle_signal.connect(self.toggle_site)
            card.edit_signal.connect(self.open_edit_site)
            card.delete_signal.connect(self.delete_site)
            card.check_now_signal.connect(self.check_site_now)
            
            row = idx // cols
            col = idx % cols
            self.grid.addWidget(card, row, col)
            self.cards[site['id']] = card

    def update_global_status(self):
        active_sites = [s for s in self.config['sites'] if s.get('enabled', True)]
        if not self.is_monitoring_active:
            text = "El monitoreo global está desactivado"
        elif not active_sites:
            text = "Sin monitores activos. Agrega un servidor para comenzar."
        else:
            offline = len([s for s in active_sites if s.get('status') == 'offline'])
            warning = len([s for s in active_sites if s.get('status') == 'warning'])
            total = len(active_sites)
            
            if offline > 0:
                text = f"🚨 {offline} caído(s) de {total} activos"
            elif warning > 0:
                text = f"⚠️ {warning} advertencia(s) de {total} activos"
            else:
                text = f"🟢 Todos los sistemas operativos online ({total}/{total})"
        
        self.lblSubtitle.setText(text)

    # --- Lógica de Monitoreo ---
    def start_site_monitoring(self, site):
        self.stop_site_monitoring(site['id'])
        if not site.get('enabled', True) or not self.is_monitoring_active:
            return
        
        interval = site.get('interval') or self.config['settings'].get('globalInterval', 30)
        
        # Primer chequeo inmediato
        self.check_site(site)
        
        timer = QTimer(self)
        timer.timeout.connect(lambda: self.check_site(site))
        timer.start(interval * 1000)
        self.timers[site['id']] = timer

    def stop_site_monitoring(self, site_id):
        if site_id in self.timers:
            self.timers[site_id].stop()
            self.timers[site_id].deleteLater()
            del self.timers[site_id]

    def start_all_monitoring(self):
        for site in self.config['sites']:
            self.start_site_monitoring(site)

    def stop_all_monitoring(self):
        for s_id in list(self.timers.keys()):
            self.stop_site_monitoring(s_id)

    def check_site(self, site):
        # Actualizar visualmente a "checking"
        site['status'] = 'checking'
        if site['id'] in self.cards:
            self.cards[site['id']].update_data(site)
        
        worker = CheckSiteWorker(site['id'], site['type'], site['address'])
        worker.signals.finished.connect(self.on_check_finished)
        self.thread_pool.start(worker)

    @pyqtSlot(str, dict)
    def on_check_finished(self, site_id, result):
        idx = next((i for i, s in enumerate(self.config['sites']) if s['id'] == site_id), -1)
        if idx == -1:
            return
        
        site = self.config['sites'][idx]
        prev_status = site.get('status')
        if prev_status == 'checking':
            prev_status = site.get('lastStatus', 'idle')
            
        new_status = 'online'
        if not result['online']:
            new_status = 'offline'
        elif result.get('warning'):
            new_status = 'warning'
            
        site['status'] = new_status
        site['lastStatus'] = new_status
        site['lastCheck'] = datetime.now().isoformat()
        site['lastLatency'] = result['latency']
        site['lastError'] = result['error']
        
        if 'history' not in site:
            site['history'] = []
        
        site['history'].append({
            'timestamp': site['lastCheck'],
            'online': result['online'],
            'warning': result.get('warning', False),
            'latency': result['latency']
        })
        if len(site['history']) > 20:
            site['history'].pop(0)
            
        self.save_config()
        self.update_global_status()
        self.update_tray_icon()
        
        if site_id in self.cards:
            self.cards[site_id].update_data(site)
            
        self.trigger_notification(site, prev_status, new_status)

    def trigger_notification(self, site, prev, new):
        if not self.config['settings'].get('notificationsEnabled', True):
            return
        if not prev or prev in ('idle', 'checking'):
            return
            
        if prev != 'offline' and new == 'offline':
            self.tray.showMessage(
                f"🚨 Sitio Caído: {site['name']}",
                f"{site['address']} no responde. Detalle: {site['lastError'] or 'Sin respuesta'}",
                QSystemTrayIcon.MessageIcon.Critical,
                5000
            )
        elif prev == 'offline' and new != 'offline':
            lat = f" ({site['lastLatency']} ms)" if site['lastLatency'] is not None else ""
            self.tray.showMessage(
                f"✅ Sitio Recuperado: {site['name']}",
                f"{site['address']} vuelve a estar en línea{lat}.",
                QSystemTrayIcon.MessageIcon.Information,
                5000
            )

    # --- Acciones de UI ---
    def check_all_now(self):
        for site in self.config['sites']:
            if site.get('enabled', True):
                self.check_site(site)

    def check_site_now(self, site_id):
        site = next((s for s in self.config['sites'] if s['id'] == site_id), None)
        if site and site.get('enabled', True):
            self.check_site(site)

    def toggle_site(self, site_id, enabled):
        idx = next((i for i, s in enumerate(self.config['sites']) if s['id'] == site_id), -1)
        if idx != -1:
            self.config['sites'][idx]['enabled'] = enabled
            if not enabled:
                self.stop_site_monitoring(site_id)
                self.config['sites'][idx]['status'] = 'idle'
                self.config['sites'][idx]['lastLatency'] = None
                self.config['sites'][idx]['lastError'] = None
            else:
                self.start_site_monitoring(self.config['sites'][idx])
            
            self.save_config()
            self.update_global_status()
            self.update_tray_icon()
            if site_id in self.cards:
                self.cards[site_id].update_data(self.config['sites'][idx])

    def open_add_site(self):
        dlg = SiteDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            s_id = str(int(time.time() * 1000))
            site = {
                'id': s_id,
                'name': data['name'],
                'type': data['type'],
                'address': data['address'],
                'interval': data['interval'],
                'enabled': True,
                'status': 'idle',
                'lastCheck': None,
                'lastLatency': None,
                'lastError': None,
                'history': []
            }
            self.config['sites'].append(site)
            self.save_config()
            self.render_cards()
            self.start_site_monitoring(site)
            self.update_global_status()
            self.update_tray_icon()

    def open_edit_site(self, site_id):
        idx = next((i for i, s in enumerate(self.config['sites']) if s['id'] == site_id), -1)
        if idx == -1: return
        
        site = self.config['sites'][idx]
        dlg = SiteDialog(self, site)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            old_enabled = site.get('enabled')
            old_address = site.get('address')
            old_type = site.get('type')
            old_interval = site.get('interval')
            
            site.update({
                'name': data['name'],
                'type': data['type'],
                'address': data['address'],
                'interval': data['interval']
            })
            self.save_config()
            
            if (old_enabled != site.get('enabled') or
                old_address != site.get('address') or
                old_type != site.get('type') or
                old_interval != site.get('interval')):
                if site.get('enabled', True):
                    self.start_site_monitoring(site)
                else:
                    self.stop_site_monitoring(site_id)
                    site['status'] = 'idle'
            
            self.render_cards()
            self.update_global_status()
            self.update_tray_icon()

    def delete_site(self, site_id):
        reply = QMessageBox.question(
            self, "Confirmar eliminación",
            "¿Estás seguro de que deseas eliminar este monitor?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.stop_site_monitoring(site_id)
            self.config['sites'] = [s for s in self.config['sites'] if s['id'] != site_id]
            self.save_config()
            self.render_cards()
            self.update_global_status()
            self.update_tray_icon()

    def open_settings(self):
        dlg = SettingsDialog(self, self.config['settings'])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            old_interval = self.config['settings'].get('globalInterval')
            old_autostart = self.config['settings'].get('autostart')
            
            self.config['settings'].update(data)
            self.save_config()
            
            # Autostart
            if old_autostart != data['autostart']:
                self.update_autostart(data['autostart'])
                
            # Reiniciar monitoreos globales si cambió el intervalo
            if old_interval != data['globalInterval']:
                for site in self.config['sites']:
                    if not site.get('interval') and site.get('enabled', True):
                        self.start_site_monitoring(site)
            
            self.update_global_status()

    # --- Autostart Multiplataforma ---
    def update_autostart(self, enabled):
        if sys.platform == 'win32':
            try:
                import winreg
                key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
                if enabled:
                    if getattr(sys, 'frozen', False):
                        exec_path = f'"{sys.executable}" --hidden'
                    else:
                        exec_path = f'"{sys.executable}" "{os.path.abspath(__file__)}" --hidden'
                    winreg.SetValueEx(key, "MonTrayPython", 0, winreg.REG_SZ, exec_path)
                else:
                    try:
                        winreg.DeleteValue(key, "MonTrayPython")
                    except FileNotFoundError:
                        pass
                winreg.CloseKey(key)
            except Exception as e:
                print("Error en registro de autostart (Windows):", e)
        else:
            # Linux Autostart
            autostart_dir = os.path.expanduser('~/.config/autostart')
            autostart_file = os.path.join(autostart_dir, 'montray-python.desktop')
            try:
                if enabled:
                    os.makedirs(autostart_dir, exist_ok=True)
                    if getattr(sys, 'frozen', False):
                        exec_path = f'"{sys.executable}" --hidden'
                    else:
                        exec_path = f'"{sys.executable}" "{os.path.abspath(__file__)}" --hidden'
                    
                    desktop_content = f"""[Desktop Entry]
Type=Application
Version=1.0
Name=MonTray (Python)
Comment=Monitoreo de servidores en bandeja de sistema
Exec={exec_path}
StartupNotify=false
Terminal=false
Icon={get_asset_path('app-icon.png')}
Categories=Network;Utility;
"""
                    with open(autostart_file, 'w', encoding='utf-8') as f:
                        f.write(desktop_content)
                    os.chmod(autostart_file, 0o755)
                else:
                    if os.path.exists(autostart_file):
                        os.remove(autostart_file)
            except Exception as e:
                print("Error en archivo de autostart (Linux):", e)

    # --- Icono de Bandeja de Sistema (System Tray) ---
    def init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(get_asset_path('icon-idle.png')))
        self.tray.setToolTip("MonTray - Monitoreo de Red (Python)")
        
        # Menú contextual de la bandeja
        menu = QMenu()
        
        act_open = QAction("Abrir MonTray", self)
        act_open.triggered.connect(self.show_window)
        menu.addAction(act_open)
        
        act_check = QAction("Verificar todo ahora", self)
        act_check.triggered.connect(self.check_all_now)
        menu.addAction(act_check)
        
        menu.addSeparator()
        
        self.act_active = QAction("Monitoreo Activo", self)
        self.act_active.setCheckable(True)
        self.act_active.setChecked(self.is_monitoring_active)
        self.act_active.triggered.connect(self.toggle_global_monitoring)
        menu.addAction(self.act_active)
        
        menu.addSeparator()
        
        act_exit = QAction("Salir", self)
        act_exit.triggered.connect(self.quit_app)
        menu.addAction(act_exit)
        
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def update_tray_icon(self):
        active_sites = [s for s in self.config['sites'] if s.get('enabled', True)]
        if not self.is_monitoring_active or not active_sites:
            self.tray.setIcon(QIcon(get_asset_path('icon-idle.png')))
            self.tray.setToolTip("MonTray - Monitoreo desactivado / Sin sitios")
            return
            
        offline = len([s for s in active_sites if s.get('status') == 'offline'])
        warning = len([s for s in active_sites if s.get('status') == 'warning'])
        total = len(active_sites)
        
        if offline > 0:
            self.tray.setIcon(QIcon(get_asset_path('icon-offline.png')))
            self.tray.setToolTip(f"MonTray - {offline} caído(s) de {total}")
        elif warning > 0:
            self.tray.setIcon(QIcon(get_asset_path('icon-offline.png')))
            self.tray.setToolTip(f"MonTray - {warning} advertencia(s) de {total}")
        else:
            self.tray.setIcon(QIcon(get_asset_path('icon-online.png')))
            self.tray.setToolTip(f"MonTray - Todos online ({total}/{total})")

    def toggle_global_monitoring(self, checked):
        self.is_monitoring_active = checked
        if checked:
            self.start_all_monitoring()
        else:
            self.stop_all_monitoring()
            for site in self.config['sites']:
                if site.get('enabled', True):
                    site['status'] = 'idle'
            self.render_cards()
            
        self.update_global_status()
        self.update_tray_icon()
        self.act_active.setChecked(checked)

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.toggle_window_visibility()

    def toggle_window_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show_window()

    def show_window(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def closeEvent(self, event):
        # En lugar de cerrar, ocultamos a la bandeja
        if not QApplication.isSavingSession():
            event.ignore()
            self.hide()

    def quit_app(self):
        self.stop_all_monitoring()
        QApplication.quit()

# --- Estilos Globales de la Interfaz (QSS Dark Premium) ---
QSS_STYLESHEET = """
QMainWindow {
    background-color: #0f141f;
}
QWidget {
    color: #cbd5e0;
    font-family: "Segoe UI", "Inter", "Helvetica", sans-serif;
    font-size: 12px;
}
QFrame#siteCard {
    background-color: #1a202c;
    border: 1px solid rgba(255, 255, 255, 12);
    border-radius: 8px;
}
QFrame#siteCard:hover {
    border: 1px solid rgba(16, 185, 129, 50);
}
QLabel#siteName {
    color: #ffffff;
    font-weight: bold;
    font-size: 14px;
}
QLabel#siteAddress {
    color: #a0aec0;
    font-size: 11px;
}
QLabel#statusBadge {
    border-radius: 4px;
    padding: 2px 6px;
    font-weight: bold;
    font-size: 9px;
    color: #ffffff;
}
QLabel#badge-online {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #047857;
}
QLabel#badge-offline {
    background-color: #7f1d1d;
    color: #f87171;
    border: 1px solid #b91c1c;
}
QLabel#badge-warning {
    background-color: #78350f;
    color: #fbbf24;
    border: 1px solid #b45309;
}
QLabel#badge-idle {
    background-color: #2d3748;
    color: #cbd5e0;
    border: 1px solid #4a5568;
}
QLabel#badge-checking {
    background-color: #1e3a8a;
    color: #60a5fa;
    border: 1px solid #1d4ed8;
}
QPushButton {
    background-color: #1e293b;
    color: #ffffff;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #334155;
    border: 1px solid #475569;
}
QPushButton:pressed {
    background-color: #0f172a;
}
QPushButton#btnPrimary {
    background-color: #10b981;
    border: 1px solid #059669;
}
QPushButton#btnPrimary:hover {
    background-color: #059669;
    border: 1px solid #047857;
}
QScrollArea {
    background-color: transparent;
    border: none;
}
QWidget#scrollAreaWidgetContents {
    background-color: transparent;
}
/* Scrollbar custom elegante */
QScrollBar:vertical {
    border: none;
    background: #0f141f;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #2d3748;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #4a5568;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
/* Estilo de Diálogos */
QDialog {
    background-color: #1a202c;
    color: #cbd5e0;
}
QLineEdit, QSpinBox, QComboBox {
    background-color: #2d3748;
    border: 1px solid #4a5568;
    border-radius: 4px;
    padding: 6px;
    color: #ffffff;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #10b981;
}
QDialog QLabel {
    color: #ffffff;
    font-weight: bold;
}
"""

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(QSS_STYLESHEET)
    
    # Manejar inicio oculto --hidden
    start_hidden = "--hidden" in sys.argv
    
    window = MainWindow()
    if not start_hidden and not window.config['settings'].get('startMinimized', False):
        window.show_window()
        
    sys.exit(app.exec())
