import ezdxf
from ezdxf import path

class DXFProcessor:
    def __init__(self):
        self.doc = None
        self.msp = None # Modelspace

    def load_file(self, filename):
        """Carga el archivo y prepara el espacio de modelo"""
        try:
            self.doc = ezdxf.readfile(filename)
            self.msp = self.doc.modelspace()
            return True
        except IOError:
            return False
        except ezdxf.DXFStructureError:
            return False

    def get_paths(self):
        """
        Itera sobre el DXF y devuelve una lista de 'caminos' (puntos conectados).
        Usa ezdxf.path para unificar líneas, arcos y splines.
        """
        if not self.msp:
            return []

        paths = []
        # Recorremos todas las entidades del dibujo
        for entity in self.msp:
            try:
                # Convertimos cualquier cosa (arco, linea, spline) a un Path
                p = path.make_path(entity)
                # Lo aplanamos (convertimos curvas en segmentos rectos pequeños)
                # distance=0.1 es la precisión (0.1mm)
                vertices = list(p.flattening(distance=0.1))
                if len(vertices) > 1:
                    paths.append(vertices)
            except Exception:
                # Ignoramos entidades no geométricas (texto, cotas complejas)
                continue
        
        return paths