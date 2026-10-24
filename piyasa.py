"""Piyasa degeri ekleme: python piyasa.py "Kerem Demirbay" 4.5   (milyon euro)"""
import json
import sys
from pathlib import Path

yol = Path(__file__).parent / "data" / "piyasa_degeri.json"
veri = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}
if len(sys.argv) == 3:
    veri[sys.argv[1]] = float(sys.argv[2].replace(",", "."))
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Kaydedildi: {sys.argv[1]} = {sys.argv[2]} mn euro")
else:
    print(__doc__)
