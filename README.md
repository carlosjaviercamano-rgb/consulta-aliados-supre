# Consulta Aliados Supre

Portal externo para que los proveedores/aliados de Suprecredito consulten
sus facturas de comisión, filtradas automáticamente por NIT.

Reemplaza la implementación en Power Pages (bloqueada por licenciamiento)
con una app Streamlit independiente, respaldada por Google Sheets.

---

## 1. Crear la cuenta de servicio de Google (dedicada, no reutilizar otras)

1. Ve a [console.cloud.google.com](https://console.cloud.google.com/) y crea un
   **proyecto nuevo** (ej. `supre-aliados-portal`).
2. En el menú, ve a **APIs y servicios > Biblioteca**, busca y habilita:
   - **Google Sheets API**
   - **Google Drive API**
3. Ve a **APIs y servicios > Credenciales > Crear credenciales > Cuenta de servicio**.
   - Nombre: `aliados-supre-bot` (o el que prefieras).
   - No necesita roles de proyecto adicionales.
4. Entra a la cuenta de servicio creada > pestaña **Claves** > **Agregar clave >
   Crear clave nueva > JSON**. Se descarga un archivo `.json` — este archivo
   tiene las credenciales, guárdalo en un lugar seguro (no lo subas a GitHub).
5. Copia el valor de `client_email` del JSON — lo necesitas en el paso 3.

## 2. Crear el Google Sheet

1. Crea un Google Sheet nuevo llamado, por ejemplo, `Consulta Aliados Supre - Datos`.
2. Crea dos pestañas (hojas) dentro, con estos nombres **exactos**:
   - `Facturas`
   - `Proveedores`
3. En la pestaña **Facturas**, la fila 1 debe tener estos encabezados exactos:
   ```
   fecha_factura | factura_comision | cedula_cliente | nombre_cliente | factura_aliado | nit_aliado | nombre_aliado | validacion
   ```
4. En la pestaña **Proveedores**, la fila 1 debe tener estos encabezados exactos:
   ```
   nit | nombre | correo | fecha_alta
   ```
5. Comparte el Sheet (botón **Compartir**) con el `client_email` de la cuenta
   de servicio (paso 1.5), dándole permiso de **Editor**.
6. Copia el **ID del Sheet** desde la URL:
   `https://docs.google.com/spreadsheets/d/ESTE-ES-EL-ID/edit`

## 3. Configurar los secrets localmente (para probar antes de desplegar)

1. Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml`.
2. Rellena:
   - `google_sheet_id`: el ID del paso 2.6.
   - `admin_password`: una clave que solo tú y Leidy conozcan (para la página
     de Administración).
   - `[gcp_service_account]`: copia cada valor directamente del archivo JSON
     descargado en el paso 1.4 (los nombres de campo coinciden).
3. **Nunca subas `secrets.toml` a GitHub** — ya está excluido en `.gitignore`.

## 4. Probar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre `http://localhost:8501`. Prueba:
- Entrar a la página **Administración** (menú lateral) con `admin_password`
  y dar de alta un proveedor de prueba.
- Cerrar sesión y entrar como ese proveedor (usuario = NIT, contraseña = NIT).

## 5. Subir a GitHub

```bash
cd consulta-aliados-supre
git init
git add .
git commit -m "Portal inicial Consulta Aliados Supre"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/consulta-aliados-supre.git
git push -u origin main
```

Si el repo es público, cualquiera podría ver el código (no las credenciales,
esas nunca se suben). Si prefieres privacidad total, crea el repo como
**privado** en GitHub — Streamlit Community Cloud igual puede desplegarlo.

## 6. Desplegar en Streamlit Community Cloud

1. Ve a [share.streamlit.io](https://share.streamlit.io/) e inicia sesión con
   tu cuenta de GitHub.
2. **New app** > selecciona el repo `consulta-aliados-supre`, rama `main`,
   archivo principal `app.py`.
3. Antes de darle "Deploy", ve a **Advanced settings > Secrets** y pega el
   contenido completo de tu `secrets.toml` local (el real, con tus
   credenciales) — esto lo guarda Streamlit de forma segura en su plataforma,
   no en el repo.
4. Dale **Deploy**. En unos minutos tendrás una URL pública tipo
   `https://consulta-aliados-supre.streamlit.app`.

## 7. Flujo diario de carga de facturas

Pendiente de construir: un paso (script Python o flow de Power Automate)
que tome el CSV diario descargado de AWS y lo agregue a la pestaña
`Facturas` del Google Sheet, evitando duplicados por `factura_comision`.

## Estructura del proyecto

```
consulta-aliados-supre/
├── app.py                       # Login + vista de facturas (página pública)
├── sheets_client.py              # Conexión y helpers de Google Sheets
├── pages/
│   └── 1_Administracion.py       # Alta de proveedores (protegida)
├── requirements.txt
├── .streamlit/
│   └── secrets.toml.example      # Plantilla (el real NO se sube)
├── .gitignore
└── README.md
```
