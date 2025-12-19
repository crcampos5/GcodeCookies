from PySide6.QtWidgets import (QMainWindow, QHBoxLayout, QVBoxLayout, QWidget, 
                               QFileDialog, QMessageBox, QLabel, QTabWidget, QTextEdit)

from gui.canvas import ViewerCanvas
from gui.control_panel import ControlPanel
from gui.file_panel import FilePanel
from gui.gcode_panel import GCodePanel
from gui.collapsible_box import CollapsibleBox  # <--- IMPORTACIÓN NUEVA
from core.dxf_processor import DXFReader

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CookieCNC - Editor Multicapa")
        self.resize(1100, 750)
        
        self.dxf_reader = DXFReader()
        self.current_selected_item = None 

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Layout Principal Horizontal: [ Pestañas Centrales | Barra Lateral ]
        self.main_layout = QHBoxLayout(main_widget)

        # --- A. ZONA CENTRAL (PESTAÑAS) ---
        self.tabs = QTabWidget()
        
        # 1. Pestaña Diseño
        self.tab_design = QWidget()
        self.layout_design = QVBoxLayout(self.tab_design)
        self.layout_design.setContentsMargins(0,0,0,0)
        
        self.lbl_info = QLabel("Carga un DXF y selecciona un objeto.")
        self.canvas = ViewerCanvas()
        
        self.layout_design.addWidget(self.lbl_info)
        self.layout_design.addWidget(self.canvas)
        
        # 2. Pestaña Visor G-Code
        self.tab_viewer = QWidget()
        self.layout_viewer = QVBoxLayout(self.tab_viewer)
        self.layout_viewer.setContentsMargins(0,0,0,0)
        
        self.gcode_display = QTextEdit()
        self.gcode_display.setPlaceholderText("Genera el código desde el panel derecho para verlo aquí.")
        self.gcode_display.setReadOnly(True)
        self.gcode_display.setStyleSheet("font-family: Consolas, monospace; font-size: 13px; color: #333;")
        
        self.layout_viewer.addWidget(self.gcode_display)

        # Agregar pestañas
        self.tabs.addTab(self.tab_design, "🎨 Diseño (Canvas)")
        self.tabs.addTab(self.tab_viewer, "📝 Código Generado")

        # --- B. BARRA LATERAL (FIJA) ---
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(300) 
        l_sidebar = QVBoxLayout(self.sidebar)
        l_sidebar.setContentsMargins(5, 5, 5, 5)
        
        # 1. Panel de Archivo (Siempre visible)
        self.file_panel = FilePanel()
        l_sidebar.addWidget(self.file_panel)
        
        l_sidebar.addSpacing(10)

        # 2. Panel de Control (DESPLEGABLE)
        self.control_panel = ControlPanel()
        # Envolvemos el panel en nuestra caja colapsable
        self.box_control = CollapsibleBox("Transformación", self.control_panel)
        l_sidebar.addWidget(self.box_control)
        
        l_sidebar.addSpacing(5)

        # 3. Panel G-Code (DESPLEGABLE)
        self.gcode_panel = GCodePanel()
        self.box_gcode = CollapsibleBox("Configuración G-Code", self.gcode_panel)
        l_sidebar.addWidget(self.box_gcode)

        l_sidebar.addStretch() # Empuja todo hacia arriba

        # Agregar al layout principal
        self.main_layout.addWidget(self.tabs, stretch=1)
        self.main_layout.addWidget(self.sidebar, stretch=0)

    def setup_connections(self):
        # Carga
        self.file_panel.signal_load.connect(self.action_load_file)
        
        # Canvas -> Selección
        self.canvas.item_selected.connect(self.on_item_selected)
        
        # Panel Control -> Transformación
        self.control_panel.value_changed.connect(self.apply_transformations)
        
        # Panel GCode -> Visor
        self.gcode_panel.gcode_generated.connect(self.display_gcode_result)

        self.gcode_panel.operations_changed.connect(self.update_canvas_preview)

    def action_load_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Importar DXF", "", "DXF (*.dxf)")
        if filename:
            paths = self.dxf_reader.read(filename)
            if paths:
                self.canvas.add_dxf_object(paths)
                self.lbl_info.setText(f"Añadido: {filename.split('/')[-1]}")
                self.tabs.setCurrentIndex(0)
            else:
                QMessageBox.critical(self, "Error", "DXF inválido.")

    def on_item_selected(self, item):
        self.current_selected_item = item
        
        # Actualizamos paneles laterales
        self.control_panel.update_ui_from_item(item)
        self.gcode_panel.update_selection(item)
        
        if item:
            self.lbl_info.setText("Objeto seleccionado.")
            # UX: Desplegar automáticamente el panel de control al seleccionar si está cerrado
            if not self.box_control.toggle_button.isChecked():
                self.box_control.toggle_button.click()
        else:
            self.lbl_info.setText("Ningún objeto seleccionado.")

    def apply_transformations(self, x, y, scale, rotation):
        if self.current_selected_item:
            self.current_selected_item.setPos(x, y)
            self.current_selected_item.setScale(scale)
            self.current_selected_item.setRotation(rotation)

    def display_gcode_result(self, text):
        self.gcode_display.setText(text)
        self.tabs.setCurrentIndex(1)
        self.file_panel.enable_gcode_button(True)

    def update_canvas_preview(self):
        """Pide al generador los caminos calculados y se los manda al canvas"""
        # 1. Obtener datos de geometría (rutas de relleno o borde)
        preview_data = self.gcode_panel.generator.get_all_preview_paths()
        
        # 2. Mandarlos a pintar
        self.canvas.draw_preview_paths(preview_data)