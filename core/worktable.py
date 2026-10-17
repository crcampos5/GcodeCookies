"""Table coordinates remain fixed; output XY is relative to the chosen origin."""
import math

WORK_AREA_SIZE = 200
ORIGIN_CORNERS = [
    ('Inferior izquierda', (0.0, 0.0)),
    ('Inferior derecha', (WORK_AREA_SIZE, 0.0)),
    ('Superior izquierda', (0.0, WORK_AREA_SIZE)),
    ('Superior derecha', (WORK_AREA_SIZE, WORK_AREA_SIZE)),
]

def default_worktable():
    return {'origin':[0.0,0.0], 'pins':[[85.0,95.0],[150.0,95.0]]}

def validate_worktable(value):
    try:
        if set(value)!= {'origin','pins'} or len(value['pins'])!=2:
            raise ValueError
        pairs=[value['origin'],*value['pins']]
        if any(len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>10000 for v in p) for p in pairs):
            raise ValueError
        return {'origin':list(value['origin']), 'pins':[list(p) for p in value['pins']]}
    except (TypeError,ValueError,KeyError,OverflowError) as exc:
        raise ValueError('Posiciones de topes u origen inválidas.') from exc
