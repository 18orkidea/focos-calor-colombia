#!/usr/bin/env python3
"""
Compara focos de calor (detecciones satelitales FIRMS) en Colombia:
  - todo 2025
  - 2026 hasta hoy
  - mismo tramo de 2025 (1 ene → misma fecha) para comparar a igual periodo

Fuente: NASA FIRMS, API "area" → https://firms.modaps.eosdis.nasa.gov/api/area/
  URL: /api/area/csv/{MAP_KEY}/{SOURCE}/{W,S,E,N}/{DAY_RANGE}/{YYYY-MM-DD}
  Límites comprobados el 2026-09-23: DAY_RANGE máximo 5 días por petición
  (la API respondió "Expects [1..5]"); la llamada por país (/api/country/)
  devuelve "Invalid API call", así que se pide el rectángulo que envuelve a
  Colombia y se filtran los focos con el contorno oficial (geoBoundaries
  ADM0, colombia_adm0.geojson). Un año son ~73 peticiones por sensor; el
  límite es 5000 cada 10 minutos.

Sensor: VIIRS a bordo de Suomi-NPP (375 m). Se usa la serie "SP" (Standard
Processing, reprocesada y estable) hasta donde llegue su archivo y "NRT"
(Near Real Time) para las fechas más recientes. Los conteos NRT pueden
cambiar ligeramente cuando NASA reprocesa.

OJO: FIRMS cuenta FOCOS DE CALOR (píxeles con anomalía térmica), no incendios.
Un incendio grande genera decenas de focos; quemas agrícolas también cuentan.

Uso:
  python3 incendios_colombia.py            # lee FIRMS_MAP_KEY de .env
  python3 incendios_colombia.py --source MODIS   # alternativa 1 km
"""
import argparse, csv, io, os, sys, time, urllib.request, urllib.error
from collections import Counter
from datetime import date, timedelta

BASE = "https://firms.modaps.eosdis.nasa.gov/api"
BBOX = "-79.1,-4.3,-66.8,13.5"  # W,S,E,N que envuelve a Colombia continental e insular cercana
CONTORNO = "colombia_adm0.geojson"
HOY = date.today()


def leer_env(ruta=".env"):
    if os.path.exists(ruta):
        for linea in open(ruta):
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get(url, reintentos=3):
    for i in range(reintentos):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode("utf-8", "replace")[:200]
            if e.code == 429 or "limit" in cuerpo.lower():
                print(f"  límite de peticiones, espero 60 s ({cuerpo})", file=sys.stderr)
                time.sleep(60)
                continue
            raise SystemExit(f"HTTP {e.code} en {url.replace(KEY, 'KEY')}: {cuerpo}")
        except Exception as e:  # red
            if i == reintentos - 1:
                raise
            time.sleep(5)
    raise SystemExit("agotados los reintentos")


def disponibilidad():
    """Devuelve {source: (min_date, max_date)} según FIRMS."""
    txt = get(f"{BASE}/data_availability/csv/{KEY}/ALL")
    if not txt.startswith("data_id"):
        raise SystemExit(f"Respuesta inesperada de data_availability (¿clave inválida?): {txt[:200]}")
    out = {}
    for fila in csv.DictReader(io.StringIO(txt)):
        out[fila["data_id"]] = (date.fromisoformat(fila["min_date"]), date.fromisoformat(fila["max_date"]))
    return out


def tramos(inicio, fin, paso=5):
    d = inicio
    while d <= fin:
        n = min(paso, (fin - d).days + 1)
        yield d, n
        d += timedelta(days=n)


