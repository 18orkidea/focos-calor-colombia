# Focos de fuego en Colombia · 2025 frente a 2026

Mapa interactivo de focos de fuego (detecciones térmicas satelitales) en Colombia,
comparando todo 2025 con 2026 hasta el 23 de septiembre, por departamento y en
rejilla de 0,1°. Página estática sin dependencias de servidor: `index.html`
incrusta los datos agregados; solo carga Leaflet (cdnjs) y las fuentes de Google.

## Fuente y método

- **Datos:** NASA FIRMS, sensor VIIRS a bordo de NOAA-20 (375 m). Serie reprocesada
  (SP) hasta el 30 de junio de 2026 y tiempo casi real (NRT) desde el 1 de julio.
  Se descartó Suomi-NPP porque FIRMS no tiene datos de mayo de 2026 ni del 11 al
  15 de julio de 2026 para ese satélite.
- **Descarga:** `incendios_colombia.py` pide el rectángulo que envuelve a Colombia
  a la API `area` de FIRMS en tramos de 5 días (máximo actual de la API; la llamada
  por país ya no funciona) y filtra con el contorno oficial de geoBoundaries.
  Requiere una `FIRMS_MAP_KEY` gratuita en un fichero `.env`.
- **Agregación:** `datos/departamentos.json` (33 departamentos, geoBoundaries ADM1
  simplificado, con conteos) y `datos/rejilla.json` (celdas de 0,1° con conteos).
  Los focos que caen fuera del contorno simplificado (1.091 de 150.064) se asignan
  al departamento más cercano.

## Qué es un foco

Un foco es un píxel de 375 m con anomalía térmica en una pasada del satélite, no un
incendio. Un fuego grande genera decenas de focos y las quemas agrícolas también
cuentan. Sirve para comparar intensidad y distribución entre periodos, no para
contar incendios.

## Cifras (VIIRS NOAA-20, corte 23 sep 2026)

| Periodo | Focos |
|---|---:|
| 2025 completo | 82.365 |
| 2025, 1 ene → 23 sep | 67.546 |
| 2026, 1 ene → 23 sep | 67.699 |

Límites administrativos: [geoBoundaries](https://www.geoboundaries.org/) (CC BY 4.0).
Datos de focos: [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/).
