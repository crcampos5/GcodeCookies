from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QGroupBox, 
                               QDoubleSpinBox, QFormLayout)
from PySide6.QtCore import Qt, Signal

class ControlPanel(QWidget):
    # Señales solo de manipulación
    signal_move = Signal(float, float)
    signal_scale = Signal(float)
    signal_rotate = Signal(float)

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        # --- SECCIÓN 1: MOVER ---
        group_move = QGroupBox("Mover (mm)")
        layout_move = QFormLayout()
        
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(-500, 500)
        self.spin_x.setSuffix(" mm")
        
        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(-500, 500)
        self.spin_y.setSuffix(" mm")
        
        btn_move = QPushButton("Aplicar Traslación")
        btn_move.clicked.connect(self.on_move_clicked)
        
        layout_move.addRow("X:", self.spin_x)
        layout_move.addRow("Y:", self.spin_y)
        layout_move.addWidget(btn_move)
        group_move.setLayout(layout_move)
        layout.addWidget(group_move)

        # --- SECCIÓN 2: ESCALAR ---
        group_scale = QGroupBox("Escalar")
        layout_scale = QVBoxLayout()
        
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(0.1, 10.0)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setValue(1.0)
        self.spin_scale.setPrefix("x ")
        
        btn_scale = QPushButton("Aplicar Escala")
        btn_scale.clicked.connect(self.on_scale_clicked)
        
        layout_scale.addWidget(self.spin_scale)
        layout_scale.addWidget(btn_scale)
        group_scale.setLayout(layout_scale)
        layout.addWidget(group_scale)

        # --- SECCIÓN 3: ROTAR ---
        group_rot = QGroupBox("Rotar")
        layout_rot = QVBoxLayout()
        
        self.spin_rot = QDoubleSpinBox()
        self.spin_rot.setRange(-360, 360)
        self.spin_rot.setSuffix(" °")
        
        btn_rot = QPushButton("Rotar")
        btn_rot.clicked.connect(self.on_rotate_clicked)
        
        layout_rot.addWidget(self.spin_rot)
        layout_rot.addWidget(btn_rot)
        group_rot.setLayout(layout_rot)
        layout.addWidget(group_rot)

    def on_move_clicked(self):
        dx = self.spin_x.value()
        dy = self.spin_y.value()
        if dx != 0 or dy != 0:
            self.signal_move.emit(dx, dy)
            self.spin_x.setValue(0)
            self.spin_y.setValue(0)

    def on_scale_clicked(self):
        factor = self.spin_scale.value()
        if factor != 1.0:
            self.signal_scale.emit(factor)
            self.spin_scale.setValue(1.0)

    def on_rotate_clicked(self):
        angle = self.spin_rot.value()
        if angle != 0:
            self.signal_rotate.emit(angle)
            self.spin_rot.setValue(0)