import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { cookies } from "next/headers";

import { ProveedorDeAvisos } from "@/componentes/ui/Avisos";
import { ProveedorDeIdioma } from "@/i18n/proveedor";
import type { Idioma } from "@/i18n/textos";
import { IDIOMA } from "@/lib/sesion";

import "./globals.css";

// Las fuentes se sirven desde el mismo dominio: next/font las baja al
// compilar, asi la pagina no le pide nada a Google en cada visita.
const geist = Geist({
  subsets: ["latin"],
  variable: "--fuente-geist",
  display: "swap",
});
const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--fuente-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "StockARG", template: "%s · StockARG" },
  description:
    "Gestion de stock, ventas, clientes y proveedores para un comercio.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f8fa" },
    { media: "(prefers-color-scheme: dark)", color: "#0b0e14" },
  ],
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
    <html lang={idioma} className={`${geist.variable} ${geistMono.variable}`}>
      <body className="min-h-dvh">
        <a
          href="#contenido"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-superficie focus:px-3 focus:py-2 focus:shadow-flotante"
        >
          {idioma === "en" ? "Skip to content" : "Ir al contenido"}
        </a>
        <ProveedorDeIdioma idioma={idioma}>
          <ProveedorDeAvisos>{children}</ProveedorDeAvisos>
        </ProveedorDeIdioma>
      </body>
    </html>
  );
}
