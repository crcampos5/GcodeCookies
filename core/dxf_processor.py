import ezdxf
from ezdxf import path

class DXFReader:
    """
    Clase simplificada: Solo lee el archivo y devuelve la lista de puntos.
    Ya no guarda estado ni transforma matrices, eso lo hará la GUI.
    """
    def read(self, filename):
        paths_found = []
        try:
            doc = ezdxf.readfile(filename)
            msp = doc.modelspace()
            
            for entity in msp:
                try:
                    p = path.make_path(entity)
                    # distance=0.1 es la calidad de curva
                    vertices = list(p.flattening(distance=0.1))
                    if len(vertices) > 1:
                        paths_found.append(vertices)
                except Exception:
                    continue
            return paths_found
            
        except (IOError, ezdxf.DXFStructureError):
            return None