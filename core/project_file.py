"""Versioned, self-contained editable projects. No DXF access or code execution."""
import copy
import json
import math
import re
import uuid
from pathlib import Path
from PySide6.QtCore import Qt, QPointF, QSaveFile, QIODevice
from PySide6.QtGui import QPainterPath, QTransform, QPolygonF
from PySide6.QtWidgets import QGraphicsScene
from gui.dxf_item import DXFGraphicsItem
from core.gcode_generator import GCodeGenerator
from core.aruco_registration import validate_metadata


def number(value):
    if type(value) not in (float,int) or not math.isfinite(value):
        raise ValueError('El proyecto contiene un número inválido.')
    return value


def xy(value):
    if not isinstance(value,(list,tuple)) or len(value)!=2:
        raise ValueError('Coordenada de proyecto inválida.')
    return tuple(number(v) for v in value)


def geometry(value):
    if not isinstance(value,(list,tuple)):
        raise ValueError('Geometría de proyecto inválida.')
    return tuple(tuple(xy(p) for p in poly) for poly in value)


def item_id(item):
    if not hasattr(item,'project_id'):
        item.project_id=uuid.uuid4().hex
    return item.project_id


def encode_project(window):
    g=window.gcode_panel.generator
    items=[i for i in window.canvas.scene.items(Qt.AscendingOrder) if isinstance(i,DXFGraphicsItem)]
    records=[]
    for item in items:
        path=item.path(); transform=item.transform()
        records.append(dict(id=item_id(item),path=[
            [path.elementAt(i).type.value,path.elementAt(i).x,path.elementAt(i).y]
            for i in range(path.elementCount())],fill_rule=path.fillRule().value,
            position=[item.x(),item.y()],rotation=item.rotation(),scale=item.scale(),z=item.zValue(),
            origin=[item.transformOriginPoint().x(),item.transformOriginPoint().y()],
            transform=[transform.m11(),transform.m12(),transform.m13(),transform.m21(),transform.m22(),
                       transform.m23(),transform.m31(),transform.m32(),transform.m33()]))
    operations=[]
    for op in g.operations:
        source=op.get('source_item')
        if source is not None and source not in items:
            raise ValueError('Una operación apunta a un objeto que ya no está en el diseño.')
        entry={key:op[key] for key in ('type','injector','color','name','nozzle','material_name')}
        entry['source_id']=item_id(source) if source is not None else None
        entry['polygons']=[] if source is not None else [[[p.x(),p.y()] for p in poly] for poly in op['polygons']]
        if 'scan_points_local' in op:
            entry['scan_points_local']=op['scan_points_local']
        operations.append(entry)
    data=dict(format='gcodecookies-project',version=1,design_name=g.design_name,
              settings=dict(fill_overlap=g.fill_overlap,simplification_tolerance=g.simplification_tolerance),
              items=records,operations=operations,registration=copy.deepcopy(g.registration),
              registration_geometry={item_id(i):g.registration_geometry[i] for i in items if i in g.registration_geometry})
    return json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8')


def save_project(window,filename):
    data=encode_project(window)
    target=QSaveFile(str(filename))
    if not target.open(QIODevice.WriteOnly):
        raise OSError(target.errorString())
    if target.write(data)!=len(data):
        error=target.errorString();target.cancelWriting();raise OSError(error)
    if not target.commit():
        raise OSError(target.errorString())


def unique_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError(f'Clave duplicada en el proyecto: {key}')
        result[key]=value
    return result


def read_project(filename):
    try:
        data=json.loads(Path(filename).read_text(encoding='utf-8'),object_pairs_hook=unique_keys,
                        parse_constant=lambda s: (_ for _ in ()).throw(ValueError(f'Número inválido: {s}')))
        return decode_project(data)
    except (KeyError,TypeError,IndexError,OverflowError,AttributeError,UnicodeError) as exc:
        raise ValueError('El archivo no contiene un proyecto GcodeCookies válido.') from exc


