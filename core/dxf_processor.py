import ezdxf
from ezdxf import path
from core.aruco_registration import read_registration
import hashlib

class DXFReader:
    """
    Clase simplificada: Solo lee el archivo y devuelve la lista de puntos.
    Ya no guarda estado ni transforma matrices, eso lo hará la GUI.
    """
    def read(self, filename):
        self.registration = None
        paths_found = []
        try:
            doc = ezdxf.readfile(filename)
            msp = doc.modelspace()
            registration = read_registration(doc)
            if registration:
                with open(filename, 'rb') as source:
                    registration['metadata']['source_dxf_sha256'] = hashlib.sha256(source.read()).hexdigest()
            
            for entity in msp:
                if registration and entity.dxf.layer == registration['layer']:
                    continue
                try:
                    p = path.make_path(entity)
                    # distance=0.1 es la calidad de curva
                    vertices = list(p.flattening(distance=0.1))
                    if len(vertices) > 1:
                        paths_found.append(vertices)
                except Exception:
                    continue
            self.registration = registration
            return paths_found
            
        except (IOError, ezdxf.DXFStructureError):
            return None
