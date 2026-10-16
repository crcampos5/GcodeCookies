import math
from PySide6.QtCore import QPointF

class TransformManager:
    """
    Gestiona la transformación (movimiento, escala, rotación).
    CORREGIDO: Recalcula el centro dinámicamente para evitar rotar sobre 0,0
    si los objetos fueron movidos.
    """
    def __init__(self):
        self.selected_items = []
        
        # Referencias para calcular cambios relativos (deltas)
        self.ref_rotation = 0.0
        self.ref_scale = 1.0

    def set_selection(self, items):
        """Establece los items a transformar."""
        self.selected_items = items
        
        if not items:
            return

        # Tomamos al primer ítem como referencia para los valores del panel
        self.ref_rotation = items[0].rotation()
        self.ref_scale = items[0].scale()
        # NOTA: Ya no calculamos el centro aquí para evitar que se vuelva obsoleto.

    def apply(self, x, y, scale, rotation):
        """
        Aplica los cambios recibidos del panel de control.
        """
        if not self.selected_items:
            return

        # --- MODO INDIVIDUAL ---
        if len(self.selected_items) == 1:
            item = self.selected_items[0]
            item.setPos(x, y)
            item.setScale(scale)
            item.setRotation(rotation)
            
            # Actualizamos referencias
            self.ref_rotation = rotation
            self.ref_scale = scale

        # --- MODO GRUPAL ---
        else:
            # 1. Calcular DELTAS (Diferencia entre valor nuevo y anterior)
            prev_scale = self.ref_scale if self.ref_scale != 0 else 0.0001
            
            delta_scale = scale / prev_scale
            delta_rotation = rotation - self.ref_rotation

            # 2. Si no hay cambios reales, salir
            if delta_scale == 1.0 and delta_rotation == 0:
                return

            # 3. OBTENER CENTRO ACTUAL (CRUCIAL)
            # Recalculamos el centro justo ahora. Si moviste los objetos, esto 
            # asegura que el pivote sea el correcto y no el (0,0).
            group_center = self._get_current_group_center()

            # 4. Aplicar transformación orbital usando ese centro
            self._apply_group_transform(delta_scale, delta_rotation, group_center)

            # 5. Actualizar referencias
            self.ref_scale = scale
            self.ref_rotation = rotation

    def _get_current_group_center(self):
        """Calcula el centro del rectángulo que envuelve a toda la selección actual."""
        if not self.selected_items: 
            return QPointF(0,0)
        
        # Unimos los bounding rects de todos los items en coordenadas de escena
        total_rect = self.selected_items[0].sceneBoundingRect()
        for item in self.selected_items[1:]:
            total_rect = total_rect.united(item.sceneBoundingRect())
        
        return total_rect.center()

    def _apply_group_transform(self, delta_scale, delta_rotation, center):
        """
        Aplica rotación y escala relativas al centro dado (Orbital).
        """
        cx = center.x()
        cy = center.y()
        
        # Pre-cálculo trigonométrico
        rad_angle = math.radians(delta_rotation)
        cos_a = math.cos(rad_angle)
        sin_a = math.sin(rad_angle)

        for item in self.selected_items:
            # Vector desde el centro del grupo al objeto
            vx = item.x() - cx
            vy = item.y() - cy

            # --- ESCALADO ---
            if delta_scale != 1.0:
                vx *= delta_scale
                vy *= delta_scale
                item.setScale(item.scale() * delta_scale)

            # --- ROTACIÓN (Orbital) ---
            if delta_rotation != 0.0:
                # Rotamos el vector de posición
                rx = vx * cos_a - vy * sin_a
                ry = vx * sin_a + vy * cos_a
                
                # Actualizamos vectores
                vx = rx
                vy = ry
                
                # Rotamos también el objeto sobre su propio eje
                item.setRotation(item.rotation() + delta_rotation)

            # Movemos el objeto a la nueva posición orbital
            item.setPos(cx + vx, cy + vy)