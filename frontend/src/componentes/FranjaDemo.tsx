"use client";

import { RotateCcw, Timer } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useUsuario } from "@/componentes/Sesion";
import { useTextos } from "@/i18n/proveedor";
import { ErrorDeApi, pedir } from "@/lib/api";
import { inicioPara, type Rol } from "@/lib/rutas";
import { olvidarSesion } from "@/lib/sesion";

type Estado = { segundos_restantes: number; rol: Rol };

const ROLES: Rol[] = ["propietario", "encargado", "vendedor"];

/** Franja permanente del modo demo (RF-J10). */
export function FranjaDemo() {
  const [estado, setEstado] = useState<Estado | null>(null);

  useEffect(() => {
    let vigente = true;

    async function mirar() {
      try {
        const datos = await pedir<Estado>("/demo/sesion");
        if (vigente) setEstado(datos);
      } catch (falla) {
        // 404 es lo normal fuera de la demo: no hay franja que mostrar.
        if (vigente && falla instanceof ErrorDeApi && falla.estado === 404) {
          setEstado(null);
        }
      }
    }

    mirar();
    // El tiempo restante se descuenta solo; cada minuto se confirma
    // contra la API, que es la que decide cuando la sesion murio.
    const reloj = setInterval(() => {
      setEstado((anterior) =>
        anterior
          ? {
              ...anterior,
              segundos_restantes: Math.max(0, anterior.segundos_restantes - 1),
            }
          : anterior,
      );
    }, 1000);
    const confirmacion = setInterval(mirar, 60_000);

    return () => {
      vigente = false;
      clearInterval(reloj);
      clearInterval(confirmacion);
    };
  }, []);

  return <Franja estado={estado} />;
}

function Franja({ estado }: { estado: Estado | null }) {
  const { t } = useTextos();
  const usuario = useUsuario();
  const router = useRouter();
  const [ocupada, setOcupada] = useState(false);
  const agotada = estado?.segundos_restantes === 0;

  // Al llegar a cero se consulta a la API: si la sesion murio, responde
  // 401 y el cliente de la API lleva al ingreso con el aviso.
  useEffect(() => {
    if (agotada) pedir("/demo/sesion").catch(() => {});
  }, [agotada]);

  if (!estado) return null;

  const minutos = Math.floor(estado.segundos_restantes / 60);
  const segundos = String(estado.segundos_restantes % 60).padStart(2, "0");
  const nombresDeRol = {
    propietario: t.rolPropietario,
    encargado: t.rolEncargado,
    vendedor: t.rolVendedor,
  };

  async function reiniciar() {
    setOcupada(true);
    try {
      await pedir("/demo/sesion/reiniciar", { method: "POST" });
      // Recarga completa: todas las pantallas vuelven a pedir sus datos.
      window.location.assign(inicioPara(usuario.rol));
    } catch {
      setOcupada(false);
    }
  }

  async function cambiarRol(rol: Rol) {
    setOcupada(true);
    try {
      await pedir("/demo/sesion/rol", { method: "POST", cuerpo: { rol } });
      window.location.assign(inicioPara(rol));
    } catch {
      setOcupada(false);
    }
  }

  async function terminar() {
    setOcupada(true);
    try {
      await pedir("/demo/sesion/terminar", { method: "POST" });
    } catch {
      // Si la API no contesta, la sesion vence sola igual.
    } finally {
      olvidarSesion();
      router.push("/");
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-marca/15 bg-marca-suave px-4 py-2 text-[13px] text-marca-texto sm:px-6 lg:px-8">
      <p className="flex items-center gap-2">
        <span className="relative flex size-2" aria-hidden>
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-marca opacity-40" />
          <span className="relative inline-flex size-2 rounded-full bg-marca" />
        </span>
        <strong className="font-semibold">{t.modoDemo}</strong>
        <span className="flex items-center gap-1 opacity-80">
          <Timer size={13} aria-hidden />
          {t.terminaEn}{" "}
          <span className="cifra font-medium">
            {minutos}:{segundos}
          </span>
        </span>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5">
          <span className="opacity-80">{t.verComo}</span>
          <select
            value={usuario.rol}
            disabled={ocupada}
            onChange={(e) => cambiarRol(e.target.value as Rol)}
            className="h-7 cursor-pointer rounded-md border border-marca/25 bg-superficie px-1.5 text-[13px] text-texto"
          >
            {ROLES.map((rol) => (
              <option key={rol} value={rol}>
                {nombresDeRol[rol]}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={reiniciar}
          disabled={ocupada}
          className="inline-flex h-7 items-center gap-1 rounded-md px-2 font-medium hover:bg-marca/10 disabled:opacity-60"
        >
          <RotateCcw size={13} aria-hidden />
          {t.reiniciarDemo}
        </button>
        <button
          type="button"
          onClick={terminar}
          disabled={ocupada}
          className="inline-flex h-7 items-center rounded-md bg-marca px-2.5 font-medium text-sobre-marca hover:bg-marca-hover disabled:opacity-60"
        >
          {t.salirDemo}
        </button>
      </div>
    </div>
  );
}