def decode_project(data):
    if not isinstance(data,dict) or data.get('format')!='gcodecookies-project' or type(data.get('version')) is not int or data['version']!=1:
        raise ValueError('Formato o versión de proyecto no compatible. Selecciona un archivo .gcookies.')
    # Build off-screen first. A malformed project must not erase the current work.
    scene=QGraphicsScene();items={};g=GCodeGenerator()
    if not isinstance(data['design_name'],str):raise ValueError('Nombre de proyecto inválido.')
    g.design_name=data['design_name']
    g.fill_overlap=number(data['settings']['fill_overlap'])
    g.simplification_tolerance=number(data['settings']['simplification_tolerance'])
    if not 0<=g.fill_overlap<1 or g.simplification_tolerance<0:
        raise ValueError('Parámetros de generación inválidos.')
    if not isinstance(data['items'],list) or not isinstance(data['operations'],list):
        raise ValueError('Lista de objetos u operaciones inválida.')
    for record in data['items']:
        key=record['id']
        if not isinstance(key,str) or not key or key in items:
            raise ValueError('Identificador de objeto duplicado o inválido.')
        path=QPainterPath();elements=record['path'];i=0
        if not isinstance(elements,list) or not elements:raise ValueError('Objeto sin geometría.')
        while i<len(elements):
            e=elements[i]
            if len(e)!=3 or type(e[0]) is not int:raise ValueError('Elemento de curva inválido.')
            kind=e[0];point=xy(e[1:])
            if i==0 and kind!=0:raise ValueError('Falta el inicio de una curva.')
            if kind==0:path.moveTo(*point)
            elif kind==1:path.lineTo(*point)
            elif kind==2:
                if i+2>=len(elements) or any(len(e)!=3 or e[0]!=3 for e in elements[i+1:i+3]):
                    raise ValueError('Curva incompleta.')
                path.cubicTo(QPointF(*point),QPointF(*xy(elements[i+1][1:])),QPointF(*xy(elements[i+2][1:])))
                i+=2
            else:raise ValueError('Tipo de curva desconocido.')
            i+=1
        rule=record['fill_rule']
        if type(rule) is not int or rule not in (0,1):raise ValueError('Regla de relleno inválida.')
        path.setFillRule(Qt.FillRule(rule))
        item=DXFGraphicsItem([]);item.setPath(path);item.project_id=key
        item.setPos(*xy(record['position']));item.setTransformOriginPoint(*xy(record['origin']))
        scale=number(record['scale'])
        if scale<=0:raise ValueError('Escala inválida.')
        item.setScale(scale);item.setRotation(number(record['rotation']));item.setZValue(number(record['z']))
        matrix=record['transform']
        if len(matrix)!=9:raise ValueError('Transformación inválida.')
        transform=QTransform(*(number(v) for v in matrix))
        if not transform.isAffine() or not transform.isInvertible():raise ValueError('Transformación no compatible.')
        item.setTransform(transform);scene.addItem(item);items[key]=item
    for record in data['operations']:
        source_id=record['source_id']
        if source_id is not None and source_id not in items:raise ValueError('Operación con referencia a un objeto inexistente.')
        if record['type'] not in ('line','fill') or type(record['injector']) is not int or record['injector'] not in range(1,5):
            raise ValueError('Tipo de operación o inyector inválido.')
        if not isinstance(record['color'],str) or not re.fullmatch('#[0-9a-fA-F]{6}',record['color']):raise ValueError('Color inválido.')
        if not isinstance(record['name'],str) or not isinstance(record['material_name'],str):raise ValueError('Nombre de operación inválido.')
        nozzle=number(record['nozzle'])
        if nozzle<=0:raise ValueError('Boquilla inválida.')
        polys=[QPolygonF([QPointF(*p) for p in poly]) for poly in geometry(record['polygons'])]
        g.add_operation(polys,record['type'],record['injector'],record['color'],record['name'],nozzle,
                        material_name=record['material_name'],source_item=items.get(source_id))
        if 'scan_points_local' in record:
            g.operations[-1]['scan_points_local']=tuple(xy(p) for p in record['scan_points_local'])
    reg=data['registration']
    if reg is not None:
        if not items:raise ValueError('Referencia ArUco sin diseño.')
        validate_metadata(reg['metadata'])
        if not isinstance(reg['layer'],str) or not isinstance(reg['shapes'],list) or not reg['shapes']:
            raise ValueError('Referencia ArUco incompleta.')
        for shape in reg['shapes']:
            if shape['color'] not in ('#000000','#FFFFFF') or len(shape['points'])<3:
                raise ValueError('Geometría ArUco inválida.')
            for point in shape['points']:xy(point)
        if 'placement_center' in reg:xy(reg['placement_center'])
        if 'placement_rotation' in reg:number(reg['placement_rotation'])
        stored=data['registration_geometry']
        if set(stored)!=set(items):raise ValueError('Faltan referencias de geometría ArUco.')
        for key,item in items.items():
            expected=geometry(stored[key])
            if expected!=g.item_geometry(item) or item.scale()!=1 or not item.transform().isIdentity():
                raise ValueError('La geometría no coincide con su referencia ArUco guardada.')
            item.registration_locked=True;item.setFlag(item.GraphicsItemFlag.ItemIsMovable,False)
            g.registration_geometry[item]=expected
        g.registration=reg
    # Preserve unfinished designs: export validation remains the generator's job.
    return scene,list(items.values()),g
