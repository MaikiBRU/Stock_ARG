"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useTextos } from "@/i18n/proveedor";
import { pedir } from "@/lib/api";
import { olvidarSesion } from "@/lib/sesion";

/** Barra lateral en pantallas grandes, superior en un celular. */
export function Navegacion() {
  const { t } = useTextos();
  const ruta = usePathname();
  const router = useRouter();

  const secciones = [{ href: "/panel", texto: t.panel }];

  async function salir() {
    try {
      await pedir("/auth/logout", { method: "POST" });
    } finally {
      // Aunque la API no conteste, la marca local se borra igual.
      olvidarSesion();
      router.push("/ingresar");
    }
  }

  return (
    <nav
      aria-label={t.marca}
      className="flex items-center justify-between gap-4 bg-marca-900 px-4 py-3 text-white sm:flex-col sm:items-stretch sm:justify-start sm:py-6"
    >
      <Link href="/panel" className="text-lg font-bold">
        {t.marca}
      </Link>

      <ul className="flex gap-1 sm:mt-4 sm:flex-col">
        {secciones.map((seccion) => {
          const activa = ruta === seccion.href;
          return (
            <li key={seccion.href}>
              <Link
                href={seccion.href}
                aria-current={activa ? "page" : undefined}
                className={`block rounded-lg px-3 py-2 text-sm ${
                  activa ? "bg-marca-700 font-medium" : "hover:bg-marca-800"
                }`}
              >
                {seccion.texto}
              </Link>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        onClick={salir}
        className="rounded-lg px-3 py-2 text-sm hover:bg-marca-800 sm:mt-auto sm:text-left"
      >
        {t.salir}
      </button>
    </nav>
  );
}
