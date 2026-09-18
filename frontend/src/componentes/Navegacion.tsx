"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useUsuario } from "@/componentes/Sesion";
import { useTextos } from "@/i18n/proveedor";
import { pedir } from "@/lib/api";
import { gestiona, inicioPara } from "@/lib/rutas";
import { olvidarSesion } from "@/lib/sesion";

/** Barra lateral en pantallas grandes, superior en un celular. */
export function Navegacion() {
  const { t } = useTextos();
  const usuario = useUsuario();
  const ruta = usePathname();
  const router = useRouter();

  // Cada rol ve solo lo que puede usar: mostrar una seccion que despues
  // responde 403 es una trampa.
  const secciones = [
    { href: "/panel", texto: t.panel, soloGestion: true },
    { href: "/vender", texto: t.vender, soloGestion: false },
  ].filter((s) => !s.soloGestion || gestiona(usuario.rol));

  const nombresDeRol = {
    propietario: t.rolPropietario,
    encargado: t.rolEncargado,
    vendedor: t.rolVendedor,
  };

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
      className="flex flex-wrap items-center justify-between gap-3 bg-marca-900 px-4 py-3 text-white sm:w-56 sm:flex-col sm:flex-nowrap sm:items-stretch sm:justify-start sm:py-6"
    >
      <Link href={inicioPara(usuario.rol)} className="text-lg font-bold">
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

      <div className="flex items-center gap-3 sm:mt-auto sm:flex-col sm:items-stretch">
        <p className="text-xs text-marca-100">
          <span className="block truncate font-medium text-white">
            {usuario.nombre}
          </span>
          {nombresDeRol[usuario.rol]}
        </p>
        <button
          type="button"
          onClick={salir}
          className="rounded-lg px-3 py-2 text-left text-sm hover:bg-marca-800"
        >
          {t.salir}
        </button>
      </div>
    </nav>
  );
}
