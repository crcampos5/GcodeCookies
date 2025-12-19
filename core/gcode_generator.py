import json
from PySide6.QtCore import QPointF

# Importamos Shapely
try:
    from shapely.geometry import Polygon, MultiPolygon
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

class GCodeGenerator:
    def __init__(self):
        self.operations = []
        self.z_safe = 5.0
        self.z_print = 0.0 
        self.design_name = "SinTitulo"
        
        # --- PARÁMETROS DE RELLENO ---
        self.fill_overlap = 0.1
        
        # Tolerancia MUY baja (0.05mm). 
        # Solo para limpiar el "ruido" matemático que genera el buffer, sin alterar la forma.
        self.simplification_tolerance = 0.05

    def add_operation(self, polygons, op_type, injector_id, color_hex, name, nozzle_size):
        op = {
            "type": op_type, 
            "injector": int(injector_id),
            "color": color_hex,
            "polygons": polygons, 
            "name": name,
            "nozzle": float(nozzle_size)
        }
        self.operations.append(op)

    def update_operation(self, index, op_type, injector_id, color_hex, name, nozzle_size):
        if 0 <= index < len(self.operations):
            op = self.operations[index]
            op['type'] = op_type
            op['injector'] = int(injector_id)
            op['color'] = color_hex
            op['name'] = name
            op['nozzle'] = float(nozzle_size)

    def delete_operation(self, index):
        if 0 <= index < len(self.operations):
            self.operations.pop(index)

    def clear_operations(self):
        self.operations = []

    def _calculate_center(self):
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')
        has_points = False
        
        for op in self.operations:
            for poly in op['polygons']:
                for p in poly:
                    has_points = True
                    if p.x() < min_x: min_x = p.x()
                    if p.x() > max_x: max_x = p.x()
                    if p.y() < min_y: min_y = p.y()
                    if p.y() > max_y: max_y = p.y()
        
        if not has_points: return [0, 0]
        return [round((min_x + max_x) / 2, 2), round((min_y + max_y) / 2, 2)]

    def _generate_concentric_fill(self, qpoints_list, nozzle_mm):
        """
        Genera caminos de relleno.
        La simplificación se aplica SOLO al resultado del buffer.
        """
        if not SHAPELY_AVAILABLE:
            return []

        fill_paths = []
        step = nozzle_mm * (1.0 - self.fill_overlap)

        # 1. Conversión
        coords = [(p.x(), p.y()) for p in qpoints_list]
        if len(coords) < 3: return []

        poly = Polygon(coords)
        if not poly.is_valid:
            poly = poly.buffer(0)
        
        # NOTA: Hemos quitado la simplificación aquí. 
        # El polígono original se respeta al 100%.

        # 2. Erosión Inicial (Inset)
        current_poly = poly.buffer(-nozzle_mm / 2)

        while not current_poly.is_empty:
            # APLICAMOS SIMPLIFICACIÓN SOLO AL BUFFER
            # Esto evita que las curvas offset tengan miles de micro-segmentos
            current_poly = current_poly.simplify(self.simplification_tolerance, preserve_topology=True)

            geoms = []
            if isinstance(current_poly, MultiPolygon):
                geoms = list(current_poly.geoms)
            else:
                geoms = [current_poly]

            for geom in geoms:
                if not geom.is_empty:
                    fill_paths.append(list(geom.exterior.coords))

            # Siguiente paso
            current_poly = current_poly.buffer(-step)
        
        return fill_paths
    
    def get_all_preview_paths(self):
        """
        Devuelve una lista de diccionarios con la geometría CALCULADA para visualizar.
        Estructura: [{'color': '#hex', 'paths': [[(x,y)...], ...]}, ...]
        """
        previews = []
        
        for op in self.operations:
            op_type = op['type']
            nozzle = op['nozzle']
            raw_polygons = op['polygons']
            color = op['color']
            
            calculated_paths = []

            if op_type == 'fill':
                if SHAPELY_AVAILABLE:
                    for poly in raw_polygons:
                        loops = self._generate_concentric_fill(poly, nozzle)
                        calculated_paths.extend(loops)
            else:
                # Si es borde, devolvemos el polígono original convertido a tuplas
                for poly in raw_polygons:
                    calculated_paths.append([(p.x(), p.y()) for p in poly])
            
            if calculated_paths:
                previews.append({
                    'color': color,
                    'paths': calculated_paths
                })
                
        return previews

    def generate_full_code(self):
        if not self.operations:
            return "; No hay operaciones definidas."

        gcode = []
        
        # --- HEADER ---
        center = self._calculate_center()
        header = {
            "version": "1.3",
            "design_name": self.design_name,
            "total_ops": len(self.operations),
            "center": center,
            "simplification": self.simplification_tolerance
        }
        gcode.append(f"; JSON_HEADER: {json.dumps(header)}")
        
        # --- DEFINITIONS ---
        gcode.append("; --- DEFINITIONS ---")
        for op in self.operations:
            op_name = op['name'] if op['name'] else f"{op['type'].upper()} {op['injector']}"
            gcode.append(f'; DEFINE_INJECTOR ID={op["injector"]} COLOR="{op["color"]}" NAME="{op_name}" NOZZLE="{op["nozzle"]}mm"')

        # --- BODY ---
        gcode.append("; --- BODY ---")
        
        for op in self.operations:
            inj_id = op['injector']
            op_type = op['type']
            nozzle = op['nozzle']
            raw_polygons = op['polygons']
            
            gcode.append(f"; --- OPERACION: {op['name']} ({op_type}) ---")
            gcode.append(f"T{inj_id - 1}") 
            gcode.append(f"G0 Z{self.z_safe:.3f}")

            paths_to_print = []

            if op_type == 'fill':
                if SHAPELY_AVAILABLE:
                    for poly_points in raw_polygons:
                        fill_loops = self._generate_concentric_fill(poly_points, nozzle)
                        paths_to_print.extend(fill_loops)
            else:
                # BORDES (LINE)
                # Aquí NO usamos simplificación de Shapely para respetar el DXF original,
                # a menos que el DXF venga muy sucio, pero por defecto lo dejamos puro.
                for poly_points in raw_polygons:
                    paths_to_print.append([(p.x(), p.y()) for p in poly_points])

            feed_rate = 800.0 if op_type == 'line' else 1000.0
            
            for path in paths_to_print:
                if not path: continue
                
                # Filtro de seguridad mínimo (0.05mm) para evitar puntos duplicados exactos
                clean_path = [path[0]]
                for i in range(1, len(path)):
                    prev = clean_path[-1]
                    curr = path[i]
                    dist_sq = (curr[0]-prev[0])**2 + (curr[1]-prev[1])**2
                    # 0.05^2 = 0.0025
                    if dist_sq > 0.0025: 
                        clean_path.append(curr)
                
                if len(clean_path) < 2: continue

                start = clean_path[0]
                gcode.append(f"G0 X{start[0]:.3f} Y{start[1]:.3f} Z{self.z_print:.3f}")
                gcode.append(f"G1 Z-1.000 F250.0")
                
                for p in clean_path[1:]:
                    gcode.append(f"G1 X{p[0]:.3f} Y{p[1]:.3f} F{feed_rate:.1f}")
                
                gcode.append(f"G0 Z{self.z_safe:.3f}")

        gcode.append("M30 ; Fin")
        
        return "\n".join(gcode)