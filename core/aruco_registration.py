"""Read a single Corel ArUco layer. All coordinates remain DXF millimetres, Y up."""
import math
import re
from ezdxf import path

DICTIONARY = 'DICT_4X4_50'


def read_registration(doc):
    layers = [layer.dxf.name for layer in doc.layers
              if layer.dxf.name.upper().startswith('ARUCO')]
    if not layers:
        return None
    if len(layers) != 1 or not re.fullmatch(r'ARUCO_(?:[0-9]|[1-4][0-9])', layers[0]):
        raise ValueError('Usa una sola capa ARUCO_0 a ARUCO_49, con un marcador DICT_4X4_50.')
    if doc.units != 4:
        raise ValueError('El DXF con ArUco debe declarar milímetros. Exporta de Corel usando mm.')
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise ValueError('Falta OpenCV para leer ArUco. Instala requirements-aruco.txt en el entorno virtual.') from exc
    if not hasattr(cv2, 'aruco') or not hasattr(cv2.aruco, 'ArucoDetector'):
        raise ValueError('Se necesita OpenCV 4.7 o posterior con ArUco.')
    layer = layers[0]
    expected_id = int(layer.split('_')[1])
    entities = [e for e in doc.modelspace() if e.dxf.layer == layer]
    if not entities or any(e.dxftype() not in ('SPLINE','LWPOLYLINE','POLYLINE','HATCH') for e in entities):
        raise ValueError('La capa ArUco debe contener únicamente contornos y rellenos vectoriales del SVG.')
    shapes = []
    candidates = []
    for entity in entities:
        if entity.dxftype() != 'HATCH':
            continue  # Corel also exports duplicate contour entities.
        color = entity.dxf.get('true_color', None)
        if not entity.dxf.solid_fill or color not in (0, 0xFFFFFF):
            raise ValueError('El ArUco debe conservar sus rellenos sólidos negros y blancos.')
        boundaries = list(path.from_hatch(entity))
        if len(boundaries) != 1:
            raise ValueError('Relleno ArUco no compatible: conserva el SVG original de la prueba.')
        vertices = [(p.x, p.y) for p in boundaries[0].flattening(distance=0.0005)]
        pts = np.asarray(vertices, dtype=float)
        if len(pts) < 4 or not np.isfinite(pts).all():
            raise ValueError('El ArUco contiene geometría inválida.')
        if np.linalg.norm(pts[0]-pts[-1]) > 0.001:
            raise ValueError('El ArUco contiene un relleno abierto.')
        shapes.append({'points': pts.tolist(), 'color': '#000000' if color == 0 else '#FFFFFF'})
        if color == 0:
            # Simplify only collinear export vertices; never square a deformed marker.
            contour = cv2.approxPolyDP(pts.astype(np.float32), 0.001, True).reshape(-1, 2).astype(float)
            if len(contour) == 4:
                candidates.append(contour)
    if len(candidates) != 1:
        raise ValueError('Se requiere un único marcador, con su cuadrado negro exterior completo.')
    outer = candidates[0]
    edges = np.roll(outer, -1, axis=0)-outer
    lengths = np.linalg.norm(edges, axis=1)
    side = float(lengths.mean())
    if not 1 <= side <= 100 or max(abs(lengths-side)) > side*0.002:
        raise ValueError('El ArUco está deformado o su tamaño no es válido; no estires el SVG.')
    if max(abs(np.sum(edges*np.roll(edges,-1,axis=0),axis=1))) > side*side*0.002:
        raise ValueError('El ArUco no es cuadrado; no inclines ni deformes el SVG.')
    points = np.vstack([s['points'] for s in shapes])
    lo, hi = points.min(axis=0), points.max(axis=0)
    if max(hi-lo) > side*1.5:
        raise ValueError('Hay geometría adicional fuera del marcador en la capa ArUco.')
    scale, margin = 900/side, 150
    width,height = np.ceil((hi-lo)*scale).astype(int)+2*margin+1
    image = np.full((height,width),255,np.uint8)
    for shape in shapes:
        pts = np.asarray(shape['points'])
        pixels = np.column_stack(((pts[:,0]-lo[0])*scale+margin,(hi[1]-pts[:,1])*scale+margin))
        cv2.fillPoly(image,[np.rint(pixels).astype(np.int32)],0 if shape['color']=='#000000' else 255)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    corners, ids, _ = cv2.aruco.ArucoDetector(dictionary).detectMarkers(image)
    if ids is None or len(ids) != 1 or int(ids[0,0]) != expected_id:
        raise ValueError(f'El patrón no corresponde a un único ArUco {expected_id} de {DICTIONARY}.')
    pixels = corners[0][0]
    detected = np.column_stack(((pixels[:,0]-margin)/scale+lo[0],hi[1]-(pixels[:,1]-margin)/scale))
    # Use exact DXF geometry, with corner identities supplied by the decoder.
    indices = [int(np.argmin(np.linalg.norm(outer-p,axis=1))) for p in detected]
    if len(set(indices)) != 4 or any(np.linalg.norm(outer[j]-p)>side*0.02 for p,j in zip(detected,indices)):
        raise ValueError('No se pudieron identificar las cuatro esquinas del borde exterior.')
    ordered = outer[indices]
    expected = cv2.aruco.generateImageMarker(dictionary,expected_id,600)
    warp = cv2.getPerspectiveTransform(pixels.astype(np.float32),np.array([[0,0],[599,0],[599,599],[0,599]],np.float32))
    sampled = cv2.warpPerspective(image,warp,(600,600))
    if any((sampled[y,x]>127)!=(expected[y,x]>127) for y in range(25,600,50) for x in range(25,600,50)):
        raise ValueError('El patrón ArUco está alterado. Importa nuevamente el SVG original.')
    return dict(layer=layer, shapes=shapes, metadata=dict(
        schema_version='1.0', mode='aruco', model='rigid', units='mm',
        coordinate_frame='toolpath_xy', x_axis='right', y_axis='up',
        dictionary=DICTIONARY, id=expected_id, border_bits=1,
        side_mm=round(side,6), quiet_zone_mm=1.0,
        corners_design_mm=[[round(float(v),6) for v in p] for p in ordered],
        scale_limits=[1.0,1.0]))


def validate_metadata(data):
    """Fail closed at export, even if registration data is supplied programmatically."""
    try:
        if (data['schema_version']!='1.0' or data['mode']!='aruco' or data['model']!='rigid'
                or data['dictionary']!=DICTIONARY or type(data['id']) is not int
                or not 0<=data['id']<50 or data['units']!='mm'
                or data['coordinate_frame']!='toolpath_xy' or data['x_axis']!='right'
                or data['y_axis']!='up' or data['border_bits']!=1 or data['scale_limits']!=[1.0,1.0]):
            raise ValueError
        c=data['corners_design_mm']; side=data['side_mm']
        if len(c)!=4 or any(len(p)!=2 for p in c) or not all(math.isfinite(v) for p in c for v in p):
            raise ValueError
        if not math.isfinite(side) or not 1<=side<=100 or data['quiet_zone_mm']!=1.0:
            raise ValueError
        edges=[(c[(i+1)%4][0]-c[i][0],c[(i+1)%4][1]-c[i][1]) for i in range(4)]
        for i,(x,y) in enumerate(edges):
            nx,ny=edges[(i+1)%4]
            if abs(math.hypot(x,y)-side)>side*0.002 or abs(x*nx+y*ny)>side*side*0.002 or x*ny-y*nx>=0:
                raise ValueError
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        raise ValueError('La referencia ArUco no es válida. Importa nuevamente el DXF.') from exc
