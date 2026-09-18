"use client";

import { CircleCheck } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { MarcoDeAcceso } from "@/componentes/Acceso";
import { Boton, clasesDeBoton } from "@/componentes/ui/Boton";
import { Campo } from "@/componentes/ui/Campo";
import { Alerta } from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { mensajeDe, pedir } from "@/lib/api";

function Formulario() {
  const { t } = useTextos();
  const token = useSearchParams().get("token") ?? "";
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hecho, setHecho] = useState(false);

  async function guardar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const formulario = new FormData(evento.currentTarget);
    const contrasena = String(formulario.get("contrasena"));
    if (contrasena !== formulario.get("repetida")) {
      setError(t.contrasenasDistintas);
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      await pedir("/auth/restablecer", {
        method: "POST",
        cuerpo: { token, contrasena },
      });
      setHecho(true);
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
    } finally {
      setGuardando(false);
    }
  }

  if (token.length < 20) {
    return (
      <MarcoDeAcceso titulo={t.restablecerTitulo}>
        <Alerta>{t.enlaceInvalido}</Alerta>
        <Link
          href="/recuperar"
          className={clasesDeBoton("secundario", "lg", "mt-4 w-full")}
        >
          {t.recuperarTitulo}
        </Link>
      </MarcoDeAcceso>
    );
  }

  return (
    <MarcoDeAcceso titulo={t.restablecerTitulo}>
      {hecho ? (
        <div className="flex flex-col gap-4">
          <p
            role="status"
            className="flex items-start gap-3 rounded-xl border border-borde bg-superficie p-4 text-sm"
          >
            <CircleCheck
              size={18}
              className="mt-0.5 shrink-0 text-ok"
              aria-hidden
            />
            {t.contrasenaRestablecida}
          </p>
          <Link href="/ingresar" className={clasesDeBoton("primario", "lg")}>
            {t.entrar}
          </Link>
        </div>
      ) : (
        <form onSubmit={guardar} className="flex flex-col gap-4">
          <Campo
            etiqueta={t.nuevaContrasena}
            name="contrasena"
            type="password"
            required
            minLength={8}
            maxLength={72}
            autoComplete="new-password"
            ayuda={t.requisitoContrasena}
            autoFocus
          />
          <Campo
            etiqueta={t.repetirContrasena}
            name="repetida"
            type="password"
            required
            autoComplete="new-password"
          />
          {error && <Alerta>{error}</Alerta>}
          <Boton
            type="submit"
            variante="primario"
            tamano="lg"
            cargando={guardando}
          >
            {guardando ? t.guardando : t.guardar}
          </Boton>
        </form>
      )}
    </MarcoDeAcceso>
  );
}

export default function Restablecer() {
  return (
    <Suspense>
      <Formulario />
    </Suspense>
  );
}
