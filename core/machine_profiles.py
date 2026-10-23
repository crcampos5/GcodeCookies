"""Named machine settings stored per Windows user, independently of projects."""
import copy
import json
from PySide6.QtCore import QSettings
from core.worktable import default_worktable, validate_worktable


class MachineProfiles:
    def __init__(self, storage=None):
        self.storage = storage if storage is not None else QSettings('GcodeCookies', 'MachineProfiles')

    def read(self):
        raw = self.storage.value('profiles')
        if raw is None:
            return {'profiles': {}, 'default': None}
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get('profiles'), dict):
            raise ValueError('Configuración de máquinas inválida.')
        profiles = {}
        for name, settings in data['profiles'].items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError('Nombre de máquina inválido.')
            profiles[name] = validate_worktable(settings)
        selected = data.get('default')
        if selected is not None and selected not in profiles:
            raise ValueError('Máquina predeterminada inválida.')
        return {'profiles': profiles, 'default': selected}

    def write(self, data):
        self.storage.setValue('profiles', json.dumps(data, ensure_ascii=False, allow_nan=False))
        self.storage.sync()
        if self.storage.status() != QSettings.NoError:
            raise OSError('No se pudo guardar la configuración de máquinas.')

    def initial_settings(self):
        data = self.read()
        return copy.deepcopy(data['profiles'][data['default']]) if data['default'] else default_worktable()
