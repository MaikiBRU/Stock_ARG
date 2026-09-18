import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { FranjaDemo } from "@/componentes/FranjaDemo";
import { Navegacion } from "@/componentes/Navegacion";
import { ProveedorDeSesion } from "@/componentes/Sesion";
import { MARCA } from "@/lib/sesion";

/**
 * Armazon de las pantallas internas.
 *
 * El desvio se decide en el servidor, antes de dibujar nada: si se
 * hiciera despues de cargar, quien llega sin sesion veria la aplicacion
 * entera y recien despues un error. La marca no autoriza nada; la
 * sesion de verdad la comprueba la API en cada llamada, y si ya no vale
 * el proveedor de sesion devuelve al ingreso.
 */
export default async function LayoutDeLaAplicacion({
  children,
}: {
  children: React.ReactNode;
}) {
  const galletas = await cookies();
  if (!galletas.get(MARCA)) redirect("/ingresar");

  return (
    <ProveedorDeSesion>
      <div className="flex min-h-dvh flex-col sm:flex-row">
        <Navegacion />
        <div className="flex min-w-0 flex-1 flex-col">
          <FranjaDemo />
          <main id="contenido" className="flex-1 px-4 py-6 sm:px-8">
            {children}
          </main>
        </div>
      </div>
    </ProveedorDeSesion>
  );
}
