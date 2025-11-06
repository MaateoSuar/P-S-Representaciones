# Pablo y Sergio Representaciones (Flask + Pandas)

Sistema simple para: cargar listado de precios desde CSV/URL (Apps Script), aplicar margen %, armar carrito y generar Remito (PDF) para enviar al cliente.

## Características
- Productos desde CSV local (`data/products.csv`) o URL remota (`PRODUCTS_CSV_URL`, ideal para Google Apps Script publicado como CSV).
- Búsqueda y margen dinámico por vista.
- Carrito con sesión, consolidación por producto+margen.
- Checkout que genera Remito (PDF) en `./pdfs` y guarda pedido en `./orders`.
- Sin subida de Excel en la app (se asume integración por Apps Script o CSV local).

## Estructura
- `app.py`: servidor Flask.
- `templates/`: vistas Jinja2 (`layout`, `dashboard`, `products`, `cart`).
- `static/style.css`: estilos.
- `data/products.csv`: ejemplo de datos.
- `pdfs/`: se generan remitos.
- `orders/`: JSONs de pedidos.

## Requisitos
- Python 3.10+
- Instalar dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Variables de entorno (opcional)
- `PRODUCTS_CSV` = ruta a un CSV local (por defecto `data/products.csv`).
- `PRODUCTS_CSV_URL` = URL pública a CSV (por ejemplo, Apps Script desplegado como "Web App" que devuelva CSV). Si está definida, tiene prioridad sobre `PRODUCTS_CSV`.
- `APP_SECRET` = secret de Flask para sesiones.

Ejemplos en PowerShell:
```powershell
$env:APP_SECRET = "super-secreto"
$env:PRODUCTS_CSV = (Resolve-Path "data/products.csv").Path
# o remoto (Apps Script publicado que emite CSV)
# $env:PRODUCTS_CSV_URL = "https://script.google.com/.../exec?format=csv"
```

## Ejecutar
```powershell
python app.py
```
Abrir: http://localhost:5000

- Dashboard: `/`
- Productos: `/products` (usar búsqueda y margen, agregar al carrito)
- Carrito: `/cart`
- Checkout: genera PDF y redirige a la descarga del remito

## Formato de CSV esperado
Columnas mínimas: `name,cost,vencimiento`

El backend intenta mapear variantes comunes:
- `name` ⇔ `producto`
- `cost` ⇔ `precio`/`costo`
- `vencimiento` ⇔ `fecha vencimiento`/`fecha_vencimiento`

Ejemplo:
```csv
name,cost,vencimiento
"PS=ALPRAZOLAM 0.5 MG X 15 COMP DENVER FARMA",571.33,2027-11-30
```

## Integración con Google Apps Script
- Publique el Apps Script como Web App que devuelva `Content-Type: text/csv` y las columnas arriba.
- Configure `PRODUCTS_CSV_URL` con la URL pública.
- No se sube archivo en la app; la fuente es el CSV remoto.

## Notas
- Los PDFs se guardan en `pdfs/` y se sirven vía `/remitos/<archivo>`. Puede enviarse por email con una futura integración SMTP.
- No se eliminan los archivos HTML/JS originales, pero ya no son necesarios para el flujo Flask.
