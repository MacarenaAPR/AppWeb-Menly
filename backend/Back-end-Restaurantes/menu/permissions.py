# permissions.py
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from django.db.models import Q

from .models import UsuarioRestaurante, Restaurante


MENSAJE_CUENTA_INACTIVA = (
    "La cuenta del restaurante está inactiva. Contacta al soporte de Menly para reactivar tu cuenta."
)


def bloquear_si_restaurante_inactivo(perfil, request):
    if (
        perfil
        and perfil.restaurante
        and not perfil.restaurante.activo
        and request.method not in ["GET", "HEAD", "OPTIONS"]
    ):
        raise PermissionDenied({"error": MENSAJE_CUENTA_INACTIVA})


# ---------- helpers ----------
def get_perfil(request, restaurante: Restaurante = None):
    """
    Retorna el UsuarioRestaurante del request.user.
    Si se pasa restaurante, filtra por ese restaurante.
    """
    qs = UsuarioRestaurante.objects.filter(user=request.user, activo=True)
    if restaurante:
        qs = qs.filter(restaurante=restaurante)
    return qs.select_related("restaurante").first()


def get_restaurante_from_view(view, request):
    """
    Intenta resolver el restaurante desde:
    - view.get_object()
    - view.kwargs (slug/id)
    - fallback: primer restaurante activo del usuario
    """
    # 1) object-level
    if hasattr(view, "get_object"):
        try:
            obj = view.get_object()
            if hasattr(obj, "restaurante"):
                return obj.restaurante
            if isinstance(obj, Restaurante):
                return obj
        except Exception:
            pass

    # 2) kwargs
    slug = view.kwargs.get("slug")
    if slug:
        return Restaurante.objects.filter(slug=slug).first()

    rid = view.kwargs.get("restaurante_id")
    if rid:
        return Restaurante.objects.filter(id=rid).first()

    # 3) fallback
    perfil = get_perfil(request)
    return perfil.restaurante if perfil else None


def is_dueno(perfil):
    return perfil and perfil.rol == "dueno"


def is_admin(perfil):
    return perfil and perfil.rol == "admin"


def is_empleado(perfil):
    return perfil and perfil.rol == "empleado"


# ---------- permisos base ----------
class IsAuthenticatedAndActivo(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsDueno(BasePermission):
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)
        return is_dueno(perfil)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)
        return is_admin(perfil)


class IsEmpleado(BasePermission):
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)
        return is_empleado(perfil)


class IsDuenoOrAdmin(BasePermission):
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)
        return is_dueno(perfil) or is_admin(perfil)


class IsAnyRol(BasePermission):
    """Cualquier usuario del restaurante (dueño/admin/empleado)."""
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        return bool(get_perfil(request, rest))


# ---------- casos específicos ----------

# 1) Configuración del restaurante
class CanManageConfiguracion(BasePermission):
    """
    Dueño: GET + PATCH (todo)
    Admin: solo GET
    Empleado: nada
    """
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)

        if not perfil:
            return False

        bloquear_si_restaurante_inactivo(perfil, request)

        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return is_dueno(perfil) or is_admin(perfil)

        if request.method in ["POST", "PATCH", "PUT"]:
            return is_dueno(perfil)

        return False


# 2) Usuarios (crear/ver)
class CanManageUsuarios(BasePermission):
    """
    Solo dueño:
      - crear usuarios (máx 3: 1 admin y 2 empleados)
      - ver usuarios
    Admin: puede ver (GET) pero no modificar
    Empleado: no acceso
    """
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)

        if not perfil:
            return False

        bloquear_si_restaurante_inactivo(perfil, request)

        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return is_dueno(perfil) or is_admin(perfil)

        # crear / modificar / eliminar usuarios
        if request.method in ["POST", "PATCH", "PUT", "DELETE"]:
            return is_dueno(perfil)

        return False


