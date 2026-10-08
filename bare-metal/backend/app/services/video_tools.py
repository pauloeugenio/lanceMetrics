"""Prefer system tools; optional user-local Linux installation needs no sudo."""
import os,shutil,platform
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[3]

def tool_path(name):
    found=shutil.which(name)
    if found:return found
    private=PROJECT_ROOT/'.venv/video-tools/bin'/name
    return str(private) if platform.system()=='Linux' and private.is_file() and os.access(private,os.X_OK) else None

def tool_env(name='ffmpeg'):
    env=dict(os.environ);lib=PROJECT_ROOT/'.venv/video-tools/lib'
    if platform.system()=='Linux' and lib.is_dir() and tool_path(name)==str(PROJECT_ROOT/'.venv/video-tools/bin'/name):env['LD_LIBRARY_PATH']=str(lib)+os.pathsep+env.get('LD_LIBRARY_PATH','')
    return env
