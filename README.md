# ARANKO FOOD

Aplicación privada para caja, facturación, cartera, inventario y deudas. Flask sirve el panel; Supabase Auth autentica al administrador y PostgreSQL aplica RLS. Las operaciones de facturación, inventario, abonos y caja son funciones transaccionales de PostgreSQL.

## Estructura

```text
api/index.py                 Adaptador de entrada para Vercel
app.py                       Fábrica Flask, middleware y cabeceras
config.py                    Configuración de entorno
controllers/                 Validación y lógica de aplicación
models/finance.py            Consultas y RPC a Supabase
routes/                      Rutas de autenticación y API financiera
supabase/schema.sql          Tablas, RLS, permisos y funciones transaccionales
templates/                   Inicio de sesión y panel responsivo
static/                      JavaScript, manifest, icono y Service Worker
tests/                       Pruebas unitarias de validación
vercel.json                  Despliegue y cabeceras
```

## Reglas contables implementadas

- Los ingresos del día son facturas emitidas más ingresos operativos manuales. Un pago posterior de una factura aumenta caja, no vuelve a contar la venta como ingreso.
- La utilidad diaria es ingresos facturados/operativos menos costo de ventas menos gastos registrados.
- La caja final es caja inicial más entradas y menos salidas del libro de caja.
- El capital neto calculado es capital inicial + aportes + utilidades retenidas - saldo de deudas. No representa un balance contable completo: no incluye activos no monetarios como inventario, cuentas por cobrar o activos fijos.
- Al crear una factura, el sistema conserva precio y costo de ese momento, descuenta inventario y crea saldo de cartera. Los abonos posteriores actualizan ese saldo.
- Registrar una deuda asume que el dinero prestado ingresa a la caja ese mismo día; cada abono a deuda descuenta caja y reduce el pasivo, sin registrarse como gasto operativo.
- Las fechas del corte usan `BUSINESS_TIMEZONE`; configura una zona IANA apropiada antes de operar. La moneda se configura en `company_settings.currency_code` y el mismo código debe estar en `CURRENCY_CODE`.
- Los valores monetarios usan `numeric(14,2)`. Impuestos, descuentos, devoluciones, compras/proveedores, anulaciones y exportaciones contables no están incluidos.

## 1. Crear Supabase

1. Crea un proyecto en Supabase y conserva el **Project URL** y la **anon/public key**.
2. En **SQL Editor**, ejecuta el contenido de [`supabase/schema.sql`](./supabase/schema.sql).
3. En **Authentication → Users**, crea la única cuenta administradora con una contraseña robusta y confirma el correo si la configuración lo exige.
4. Copia el UUID de esa cuenta y asígnale el rol en SQL Editor:

   ```sql
   insert into public.user_roles (user_id, role)
   values ('UUID-DEL-USUARIO-ADMIN', 'admin')
   on conflict (user_id) do update set role = excluded.role;
   ```

5. Si la moneda no es USD, selecciona el código ISO 4217 de tres letras en la base y configura el mismo valor en `CURRENCY_CODE`:

   ```sql
   update public.company_settings
   set currency_code = 'COP'
   where id = true;
   ```

No se proporciona una pantalla pública para crear usuarios ni elevar roles. Las cuentas se provisionan en Supabase y el rol solo se concede desde un contexto administrativo confiable. No uses la `service_role` key en esta aplicación.

Desactiva el registro público de usuarios en la configuración de Authentication de Supabase si esta instancia debe tener exclusivamente la cuenta del propietario.

## 2. Variables de entorno

Copia `.env.example` como `.env` para desarrollo. Genera dos secretos diferentes:

```powershell
py -c "import secrets; print(secrets.token_urlsafe(48))"
py -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Configura los valores resultantes y los datos del proyecto:

```dotenv
SECRET_KEY=<secreto aleatorio de Flask>
FERNET_KEY=<clave Fernet generada>
SUPABASE_URL=https://<proyecto>.supabase.co
SUPABASE_ANON_KEY=<anon/public key>
CURRENCY_CODE=COP
BUSINESS_TIMEZONE=America/Bogota
COOKIE_SECURE=false
```

`COOKIE_SECURE=false` es solo para desarrollo HTTP local. En producción usa `true` y HTTPS. No subas `.env` al repositorio. La contraseña nunca se almacena en Flask: Supabase Auth la gestiona; los JWT de sesión se cifran con Fernet dentro de la cookie firmada, `HttpOnly`, `SameSite=Lax` y con expiración.

## 3. Ejecutar localmente

En PowerShell desde la carpeta del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m flask --app app run
```

Abre `http://127.0.0.1:5000`. En un servidor Linux, para servir producción fuera de Vercel:

```powershell
gunicorn app:app
```

Tailwind CSS (3.4.17) y jsPDF se cargan desde CDN; el dispositivo necesita conexión para abrir el panel y generar PDF. El Play CDN de Tailwind facilita el arranque, pero no es el modo recomendado por Tailwind para cargas de producción de alto volumen: en ese caso compila Tailwind a un CSS estático local, sirve jsPDF localmente y ajusta la política CSP en `app.py`.

## 4. Desplegar en Vercel

1. Sube el proyecto a un repositorio privado e impórtalo en Vercel; deja el **Root Directory** en la carpeta que contiene `vercel.json` y `requirements.txt`. El punto de entrada es `api/index.py` y `.python-version` selecciona Python 3.14.
2. Antes del primer despliegue, en **Project → Settings → Environment Variables**, agrega para Production y Preview: `SECRET_KEY`, `FERNET_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `CURRENCY_CODE`, `BUSINESS_TIMEZONE` y `COOKIE_SECURE=true`. Genera secretos nuevos para producción; no copies los valores de desarrollo ni uses las claves de ejemplo.
3. No configures la `service_role` key. La app usa la anon key junto con el JWT de la sesión, por lo que las políticas RLS aplican también a las consultas del servidor.
4. Ejecuta el primer despliegue. Después abre la URL HTTPS de Vercel, inicia sesión con la cuenta cuyo UUID asignaste a `admin` y confirma que carguen los datos. Vercel debe incluir `templates/` y `static/` dentro de la función Python; no excluyas esas carpetas.
5. Si cambias una variable de entorno, vuelve a desplegar para que el nuevo valor se aplique. `X-Robots-Tag: noindex, nofollow` impide la indexación voluntaria; no sustituye autenticación, RLS ni control de acceso.

El esquema y las variables quedan preparados, pero no se puede desplegar ni validar la base contra tu cuenta sin acceso a tus proyectos Supabase y Vercel. El archivo `.vercelignore` evita subir el entorno virtual local, secretos, pruebas y cachés.

## Seguridad y respaldo

- Todas las tablas financieras tienen RLS habilitado. Las lecturas requieren el rol administrador; las escrituras contables se limitan a funciones SQL `SECURITY DEFINER` con validación explícita de `public.is_admin()`. El acceso de escritura directo se concede solo a las tablas operativas de clientes y productos.
- Cada POST/PUT del panel exige token CSRF. Las contraseñas las valida Supabase Auth y Flask nunca las persiste.
- Configura en Supabase políticas de contraseña, confirmación de correo y límites de autenticación. La interfaz actual no implementa el desafío MFA; no exijas AAL2 en Supabase hasta integrar ese flujo.
- Configura respaldos automáticos de Supabase y prueba periódicamente una restauración. El panel no permite borrar ni editar facturas y movimientos ya registrados.
- El Service Worker solo almacena recursos estáticos; excluye APIs y datos financieros del caché.
