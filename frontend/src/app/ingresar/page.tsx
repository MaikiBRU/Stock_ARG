"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { BotonDemo } from "@/componentes/BotonDemo";
import { useTextos } from "@/i18n/proveedor";
import { ErrorDeApi, pedir } from "@/lib/api";
import { inicioPara, type Rol } from "@/lib/rutas";
import { marcarSesion } from "@/lib/sesion";

type Token = { expira_en_minutos: number; usuario: { rol: Rol } };

export default function Ingresar() {
  const { t } = useTextos();
  const router = useRouter();
  const [entrando, setEntrando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ingresar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const formulario = new FormData(evento.currentTarget);
    setEntrando(true);
    setError(null);

    try {
      const sesion = await pedir<Token>("/auth/login", {
        method: "POST",
        cuerpo: {
          email: formulario.get("email"),
          contrasena: formulario.get("contrasena"),
        },
      });
      marcarSesion(sesion.expira_en_minutos);
      router.push(inicioPara(sesion.usuario.rol));
    } catch (falla) {
      setError(falla instanceof ErrorDeApi ? falla.message : t.errorGenerico);
      setEntrando(false);
    }
  }

  return (
    <main
      id="contenido"
      className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-12"
    >
      <h1 className="text-2xl font-bold">{t.entrar}</h1>

      <form onSubmit={ingresar} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          {t.correo}
          <input
            name="email"
            type="email"
            required
            autoComplete="email"
            className="rounded-lg border border-borde bg-superficie px-3 py-2 text-base"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          {t.contrasena}
          <input
            name="contrasena"
            type="password"
            required
            autoComplete="current-password"
            className="rounded-lg border border-borde bg-superficie px-3 py-2 text-base"
          />
        </label>

        {error && (
          <p role="alert" className="text-sm text-alerta">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={entrando}
          className="rounded-lg bg-marca-500 px-4 py-2.5 font-medium text-white hover:bg-marca-700 disabled:opacity-70"
        >
          {entrando ? t.ingresando : t.entrar}
        </button>
      </form>

      <div className="flex flex-col gap-3 border-t border-borde pt-6 text-center text-sm">
        <BotonDemo />
        <Link href="/" className="text-suave underline">
          {t.volverAlInicio}
        </Link>
      </div>
    </main>
  );
}
