"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useTextos } from "@/i18n/proveedor";
import { ErrorDeApi, pedir } from "@/lib/api";
import { olvidarSesion } from "@/lib/sesion";

type Estado = { segundos_restantes: number; rol: string };

/** Franja permanente del modo demo (RF-J10). */
export function FranjaDemo() {
  const { t } = useTextos();
  const router = useRouter();
  const [estado, setEstado] = useState<Estado | null>(null);
  const [ocupada, setOcupada] = useState(false);

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

  if (!estado) return null;

  const minutos = Math.floor(estado.segundos_restantes / 60);
  const segundos = String(estado.segundos_restantes % 60).padStart(2, "0");

  async function reiniciar() {
    setOcupada(true);
    try {
      await pedir("/demo/sesion/reiniciar", { method: "POST" });
      router.refresh();
    } finally {
      setOcupada(false);
    }
  }

  async function terminar() {
    setOcupada(true);
    try {
      await pedir("/demo/sesion/terminar", { method: "POST" });
    } finally {
      olvidarSesion();
      router.push("/");
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 bg-marca-100 px-4 py-2 text-sm text-marca-800">
      <p>
        <strong>{t.modoDemo}</strong>
        {" — "}
        {t.terminaEn} {minutos}:{segundos} ({estado.rol})
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={reiniciar}
          disabled={ocupada}
          className="rounded border border-marca-700 px-3 py-1 disabled:opacity-60"
        >
          {t.reiniciarDemo}
        </button>
        <button
          type="button"
          onClick={terminar}
          disabled={ocupada}
          className="rounded bg-marca-700 px-3 py-1 text-white disabled:opacity-60"
        >
          {t.salirDemo}
        </button>
      </div>
    </div>
  );
}
