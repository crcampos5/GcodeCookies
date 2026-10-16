"""Minimal manual save/open actions, separate from machine CGC export."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction,QKeySequence
from PySide6.QtWidgets import QFileDialog,QMessageBox
from core.project_file import save_project,read_project
from gui.dxf_item import DXFGraphicsItem


class ProjectActions:
    def __init__(self, window):
        self.w=window
        self.filename=None
        menu=window.menuBar().addMenu('Archivo')
        for title,shortcut,handler in [
            ('Abrir proyecto…','Ctrl+O',self.open_dialog),
            ('Guardar proyecto','Ctrl+S',self.save),
            ('Guardar proyecto como…','Ctrl+Shift+S',lambda:self.save(save_as=True))]:
            action=QAction(title,window);action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda checked=False,fn=handler:fn())
            menu.addAction(action)

    def save(self,save_as=False):
        filename=self.filename
        if filename is None or save_as:
            suggested=filename or self.w.gcode_panel.generator.design_name+'.gcookies'
            filename,_=QFileDialog.getSaveFileName(self.w,'Guardar proyecto',str(suggested),'Proyecto GcodeCookies (*.gcookies)')
            if not filename:return False
            if not filename.lower().endswith('.gcookies'):
                filename+='.gcookies'
                if Path(filename).exists() and QMessageBox.question(self.w,'Reemplazar proyecto',
                    'El proyecto ya existe. ¿Reemplazarlo?',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:
                    return False
        try:
            # Finish any completed geometry edit before marking the project saved.
            self.w.history.commit('Editar diseño')
            save_project(self.w,filename)
        except (ValueError,OSError) as exc:
            QMessageBox.warning(self.w,'No se pudo guardar el proyecto',str(exc));return False
        self.filename=str(filename)
        self.w.history.stack.setClean()
        self.w.setWindowTitle(f'GcodeCookies - {Path(filename).name}')
        self.w.statusBar().showMessage('Proyecto guardado: '+str(filename),8000)
        return True

    def open_dialog(self):
        filename,_=QFileDialog.getOpenFileName(self.w,'Abrir proyecto','','Proyecto GcodeCookies (*.gcookies)')
        if not filename:return
        try:
            prepared=read_project(filename)
        except (ValueError,OSError) as exc:
            QMessageBox.warning(self.w,'No se pudo abrir el proyecto',str(exc));return
        self.w.history.commit('Editar diseño')
        if not self.w.history.stack.isClean():
            answer=QMessageBox.question(self.w,'Cambios sin guardar','¿Guardar el proyecto actual antes de abrir otro?',
                QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save)
            if answer==QMessageBox.Cancel or (answer==QMessageBox.Save and not self.save()):return
        self.replace(prepared,filename)

    def replace(self,prepared,filename):
        staging,items,generator=prepared
        w=self.w;scene=w.canvas.scene
        w.scan_editor.finish();w.preview_timer.stop()
        w.history.restoring=True
        try:
            scene.blockSignals(True)
            try:
                for item in list(scene.items()):
                    if isinstance(item,DXFGraphicsItem):scene.removeItem(item)
                for item in items:
                    staging.removeItem(item);scene.addItem(item)
                    item.geometry_changed=w.canvas.geometry_changed.emit
            finally:scene.blockSignals(False)
            panel=w.gcode_panel
            panel.cancel_editing();panel.reset_operation_form()
            panel.generator=generator
            panel.refresh_list()
            w.on_items_selected([])
            w.update_canvas_preview()
            w.history.stack.clear()
            w.history.last=w.history.capture()
            w.history.stack.setClean()
            self.filename=str(filename)
            w.setWindowTitle(f'GcodeCookies - {Path(filename).name}')
            w.tabs.setCurrentIndex(0)
            if items:
                rect=items[0].sceneBoundingRect()
                for item in items[1:]+w.canvas.registration_items:rect=rect.united(item.sceneBoundingRect())
                rect=rect.adjusted(-5,-5,5,5)
                w.canvas.setSceneRect(w.canvas.sceneRect().united(rect))
                w.canvas.fitInView(rect,Qt.KeepAspectRatio)
            w.statusBar().showMessage('Proyecto abierto: '+str(filename),8000)
        finally:w.history.restoring=False
