from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QSizePolicy
from PySide6.QtCore import Qt

class CollapsibleBox(QWidget):
    """
    Widget contenedor que permite ocultar/mostrar su contenido 
    haciendo clic en el encabezado.
    """
    def __init__(self, title="", content_widget=None, parent=None):
        super().__init__(parent)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 1. Botón de Título (Toggle)
        self.toggle_button = QToolButton(text=f" {title}")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True) # Iniciar desplegado por defecto
        # Estilos CSS para que parezca una cabecera moderna
        self.toggle_button.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: #f0f0f0;
                color: #333;
                font-weight: bold;
                text-align: left;
                padding: 5px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
            QToolButton:checked {
                background-color: #ddd;
            }
        """)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.DownArrow)
        self.toggle_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toggle_button.clicked.connect(self.on_toggle)

        # 2. Contenedor del contenido real
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(5, 5, 5, 5) # Margen interno para el contenido
        
        # Agregar el widget específico (ControlPanel o GCodePanel)
        if content_widget:
            self.content_layout.addWidget(content_widget)

        # Agregar todo al layout principal de este componente
        self.layout.addWidget(self.toggle_button)
        self.layout.addWidget(self.content_area)

    def on_toggle(self, checked):
        # Cambiar flecha (Abajo=Abierto, Derecha=Cerrado) y visibilidad
        arrow = Qt.DownArrow if checked else Qt.RightArrow
        self.toggle_button.setArrowType(arrow)
        self.content_area.setVisible(checked)