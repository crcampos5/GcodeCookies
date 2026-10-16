"""Static CGC viewer. OpenGL and NumPy are imported only when this widget is created."""
import math
import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QVector3D
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QComboBox
import pyqtgraph.opengl as gl
from OpenGL import GL
from core.cgc_view_parser import parse_cgc_view


class Gcode3DViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self.items = []
        self.center = (0,0,0)
        self.span = 100
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        bar = QHBoxLayout()
        self.filter = QComboBox()
        self.filter.setMinimumContentsLength(12)
        self.filter.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.filter.addItem('Todas las operaciones', -1)
        bar.addWidget(self.filter, 1)
        top = QPushButton('Superior')
        iso = QPushButton('Isométrica')
        fit = QPushButton('Ajustar')
        for button in (top,iso,fit): bar.addWidget(button)
        layout.addLayout(bar)
        options = QHBoxLayout()
        self.show_travels = QCheckBox('Traslados, subidas y bajadas')
        self.show_travels.setChecked(True)
        self.show_scan = QCheckBox('Puntos de escaneo')
        self.show_scan.setChecked(True)
        options.addWidget(self.show_travels);options.addWidget(self.show_scan);options.addStretch()
        layout.addLayout(options)
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor('#747b84')
        layout.addWidget(self.view,1)
        self.status = QLabel('Genera un CGC para visualizarlo.')
        self.status.setWordWrap(True);layout.addWidget(self.status)
        note = QLabel('Z ficticio: dibujo 0 mm · retirada 10 mm. No son alturas de máquina. Izquierdo: girar · Central: desplazar · Rueda: zoom')
        note.setWordWrap(True);layout.addWidget(note)
        self.grid = gl.GLGridItem()
        self.grid.setColor((190,195,205,95))
        self.grid.translate(0,0,-0.01)  # Reference grid only; toolpaths and samples stay at Z=0.
        self.view.addItem(self.grid)
        self.filter.currentIndexChanged.connect(self.render_data)
        self.show_travels.toggled.connect(self.render_data)
        self.show_scan.toggled.connect(self.render_data)
        top.clicked.connect(lambda:self.set_view(90,-90))
        iso.clicked.connect(lambda:self.set_view(40,-60))
        fit.clicked.connect(self.fit)
        self.set_view(40,-60)
        QTimer.singleShot(600,self.check_context)

    def check_context(self):
        if self.isVisible() and not self.view.isValid():
            self.status.setText('No se pudo iniciar OpenGL. Revisa el controlador gráfico. Diseño y exportación siguen disponibles.')

    def clear(self, message='El diseño cambió. Genera el código de nuevo.'):
        self.data = None
        for item in self.items:self.view.removeItem(item)
        self.items.clear()
        self.filter.blockSignals(True);self.filter.clear();self.filter.addItem('Todas las operaciones',-1);self.filter.blockSignals(False)
        self.status.setText(message)

    def load_code(self, code):
        self.clear()
        if not code.strip():
            self.status.setText('Agrega operaciones y genera el código para ver sus trayectorias.')
            return
        try:
            self.data = parse_cgc_view(code)
        except ValueError as exc:
            self.status.setText(f'No se puede visualizar: {exc}')
            return
        self.filter.blockSignals(True)
        for i,op in enumerate(self.data.operations):
            self.filter.addItem(f'{i+1}. {op.name} · {op.kind} · Inyector {op.injector}',i)
        self.filter.blockSignals(False)
        self.render_data();self.fit()

    def render_data(self, *_):
        for item in self.items:self.view.removeItem(item)
        self.items.clear()
        if not self.data:return
        selected=self.filter.currentData()
        ops=self.data.operations if selected == -1 else [self.data.operations[selected]]
        points=[];count=0
        for op in ops:
            color=QColor(op.color);rgba=(color.redF(),color.greenF(),color.blueF(),1)
            if op.lines:
                item=gl.GLLinePlotItem(pos=np.asarray(op.lines,dtype=np.float32),color=rgba,width=2,mode='lines',antialias=True,glOptions='opaque')
                self.view.addItem(item);self.items.append(item);points.extend(op.lines);count+=len(op.lines)//2
            if self.show_travels.isChecked() and op.travels:
                item=gl.GLLinePlotItem(pos=np.asarray(op.travels,dtype=np.float32),color=(.85,.85,.85,1),width=1,mode='lines',glOptions='opaque')
                self.view.addItem(item);self.items.append(item);points.extend(op.travels)
            if self.show_scan.isChecked() and op.scan_points:
                item=gl.GLScatterPlotItem(pos=np.asarray(op.scan_points,dtype=np.float32),color=(1,.2,.75,1),size=10,pxMode=True)
                item.setGLOptions({GL.GL_DEPTH_TEST: False, GL.GL_BLEND: False})
                item.setDepthValue(10)
                self.view.addItem(item);self.items.append(item);points.extend(op.scan_points)
        if self.data.alignment:
            corners = [(*p,0.0) for p in self.data.alignment['corners_design_mm']]
            item = gl.GLLinePlotItem(pos=np.asarray(corners+[corners[0]],dtype=np.float32),
                                    color=(0,.8,1,1),width=3,mode='line_strip',glOptions='opaque')
            self.view.addItem(item);self.items.append(item);points.extend(corners)
            dot = gl.GLScatterPlotItem(pos=np.asarray([corners[0]],dtype=np.float32),color=(0,.8,1,1),size=9,pxMode=True)
            self.view.addItem(dot);self.items.append(dot)
        if points:
            array=np.asarray(points);low=array.min(axis=0);high=array.max(axis=0)
            self.center=tuple((low+high)/2);self.span=max(float(max(high-low)),1)
            self.grid.resetTransform();self.grid.translate(self.center[0],self.center[1],-.01)
            size=self.span*1.4;step=10**math.floor(math.log10(max(size/10,.001)))
            self.grid.setSize(x=size,y=size);self.grid.setSpacing(x=step,y=step)
        self.status.setText(f'{self.data.design_name} · {len(ops)} operaciones · {count} segmentos. Escaneo: puntos rosados.')
        if self.data.alignment:
            self.status.setText(self.status.text()+f' ArUco {self.data.alignment["id"]}: marco azul, referencia sin recorrido.')

    def fit(self):
        aspect=max(self.view.width(),1)/max(self.view.height(),1)
        distance=self.span*1.8*max(1,aspect)
        self.view.setCameraPosition(pos=QVector3D(*map(float,self.center)),distance=distance)

    def set_view(self,elevation,azimuth):
        self.view.setCameraPosition(elevation=elevation,azimuth=azimuth)
        self.fit()
