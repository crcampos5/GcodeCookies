import ezdxf
from ezdxf import path
from ezdxf.math import Matrix44, Vec3

class DXFProcessor:
    def __init__(self):
        self.doc = None
        self.msp = None 
        # Aquí guardaremos la geometría actual para poder modificarla
        self.current_paths = [] 

    def load_file(self, filename):
        """Carga el archivo, procesa la geometría y la guarda en memoria"""
        try:
            self.doc = ezdxf.readfile(filename)
            self.msp = self.doc.modelspace()
            self._extract_paths() # Procesar inmediatamente al cargar
            return True
        except IOError:
            return False
        except ezdxf.DXFStructureError:
            return False

    def _extract_paths(self):
        """Convierte las entidades DXF en listas de puntos (Vec3)"""
        self.current_paths = []
        if not self.msp:
            return

        for entity in self.msp:
            try:
                p = path.make_path(entity)
                # distance=0.1 es la resolución (calidad) de las curvas
                vertices = list(p.flattening(distance=0.1))
                if len(vertices) > 1:
                    self.current_paths.append(vertices)
            except Exception:
                continue

    def get_paths(self):
        return self.current_paths

    # --- FUNCIONES DE TRANSFORMACIÓN ---

    def move(self, dx, dy):
        """Mueve toda la geometría (Traslación)"""
        mat = Matrix44.translate(dx, dy, 0)
        self._apply_matrix(mat)

    def scale(self, factor):
        """Escala la geometría (1.0 = 100%, 0.5 = 50%, etc.)"""
        # Escalamos desde el origen (0,0)
        if factor == 0: return # Evitar destruir el dibujo
        mat = Matrix44.scale(factor, factor, 1)
        self._apply_matrix(mat)

    def rotate(self, angle_degrees):
        """Rota la geometría alrededor del centro del dibujo"""
        center = self._get_center()
        # 1. Mover al origen -> 2. Rotar -> 3. Volver a su sitio
        mat = Matrix44.chain(
            Matrix44.translate(-center.x, -center.y, 0),
            Matrix44.z_rotate(angle_degrees * 0.0174533), # Grados a Radianes
            Matrix44.translate(center.x, center.y, 0)
        )
        self._apply_matrix(mat)

    def _get_center(self):
        """Calcula el centro aproximado de todo el dibujo"""
        if not self.current_paths:
            return Vec3(0, 0, 0)
        
        # Promedio simple de todos los puntos (Centroide aproximado)
        total_x, total_y, count = 0, 0, 0
        for path_list in self.current_paths:
            for p in path_list:
                total_x += p.x
                total_y += p.y
                count += 1
        return Vec3(total_x/count, total_y/count, 0) if count > 0 else Vec3(0,0,0)

    def _apply_matrix(self, matrix):
        """Aplica una matriz de transformación a todos los puntos"""
        new_paths = []
        for path_list in self.current_paths:
            # transform_vertices devuelve un generador, lo convertimos a lista
            new_p = list(matrix.transform_vertices(path_list))
            new_paths.append(new_p)
        self.current_paths = new_paths