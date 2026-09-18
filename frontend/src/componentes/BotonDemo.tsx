"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useTextos } from "@/i18n/proveedor";
import { ErrorDeApi, pedir } from "@/lib/api";
import { marcarSesion } from "@/lib/sesion";

type SesionDemo = { expira_en: string };

/** Abre un sandbox y entra directo al panel (RF-J01). */
export function BotonDemo({ className = "" }: { className?: string }) {
  const { t } = useTextos();
  const router = useRouter();
  const [abriendo, setAbriendo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function abrir() {
    setAbriendo(true);
    setError(null);
    try {
      const sesion = await pedir<SesionDemo>("/demo/sesion", {
        method: "POST",
      });
      const minutos = Math.max(
        1,
        Math.round((new Date(sesion.expira_en).getTime() - Date.now()) / 60000),
      );
      marcarSesion(minutos);
      router.push("/panel");
    } catch (falla) {
      setError(falla instanceof ErrorDeApi ? falla.message : t.errorGenerico);
      setAbriendo(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={abrir}
        disabled={abriendo}
        className={`rounded-lg bg-marca-500 px-6 py-3 font-medium text-white hover:bg-marca-700 disabled:opacity-70 ${className}`}
      >
        {abriendo ? t.abriendoDemo : t.probarDemo}
      </button>
      {error && (
        <p role="alert" className="text-sm text-alerta">
          {error}
        </p>
      )}
    </div>
  );
}
