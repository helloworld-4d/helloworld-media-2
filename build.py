import argparse, concurrent.futures, hashlib, json, shutil, time, urllib.request
from pathlib import Path

def build(entry, roots, output):
    name = entry['url'].rsplit('/', 1)[-1]
    if not name.endswith('.mp4') or Path(name).name != name:
        raise ValueError('Invalid media filename')
    target = output / name
    expected = entry['sha256'].removeprefix('sha256:')
    local = next((Path(root) / entry['source_path'] for root in roots if (Path(root) / entry['source_path']).is_file()), None)
    for attempt in range(3):
        try:
            if roots and local is None:
                raise FileNotFoundError(entry['source_path'])
            source = open(local, 'rb') if local else urllib.request.urlopen(entry['url'], timeout=90)
            digest = hashlib.sha256()
            size = 0
            with source, open(target.with_suffix('.part'), 'wb') as dest:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                    dest.write(chunk)
            if size != entry['bytes'] or digest.hexdigest() != expected:
                raise ValueError('Size or SHA256 mismatch: ' + name)
            target.with_suffix('.part').replace(target)
            print('Verified ' + name, flush=True)
            return
        except Exception:
            target.with_suffix('.part').unlink(missing_ok=True)
            if attempt == 2 or roots:
                raise
            time.sleep(2 ** attempt)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-root', action='append', default=[])
    args = parser.parse_args()
    entries = json.loads(Path('media-manifest.json').read_text())['videos']
    names = [e['url'].rsplit('/', 1)[-1] for e in entries]
    assert len(names) == len(set(names))
    assert sum(e['bytes'] for e in entries) < 900_000_000
    output = Path('_site')
    if output.exists():
        shutil.rmtree(output)
    output.mkdir()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda e: build(e, args.local_root, output), entries))
    (output / '.nojekyll').touch()
    (output / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>HelloWorld media</title><p>Video assets for <a href="https://helloworld-4d.github.io/">HelloWorld</a>.</p>')
