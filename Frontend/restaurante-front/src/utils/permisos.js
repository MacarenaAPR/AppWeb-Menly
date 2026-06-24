export const ROLES = {
  DUENO: "dueno",
  ADMIN: "admin",
  EMPLEADO: "empleado",
};

export function getRolActual() {
  const restaurante = JSON.parse(localStorage.getItem("restaurante") || "null");
  return restaurante?.rol || "";
}

export function permisosPorRol(rol = "") {
  return {
    isDueno: rol === ROLES.DUENO,
    isAdmin: rol === ROLES.ADMIN,
    isEmpleado: rol === ROLES.EMPLEADO,
    canViewBitacora: rol === ROLES.DUENO,
    canAccessConfiguracion: rol === ROLES.DUENO || rol === ROLES.ADMIN,
    canManageProductos: rol === ROLES.DUENO || rol === ROLES.ADMIN,
    canManageReservas: [ROLES.DUENO, ROLES.ADMIN, ROLES.EMPLEADO].includes(rol),
    canManageSolicitudesEspeciales: [ROLES.DUENO, ROLES.ADMIN, ROLES.EMPLEADO].includes(rol),
    canEditConfigCritica: rol === ROLES.DUENO,
    canToggleOperativa: rol === ROLES.DUENO || rol === ROLES.ADMIN,
  };
}

export function formatearRolVisual(rol = "") {
  const labels = {
    dueno: "Gerente",
    dueño: "Gerente",
    admin: "Administrador",
    empleado: "Empleado",
  };

  return labels[String(rol || "").toLowerCase()] || "Empleado";
}
