const BASE_URL = import.meta.env.VITE_API_URL;

export const getMenu = async (slug) => {
  const res = await fetch(`${BASE_URL}/menu/${slug}/`);

  if (!res.ok) {
    throw new Error("Error cargando menú");
  }

  return res.json();
};
