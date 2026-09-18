"use client";

import {
  Boxes,
  ChartColumn,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Receipt,
  Settings,
  ShoppingBag,
  ShoppingCart,
  Tags,
  Truck,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { CambioDeIdioma, Logo } from "@/componentes/Idioma";
import { useUsuario } from "@/componentes/Sesion";
import { useTextos } from "@/i18n/proveedor";
import { pedir } from "@/lib/api";
import { administra, gestiona, inicioPara, type Rol } from "@/lib/rutas";
import { olvidarSesion } from "@/lib/sesion";

type Seccion = {
  href: string;
  texto: string;
  icono: LucideIcon;
  puede: (rol: Rol) => boolean;
};

const todos = () => true;

/** Barra lateral en pantallas grandes; cajon deslizable en el celular. */
export function Navegacion() {
  const { t } = useTextos();
  const usuario = useUsuario();
  const ruta = usePathname();
  const router = useRouter();
  const [abierta, setAbierta] = useState(false);

  // Cada rol ve solo lo que puede usar: mostrar una seccion que despues
  // responde 403 es una trampa.
  const grupos: { titulo: string; secciones: Seccion[] }[] = [
    {
      titulo: t.seccionOperacion,
      secciones: [
        { href: "/panel", texto: t.panel, icono: LayoutDashboard, puede: gestiona },
        { href: "/vender", texto: t.vender, icono: ShoppingCart, puede: todos },
        { href: "/ventas", texto: t.ventas, icono: Receipt, puede: todos },
      ],
    },
    {
      titulo: t.seccionCatalogo,
      secciones: [
        { href: "/productos", texto: t.productos, icono: Package, puede: todos },
        { href: "/categorias", texto: t.categorias, icono: Tags, puede: gestiona },
        { href: "/stock", texto: t.stock, icono: Boxes, puede: todos },
      ],
    },
    {
      titulo: t.seccionGestion,
      secciones: [
        { href: "/clientes", texto: t.clientes, icono: Users, puede: todos },
        { href: "/proveedores", texto: t.proveedores, icono: Truck, puede: gestiona },
        { href: "/compras", texto: t.compras, icono: ShoppingBag, puede: gestiona },
        { href: "/reportes", texto: t.reportes, icono: ChartColumn, puede: gestiona },
        { href: "/administracion", texto: t.administracion, icono: Settings, puede: administra },
      ],
    },
  ]
    .map((grupo) => ({
      ...grupo,
      secciones: grupo.secciones.filter((s) => s.puede(usuario.rol)),
    }))
    .filter((grupo) => grupo.secciones.length > 0);

  const nombresDeRol = {
    propietario: t.rolPropietario,
    encargado: t.rolEncargado,
    vendedor: t.rolVendedor,
  };
  const iniciales = usuario.nombre
    .split(/\s+/)
    // Solo palabras que empiezan con letra: "(vendedora)" no cuenta.
    .filter((parte) => /^\p{L}/u.test(parte))
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase() ?? "")
    .join("");

  async function salir() {
    try {
      await pedir("/auth/logout", { method: "POST" });
    } catch {
      // Aunque la API no conteste, la marca local se borra igual.
    } finally {
      olvidarSesion();
      router.push("/ingresar");
    }
  }

  const contenido = (
    <>
      <div className="flex h-14 items-center justify-between px-4">
        <Link
          href={inicioPara(usuario.rol)}
          onClick={() => setAbierta(false)}
          className="rounded-md"
        >
          <Logo />
        </Link>
        <button
          type="button"
          onClick={() => setAbierta(false)}
          aria-label={t.cerrarMenu}
          className="inline-flex size-8 items-center justify-center rounded-md text-suave hover:bg-sutil lg:hidden"
        >
          <X size={18} aria-hidden />
        </button>
      </div>

      <nav aria-label={t.marca} className="flex-1 overflow-y-auto px-3 py-2">
        {grupos.map((grupo) => (
          <div key={grupo.titulo} className="mb-5">
            <p className="px-2 pb-1.5 text-[11px] font-medium tracking-wide text-suave uppercase">
              {grupo.titulo}
            </p>
            <ul className="flex flex-col gap-0.5">
              {grupo.secciones.map((seccion) => {
                const activa =
                  ruta === seccion.href || ruta.startsWith(`${seccion.href}/`);
                const Icono = seccion.icono;
                return (
                  <li key={seccion.href}>
                    <Link
                      href={seccion.href}
                      onClick={() => setAbierta(false)}
                      aria-current={activa ? "page" : undefined}
                      className={`flex h-8 items-center gap-2.5 rounded-md px-2 text-sm transition-colors ${
                        activa
                          ? "bg-marca-suave font-medium text-marca-texto"
                          : "text-suave hover:bg-sutil hover:text-texto"
                      }`}
                    >
                      <Icono size={16} aria-hidden />
                      {seccion.texto}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-borde p-3">
        <Link
          href="/perfil"
          onClick={() => setAbierta(false)}
          aria-current={ruta === "/perfil" ? "page" : undefined}
          className="flex items-center gap-2.5 rounded-lg p-2 transition-colors hover:bg-sutil"
        >
          <span
            aria-hidden
            className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-marca-suave text-xs font-semibold text-marca-texto"
          >
            {iniciales}
          </span>
          <span className="min-w-0 text-left">
            <span className="block truncate text-sm font-medium">
              {usuario.nombre}
            </span>
            <span className="block truncate text-xs text-suave">
              {nombresDeRol[usuario.rol]}
            </span>
          </span>
        </Link>
        <div className="mt-1 flex items-center justify-between">
          <CambioDeIdioma />
          <button
            type="button"
            onClick={salir}
            className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-[13px] text-suave transition-colors hover:bg-sutil hover:text-texto"
          >
            <LogOut size={15} aria-hidden />
            {t.salir}
          </button>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Barra superior del celular */}
      <div className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-borde bg-superficie/90 px-4 backdrop-blur lg:hidden">
        <button
          type="button"
          onClick={() => setAbierta(true)}
          aria-label={t.menu}
          aria-expanded={abierta}
          className="-ml-1.5 inline-flex size-9 items-center justify-center rounded-md hover:bg-sutil"
        >
          <Menu size={20} aria-hidden />
        </button>
        <Logo />
      </div>

      {/* Fondo del cajon */}
      {abierta && (
        <div
          aria-hidden
          onClick={() => setAbierta(false)}
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-borde bg-superficie transition-[transform,visibility] lg:w-60 lg:translate-x-0 ${
          abierta ? "translate-x-0" : "-translate-x-full max-lg:invisible"
        }`}
      >
        {contenido}
      </aside>
    </>
  );
}
