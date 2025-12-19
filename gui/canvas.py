from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPathItem
from PySide6.QtGui import (QPen, QColor, QPainter, QFont, QTransform, 
                           QWheelEvent, QMouseEvent, QBrush, QPainterPath)
from PySide6.QtCore import Qt, QPoint, Signal
from gui.dxf_item import DXFGraphicsItem

class ViewerCanvas(QGraphicsView):
    items_selected = Signal(list)

    def __init__(self):
        super().__init__()
        
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(255, 255, 255))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)

        self._panning = False
        self._last_mouse_pos = QPoint()
        self.work_area_size = 200 
        self.setSceneRect(-30, -10, self.work_area_size + 50, self.work_area_size + 10)
        self.first_show = True
        
        self.draw_grid()
        self.draw_pins() 
        self.scale(1, -1)
        
        # --- Contenedor para las previsualizaciones ---
        self.preview_items = [] 

        self.scene.selectionChanged.connect(self.on_selection_changed)

    def draw_preview_paths(self, preview_data):
        """
        Recibe una lista de dicts: [{'color': '#...', 'paths': [[(x,y)...]]}, ...]
        Dibuja estas rutas encima de todo con líneas punteadas.
        """
        # 1. Limpiar previsualización anterior
        for item in self.preview_items:
            self.scene.removeItem(item)
        self.preview_items.clear()
        
        # 2. Dibujar nuevas rutas
        for op_data in preview_data:
            color_hex = op_data['color']
            paths_list = op_data['paths']
            
            # Configurar Lápiz: Punteado, del color de la operación
            pen = QPen(QColor(color_hex))
            pen.setWidth(0) # 'Cosmetic' (siempre fino)
            pen.setStyle(Qt.DotLine) # <--- LINEA PUNTEADA
            
            # Crear el camino gráfico
            painter_path = QPainterPath()
            
            for poly in paths_list:
                if not poly: continue
                painter_path.moveTo(poly[0][0], poly[0][1])
                for point in poly[1:]:
                    painter_path.lineTo(point[0], point[1])
            
            # Crear item y añadir a escena
            item = QGraphicsPathItem(painter_path)
            item.setPen(pen)
            item.setZValue(10) # Asegurar que se pinte ENCIMA del DXF original (Z=0)
            
            self.scene.addItem(item)
            self.preview_items.append(item)

    def draw_pins(self):
        diameter = 3.175
        radius = diameter / 2
        pin_positions = [(85, 95), (150, 95)]
        brush = QBrush(QColor(0, 200, 50)) 
        pen = QPen(Qt.NoPen)
        for cx, cy in pin_positions:
            self.scene.addEllipse(cx-radius, cy-radius, diameter, diameter, pen, brush)

    def add_dxf_object(self, paths_list):
        """
        Agrega los objetos del DXF a la escena.
        MODIFICADO: Se crea un DXFGraphicsItem independiente por cada camino (entidad)
        para permitir selección y manipulación individual.
        """
        self.scene.clearSelection()
        
        for single_path in paths_list:
            # DXFGraphicsItem espera una lista de caminos, así que pasamos una lista con un solo elemento.
            # Al crearse, cada ítem calculará su propio centro (bounding box) y se posicionará correctamente
            # en el espacio absoluto de la escena.
            item = DXFGraphicsItem([single_path])
            self.scene.addItem(item)
            
        # Nota: No seleccionamos nada automáticamente al cargar para no abrumar al usuario
        # si el archivo contiene muchas líneas sueltas.

    def on_selection_changed(self):
        items = self.scene.selectedItems()
        self.items_selected.emit(items)

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
            #self.on_selection_changed()

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