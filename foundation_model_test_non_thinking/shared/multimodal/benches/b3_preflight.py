"""B-3 manifest 이미지 누락 검사."""

# manifest 가 있어도 image 가 모두 존재해야 의미 있는 평가 가능.
# 누락 시 total=0 인 "성공 exit + 0건 결과" 함정에 빠지므로 preflight 에서 fail-fast.
import json, sys
from pathlib import Path
manifest_path = Path(sys.argv[1])
base_dir = Path(sys.argv[2])
items = json.loads(manifest_path.read_text())
missing = []
for it in items:
    img = it.get('image')
    if not img:
        continue
    full = base_dir / img
    if not full.exists():
        missing.append(str(full))
if missing:
    sys.stderr.write("[run_all] B-3 preflight 실패: 이미지 누락\n")
    for m in missing:
        sys.stderr.write(f"  - {m}\n")
    print("NO")
else:
    print("OK")
