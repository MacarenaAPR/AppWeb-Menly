# 🍽 Restaurant Menu API

Backend API para gestión dinámica de menús de restaurantes.

Este proyecto proporciona una **API REST construida con Django** que permite administrar y exponer el menú de restaurantes para ser consumido por aplicaciones web o móviles.

El objetivo del sistema es permitir que los sitios web de restaurantes muestren su menú **de forma dinámica**, sin necesidad de modificar el frontend cada vez que cambian los productos.

---

# 🚀 Características

* API REST para obtener menús de restaurantes
* Soporte para **múltiples restaurantes**
* Organización por **categorías**
* Gestión de **productos disponibles**
* Integración con **Cloudinary** para almacenamiento de imágenes
* Base de datos PostgreSQL
* Backend desplegado en producción en Render

---

# 🧠 Arquitectura del sistema

El sistema utiliza una arquitectura **frontend desacoplada del backend**.

```text
Frontend (sitio web restaurante)
        │
        │ fetch API
        ▼
Backend API (Django)
        │
        │ ORM
        ▼
PostgreSQL
```

Esto permite:

* reutilizar el backend para múltiples sitios web
* actualizar menús sin modificar el frontend
* escalar fácilmente la plataforma

---

# ⚙ Tecnologías utilizadas

| Tecnología | Uso                        |
| ---------- | -------------------------- |
| Python     | lenguaje backend           |
| Django     | framework web              |
| PostgreSQL | base de datos              |
| Cloudinary | almacenamiento de imágenes |
| Render     | despliegue del backend     |

---

# 📦 Estructura del proyecto

```text
backend-restaurantes
│
├── core
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── menu
│   ├── models.py
│   ├── views.py
│   ├── admin.py
│   └── migrations
│
├── manage.py
└── requirements.txt
```

---

# 📡 Endpoint principal

## Obtener menú de restaurante

```http
GET /api/menu/<slug_restaurante>/
```

Ejemplo:

```http
GET /api/menu/la-mechada-real/
```

Respuesta:

```json
[
  {
    "categoria": "Promociones",
    "productos": [
      {
        "nombre": "Promo Mechada",
        "descripcion": "Sandwich mechada + bebida",
        "precio": "5990",
        "imagen": "https://res.cloudinary.com/.../promo.jpg"
      }
    ]
  },
  {
    "categoria": "Mechadas",
    "productos": [
      {
        "nombre": "Mechada Italiana",
        "descripcion": "Carne mechada con palta, tomate y mayo",
        "precio": "6990",
        "imagen": null
      }
    ]
  }
]
```

Este endpoint es consumido por el frontend mediante `fetch`.

---

# 🔌 Ejemplo de consumo desde frontend

```javascript
const slug = "la-mechada-real";

fetch(`https://back-end-restaurantes.onrender.com/api/menu/${slug}/`)
  .then(response => response.json())
  .then(data => {
    console.log(data);
  });
```

---

# 🔐 Seguridad

El proyecto utiliza **variables de entorno** para manejar información sensible.

Variables requeridas:

```env
SECRET_KEY
DATABASE_URL
CLOUDINARY_CLOUD_NAME
CLOUDINARY_API_KEY
CLOUDINARY_API_SECRET
REDIS_URL
ADMIN_ALLOWED_NETWORKS
```

Estas variables **no se almacenan en el repositorio**, sino en el entorno del servidor (Render).

El acceso a Django Admin se limita en produccion mediante
`ADMIN_ALLOWED_NETWORKS` (IPs o redes CIDR separadas por coma). La ruta puede
cambiarse con `ADMIN_URL_PATH`. En Render, configure
`ADMIN_CLIENT_IP_HEADER=HTTP_X_FORWARDED_FOR` y declare separadamente las redes
de los proxies inmediatos en `ADMIN_TRUSTED_PROXY_NETWORKS`. Estas redes solo
habilitan la lectura segura del encabezado y nunca conceden acceso al Admin.
Mantenga `REMOTE_ADDR` cuando no exista un proxy confiable. El diagnostico
enmascarado puede habilitarse temporalmente con `ADMIN_IP_DIAGNOSTICS=true` y
esta desactivado por defecto.
El login bloquea progresivamente por IP y por cuenta despues de cinco fallos.

Esto permite mantener el repositorio público sin exponer credenciales.

---

# 🌍 Deploy

El backend está desplegado en **Render**.

Base URL:

```
https://back-end-restaurantes.onrender.com
```

---

# 🧩 Modelo de datos (simplificado)

### Restaurante

* nombre
* slug

### Categoría

* nombre
* activa
* restaurante

### Producto

* nombre
* descripción
* precio
* disponible
* imagen
* categoría

---

# 📈 Roadmap

Próximas mejoras planificadas:

* panel de administración para restaurantes
* autenticación de usuarios
* sistema de reservas
* dashboard de gestión de menú
* soporte multi-restaurante completo

---

# 👩‍💻 Autor

**Makarena Pérez**

Desarrolladora Web
Frontend · Backend · UI/UX

Proyecto desarrollado como base para una **plataforma de gestión de menús digitales para restaurantes**.
