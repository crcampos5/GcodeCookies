from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsTextItem, QGraphicsLineItem
from PySide6.QtGui import QPen, QColor, QPainter, QFont, QTransform
from PySide6.QtCore import Qt

class ViewerCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        
        # Crear la escena
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # --- 1. CONFIGURACIÓN VISUAL ---
        self.setRenderHint(QPainter.Antialiasing)
        self.scale(1, -1)  # Invertir Y (Coordenadas CAD)
        self.setBackgroundBrush(QColor(255, 255, 255)) # Fondo Blanco

        # Definir el tamaño de la "Cama" o Área de trabajo
        self.work_area_size = 200 # 200mm x 200mm
        
        # Ajustar la vista inicial con un margen para ver las reglas
        # (x, y, w, h) -> Le damos 20mm de margen a cada lado
        self.setSceneRect(-30, -30, self.work_area_size + 60, self.work_area_size + 60)

        # Lápiz para el dibujo del usuario (Ahora Negro para contraste)
        self.pen_geometry = QPen(QColor(0, 0, 0)) 
        self.pen_geometry.setWidth(1) # Grosor visual de 1px (Cosmetic)

        # Dibujar la grilla inicial
        self.draw_grid()

    def draw_grid(self):
        """Dibuja el área de trabajo, la cuadrícula y las reglas"""
        
        # Colores de la interfaz
        color_grid_fine = QColor(240, 240, 240)  # Gris muy claro (cada 10mm)
        color_grid_main = QColor(200, 200, 200)  # Gris claro (cada 50mm)
        color_axis = QColor(100, 100, 100)       # Gris oscuro (Borde)
        
        pen_fine = QPen(color_grid_fine)
        pen_fine.setWidth(0)
        
        pen_main = QPen(color_grid_main)
        pen_main.setWidth(0)

        # 1. Dibujar el recuadro del área de trabajo (0,0) a (200,200)
        # Usamos addRect(x, y, w, h, pen)
        rect_pen = QPen(color_axis)
        rect_pen.setWidth(2)
        # Nota: QRect se dibuja hacia abajo si h es positivo, pero como tenemos scale(1, -1),
        # el sistema de coordenadas es cartesiano.
        self.scene.addRect(0, 0, self.work_area_size, self.work_area_size, rect_pen)

        # 2. Dibujar líneas de cuadrícula y números
        font = QFont("Arial", 8)
        
        # Matriz para invertir el texto (ya que la vista está invertida)
        text_transform = QTransform().scale(1, -1)

        step = 10 # Cuadrícula cada 10mm
        
        for i in range(0, self.work_area_size + 1, step):
            # Determinar si es línea principal (cada 50mm) o secundaria
            is_main = (i % 50 == 0)
            current_pen = pen_main if is_main else pen_fine
            
            # --- Líneas Verticales (Eje X) ---
            self.scene.addLine(i, 0, i, self.work_area_size, current_pen)
            
            # --- Líneas Horizontales (Eje Y) ---
            self.scene.addLine(0, i, self.work_area_size, i, current_pen)

            # --- Números (Solo en líneas principales) ---
            if is_main:
                # Etiqueta X (Abajo del eje)
                text_x = self.scene.addText(str(i), font)
                text_x.setTransform(text_transform)
                # Ajustamos posición: x=i, y=-5 (un poco abajo del 0)
                # El offset visual depende del tamaño de fuente, ajustamos a ojo
                text_x.setPos(i - 10, -5) 
                text_x.setDefaultTextColor(QColor(80, 80, 80))

                # Etiqueta Y (Izquierda del eje)
                if i > 0: # Evitar superponer el 0,0
                    text_y = self.scene.addText(str(i), font)
                    text_y.setTransform(text_transform)
                    text_y.setPos(-25, i + 5)
                    text_y.setDefaultTextColor(QColor(80, 80, 80))

    def draw_geometry(self, paths_list):
        """Recibe geometría nueva, limpia la escena y redibuja todo"""
        self.scene.clear()
        
        # Importante: Volver a dibujar la grilla porque clear() la borró
        self.draw_grid()
        
        element_count = 0
        for vertices in paths_list:
            if len(vertices) < 2: continue
            
            # Dibujar segmentos
            # Opción rápida: Usar QPainterPath sería más eficiente, 
            # pero líneas individuales son fáciles de depurar.
            for i in range(len(vertices) - 1):
                p1 = vertices[i]
                p2 = vertices[i+1]
                self.scene.addLine(p1.x, p1.y, p2.x, p2.y, self.pen_geometry)
            element_count += 1
            
        return element_count