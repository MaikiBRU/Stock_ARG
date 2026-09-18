import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";

import { ProveedorDeIdioma } from "@/i18n/proveedor";
import type { Idioma } from "@/i18n/textos";
import { IDIOMA } from "@/lib/sesion";

import "./globals.css";

export const metadata: Metadata = {
  title: "StockARG",
  description:
    "Gestion de stock, ventas, clientes y proveedores para un comercio.",
};

export const viewport: Viewport = {
  themeColor: "#0a1a30",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // El idioma se resuelve en el servidor: asi la pagina llega escrita y
  // no cambia de idioma despues de cargar.
  const galletas = await cookies();
  const idioma: Idioma = galletas.get(IDIOMA)?.value === "en" ? "en" : "es";

  return (
    <html lang={idioma}>
      <body className="min-h-dvh">
        <a
          href="#contenido"
          className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-superficie focus:px-3 focus:py-2"
        >
          {idioma === "en" ? "Skip to content" : "Ir al contenido"}
        </a>
        <ProveedorDeIdioma idioma={idioma}>{children}</ProveedorDeIdioma>
      </body>
    </html>
  );
}
