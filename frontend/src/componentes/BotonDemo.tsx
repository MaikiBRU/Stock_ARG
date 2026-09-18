"use client";

import { ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Boton } from "@/componentes/ui/Boton";
import { useTextos } from "@/i18n/proveedor";
import { mensajeDe, pedir } from "@/lib/api";
import { marcarSesion } from "@/lib/sesion";

type SesionDemo = { expira_en: string };

/** Abre un sandbox y entra directo al panel (RF-J01). */
export function BotonDemo({
  variante = "primario",
  tamano = "lg",
  className = "",
}: {
  variante?: "primario" | "secundario";
  tamano?: "md" | "lg";
  className?: string;
}) {
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
      setError(mensajeDe(falla, t.errorGenerico));
      setAbriendo(false);
    }
  }

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      <Boton
        variante={variante}
        tamano={tamano}
        onClick={abrir}
        cargando={abriendo}
        className="w-full"
      >
        {abriendo ? t.abriendoDemo : t.probarDemo}
        {!abriendo && <ArrowRight size={16} aria-hidden />}
      </Boton>
      {error && (
        <p role="alert" className="text-center text-sm text-alerta">
          {error}
        </p>
      )}
    </div>
  );
}
