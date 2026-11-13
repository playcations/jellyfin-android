"""Copy and verify built prototypes; no keys are generated or modified."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
parser.add_argument('--flavor', action='append', choices=['librePhone', 'libreTv', 'proprietaryPhone', 'proprietaryTv'])
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
build_tools = Path(os.environ['ANDROID_HOME']) / 'build-tools/37.0.0'
args.artifacts.mkdir(parents=True, exist_ok=True)
def run(*cmd): return subprocess.check_output([str(x) for x in cmd], text=True, stderr=subprocess.STDOUT)
records = []
for flavor in args.flavor or ['librePhone', 'libreTv']:
    folder = root / 'app/build/outputs/apk' / flavor / 'debug'
    info = json.loads((folder/'output-metadata.json').read_text())
    source = folder / info['elements'][0]['outputFile']
    target = args.artifacts / source.name
    shutil.copy2(source, target)
    badging = run(build_tools/'aapt2', 'dump', 'badging', target)
    manifest = run(build_tools/'aapt2', 'dump', 'xmltree', target, '--file', 'AndroidManifest.xml')
    signing = run(build_tools/'apksigner', 'verify', '--verbose', '--print-certs', target)
    (args.artifacts/f'{flavor}-badging.txt').write_text(badging)
    (args.artifacts/f'{flavor}-manifest.txt').write_text(manifest)
    (args.artifacts/f'{flavor}-signing.txt').write_text(signing)
    assert "name='com.playcations.familyfin.web.debug'" in badging
    assert "application-label:'Familyfin Web'" in badging
    assert ('android.intent.category.LEANBACK_LAUNCHER' in manifest) == flavor.endswith('Tv')
    assert ('android.hardware.touchscreen' in manifest) == flavor.endswith('Tv')
    assert "versionName='0.1.0-familyfin.1'" in badging
    certificate = re.search(r'certificate SHA-256 digest: (\w+)', signing).group(1)
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    assert sha == hashlib.sha256(source.read_bytes()).hexdigest()
    records.append({'flavor':flavor,'file':str(target),'package':info['applicationId'],
        'versionName':info['elements'][0]['versionName'],'versionCode':info['elements'][0]['versionCode'],
        'sha256':sha,'certificateSha256':certificate,'bytes':target.stat().st_size})
assert len({record['certificateSha256'] for record in records}) == 1
test_records = []
for test in (root/'app/build/outputs/apk/androidTest/libreTv/debug').glob('*.apk'):
    target = args.artifacts/test.name
    shutil.copy2(test, target)
    badging = run(build_tools/'aapt2', 'dump', 'badging', target)
    signing = run(build_tools/'apksigner', 'verify', '--verbose', '--print-certs', target)
    assert "name='com.playcations.familyfin.web.debug.test'" in badging
    certificate = re.search(r'certificate SHA-256 digest: (\w+)', signing).group(1)
    assert certificate == records[0]['certificateSha256']
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    assert sha == hashlib.sha256(test.read_bytes()).hexdigest()
    test_records.append({'file':str(target),'sha256':sha,'certificateSha256':certificate})
    (args.artifacts/'instrumentation-apk-badging.txt').write_text(badging)
    (args.artifacts/'instrumentation-apk-signing.txt').write_text(signing)
(args.artifacts/'instrumentation-apk-verification.json').write_text(json.dumps(test_records,indent=2)+'\n')
(args.artifacts/'apk-verification.json').write_text(json.dumps(records,indent=2)+'\n')
(args.artifacts/'SHA256SUMS').write_text(''.join(f"{r['sha256']}  {Path(r['file']).name}\n" for r in records + test_records))
print(json.dumps(records,indent=2))
