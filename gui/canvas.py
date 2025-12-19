from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QPen, QColor, QPainter
from PySide6.QtCore import Qt

class ViewerCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        
        # Crear la escena (el mundo infinito)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # Configuración visual
        self.setRenderHint(QPainter.Antialiasing) # Suavizar bordes
        self.scale(1, -1) # Invertir eje Y para coordenadas CAD correctas
        self.setBackgroundBrush(QColor(30, 30, 30)) # Fondo oscuro estilo CAD

        # Lápiz para dibujar
        self.pen = QPen(QColor(0, 255, 128)) # Verde brillante
        self.pen.setWidth(0) # 'Cosmetic pen': siempre delgado sin importar zoom

    def draw_geometry(self, paths_list):
        """Recibe una lista de listas de vértices y dibuja"""
        self.scene.clear()
        
        element_count = 0
        for vertices in paths_list:
            # Dibujar segmentos
            for i in range(len(vertices) - 1):
                p1 = vertices[i]
                p2 = vertices[i+1]
                self.scene.addLine(p1.x, p1.y, p2.x, p2.y, self.pen)
            element_count += 1
            
        # Ajustar cámara para ver todo
        self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        return element_count