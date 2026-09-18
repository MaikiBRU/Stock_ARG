"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import {
  BotonGoogle,
  MarcoDeAcceso,
  Separador,
  useEntrar,
  type Token,
} from "@/componentes/Acceso";
import { BotonDemo } from "@/componentes/BotonDemo";
import { Boton } from "@/componentes/ui/Boton";
import { Campo } from "@/componentes/ui/Campo";
import { Alerta } from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { mensajeDe, pedir } from "@/lib/api";

function Formulario() {
  const { t } = useTextos();
  const vencida = useSearchParams().get("vencida") === "1";
  const entrar = useEntrar();
  const [entrando, setEntrando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ingresar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const formulario = new FormData(evento.currentTarget);
    setEntrando(true);
    setError(null);

    try {
      entrar(
        await pedir<Token>("/auth/login", {
          method: "POST",
          cuerpo: {
            email: formulario.get("email"),
            contrasena: formulario.get("contrasena"),
          },
        }),
      );
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
      setEntrando(false);
    }
  }

  return (
    <MarcoDeAcceso
      titulo={t.ingresarTitulo}
      texto={t.ingresarTexto}
      pie={
        <>
          <Link href="/registro" className="hover:text-texto">
            {t.noTengoCuenta}
          </Link>
          <Link href="/verificar" className="text-xs hover:text-texto">
            {t.tengoCodigo}
          </Link>
        </>
      }
    >
      {vencida && (
        <p
          role="status"
          className="mb-5 rounded-lg border border-aviso/25 bg-aviso-suave px-3 py-2 text-sm text-aviso"
        >
          {t.sesionVencida}
        </p>
      )}
      <form onSubmit={ingresar} className="flex flex-col gap-4">
        <Campo
          etiqueta={t.correo}
          name="email"
          type="email"
          required
          autoComplete="email"
          autoFocus
        />
        <div className="flex flex-col gap-1.5">
          <Campo
            etiqueta={t.contrasena}
            name="contrasena"
            type="password"
            required
            autoComplete="current-password"
          />
          <Link
            href="/recuperar"
            className="self-end text-xs text-suave hover:text-texto"
          >
            {t.olvide}
          </Link>
        </div>

        {error && <Alerta>{error}</Alerta>}

        <Boton type="submit" variante="primario" tamano="lg" cargando={entrando}>
          {entrando ? t.ingresando : t.entrar}
        </Boton>
      </form>

      <Separador />
      <div className="flex flex-col gap-3">
        <BotonGoogle />
        <BotonDemo variante="secundario" />
      </div>
    </MarcoDeAcceso>
  );
}

export default function Ingresar() {
  return (
    <Suspense>
      <Formulario />
    </Suspense>
  );
}
