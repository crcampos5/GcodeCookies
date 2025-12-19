import math
from PySide6.QtCore import QPointF

class TransformManager:
    """
    Gestiona la transformación (movimiento, escala, rotación) de objetos individuales o grupos.
    Mantiene el estado del 'pivote' y calcula las transformaciones orbitales para grupos.
    """
    def __init__(self):
        self.selected_items = []
        self.group_center = QPointF(0, 0)
        
        # Referencias para calcular cambios relativos (deltas)
        # porque el panel de control nos envía valores absolutos.
        self.ref_rotation = 0.0
        self.ref_scale = 1.0

    def set_selection(self, items):
        """Establece los items a transformar y recalcula el centro del grupo."""
        self.selected_items = items
        
        if not items:
            return

        if len(items) > 1:
            self._calculate_group_center(items)
            # Tomamos al primer ítem (líder) como referencia para el panel
            self.ref_rotation = items[0].rotation()
            self.ref_scale = items[0].scale()
        else:
            # En modo individual, la referencia es el propio objeto
            self.ref_rotation = items[0].rotation()
            self.ref_scale = items[0].scale()

    def apply(self, x, y, scale, rotation):
        """
        Recibe los valores absolutos del panel y aplica la lógica correspondiente
        (Directa para 1 ítem, Orbital para grupos).
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
            # Evitamos división por cero con un valor mínimo
            prev_scale = self.ref_scale if self.ref_scale != 0 else 0.0001
            
            delta_scale = scale / prev_scale
            delta_rotation = rotation - self.ref_rotation

            # 2. Si no hay cambios reales, salir para ahorrar cómputo
            if delta_scale == 1.0 and delta_rotation == 0:
                return

            # 3. Aplicar transformación orbital
            self._apply_group_transform(delta_scale, delta_rotation)

            # 4. Actualizar referencias para el próximo ciclo
            self.ref_scale = scale
            self.ref_rotation = rotation

    def _calculate_group_center(self, items):
        """Calcula el centro del rectángulo que envuelve a todos los items."""
        if not items: return
        
        total_rect = items[0].sceneBoundingRect()
        for item in items[1:]:
            total_rect = total_rect.united(item.sceneBoundingRect())
        self.group_center = total_rect.center()

    def _apply_group_transform(self, delta_scale, delta_rotation):
        """Aplica matemática vectorial para rotar/escalar alrededor del pivote."""
        cx = self.group_center.x()
        cy = self.group_center.y()
        
        # Pre-cálculo trigonométrico
        rad_angle = math.radians(delta_rotation)
        cos_a = math.cos(rad_angle)
        sin_a = math.sin(rad_angle)

        for item in self.selected_items:
            # --- ESCALADO ---
            if delta_scale != 1.0:
                # Vector desde el centro al objeto
                vx = item.x() - cx
                vy = item.y() - cy
                
                # Escalamos el vector y movemos el objeto
                vx *= delta_scale
                vy *= delta_scale
                item.setPos(cx + vx, cy + vy)
                
                # Escalamos el objeto en sí
                item.setScale(item.scale() * delta_scale)

            # --- ROTACIÓN ---
            if delta_rotation != 0.0:
                vx = item.x() - cx
                vy = item.y() - cy
                
                # Rotación de vector 2D
                rx = vx * cos_a - vy * sin_a
                ry = vx * sin_a + vy * cos_a
                
                item.setPos(cx + rx, cy + ry)
                item.setRotation(item.rotation() + delta_rotation)