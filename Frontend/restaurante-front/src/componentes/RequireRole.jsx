import { Navigate, useParams } from "react-router-dom";
import { getRolActual } from "../utils/permisos";

export default function RequireRole({ roles, children }) {
  const { slug } = useParams();
  const rol = getRolActual();

  if (!roles.includes(rol)) {
    return <Navigate to={slug ? `/dashboard/${slug}` : "/"} replace />;
  }

  return children;
}
