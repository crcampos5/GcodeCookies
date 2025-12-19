import json
from PySide6.QtCore import QPointF

class GCodeGenerator:
    def __init__(self):
        # Aquí guardaremos las operaciones agregadas
        # Cada operación será un dict: { 'type': 'line'/'fill', 'injector': 1, 'color': '#RRGGBB', 'polygons': [] }
        self.operations = []
        self.z_safe = 5.0
        self.z_print = 0.0 # Ajustado a 0.0 según tu ejemplo, bajando a -1.0
        self.design_name = "SinTitulo"

    def add_operation(self, polygons, op_type, injector_id, color_hex):
        """Agrega una operación a la cola sin generar el texto final todavía."""
        op = {
            "type": op_type, # "line" o "fill"
            "injector": int(injector_id),
            "color": color_hex,
            "polygons": polygons
        }
        self.operations.append(op)

    def clear_operations(self):
        self.operations = []

    def _calculate_center(self):
        """Calcula el centro aproximado de todas las geometrías."""
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')
        
        has_points = False
        for op in self.operations:
            for poly in op['polygons']:
                points = list(poly)
                for p in points:
                    has_points = True
                    if p.x() < min_x: min_x = p.x()
                    if p.x() > max_x: max_x = p.x()
                    if p.y() < min_y: min_y = p.y()
                    if p.y() > max_y: max_y = p.y()
        
        if not has_points:
            return [0, 0]
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        return [round(center_x, 2), round(center_y, 2)]

    def generate_full_code(self):
        """Construye el string completo con formato .cgc"""
        if not self.operations:
            return "; No hay operaciones definidas."

        gcode = []
        
        # --- 1. HEADER (JSON format) ---
        center = self._calculate_center()
        header_data = {
            "version": "1.0",
            "design_name": self.design_name,
            "total_colors": len(self.operations), # Simplificado: cuenta operaciones
            "way_travel": "todo",
            "centro": center
        }
        
        gcode.append("; --- HEADER START ---")
        # Convertimos el dict a JSON string bonito e indentado
        json_lines = json.dumps(header_data, indent=2).split('\n')
        for line in json_lines:
            gcode.append(f"; {line}")
        gcode.append("; --- HEADER END ---")
        
        # --- 2. DEFINITIONS ---
        gcode.append("; --- DEFINITIONS ---")
        # Recorremos operaciones para definir los inyectores usados
        # Nota: Si usas el mismo inyector varias veces, aquí podrías filtrarlos para no repetir DEFINE
        for i, op in enumerate(self.operations):
            op_id = op['injector']
            # Nombre basado en tipo (Borde/Relleno) y ID
            name = f"{'Borde' if op['type'] == 'line' else 'Relleno'} Inj{op_id}"
            line_def = f'; DEFINE_INJECTOR ID={op_id} COLOR="{op["color"]}" NAME="{name}" NOZZLE="2.0mm"'
            gcode.append(line_def)

        # --- 3. BODY ---
        gcode.append("; --- BODY ---")
        
        for op in self.operations:
            inj_id = op['injector']
            polys = op['polygons']
            
            # Cambio de inyector
            gcode.append(f"; CHANGE_INJECTOR ID={inj_id}")
            
            # Iniciar secuencia de impresión
            # Asumimos que T(n-1) es el comando para cambiar herramienta físicamente
            gcode.append(f"T{inj_id - 1}") 
            gcode.append(f"G0 Z{self.z_safe:.3f}")

            feed_rate = 889.0 if op['type'] == 'line' else 1016.0 # Velocidades ejemplo
            
            for poly in polys:
                points = list(poly)
                if not points: continue
                
                start = points[0]
                # Viaje rápido al inicio
                gcode.append(f"G0 X{start.x():.3f} Y{start.y():.3f} Z{self.z_print:.3f}")
                
                # Bajar a profundidad de trabajo (ej: -1.0mm como en tu archivo)
                gcode.append(f"G1 Z-1.000 F254.0")
                
                # Recorrer puntos
                for p in points[1:]:
                    gcode.append(f"G1 X{p.x():.3f} Y{p.y():.3f} F{feed_rate:.1f}")
                
                # Levantar al terminar el polígono
                gcode.append(f"G0 Z{self.z_safe:.3f}")

        gcode.append("M30 ; Fin del programa")
        
        return "\n".join(gcode)