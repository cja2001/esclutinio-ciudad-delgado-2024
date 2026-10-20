"""
Genera los mapas base (OpenStreetMap y satelite) recortados a Ciudad Delgado, para el tablero web.

El tablero publicado no puede pedir teselas a internet, asi que cada fondo se descarga una vez,
se une, se recorta al area del distrito y se guarda como JPEG + archivos .js con la imagen en base64
(partidos en trozos de < 200 KB, porque el tablero acepta archivos de hasta 256 KB).

Fuentes:
  - OpenStreetMap (teselas estandar)        (c) OpenStreetMap contributors, ODbL / CC BY-SA
  - Sentinel-2 cloudless 2016 de EOX         CC BY 4.0, contiene datos Copernicus Sentinel modificados 2016
Uso: python -I generar_mapas_base.py
"""
import base64
import io
import json
import math
import time
import urllib.request
from pathlib import Path

from PIL import Image

aqui = Path(__file__).parent
salida = aqui / "mapas_base"
cache = salida / "teselas"
Z = 15
ANCHO_FINAL = 1000      # px de la imagen final
TROZO = 190_000         # caracteres base64 por archivo .js
UA = "CiudadDelgadoDashboard/1.0 (uso unico, mapa estatico)"
FUENTES = {
    "osm": {"url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "calidad": 78,
            "atribucion": "© OpenStreetMap contributors"},
    "sat": {"url": "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg", "calidad": 72,
            "atribucion": "Sentinel-2 cloudless 2016 by EOX IT Services GmbH (contiene datos Copernicus Sentinel modificados 2016), CC BY 4.0"},
}

# extension: divisiones del distrito + 4 % de margen
divs = json.loads((aqui / "datos" / "divisiones.json").read_text(encoding="utf-8"))
pts = [p for d in divs for poly in (d["geometry"]["coordinates"] if d["geometry"]["type"] == "MultiPolygon"
                                    else [d["geometry"]["coordinates"]]) for p in poly[0]]
w, e = min(p[0] for p in pts), max(p[0] for p in pts)
s, n = min(p[1] for p in pts), max(p[1] for p in pts)
mx, my = (e - w) * 0.04, (n - s) * 0.04
w, e, s, n = w - mx, e + mx, s - my, n + my


def a_pixel(lon, lat, z=Z):  # coordenadas de pixel global Web Mercator
    k = 256 * 2 ** z
    x = (lon + 180) / 360 * k
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * k
    return x, y


x0, y0 = a_pixel(w, n)
x1, y1 = a_pixel(e, s)
tx0, ty0, tx1, ty1 = int(x0 // 256), int(y0 // 256), int(x1 // 256), int(y1 // 256)
print(f"Teselas z{Z}: x {tx0}-{tx1}, y {ty0}-{ty1} ({(tx1 - tx0 + 1) * (ty1 - ty0 + 1)} por fondo)")

meta = {"bbox": [round(w, 6), round(s, 6), round(e, 6), round(n, 6)]}
for clave, f in FUENTES.items():
    lienzo = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            archivo = cache / clave / f"{Z}_{tx}_{ty}"
            if not archivo.exists():
                archivo.parent.mkdir(parents=True, exist_ok=True)
                req = urllib.request.Request(f["url"].format(z=Z, x=tx, y=ty), headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as r:
                    archivo.write_bytes(r.read())
                time.sleep(0.3)
            lienzo.paste(Image.open(archivo).convert("RGB"), ((tx - tx0) * 256, (ty - ty0) * 256))
    recorte = lienzo.crop((round(x0 - tx0 * 256), round(y0 - ty0 * 256), round(x1 - tx0 * 256), round(y1 - ty0 * 256)))
    alto = round(recorte.height * ANCHO_FINAL / recorte.width)
    img = recorte.resize((ANCHO_FINAL, alto), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=f["calidad"], optimize=True, progressive=True)
    (salida / f"base_{clave}.jpg").write_bytes(buf.getvalue())
    b64 = base64.b64encode(buf.getvalue()).decode()
    trozos = [b64[i:i + TROZO] for i in range(0, len(b64), TROZO)]
    for i, t in enumerate(trozos, 1):
        cab = ""
        if i == 1:
            cab = (f"window.CD_BASE = window.CD_BASE || {{}};\n"
                   f"window.CD_BASE.{clave} = {{ bbox: {json.dumps(meta['bbox'])}, atribucion: {json.dumps(f['atribucion'], ensure_ascii=False)}, "
                   f"partes: {len(trozos)}, b64: [] }};\n")
        (salida / f"base_{clave}_{i}.js").write_text(cab + f"window.CD_BASE.{clave}.b64.push('{t}');\n", encoding="utf-8")
    print(f"{clave}: {img.width}x{img.height}px, {len(buf.getvalue()) // 1024} KB JPEG, {len(trozos)} archivo(s) .js")
(salida / "mapas_base_meta.json").write_text(json.dumps(meta), encoding="utf-8")
