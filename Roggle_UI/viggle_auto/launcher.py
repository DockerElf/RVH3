import json, socket, subprocess, sys, urllib.request
from urllib.parse import urlsplit
from settings import R, C, BASE, BACKEND, PYTHON, MODEL_CONFIG, INPUT, OUTPUT, USER

def endpoint():
    u = urlsplit(C['server'])
    if u.scheme != 'http' or not u.hostname or u.path not in ('', '/') or u.query or u.fragment:
        raise ValueError('server must be an HTTP origin such as http://127.0.0.1:8000')
    return u.hostname, u.port or 80

def check():
    with urllib.request.urlopen(C['server'].rstrip('/') + '/system_stats', timeout=10) as response:
        data = json.load(response)
    print('Backend API is responding:', C['server'])
    print(json.dumps(data, indent=2))
    return 0

def start():
    host, port = endpoint()
    if host not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('This launcher starts a local backend; use a loopback server address.')
    try:
        with urllib.request.urlopen(C['server'].rstrip('/') + '/system_stats', timeout=5) as response:
            json.load(response)
        print('Backend already responding. No second backend started.')
        return 0
    except Exception:
        pass
    try:
        with socket.create_connection((host, port), timeout=2):
            raise RuntimeError('Configured port is in use but the backend API is not responding. No second backend started.')
    except OSError:
        pass
    for p in (PYTHON, BACKEND / 'main.py', MODEL_CONFIG):
        if not p.is_file():
            raise FileNotFoundError('Required file not found: ' + str(p))
    args = C.get('startup_args', [])
    if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
        raise ValueError('startup_args must be a list of strings.')
    managed = {'--base-directory', '--user-directory', '--database-url', '--port', '--listen',
               '--extra-model-paths-config', '--input-directory', '--output-directory'}
    for a in args:
        if a.split('=', 1)[0] in managed:
            raise ValueError('Argument is derived from paths/server; remove from startup_args: ' + a)
    for p in (INPUT, OUTPUT, USER):
        p.mkdir(parents=True, exist_ok=True)
    command = [str(PYTHON), '-s', str(BACKEND / 'main.py'),
               '--base-directory', str(BASE), '--user-directory', str(USER),
               '--database-url', 'sqlite:///' + (USER / 'comfyui.db').as_posix(),
               '--port', str(port), '--listen', host,
               '--extra-model-paths-config', str(MODEL_CONFIG),
               '--input-directory', str(INPUT), '--output-directory', str(OUTPUT)] + args
    print('Starting backend:', subprocess.list2cmdline(command), flush=True)
    return subprocess.call(command, cwd=str(BACKEND))

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'start':
        return start()
    if mode == 'check':
        return check()
    if mode in ('step3', 'step4', 'both', 'cleanup', 'reset'):
        return subprocess.call([str(PYTHON), str(R / 'run.py'), mode], cwd=str(R))
    raise ValueError('Expected start, check, step3, step4, both, cleanup, or reset.')

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as e:
        print('ERROR:', e, file=sys.stderr)
        sys.exit(1)
