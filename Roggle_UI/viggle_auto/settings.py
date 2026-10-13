import json, os, re
from pathlib import Path, PurePosixPath
R=Path(__file__).resolve().parent
C=json.loads((R/'config.json').read_text(encoding='utf-8-sig'))
def configured_path(name,default=None):
    value=C['paths'].get(name,default)
    if value is None:raise ValueError('Missing paths.'+name)
    value=os.path.expandvars(os.path.expanduser(str(value)))
    if re.search(r'%[^%]+%',value):raise ValueError('Unresolved environment variable in paths.'+name+': '+value)
    p=Path(value);return (p if p.is_absolute() else R/p).resolve()
def subdirectory(name,default):
    value=str(C['paths'].get(name,default)).replace('\\','/')
    p=PurePosixPath(value)
    if not value or p.is_absolute() or re.match(r'^[A-Za-z]:',value) or '..' in p.parts or not p.parts:raise ValueError('paths.'+name+' must be a relative subdirectory without ..')
    return p.as_posix()
def under(root,relative):
    p=(root/relative).resolve()
    if not p.is_relative_to(root) or p==root:raise ValueError('Configured subdirectory escapes its root: '+relative)
    return p
BASE=configured_path('comfy_base')
BACKEND=configured_path('comfy_backend')
PYTHON=configured_path('python_executable')
MODEL_CONFIG=configured_path('model_paths_config')
INPUT=configured_path('comfy_input_directory',BASE/'input')
OUTPUT=configured_path('comfy_output_directory',BASE/'output')
USER=configured_path('comfy_user_directory',BASE/'user')
STAGING_SUBDIR=subdirectory('comfy_staging_subdir','viggle_auto')
STEP3_PREFIX=subdirectory('step3_output_subdir','viggle_auto/step3output')
STEP4_PREFIX=subdirectory('step4_output_subdir','viggle_auto/step4output')
STAGING=under(INPUT,STAGING_SUBDIR)
STEP34INPUT=R/'step34input'
STEP3_OUTPUT=under(OUTPUT,STEP3_PREFIX)
STEP4_OUTPUT=under(OUTPUT,STEP4_PREFIX)
