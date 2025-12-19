"""
gui/dxf_item.py
Clase que encapsula un archivo DXF importado.
Maneja su propia geometría, selección y cambio de color.
MODIFICADO: La geometría se centra en (0,0) local para que la rotación/escala
sea desde el centro, y la posición corresponda al centro en la grilla.
"""
from PySide6.QtWidgets import QGraphicsPathItem, QStyle
from PySide6.QtGui import QPen, QColor, QPainterPath
from PySide6.QtCore import Qt

class DXFGraphicsItem(QGraphicsPathItem):
    def __init__(self, paths_list):
        super().__init__()
        
        # 1. Construir un "Path" unificado con todas las líneas del DXF
        raw_path = QPainterPath()
        for vertices in paths_list:
            if len(vertices) < 2: continue
            raw_path.moveTo(vertices[0].x, vertices[0].y)
            for i in range(1, len(vertices)):
                raw_path.lineTo(vertices[i].x, vertices[i].y)
        
        # 2. CENTRAR GEOMETRÍA (Lógica clave para rotación/escala correcta)
        # Obtenemos el rectángulo que encierra todo el dibujo original
        bbox = raw_path.boundingRect()
        center = bbox.center() # Este es el punto medio original (ej: 50, 50)
        
        # Desplazamos el dibujo para que su centro quede en (0,0) local
        # Al hacer esto, el punto de pivote natural (0,0) coincide con el centro visual
        raw_path.translate(-center.x(), -center.y())
        
        self.setPath(raw_path)
        
        # 3. Posicionar el ítem en la escena
        # Para que el dibujo no "salte" visualmente al cargarlo, movemos 
        # el ítem entero a donde estaba su centro original.
        self.setPos(center.x(), center.y())
        
        # 4. Habilitar interacción
        self.setFlags(
            QGraphicsPathItem.ItemIsSelectable | 
            QGraphicsPathItem.ItemIsMovable |
            QGraphicsPathItem.ItemSendsGeometryChanges
        )
        
        # 5. Estilos de Línea
        self.pen_normal = QPen(QColor(0, 0, 0))
        self.pen_normal.setWidth(0) # 0 = Cosmetic (siempre nítido, no engrosa al hacer zoom)
        
        self.pen_selected = QPen(QColor(0, 200, 255)) 
        self.pen_selected.setWidth(0) # Mantenemos estilo fino para precisión
        
        self.setPen(self.pen_normal)

    def paint(self, painter, option, widget=None):
        """
        Sobreescribimos el pintado para cambiar el lápiz según el estado.
        """
        # Usamos QStyle.State_Selected para detectar selección en PySide6
        if option.state & QStyle.State_Selected:
            self.setPen(self.pen_selected)
            # Opcional: dibujar un pequeño punto en el centro para referencia visual
            painter.setPen(QPen(QColor(255, 0, 0), 0))
            painter.drawPoint(0, 0)
        else:
            self.setPen(self.pen_normal)
            
        super().paint(painter, option, widget)

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.ItemSelectedChange:
            pass 
        return super().itemChange(change, value)