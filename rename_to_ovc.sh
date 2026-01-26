set -euo pipefail

test -d geoqc
test -f pyproject.toml

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git mv geoqc ovc
else
  mv geoqc ovc
fi

find . -type f \( -name "*.py" -o -name "*.toml" -o -name "*.md" \) -print0 \
  | xargs -0 sed -i \
    -e 's/\bgeoqc\b/ovc/g' \
    -e 's/\bGeoQC\b/OVC/g' \
    -e 's/GeoQC legend/OVC \xE2\x80\x93 Overlap Violation Checker/g'

python - <<'PY'
from pathlib import Path
p = Path("pyproject.toml")
t = p.read_text(encoding="utf-8")
t = t.replace('name = "ovc"', 'name = "ovc"')
t = t.replace('description = "Research-grade building QC for OpenStreetMap"', 'description = "OVC: Overlap Violation Checker \xe2\x80\x93 spatial QC for building violations"')
p.write_text(t, encoding="utf-8")
PY

echo "OK"
