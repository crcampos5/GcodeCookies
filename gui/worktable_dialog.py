from PySide6.QtWidgets import QDialog,QVBoxLayout,QGridLayout,QLabel,QDoubleSpinBox,QDialogButtonBox,QComboBox
from core.worktable import ORIGIN_CORNERS

class WorktableDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Configuración de topes y origen')
        layout=QVBoxLayout(self)
        note=QLabel('Topes en milímetros desde la esquina inferior izquierda.')
        note.setWordWrap(True);layout.addWidget(note)
        grid=QGridLayout();layout.addLayout(grid)
        grid.addWidget(QLabel('X (mm)'),0,1);grid.addWidget(QLabel('Y (mm)'),0,2)
        self.fields=[]
        for row,(name,point) in enumerate(zip(['Tope 1','Tope 2'],settings['pins']),1):
            grid.addWidget(QLabel(name),row,0)
            pair=[]
            for column,value in enumerate(point,1):
                field=QDoubleSpinBox();field.setRange(-10000,10000);field.setDecimals(3)
                field.setSingleStep(1);field.setValue(value);grid.addWidget(field,row,column);pair.append(field)
            self.fields.append(pair)
        self.origin_combo=QComboBox()
        for name,point in ORIGIN_CORNERS:
            self.origin_combo.addItem(name,list(point))
            if list(point)==settings['origin']:
                self.origin_combo.setCurrentIndex(self.origin_combo.count()-1)
        grid.addWidget(QLabel('Origen (0,0)'),3,0)
        grid.addWidget(self.origin_combo,3,1,1,2)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Aplicar')
        buttons.button(QDialogButtonBox.Cancel).setText('Cancelar')
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def settings(self):
        positions=[[field.value() for field in pair] for pair in self.fields]
        return {'pins':positions,'origin':self.origin_combo.currentData()}
