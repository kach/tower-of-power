import subprocess

def brew(p):
    x = subprocess.check_output(['brew', 'deps', p])
    return x.split('\n')[:-1]

def npm(p):
    import json
    x = subprocess.check_output(['npm', 'view', p, 'dependencies', '--json'])
    if x == '':
        return []
    obj = json.loads(x)
    return obj.keys()

seen = set()

def walk(p, get_deps):
    if p in seen:
        return
    seen.add(p)
    deps = get_deps(p)
    for dep in deps:
        walk(dep)
    print p + '(' + (', '.join(deps)) + ')' + ': ' + p

#walk('pdf-redact-tools')
walk('nearley', npm)
