from PySide6.QtWidgets import QDialog,QVBoxLayout,QGridLayout,QLabel,QDoubleSpinBox,QDialogButtonBox,QComboBox,QCheckBox,QMessageBox
from core.worktable import ORIGIN_CORNERS, WORK_AREA_SIZE
from core.machine_profiles import MachineProfiles

class WorktableDialog(QDialog):
    def __init__(self, settings, parent=None, profile_store=None):
        super().__init__(parent)
        self.setWindowTitle('Configuración de topes y origen')
        layout=QVBoxLayout(self)
        self.profile_store=profile_store if profile_store is not None else MachineProfiles()
        self.profile_error=None
        try:
            self.profiles=self.profile_store.read()
        except (ValueError,TypeError,OSError) as exc:
            self.profile_error=str(exc)
            self.profiles={'profiles':{},'default':None}
        layout.addWidget(QLabel('Máquina: elige un perfil o escribe un nombre para guardarlo.'))
        self.profile_combo=QComboBox();self.profile_combo.setEditable(True)
        self.profile_combo.setInsertPolicy(QComboBox.NoInsert)
        self.profile_combo.addItems(sorted(self.profiles['profiles']))
        self.profile_combo.setCurrentIndex(-1)
        layout.addWidget(self.profile_combo)
        self.default_check=QCheckBox('Usar por defecto al iniciar')
        layout.addWidget(self.default_check)
        note=QLabel('Topes respecto al origen elegido, en mm. X hacia la derecha; Y hacia arriba.')
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
        self._origin=[0.0,0.0]
        self.update_origin()
        self.origin_combo.currentIndexChanged.connect(lambda _: self.update_origin())
        self.profile_combo.textActivated.connect(lambda name: self.load_profile(name))
        self.profile_combo.editTextChanged.connect(lambda name: self.default_check.setChecked(name.strip()==self.profiles['default']))
        for name,values in self.profiles['profiles'].items():
            if values==settings:
                self.profile_combo.setCurrentText(name)
                break
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Aplicar')
        buttons.button(QDialogButtonBox.Cancel).setText('Cancelar')
        buttons.accepted.connect(lambda: self.save_and_accept());buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def load_profile(self, name):
        settings=self.profiles['profiles'].get(name)
        if settings is None:
            return
        index=self.origin_combo.findData(settings['origin'])
        if index < 0:
            QMessageBox.warning(self,'Máquina','El origen de este perfil no corresponde a una esquina.')
            return
        self.origin_combo.setCurrentIndex(index)
        for fields,pin in zip(self.fields,settings['pins']):
            for axis,field in enumerate(fields):
                field.setValue(pin[axis]-settings['origin'][axis])

    def save_and_accept(self):
        name=self.profile_combo.currentText().strip()
        if self.default_check.isChecked() and not name:
            QMessageBox.warning(self,'Máquina','Escribe un nombre para la máquina predeterminada.')
            return
        if name:
            if self.profile_error:
                QMessageBox.warning(self,'Máquinas',self.profile_error)
                return
            import copy
            data=copy.deepcopy(self.profiles)
            data['profiles'][name]=self.settings()
            if self.default_check.isChecked():
                data['default']=name
            elif data['default']==name:
                data['default']=None
            try:
                self.profile_store.write(data)
            except (ValueError,TypeError,OSError) as exc:
                QMessageBox.warning(self,'Máquinas',str(exc))
                return
        self.accept()
    def settings(self):
        positions=[[field.value() for field in pair] for pair in self.fields]
        origin=self.origin_combo.currentData()
        return {'pins':[[round(p[a]+origin[a],3) for a in (0,1)] for p in positions],'origin':origin}

    def update_origin(self, *_):
        origin=self.origin_combo.currentData()
        for pair in self.fields:
            for axis,field in enumerate(pair):
                physical=field.value()+self._origin[axis]
                field.setRange(-origin[axis],WORK_AREA_SIZE-origin[axis])
                field.setValue(physical-origin[axis])
        self._origin=list(origin)
