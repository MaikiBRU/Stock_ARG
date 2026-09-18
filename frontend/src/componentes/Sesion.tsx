"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { useTextos } from "@/i18n/proveedor";
import { ErrorDeApi, pedir } from "@/lib/api";
import type { Rol } from "@/lib/rutas";
import { olvidarSesion } from "@/lib/sesion";

export type Usuario = {
  id: number;
  email: string;
  nombre: string;
  rol: Rol;
};

const Contexto = createContext<Usuario | null>(null);

/**
 * Trae el usuario de la sesion y lo comparte con las pantallas.
 *
 * Si la API dice que la sesion ya no vale (vencio, se cerro en otro
 * lado o termino la demo), se borra la marca local y se vuelve al
 * ingreso: la marca sola no alcanza para quedarse.
 */
export function ProveedorDeSesion({ children }: { children: ReactNode }) {
  const { t } = useTextos();
  const router = useRouter();
  const [usuario, setUsuario] = useState<Usuario | null>(null);

  useEffect(() => {
    let vigente = true;
    pedir<Usuario>("/auth/perfil")
      .then((datos) => {
        if (vigente) setUsuario(datos);
      })
      .catch((falla) => {
        if (vigente && falla instanceof ErrorDeApi && falla.estado === 401) {
          olvidarSesion();
          router.replace("/ingresar");
        }
      });
    return () => {
      vigente = false;
    };
  }, [router]);

  if (!usuario) {
    return (
      <p role="status" className="p-6 text-suave">
        {t.cargando}
      </p>
    );
  }
  return <Contexto.Provider value={usuario}>{children}</Contexto.Provider>;
}

/** Usuario de la sesion en curso. */
export function useUsuario() {
  const usuario = useContext(Contexto);
  if (!usuario) {
    throw new Error("useUsuario se usa dentro de ProveedorDeSesion.");
  }
  return usuario;
}
