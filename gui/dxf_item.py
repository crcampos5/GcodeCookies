"""
gui/dxf_item.py
Clase que encapsula un archivo DXF importado.
Maneja su propia geometría, selección y cambio de color.
CORREGIDO: Uso de QStyle.State_Selected para PySide6.
"""
from PySide6.QtWidgets import QGraphicsPathItem, QStyleOptionGraphicsItem, QStyle
from PySide6.QtGui import QPen, QColor, QPainterPath
from PySide6.QtCore import Qt

class DXFGraphicsItem(QGraphicsPathItem):
    def __init__(self, paths_list):
        super().__init__()
        
        # 1. Construir un "Path" unificado con todas las líneas del DXF
        self.path_container = QPainterPath()
        for vertices in paths_list:
            if len(vertices) < 2: continue
            self.path_container.moveTo(vertices[0].x, vertices[0].y)
            for i in range(1, len(vertices)):
                self.path_container.lineTo(vertices[i].x, vertices[i].y)
        
        self.setPath(self.path_container)
        
        # 2. Habilitar interacción
        # ItemIsSelectable: Permite seleccionarlo con clic
        # ItemIsMovable: Permite arrastrarlo directamente (opcional)
        # ItemSendsGeometryChanges: Avisa si se mueve para actualizar spinboxes
        self.setFlags(
            QGraphicsPathItem.ItemIsSelectable | 
            QGraphicsPathItem.ItemIsMovable |
            QGraphicsPathItem.ItemSendsGeometryChanges
        )
        
        # 3. Estilos de Línea
        # Normal: Negro
        self.pen_normal = QPen(QColor(0, 0, 0))
        self.pen_normal.setWidth(0.5) # Cosmetic (siempre fino)
        
        # Seleccionado: Azul Claro (Cyan)
        self.pen_selected = QPen(QColor(0, 200, 255)) 
        self.pen_selected.setWidth(0.5) # Un poco más grueso para destacar
        
        self.setPen(self.pen_normal)

    def paint(self, painter, option, widget=None):
        """
        Sobreescribimos el pintado para cambiar el lápiz según el estado.
        """
        # CORRECCIÓN AQUÍ: Usamos QStyle.State_Selected en lugar de QStyleOptionGraphicsItem.State_Selected
        if option.state & QStyle.State_Selected:
            self.setPen(self.pen_selected)
        else:
            self.setPen(self.pen_normal)
            
        super().paint(painter, option, widget)

    def itemChange(self, change, value):
        """
        Detecta cambios de estado (como selección) para forzar repintado inmediato.
        """
        if change == QGraphicsPathItem.ItemSelectedChange:
            # Forzar actualización visual al seleccionar/deseleccionar
            pass 
        return super().itemChange(change, value)