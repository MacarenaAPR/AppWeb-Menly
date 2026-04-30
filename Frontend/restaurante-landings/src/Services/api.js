const BASE_URL = "http://127.0.0.1:8000/api";

export const getMenu = async (slug) => {
  const res = await fetch(`${BASE_URL}/menu/${slug}/`);

  if (!res.ok) {
    throw new Error("Error cargando menú");
  }

  return res.json();
};