def descargar(source, inicio, fin):
    """Descarga focos de un sensor entre dos fechas; devuelve lista de dicts."""
    filas = []
    for d, n in tramos(inicio, fin):
        url = f"{BASE}/area/csv/{KEY}/{source}/{BBOX}/{n}/{d.isoformat()}"
        txt = get(url)
        if txt.startswith("Invalid") or txt.startswith("Error"):
            raise SystemExit(f"FIRMS: {txt[:200]}  ({source} {d} +{n})")
        lote = list(csv.DictReader(io.StringIO(txt)))
        dentro = [f for f in lote if EN_COLOMBIA(float(f["longitude"]), float(f["latitude"]))]
        filas.extend(dentro)
        print(f"  {source} {d} +{n:2d}d → {len(lote):6d} en el rectángulo, {len(dentro):6d} en Colombia", file=sys.stderr)
        time.sleep(0.3)
    return filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="VIIRS_SNPP", choices=["VIIRS_SNPP", "VIIRS_NOAA20", "MODIS"])
    ap.add_argument("--desde", default="2025-01-01")
    args = ap.parse_args()

    leer_env()
    global KEY, EN_COLOMBIA
    import json
    from shapely.geometry import shape
    from shapely.prepared import prep
    pais = prep(shape(json.load(open(CONTORNO))["features"][0]["geometry"]))
    from shapely.geometry import Point
    EN_COLOMBIA = lambda lon, lat: pais.contains(Point(lon, lat))
    KEY = os.environ.get("FIRMS_MAP_KEY")
    if not KEY:
        raise SystemExit("Falta FIRMS_MAP_KEY (ponla en .env: FIRMS_MAP_KEY=xxxx)")

    disp = disponibilidad()
    sp, nrt = f"{args.source}_SP", f"{args.source}_NRT"
    for s in (sp, nrt):
        if s not in disp:
            raise SystemExit(f"FIRMS no ofrece {s}. Disponibles: {', '.join(sorted(disp))}")
    print(f"Disponibilidad FIRMS: {sp} {disp[sp][0]}→{disp[sp][1]} | {nrt} {disp[nrt][0]}→{disp[nrt][1]}", file=sys.stderr)

    inicio = date.fromisoformat(args.desde)
    fin_sp = min(disp[sp][1], HOY)
    filas = descargar(sp, inicio, fin_sp)
    if fin_sp < HOY:
        ini_nrt = max(fin_sp + timedelta(days=1), disp[nrt][0])
        if ini_nrt > fin_sp + timedelta(days=1):
            print(f"AVISO: hueco sin datos entre {fin_sp} y {ini_nrt} (ni SP ni NRT lo cubren)", file=sys.stderr)
        filas += descargar(nrt, ini_nrt, min(disp[nrt][1], HOY))

    # Conteos por año y por periodo comparable
    por_anio = Counter()
    por_anio_alta = Counter()          # excluye confianza baja ("l" en VIIRS, <30 en MODIS)
    mismo_tramo_2025 = 0
    corte_2025 = date(2025, HOY.month, HOY.day)
    por_mes = Counter()
    for f in filas:
        d = date.fromisoformat(f["acq_date"])
        conf = f.get("confidence", "")
        baja = (conf == "l") if not conf.isdigit() else (int(conf) < 30)
        por_anio[d.year] += 1
        if not baja:
            por_anio_alta[d.year] += 1
        if d.year == 2025 and d <= corte_2025:
            mismo_tramo_2025 += 1
        por_mes[(d.year, d.month)] += 1

    ytd26 = por_anio[2026]
    print()
    print(f"Focos de calor en Colombia · sensor {args.source} · fuente NASA FIRMS · corte {HOY}")
    print(f"{'Periodo':<34}{'Focos':>10}{'Sin conf. baja':>16}")
    print(f"{'2025 completo':<34}{por_anio[2025]:>10,}{por_anio_alta[2025]:>16,}")
    print(f"{'2025 (1 ene → ' + corte_2025.strftime('%d %b') + ')':<34}{mismo_tramo_2025:>10,}")
    print(f"{'2026 (1 ene → ' + HOY.strftime('%d %b') + ')':<34}{ytd26:>10,}{por_anio_alta[2026]:>16,}")
    if mismo_tramo_2025:
        var = (ytd26 - mismo_tramo_2025) / mismo_tramo_2025 * 100
        print(f"\n2026 frente al mismo tramo de 2025: {var:+.1f} %")
    if por_anio[2025]:
        print(f"2026 hasta hoy frente a 2025 completo: {ytd26 / por_anio[2025] * 100:.1f} % del total del año pasado")

    print("\nPor mes:")
    print(f"{'Mes':<6}{'2025':>10}{'2026':>10}")
    for m in range(1, 13):
        a, b = por_mes[(2025, m)], por_mes[(2026, m)]
        print(f"{m:<6}{a:>10,}{(f'{b:,}' if (2026, m) <= (HOY.year, HOY.month) else '—'):>10}")

    with open(f"focos_colombia_{args.source}.csv", "w", newline="") as fh:
        if filas:
            w = csv.DictWriter(fh, fieldnames=filas[0].keys())
            w.writeheader(); w.writerows(filas)
    print(f"\nDetalle guardado en focos_colombia_{args.source}.csv ({len(filas):,} filas)")


if __name__ == "__main__":
    main()
