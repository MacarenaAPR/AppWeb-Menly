# 🍽️ Menly

Plataforma SaaS para gestión de restaurantes con arquitectura desacoplada, múltiples frontends y enfoque multi-tenant.

Menly permite que múltiples restaurantes administren su negocio desde un dashboard privado mientras ofrecen una landing pública personalizada con menú digital, reservas online y futuras analíticas.

---

# ✨ Características Principales

- 🍔 Menú dinámico por restaurante
- 🌐 Landing pública personalizada
- 📩 Sistema de reservas online
- 🔐 Autenticación JWT
- 🧩 Arquitectura desacoplada
- 🎨 Themes visuales dinámicos
- 📊 Base para analíticas y tracking
- ☁️ Infraestructura preparada para producción
- 🏪 Multi-restaurante mediante slug

---

# 🧠 Arquitectura

Menly funciona bajo una arquitectura desacoplada:

- Backend centralizado
- Frontends independientes
- Comunicación mediante API REST
- Multi-tenant basado en slugs únicos

Ejemplos:

```txt
/menu/la-mechada-real
/menu/sushi-house
/menu/pizzeria-roma
```

Un solo backend puede administrar múltiples restaurantes sin duplicar lógica.

---

# 🛠️ Stack Tecnológico

## Backend

- Python
- Django
- Django REST Framework
- PostgreSQL
- JWT Authentication (SimpleJWT)

## Frontend

- React
- Vite
- JavaScript
- Fetch API
- Bootstrap

## Infraestructura

- Render (backend)
- Vercel / Netlify (frontend)
- Cloudinary (imágenes)

---

# 📁 Estructura del Proyecto

```txt
web-apprestaurante/
│
├── backend/
│   └── Back-end-Restaurantes/
│
├── frontend/
│   ├── restaurante-front/       # Dashboard administrativo
│   └── restaurante-landings/    # Landing pública
│
└── README.md
```

---

# ⚙️ Funcionalidades Principales

## 🍔 Menú Dinámico

Endpoint:

```txt
GET /api/menu/<slug>/
```

Características:

- Categorías dinámicas
- Productos por restaurante
- Productos destacados
- Disponibilidad en tiempo real
- Multi-restaurante por slug

---

## 📩 Reservas Públicas

Endpoint:

```txt
POST /api/reservas/<slug>/
```

Validaciones implementadas:

- Fecha futura obligatoria
- Horario válido según restaurante
- Estado inicial automático: `pendiente`
- Validación de email
- Prevención básica de spam

---

## 👆 Tracking de Productos

Endpoint:

```txt
POST /api/productos/<id>/click/
```

Base para futuras funcionalidades:

- Productos más vistos
- Analíticas de interés
- Métricas por restaurante

---

## 🎨 Landing Pages

Cada restaurante puede tener:

- Carta digital personalizada
- Hero dinámico
- Themes visuales
- Formulario de reservas
- Links sociales y delivery
- Diseño responsive

---

# 🔐 Seguridad

- Autenticación JWT
- Separación frontend/backend
- Validaciones multi-restaurante
- Variables de entorno
- Configuración CORS
- Preparado para throttling y protección anti-spam

---

# 🌐 API Base

```txt
http://127.0.0.1:8000/api/
```

## Endpoints principales

```txt
GET    /menu/<slug>/
POST   /reservas/<slug>/
POST   /productos/<id>/click/
```

---

# 🧪 Desarrollo Local

## 1️⃣ Clonar repositorio

```bash
git clone https://github.com/TU-USUARIO/TU-REPOSITORIO.git
```

---

## 2️⃣ Backend

```bash
cd backend/Back-end-Restaurantes

python -m venv env
```

### Activar entorno virtual

#### Windows

```bash
env\Scripts\activate
```

#### Linux / Mac

```bash
source env/bin/activate
```

### Instalar dependencias

```bash
pip install -r requirements.txt
```

### Ejecutar migraciones

```bash
python manage.py migrate
```

### Iniciar servidor

```bash
python manage.py runserver
```

---

## 3️⃣ Frontend Dashboard

```bash
cd frontend/restaurante-front

npm install
npm run dev
```

---

## 4️⃣ Frontend Landing

```bash
cd frontend/restaurante-landings

npm install
npm run dev
```

---

# ☁️ Variables de Entorno

Ejemplo backend `.env`

```env
DEBUG=True

SECRET_KEY=tu_secret_key

DATABASE_URL=postgresql://usuario:password@localhost:5432/db

ALLOWED_HOSTS=127.0.0.1,localhost

CORS_ALLOWED_ORIGINS=http://localhost:5173

CLOUDINARY_CLOUD_NAME=xxxxx
CLOUDINARY_API_KEY=xxxxx
CLOUDINARY_API_SECRET=xxxxx
```

---

# 📈 Roadmap

- [ ] Sistema avanzado de themes
- [ ] Dashboard de analíticas
- [ ] Métricas por restaurante
- [ ] Sistema de suscripciones
- [ ] Roles y permisos avanzados
- [ ] Gestión avanzada de reservas
- [ ] Notificaciones automáticas
- [ ] Panel SaaS completo
- [ ] Deploy productivo estable

---

# 💡 Objetivo del Proyecto

Menly nace como una plataforma SaaS escalable enfocada en:

- Reutilización del backend
- Personalización visual por cliente
- Escalabilidad multi-restaurante
- UX/UI moderna
- Automatización operativa

---

# 🚀 Estado del Proyecto

Proyecto actualmente en desarrollo activo.

Enfoque actual:

- Refinamiento UX/UI
- Optimización frontend
- Escalabilidad multi-tenant
- Validaciones productivas
- Preparación para clientes reales

---

# 👩‍💻 Autor

**Macarena APR**

Proyecto desarrollado como portafolio profesional y futura base comercial SaaS.

---
