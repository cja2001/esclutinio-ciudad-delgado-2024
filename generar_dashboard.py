"""Genera index.html (un solo archivo; el mapa Leaflet y sus teselas necesitan internet) a partir de datos/*.json.

Uso: python -I generar_dashboard.py
"""
import datetime
import json
from pathlib import Path

aqui = Path(__file__).parent
datos = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((aqui / "datos").glob("*.json"))}
datos["generado"] = datetime.date.today().isoformat()
js = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = (aqui / "plantilla.html").read_text(encoding="utf-8").replace("/*__DATA__*/", js, 1)
salida = aqui / "index.html"
salida.write_text(html, encoding="utf-8")
print("Listo:", salida, f"({len(html) // 1024} KB)")
