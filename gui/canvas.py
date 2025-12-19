"""
gui/canvas.py
Lienzo con soporte para múltiples objetos DXF y PUNTILLAS DE REFERENCIA.
"""
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import (QPen, QColor, QPainter, QFont, QTransform, 
                           QWheelEvent, QMouseEvent, QCursor, QBrush) # <--- Agregado QBrush
from PySide6.QtCore import Qt, QPoint, Signal

# Importamos la clase de objeto gráfico
from gui.dxf_item import DXFGraphicsItem

class ViewerCanvas(QGraphicsView):
    # Señal que emite el objeto seleccionado (o None)
    item_selected = Signal(object)

    def __init__(self):
        super().__init__()
        
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # --- Configuración Visual ---
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(255, 255, 255))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # --- Navegación ---
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag) # Manual

        # Variables Paneo
        self._panning = False
        self._last_mouse_pos = QPoint()

        # Área de trabajo
        self.work_area_size = 200 
        self.setSceneRect(-30, -10, self.work_area_size + 50, self.work_area_size + 10)

        self.first_show = True
        
        # --- DIBUJO DE ELEMENTOS DE FONDO ---
        self.draw_grid()
        self.draw_pins() # <--- Dibujamos las puntillas fijas
        
        self.scale(1, -1)

        # CONECTAR SELECCIÓN
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def draw_pins(self):
        """
        Dibuja las guías físicas (puntillas) donde se encaja la galleta.
        Son elementos visuales fijos (no seleccionables).
        """
        diameter = 3.175
        radius = diameter / 2
        
        # Coordenadas de los centros solicitados
        pin_positions = [(85, 95), (150, 95)]
        
        # Estilo: Relleno verde, sin borde
        brush = QBrush(QColor(0, 200, 50)) 
        pen = QPen(Qt.NoPen)
        
        for center_x, center_y in pin_positions:
            # addEllipse recibe (x_esquina, y_esquina, ancho, alto)
            # Restamos el radio para que la coordenada sea el CENTRO del círculo
            self.scene.addEllipse(
                center_x - radius, 
                center_y - radius, 
                diameter, 
                diameter, 
                pen, 
                brush
            )

    def add_dxf_object(self, paths_list):
        """Crea un nuevo DXFGraphicsItem y lo suma a la escena"""
        item = DXFGraphicsItem(paths_list)
        self.scene.addItem(item)
        
        # Seleccionar automáticamente el nuevo objeto
        self.scene.clearSelection()
        item.setSelected(True)

    def on_selection_changed(self):
        """Avisa a la ventana principal qué objeto se seleccionó"""
        items = self.scene.selectedItems()
        if items:
            self.item_selected.emit(items[0])
        else:
            self.item_selected.emit(None)

    # --- Eventos ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.first_show:
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
            if self.transform().m22() > 0: self.scale(1, -1)
            self.first_show = False

    def wheelEvent(self, event: QWheelEvent):
        zoom = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        self.scale(zoom, zoom)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            # Forzamos actualización del panel al soltar el objeto tras arrastrarlo
            self.on_selection_changed()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def draw_grid(self):
        color_fine = QColor(240, 240, 240)
        color_main = QColor(200, 200, 200)
        color_axis = QColor(100, 100, 100)
        
        pen_fine = QPen(color_fine); pen_fine.setWidth(0)
        pen_main = QPen(color_main); pen_main.setWidth(0)
        rect_pen = QPen(color_axis); rect_pen.setWidth(1)

        self.scene.addRect(0, 0, self.work_area_size, self.work_area_size, rect_pen)

        font = QFont("Arial", 4)
        text_transform = QTransform().scale(1, -1)
        step = 10 
        
        for i in range(0, self.work_area_size + 1, step):
            is_main = (i % 50 == 0)
            current_pen = pen_main if is_main else pen_fine
            
            self.scene.addLine(i, 0, i, self.work_area_size, current_pen)
            self.scene.addLine(0, i, self.work_area_size, i, current_pen)

            if is_main:
                text_x = self.scene.addText(str(i), font)
                text_x.setTransform(text_transform)
                text_x.setPos(i - 10, 0)
                text_x.setDefaultTextColor(QColor(80, 80, 80))

                if i > 0:
                    text_y = self.scene.addText(str(i), font)
                    text_y.setTransform(text_transform)
                    text_y.setPos(-15, i + 5)
                    text_y.setDefaultTextColor(QColor(80, 80, 80))