# 2.1) Validación de límites al crear usuarios (helper)
def validate_user_limits(restaurante: Restaurante, rol: str = None, exclude_usuario_id: int = None):
    qs = UsuarioRestaurante.objects.filter(
        restaurante=restaurante,
        activo=True
    )

    if exclude_usuario_id:
        qs = qs.exclude(id=exclude_usuario_id)

    admins = qs.filter(rol="admin").count()
    empleados = qs.filter(rol="empleado").count()

    if qs.count() >= 4:  # 1 dueno + 1 admin + 2 empleados
        raise ValueError("Maximo de usuarios activos alcanzado para este restaurante")

    if rol == "admin" and admins >= 1:
        raise ValueError("Solo se permite 1 administrador por restaurante")

    if rol == "empleado" and empleados >= 2:
        raise ValueError("Solo se permiten 2 empleados por restaurante")


# 3) Bitácora
class CanViewBitacora(BasePermission):
    """Solo dueño puede ver."""
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)
        return is_dueno(perfil)


class CanModifyBitacora(BasePermission):
    """Nadie puede modificar/eliminar."""
    def has_permission(self, request, view):
        return False


# 4) Productos
class CanManageProductos(BasePermission):
    """
    Dueño/Admin: CRUD
    Empleado: solo GET
    """
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)

        if not perfil:
            return False

        bloquear_si_restaurante_inactivo(perfil, request)

        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True

        return is_dueno(perfil) or is_admin(perfil)


# 5) Reservas
class CanManageReservas(BasePermission):
    """
    Dueño/Admin: CRUD
    Empleado: crear + gestionar (PATCH)
    """
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)

        if not perfil:
            return False

        bloquear_si_restaurante_inactivo(perfil, request)

        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True

        if request.method in ["POST", "PATCH", "PUT"]:
            return is_dueno(perfil) or is_admin(perfil) or is_empleado(perfil)

        return False


# 6) Mesas / Horarios / Métodos de pago
class CanManageOperativa(BasePermission):
    """
    Dueño/Admin: CRUD
    Empleado: no
    """
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)

        if not perfil:
            return False

        bloquear_si_restaurante_inactivo(perfil, request)

        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True

        return is_dueno(perfil) or is_admin(perfil)


class CanManageMesas(BasePermission):
    """
    Todos los roles activos pueden ver mesas.
    Dueno gestiona todo. Admin solo puede PATCH operativo.
    """
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)

        if not perfil:
            return False

        bloquear_si_restaurante_inactivo(perfil, request)

        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True

        if request.method in ["PATCH", "PUT"]:
            return is_dueno(perfil) or is_admin(perfil)

        return is_dueno(perfil)


class CanManageHorarios(BasePermission):
    """
    Todos los roles activos pueden ver horarios.
    Dueno gestiona todo. Admin solo puede abrir o cerrar.
    """
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)

        if not perfil:
            return False

        bloquear_si_restaurante_inactivo(perfil, request)

        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True

        if request.method in ["PATCH", "PUT"]:
            return is_dueno(perfil) or is_admin(perfil)

        return is_dueno(perfil)


class CanManageMetodosPago(BasePermission):
    """
    Todos los roles activos pueden ver metodos de pago.
    Dueno gestiona todo. Admin solo puede activar o desactivar.
    """
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)

        if not perfil:
            return False

        bloquear_si_restaurante_inactivo(perfil, request)

        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True

        if request.method in ["PATCH", "PUT"]:
            return is_dueno(perfil) or is_admin(perfil)

        return is_dueno(perfil)


class CanManageRespaldos(BasePermission):
    """
    Dueno y admin pueden listar, ver ultimo y crear respaldos manuales.
    Empleado no tiene acceso.
    """
    def has_permission(self, request, view):
        rest = get_restaurante_from_view(view, request)
        perfil = get_perfil(request, rest)

        if not perfil:
            return False

        bloquear_si_restaurante_inactivo(perfil, request)

        return is_dueno(perfil) or is_admin(perfil)


# 7) Cuenta propia (bloqueos)
class CanManageOwnAccount(BasePermission):
    """
    Nadie puede eliminar/desactivar su cuenta desde aquí.
    (lo manejas tú como superadmin)
    """
    def has_permission(self, request, view):
        if request.method in ["DELETE", "PATCH", "PUT"]:
            # bloquea cambios sensibles
            return False
        return True
