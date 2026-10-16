"""Read exported CGC for a static viewer. Display-only Z references: work at 0 mm and travel at 10 mm."""
from dataclasses import dataclass, field
import json
import math
import re

@dataclass
class ViewOperation:
    injector: int
    name: str
    kind: str
    color: str
    lines: list = field(default_factory=list)
    travels: list = field(default_factory=list)
    scan_points: list = field(default_factory=list)

@dataclass
class ViewData:
    operations: list
    design_name: str
    alignment: dict = None


def parse_cgc_view(text):
    operations, definitions = [], {}
    current = None
    xy = None  # No invented move from machine origin before the first known XY.
    down = False
    header, metadata, reading_header = [], None, False
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        def fail(message):
            raise ValueError(f'Línea {number}: {message}')
        if not line:
            continue
        if line == '; --- HEADER START ---':
            if metadata is not None or reading_header:
                fail('Encabezado duplicado.')
            reading_header = True
            continue
        if line == '; --- HEADER END ---':
            if not reading_header:
                fail('Fin de encabezado sin inicio.')
            try:
                metadata = json.loads('\n'.join(header))
            except ValueError:
                fail('Encabezado JSON inválido.')
            if not isinstance(metadata, dict) or metadata.get('version') not in ('1.0','1.1'):
                fail('Este visor admite CGC 1.0 y 1.1.')
            if metadata.get('version') == '1.1':
                from core.aruco_registration import validate_metadata
                if metadata.get('required_features') != ['aruco_xy_v1']:
                    fail('Funciones requeridas no compatibles.')
                validate_metadata(metadata.get('alignment'))
            reading_header = False
            continue
        if reading_header:
            if not line.startswith(';'):
                fail('El encabezado debe estar comentado.')
            header.append(line[1:].strip())
            continue
        if line.startswith('; DEFINE_INJECTOR'):
            m = re.fullmatch(r'; DEFINE_INJECTOR ID=([1-4]) COLOR="(#[0-9a-fA-F]{6})" NAME="[^"]+" NOZZLE="[^"]+"', line)
            if not m:
                fail('Definición de inyector inválida.')
            tid = int(m[1])
            if tid in definitions:
                fail('Inyector definido más de una vez.')
            definitions[tid] = m[2]
        elif line.startswith('; CHANGE_INJECTOR'):
            if down:
                fail('Falta la retirada del trazo anterior.')
            m = re.fullmatch(r'; CHANGE_INJECTOR ID=([1-4])', line)
            if not m or int(m[1]) not in definitions:
                fail('Inyector sin definición.')
            current = ViewOperation(int(m[1]), '', '', definitions[int(m[1])])
            operations.append(current)
        elif line.startswith('; OPERATION'):
            m = re.fullmatch(r'; OPERATION TYPE=(LINE|FILL) NAME="([^"]+)"', line)
            if current is None or current.kind or not m:
                fail('Declaración de operación inválida.')
            current.kind, current.name = m[1], m[2]
        elif line.startswith('; SCAN_POINT'):
            if current is None or current.kind != 'FILL':
                fail('SCAN_POINT requiere una operación FILL.')
            m = re.fullmatch(r'; SCAN_POINT X([-+]?\d+(?:\.\d+)?) Y([-+]?\d+(?:\.\d+)?)', line)
            if not m:
                fail('Punto de escaneo inválido.')
            point = tuple(float(m[i]) for i in (1,2))
            if not all(math.isfinite(v) for v in point):
                fail('Coordenada no finita.')
            current.scan_points.append((*point, 0.0))
        elif line.startswith(';'):
            continue
        else:
            if current is None or not current.kind:
                fail('Movimiento fuera de una operación.')
            tokens = re.findall(r'([A-Z])([-+]?\d+(?:\.\d+)?)', line)
            if ''.join(a+b for a,b in tokens) != re.sub(r'\s+', '', line):
                fail('Instrucción no reconocida.')
            if len({a for a,b in tokens}) != len(tokens):
                fail('Parámetros repetidos.')
            values = {a:float(b) for a,b in tokens}
            if not all(math.isfinite(v) for v in values.values()):
                fail('Valor no finito.')
            if values.get('G') not in (0,1) or set(values)-set('GXYZF'):
                fail('Solo se admiten G0/G1 del contrato CGC.')
            if 'F' in values and values['F'] <= 0:
                fail('Velocidad inválida.')
            if values['G'] == 0:
                if values.get('Z') != 0 or down and ('X' in values or 'Y' in values):
                    fail('Traslado sin retirada o marcador de seguridad inválido.')
                down = False
                if 'X' in values or 'Y' in values:
                    if not {'X','Y'} <= values.keys():
                        fail('El traslado requiere X e Y.')
                    target = (values['X'],values['Y'],10.0)
                    if xy is not None and target != xy:
                        current.travels.extend([xy,target])
                    xy = target
                elif xy is not None:
                    target = (xy[0], xy[1], 10.0)
                    if target != xy:
                        current.travels.extend([xy, target])
                    xy = target
            elif 'Z' in values:
                if set(values)-set('GZF') or values['Z'] != -1 or xy is None or down:
                    fail('Marcador de bajada inválido.')
                target = (xy[0], xy[1], 0.0)
                current.travels.extend([xy, target])
                xy = target
                down = True
            else:
                if not down or xy is None or not {'X','Y','F'} <= values.keys():
                    fail('Segmento incompleto o sin bajada.')
                target = (values['X'],values['Y'],0.0)
                current.lines.extend([xy,target])
                xy = target
    if reading_header or metadata is None:
        raise ValueError('Falta un encabezado CGC completo.')
    if down:
        raise ValueError('Falta la retirada final.')
    if not operations:
        raise ValueError('No hay operaciones para visualizar.')
    for op in operations:
        if not op.lines or not op.kind:
            raise ValueError('Hay una operación vacía o sin tipo.')
        if op.kind == 'FILL' and not op.scan_points:
            raise ValueError(f'El relleno {op.name} no tiene puntos de escaneo.')
    return ViewData(operations, str(metadata.get('design_name','Diseño')), metadata.get('alignment'))
