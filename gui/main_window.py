from PySide6.QtWidgets import QMainWindow, QHBoxLayout, QVBoxLayout, QWidget, QFileDialog, QMessageBox, QLabel, QFrame
from PySide6.QtCore import Qt

from gui.canvas import ViewerCanvas
from gui.control_panel import ControlPanel
from gui.file_panel import FilePanel
from core.dxf_processor import DXFReader # <--- Usamos el nuevo Reader
# (El DXFItem lo maneja el canvas internamente)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CookieCNC - Editor Multicapa")
        self.resize(1100, 750)
        
        self.dxf_reader = DXFReader()
        self.current_selected_item = None # Referencia al objeto actual

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QHBoxLayout(main_widget)

        # --- Lienzo ---
        self.canvas_container = QWidget()
        l_canvas = QVBoxLayout(self.canvas_container)
        l_canvas.setContentsMargins(0,0,0,0)
        self.lbl_info = QLabel("Carga múltiples DXF. Selecciona con clic izquierdo para editar.")
        self.canvas = ViewerCanvas()
        l_canvas.addWidget(self.lbl_info)
        l_canvas.addWidget(self.canvas)

        # --- Panel Lateral ---
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(280)
        l_sidebar = QVBoxLayout(self.sidebar)
        
        self.file_panel = FilePanel()
        self.control_panel = ControlPanel() # Inicia deshabilitado
        
        l_sidebar.addWidget(self.file_panel)
        l_sidebar.addWidget(self.control_panel)
        l_sidebar.addStretch()

        self.main_layout.addWidget(self.canvas_container, stretch=1)
        self.main_layout.addWidget(self.sidebar, stretch=0)

    def setup_connections(self):
        # 1. Carga de archivos
        self.file_panel.signal_load.connect(self.action_load_file)
        
        # 2. Selección en Canvas -> Actualizar Panel Derecho
        self.canvas.item_selected.connect(self.on_item_selected)
        
        # 3. Cambio en Panel Derecho -> Actualizar Objeto en Canvas
        self.control_panel.value_changed.connect(self.apply_transformations)

    def action_load_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Importar DXF", "", "DXF (*.dxf)")
        if filename:
            paths = self.dxf_reader.read(filename)
            if paths:
                # El Canvas crea el item gráfico y lo añade
                self.canvas.add_dxf_object(paths)
                self.lbl_info.setText(f"Añadido: {filename.split('/')[-1]}")
            else:
                QMessageBox.critical(self, "Error", "DXF inválido.")

    def on_item_selected(self, item):
        """Llamado cuando el usuario hace clic en un objeto del canvas"""
        self.current_selected_item = item
        # Enviamos el item al panel para que lea sus valores (X, Y, Scale...)
        self.control_panel.update_ui_from_item(item)
        
        if item:
            self.lbl_info.setText("Objeto seleccionado. Modifica sus valores a la derecha.")
        else:
            self.lbl_info.setText("Ningún objeto seleccionado.")

    def apply_transformations(self, x, y, scale, rotation):
        """Llamado cuando el usuario mueve los spinbox"""
        if self.current_selected_item:
            # Aplicamos los valores directamente al item gráfico
            self.current_selected_item.setPos(x, y)
            self.current_selected_item.setScale(scale)
            self.current_selected_item.setRotation(rotation)