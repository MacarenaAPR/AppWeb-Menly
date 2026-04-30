# 🍽️ Appweb Menuo

Plataforma SaaS para gestión de restaurantes con **backend desacoplado** y múltiples frontends:

* 🧠 Panel de administración (dashboard)
* 🌐 Landing pública por restaurante
* 🔌 API REST centralizada

---

## 🚀 Tecnologías

**Backend**

* Django
* Django REST Framework
* PostgreSQL
* JWT (SimpleJWT)

**Frontend**

* React (Vite)
* JavaScript
* Fetch API

**Infraestructura**

* Render (backend)
* Vercel / Netlify (frontend)
* Cloudinary (imágenes)

---

## 📁 Estructura del proyecto

```txt
web apprestaurante/
├── backend/
│   └── Back-end-Restaurantes/
│
├── frontend/
│   ├── restaurante-front/      # Dashboard (admin)
│   └── restaurante-landings/   # Landing pública
│
└── README.md
```

---

## ⚙️ Funcionalidades principales

### 🍔 Menú dinámico

* Consumo desde:

```bash
/api/menu/<slug>/
```

* Categorías + productos
* Multi-restaurante por slug

---

### 📩 Reservas públicas

* Endpoint:

```bash
/api/reservas/<slug>/
```

* Validaciones:

  * Fecha futura
  * Horario del restaurante
* Estado inicial: `pendiente`

---

### 👆 Tracking de productos

* Click en productos desde landing
* Base para:

  * productos más vistos
  * analítica de interés

---

### 🎨 Landing Pages

* Renderiza menú dinámico
* Formulario de reservas
* Preparado para múltiples themes

---

## 🔑 Concepto clave

> Un solo backend → múltiples restaurantes → múltiples frontends

Ejemplo:

```txt
/menu/la-mechada-real
/menu/sushi-house
/menu/pizzeria-roma
```

---

## 🧪 Desarrollo local

### Backend

```bash
cd backend/Back-end-Restaurantes
python manage.py runserver
```

---

### Frontend (dashboard)

```bash
cd frontend/restaurante-front
npm install
npm run dev
```

---

### Frontend (landing)

```bash
cd frontend/restaurante-landings
npm install
npm run dev
```

---

## 🌐 API Base

```bash
http://127.0.0.1:8000/api/
```

Endpoints principales:

* `GET /menu/<slug>/`
* `POST /reservas/<slug>/`
* `POST /productos/<id>/click/`

---

## ⚠️ Notas importantes

* El campo `email` en reservas valida formato (aunque sea opcional)
* Las reservas solo se permiten **desde mañana**
* El horario depende de configuración del restaurante
* Siempre usar `/` al final de endpoints en Django

---

## 📈 Roadmap

* [ ] Sistema de themes (mínimo 6)
* [ ] Dashboard de analíticas (clicks)
* [ ] Panel SaaS multi-tenant
* [ ] Gestión avanzada de reservas
* [ ] Deploy productivo completo

---

## 💡 Enfoque

Este proyecto está diseñado como base de un **SaaS escalable para restaurantes**, donde:

* El backend es reutilizable
* El frontend es personalizable
* La experiencia es centrada en UX/UI

---

## 👩‍💻 Autor

Macarena APR
Proyecto en desarrollo como portafolio y base comercial 🚀
