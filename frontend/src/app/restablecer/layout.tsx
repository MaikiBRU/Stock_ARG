import type { Metadata } from "next";

// El enlace trae el token en la ruta: que ningun pedido saliente lo
// lleve en el encabezado Referer.
export const metadata: Metadata = { referrer: "no-referrer" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
