import json, os, re
from pathlib import Path

def resolve_path(value, base):
    value = os.path.expandvars(os.path.expanduser(str(value)))
    if re.search(r'%[^%]+%', value):
        raise ValueError('Unresolved environment variable: ' + value)
    p = Path(value)
    return p.resolve() if p.is_absolute() else (base / p).resolve()

def load_runtime(root):
    root = Path(root).resolve()
    c = json.loads((root / 'config.json').read_text(encoding='utf-8-sig'))
    p = c['paths']
    project = resolve_path(p['viggle_auto'], root)
    pipeline_config = project / 'config.json'
    if not pipeline_config.is_file():
        raise FileNotFoundError('Linked viggle_auto config not found: ' + str(pipeline_config) + '. Edit paths.viggle_auto in Roggle config.json.')
    pipeline = json.loads(pipeline_config.read_text(encoding='utf-8-sig'))
    pp = pipeline['paths']
    python = resolve_path(p['python_executable'], root) if p.get('python_executable') else resolve_path(pp['python_executable'], project)
    base = resolve_path(pp['comfy_base'], project)
    backend = resolve_path(pp['comfy_backend'], project)
    paths = {'roggle_root': str(root), 'viggle_auto': str(project), 'viggle_config': str(pipeline_config),
             'viggle_controller': str(project / 'run.py'), 'viggle_launcher': str(project / 'launcher.py'),
             'python_executable': str(python), 'comfy_base': str(base), 'comfy_backend': str(backend),
             'comfy_main': str(backend / 'main.py'), 'comfy_input': str(base / 'input'),
             'comfy_output': str(base / 'output'), 'comfy_user': str(base / 'user'),
             'model_paths_config': str(resolve_path(pp['model_paths_config'], project)),
             'step34input': str(project / 'step34input'), 'step3output': str(project / 'step3output'),
             'step4output': str(project / 'step4output'), 'static_directory': str(project / 'static'),
             'web_directory': str(resolve_path(p.get('web_directory', 'web'), root)),
             'data_directory': str(resolve_path(p.get('data_directory', 'data'), root)),
             'shots_csv': str(resolve_path(p.get('shots_csv', 'data/shots.csv'), root)),
             'source_video_directory': str(resolve_path(p['source_video_directory'], root)) if p.get('source_video_directory') else None}
    gui = c.get('gui', {})
    host = gui.get('host', '127.0.0.1')
    port = gui.get('port', 8765)
    if host != '127.0.0.1':
        raise ValueError('This local prototype requires gui.host = 127.0.0.1.')
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('gui.port must be an integer from 1 to 65535.')
    flags = pipeline.get('startup_args', [])
    if not isinstance(flags, list) or any(not isinstance(x, str) for x in flags):
        raise ValueError('Linked startup_args must be a list of strings.')
    missing = [name for name in ('python_executable', 'viggle_controller', 'viggle_launcher', 'comfy_main', 'model_paths_config') if not Path(paths[name]).is_file()]
    return {'config': c, 'gui': {'host': host, 'port': port, 'open_browser': gui.get('open_browser', True)},
            'resolved_paths': paths, 'pipeline': {'server': pipeline['server'], 'startup_args': flags,
            'static_images': pipeline.get('static_images', []), 'step3_workflow': pipeline.get('step3_workflow'),
            'step4_workflow': pipeline.get('step4_workflow')}, 'missing_files': missing,
            'prototype_only': True, 'production_actions_enabled': False}
