"""Generación CGC 1.0: operaciones físicas, geometría vigente y escaneo FILL."""
import json
import math
import re
import copy
from core.aruco_registration import validate_metadata
try:
    from shapely.geometry import Polygon, Point, LineString
    from shapely.ops import substring
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False


class GCodeGenerator:
    def __init__(self):
        self.operations = []
        self.design_name = 'SinTitulo'
        self.fill_overlap = 0.1
        self.simplification_tolerance = 0.05
        self.registration = None
        self.registration_geometry = {}

    @staticmethod
    def item_geometry(item):
        return tuple(tuple((p.x(), p.y()) for p in poly)
                     for poly in item.path().toSubpathPolygons(item.sceneTransform()))

    def alignment_warnings(self, blocks=None):
        if not self.registration or not self.operations:
            return []
        if not SHAPELY_AVAILABLE:
            return ['No se pudo comprobar si los recorridos cubren el ArUco.']
        zone = Polygon(self.registration['metadata']['corners_design_mm']).buffer(1.0, join_style=2)
        touched = []
        for op in self.operations:
            polygons = self._polygons(op)
            if op['type'] == 'fill':
                hit = any(r.intersects(zone) for r in self._fill_regions(polygons))
            else:
                hit = any(LineString(self._coords(p)).buffer(op['nozzle']/2).intersects(zone) for p in polygons)
            if hit:
                touched.append(op['name'])
        if touched:
            return ['Estas operaciones pueden cubrir el ArUco o su margen blanco: '+', '.join(touched)+
                    '. Ejecútalas después de la última comprobación de alineación.']
        return []

    def add_operation(self, polygons, op_type, injector_id, color_hex, name,
                      nozzle_size, material_name=None, source_item=None):
        self.operations.append(dict(type=op_type, injector=int(injector_id),
            color=color_hex, polygons=polygons, name=name, nozzle=float(nozzle_size),
            material_name=material_name or f'Royal icing {color_hex}', source_item=source_item))

    def update_operation(self, index, op_type, injector_id, color_hex, name,
                         nozzle_size, material_name=None):
        if 0 <= index < len(self.operations):
            self.operations[index].update(type=op_type, injector=int(injector_id),
                color=color_hex, name=name, nozzle=float(nozzle_size),
                material_name=material_name or f'Royal icing {color_hex}')

    def delete_operation(self, index):
        if 0 <= index < len(self.operations):
            self.operations.pop(index)

    def clear_operations(self):
        self.operations.clear()

    def _polygons(self, op):
        source = op.get('source_item')
        if source is not None:
            return list(source.path().toSubpathPolygons(source.sceneTransform()))
        return op['polygons']

    @staticmethod
    def _text(value, field):
        if not isinstance(value, str) or not value.strip() or any(c in value for c in '\r\n"'):
            raise ValueError(f'{field}: usa un texto no vacío, sin comillas ni saltos de línea.')
        return value.strip()

    @staticmethod
    def _coords(poly):
        coords = [(float(p.x()), float(p.y())) for p in poly]
        if any(not math.isfinite(v) for pair in coords for v in pair):
            raise ValueError('La geometría contiene coordenadas no finitas.')
        return coords

    @staticmethod
    def _clean_path(coords):
        result = []
        for x, y in coords:
            point = (round(x, 3), round(y, 3))
            if not result or point != result[-1]:
                result.append(point)
        if len(result) < 2:
            raise ValueError('El trazo no tiene longitud a la precisión de 0.001 mm.')
        return result

    def _calculate_center(self):
        coords = [p for op in self.operations for poly in self._polygons(op) for p in self._coords(poly)]
        if not coords:
            raise ValueError('No hay geometría para calcular el centro.')
        return [round((min(p[i] for p in coords)+max(p[i] for p in coords))/2, 3) for i in (0, 1)]

    def _fill_regions(self, polygons):
        if not SHAPELY_AVAILABLE:
            raise ValueError('No está disponible Shapely; no se puede generar el relleno.')
        rings = []
        for poly in polygons:
            coords = self._coords(poly)
            if len(coords) < 4 or math.dist(coords[0], coords[-1]) > 0.000001:
                raise ValueError('FILL requiere contornos cerrados. Cierra la curva antes de rellenar.')
            shape = Polygon(coords)
            if not shape.is_valid or shape.area <= 0:
                raise ValueError('FILL contiene un contorno cruzado o sin área válida.')
            rings.append(shape)
        for i, a in enumerate(rings):
            for b in rings[i+1:]:
                if a.intersects(b) and not (a.contains(b) or b.contains(a)):
                    raise ValueError('Los contornos del relleno se cruzan, se tocan o están duplicados.')
        # Paridad de anidación: contorno, hueco, isla. Solo dentro de la operación.
        depths = [sum(other.contains(r) for other in rings if other is not r) for r in rings]
        regions = []
        for i, ring in enumerate(rings):
            if depths[i] % 2 == 0:
                holes = [list(r.exterior.coords) for j, r in enumerate(rings)
                         if depths[j] == depths[i]+1 and ring.contains(r)]
                regions.append(Polygon(ring.exterior.coords, holes))
        return regions

    def _fill_paths(self, region, nozzle):
        step = nozzle * (1-self.fill_overlap)
        current = region.buffer(-nozzle/2)
        paths = []
        while not current.is_empty:
            geoms = [current] if current.geom_type == 'Polygon' else list(current.geoms)
            for geom in geoms:
                for ring in [geom.exterior, *geom.interiors]:
                    # Simplificar el recorrido, no la región que se erosiona sucesivamente.
                    line = ring.simplify(self.simplification_tolerance)
                    candidate = self._clean_path(list(line.coords))
                    if not region.covers(LineString(candidate)):
                        candidate = self._clean_path(list(ring.coords))
                    if not region.covers(LineString(candidate)):
                        raise ValueError('El recorrido redondeado sale de la región de relleno.')
                    paths.append(candidate)
            current = current.buffer(-step)
        if not paths:
            raise ValueError('La región es demasiado estrecha para la boquilla seleccionada.')
        return self._connect_fill_turns(paths, region, nozzle)

    def _connect_fill_turns(self, loops, region, nozzle):
        """Open each turn near its seam and feed continuously into the next inset.

        Keep a separate stroke when a connector would cross a hole or leave
        the nozzle clearance region. No changes to LINE operations.
        """
        clearance = region.buffer(-nozzle / 2 + self.simplification_tolerance + 0.002)
        result, chain = [], []
        active = loops[0]
        for following in loops[1:]:
            ring = LineString(following)
            previous = LineString(active)
            gap = min(nozzle * 0.25, previous.length * 0.1)
            opened = self._clean_path(list(substring(previous, 0, previous.length-gap).coords))
            seam = ring.project(Point(opened[-1]))
            # Rotate the closed turn to the point nearest the previous seam.
            if seam <= 1e-9 or ring.length - seam <= 1e-9:
                rotated = following
            else:
                part1 = list(substring(ring, seam, ring.length).coords)
                part2 = list(substring(ring, 0, seam).coords)
                rotated = self._clean_path(part1 + part2[1:])
            bridge = LineString([opened[-1], rotated[0]])
            # Both rounded geometry and bead clearance must remain valid.
            if clearance.covers(bridge) and region.covers(LineString(rotated)):
                chain.extend(opened)
                active = rotated
            else:
                chain.extend(active)
                result.append(self._clean_path(chain))
                chain, active = [], following
        chain.extend(active)
        result.append(self._clean_path(chain))
        return result

    @staticmethod
    def _scan_point(region):
        # Se prefiere el centro si está dentro; el punto representativo evita concavidades y huecos.
        for point in (region.centroid, region.representative_point()):
            xy = (round(point.x, 3), round(point.y, 3))
            if region.contains(Point(xy)):
                return xy
        raise ValueError('No se pudo obtener un punto interior válido a precisión de 0.001 mm.')

    def fill_scan_data(self, op):
        if op['type'] != 'fill':
            raise ValueError('Los puntos de escaneo manuales requieren una operación FILL.')
        regions = self._fill_regions(self._polygons(op))
        stored = op.get('scan_points_local')
        if stored is None:
            return regions, [[self._scan_point(r)] for r in regions]
        source = op.get('source_item')
        points = stored
        if source is not None:
            from PySide6.QtCore import QPointF
            points = [(q.x(),q.y()) for q in
                      (source.mapToScene(QPointF(*p)) for p in stored)]
        return regions, self._validate_scan_points(regions, points)

    @staticmethod
    def _validate_scan_points(regions, points):
        grouped = [[] for _ in regions]
        seen = set()
        for p in points:
            if len(p)!=2 or not all(math.isfinite(v) for v in p):
                raise ValueError('Punto de escaneo inválido.')
            xy = tuple(round(float(v),3) for v in p)
            if xy in seen:
                raise ValueError('Ya existe un punto de escaneo en esa posición.')
            seen.add(xy)
            index = next((i for i,r in enumerate(regions) if r.contains(Point(xy))),None)
            if index is None:
                raise ValueError('Coloca el punto dentro del relleno, fuera de bordes y huecos.')
            grouped[index].append(xy)
        if any(not group for group in grouped):
            raise ValueError('Cada región del relleno necesita al menos un punto de escaneo.')
        return grouped

    def set_fill_scan_points(self, op, points):
        regions = self._fill_regions(self._polygons(op))
        if op['type'] != 'fill':
            raise ValueError('Selecciona una operación de relleno.')
        self._validate_scan_points(regions,points)
        source = op.get('source_item')
        if source is not None:
            from PySide6.QtCore import QPointF
            points = [(q.x(),q.y()) for q in
                      (source.mapFromScene(QPointF(*p)) for p in points)]
        # Immutable replacement: undo snapshots must never share a mutable list.
        op['scan_points_local'] = tuple(tuple(float(v) for v in p) for p in points)

    def _prepare(self):
        if self.registration:
            validate_metadata(self.registration['metadata'])
            for op in self.operations:
                source = op.get('source_item')
                if (source not in self.registration_geometry or source.scene() is None
                        or self.item_geometry(source) != self.registration_geometry[source]):
                    raise ValueError('La geometría ya no coincide con el DXF registrado. Importa nuevamente el diseño de Corel.')
        if not self.operations:
            raise ValueError('No has agregado operaciones.')
        self._text(self.design_name, 'Nombre del diseño')
        if not math.isfinite(self.fill_overlap) or not 0 <= self.fill_overlap < 1:
            raise ValueError('El solapamiento debe estar entre 0 y 1, sin incluir 1.')
        if not math.isfinite(self.simplification_tolerance) or self.simplification_tolerance < 0:
            raise ValueError('La tolerancia de simplificación debe ser finita y no negativa.')
        injectors, blocks = {}, []
        for index, op in enumerate(self.operations, 1):
            try:
                tid = op['injector']
                if type(tid) is not int or tid not in range(1, 5):
                    raise ValueError('El inyector físico debe estar entre 1 y 4.')
                if op['type'] not in ('line', 'fill'):
                    raise ValueError('El tipo debe ser LINE o FILL.')
                name = self._text(op['name'], 'Nombre de operación')
                material = self._text(op['material_name'], 'Royal icing')
                if not re.fullmatch(r'#[0-9a-fA-F]{6}', op['color']):
                    raise ValueError('El color debe tener formato #RRGGBB.')
                nozzle = op['nozzle']
                if not math.isfinite(nozzle) or nozzle <= 0:
                    raise ValueError('La boquilla debe tener un diámetro positivo.')
                definition = (op['color'].upper(), material, nozzle)
                if tid in injectors and injectors[tid] != definition:
                    raise ValueError(f'El inyector {tid} tiene otro color, nombre de royal icing o boquilla en la cola.')
                injectors[tid] = definition
                polygons = self._polygons(op)
                if not polygons:
                    raise ValueError('La operación no contiene curvas.')
                if op['type'] == 'line':
                    paths = [self._clean_path(self._coords(p)) for p in polygons]
                    blocks.append(dict(injector=tid, type='LINE', name=name, paths=paths, scan_points=[], color=op['color']))
                else:
                    regions, scan_groups = self.fill_scan_data(op)
                    for n, region in enumerate(regions, 1):
                        paths = self._fill_paths(region, nozzle)
                        block_name = name if len(regions) == 1 else f'{name} region {n}'
                        blocks.append(dict(injector=tid, type='FILL', name=block_name, paths=paths,
                            scan_points=scan_groups[n-1], color=op['color']))
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError(f'Operación {index}: {exc}') from exc
        return injectors, blocks

    def get_all_preview_paths(self):
        if not self.operations:
            return []
        return self._prepare()[1]

    def generate_full_code(self):
        injectors, blocks = self._prepare()
        header = dict(version='1.0', design_name=self.design_name.strip(), total_colors=len(injectors),
                      way_travel='todo', centro=self._calculate_center())
        if self.registration:
            header['version'] = '1.1'
            header['required_features'] = ['aruco_xy_v1']
            header['alignment'] = copy.deepcopy(self.registration['metadata'])
        lines = ['; --- HEADER START ---']
        lines.extend('; '+line for line in json.dumps(header, ensure_ascii=False, indent=2).splitlines())
        lines.extend(['; --- HEADER END ---', '; --- DEFINITIONS ---'])
        for tid, (color, material, nozzle) in sorted(injectors.items()):
            lines.append(f'; DEFINE_INJECTOR ID={tid} COLOR="{color}" NAME="{material}" NOZZLE="{nozzle:g}mm"')
        lines.append('; --- BODY ---')
        for block in blocks:
            lines.extend([f'; CHANGE_INJECTOR ID={block["injector"]}',
                          f'; OPERATION TYPE={block["type"]} NAME="{block["name"]}"'])
            for x, y in block['scan_points']:
                lines.append(f'; SCAN_POINT X{x:.3f} Y{y:.3f}')
            feed = 800.0 if block['type'] == 'LINE' else 1000.0
            for path in block['paths']:
                x, y = path[0]
                lines.extend([f'G0 X{x:.3f} Y{y:.3f} Z0.000', 'G1 Z-1.000 F250.0'])
                lines.extend(f'G1 X{x:.3f} Y{y:.3f} F{feed:.1f}' for x, y in path[1:])
                lines.append('G0 Z0.000')
        return '\n'.join(lines)+'\n'
