from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QGroupBox, QDoubleSpinBox, QFormLayout, QLabel
from PySide6.QtCore import Qt, Signal

class ControlPanel(QWidget):
    # Señales de cambio
    value_changed = Signal(float, float, float, float) # x, y, scale, rotation

    def __init__(self):
        super().__init__()
        self.block_signals = False # Para evitar bucles infinitos al actualizar UI
        self.setup_ui()
        self.setEnabled(False) # Deshabilitado hasta que se seleccione algo

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        # --- Posición ---
        group_pos = QGroupBox("Posición (mm)")
        form_pos = QFormLayout()
        self.spin_x = self._create_spin(-500, 500)
        self.spin_y = self._create_spin(-500, 500)
        form_pos.addRow("X:", self.spin_x)
        form_pos.addRow("Y:", self.spin_y)
        group_pos.setLayout(form_pos)
        layout.addWidget(group_pos)

        # --- Escala ---
        group_scale = QGroupBox("Escala")
        v_scale = QVBoxLayout()
        self.spin_scale = self._create_spin(0.1, 10.0, step=0.1)
        v_scale.addWidget(self.spin_scale)
        group_scale.setLayout(v_scale)
        layout.addWidget(group_scale)

        # --- Rotación ---
        group_rot = QGroupBox("Rotación (°)")
        v_rot = QVBoxLayout()
        self.spin_rot = self._create_spin(-360, 360)
        v_rot.addWidget(self.spin_rot)
        group_rot.setLayout(v_rot)
        layout.addWidget(group_rot)

    def _create_spin(self, min_val, max_val, step=1.0):
        s = QDoubleSpinBox()
        s.setRange(min_val, max_val)
        s.setSingleStep(step)
        s.valueChanged.connect(self.emit_changes)
        return s

    def update_ui_from_item(self, item):
        """Actualiza los valores visuales basados en el objeto seleccionado"""
        if item is None:
            self.setEnabled(False)
            return

        self.setEnabled(True)
        self.block_signals = True # Pausar emisión mientras actualizamos UI
        
        self.spin_x.setValue(item.x())
        self.spin_y.setValue(item.y())
        self.spin_scale.setValue(item.scale())
        self.spin_rot.setValue(item.rotation())
        
        self.block_signals = False

    def emit_changes(self):
        """Emitir los nuevos valores a la ventana principal"""
        if not self.block_signals:
            self.value_changed.emit(
                self.spin_x.value(),
                self.spin_y.value(),
                self.spin_scale.value(),
                self.spin_rot.value()
            )