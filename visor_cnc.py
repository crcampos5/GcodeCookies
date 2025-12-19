import sys
import ezdxf
from ezdxf import path  # Herramienta poderosa para convertir curvas en rutas
from PySide6.QtWidgets import (QApplication, QMainWindow, QGraphicsScene, 
                               QGraphicsView, QFileDialog, QVBoxLayout, 
                               QWidget, QPushButton, QMessageBox)
from PySide6.QtGui import QPen, QColor, QPainter
from PySide6.QtCore import Qt

class VisorDXF(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Visor DXF para Galletas - v0.1")
        self.resize(800, 600)

        # 1. Configuración de la Interfaz (Layout)
        widget_central = QWidget()
        layout = QVBoxLayout(widget_central)
        
        # Botón para cargar
        self.btn_cargar = QPushButton("Cargar Archivo DXF")
        self.btn_cargar.clicked.connect(self.abrir_archivo)
        layout.addWidget(self.btn_cargar)

        # Lienzo (Scene y View)
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        
        # Configuraciones de renderizado para mejor calidad
        self.view.setRenderHint(QPainter.Antialiasing)
        
        # IMPORTANTE: Invertir eje Y. 
        # En computación (0,0) es arriba-izq. En CAD (0,0) es abajo-izq.
        self.view.scale(1, -1) 
        
        layout.addWidget(self.view)
        self.setCentralWidget(widget_central)

    def abrir_archivo(self):
        # Diálogo para seleccionar archivo
        archivo, _ = QFileDialog.getOpenFileName(self, "Abrir DXF", "", "Archivos DXF (*.dxf)")
        
        if archivo:
            self.procesar_dxf(archivo)

    def procesar_dxf(self, ruta_archivo):
        try:
            # Limpiar la escena anterior
            self.scene.clear()
            
            # Leer el DXF con ezdxf
            doc = ezdxf.readfile(ruta_archivo)
            msp = doc.modelspace()
            
            # Definir estilo de línea (Azul, grosor delgado para precisión)
            pen = QPen(QColor(0, 120, 255))
            pen.setWidth(0) # 0 = 'Cosmetic pen', siempre se ve de 1px sin importar el zoom
            
            contador_elementos = 0

            # Iterar sobre las entidades
            # Usamos ezdxf.path para unificar líneas, arcos y splines en una sola lógica
            for entity in msp:
                try:
                    # Convertir entidad a un "Path" (camino de puntos)
                    p = path.make_path(entity)
                    
                    # Convertir ese Path en líneas simples para Qt
                    # 'flattening' convierte curvas en pequeños segmentos rectos
                    vertices = list(p.flattening(distance=0.1)) 
                    
                    if len(vertices) > 1:
                        for i in range(len(vertices) - 1):
                            p1 = vertices[i]
                            p2 = vertices[i+1]
                            # Agregar línea a la escena (x1, y1, x2, y2)
                            self.scene.addLine(p1.x, p1.y, p2.x, p2.y, pen)
                        contador_elementos += 1
                        
                except Exception:
                    # Ignorar entidades que no son geometría dibujable (como texto o cotas complejas)
                    pass

            # Ajustar la cámara para ver todo el dibujo
            self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            
            # Feedback al usuario
            print(f"Dibujados {contador_elementos} elementos.")

        except IOError:
            QMessageBox.critical(self, "Error", "No se pudo leer el archivo.")
        except ezdxf.DXFStructureError:
             QMessageBox.critical(self, "Error", "Archivo DXF inválido o corrupto.")

# Punto de entrada de la aplicación
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = VisorDXF()
    ventana.show()
    sys.exit(app.exec())