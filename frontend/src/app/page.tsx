import { cookies } from "next/headers";
import Link from "next/link";

import { BotonDemo } from "@/componentes/BotonDemo";
import { textosDe } from "@/i18n/textos";
import { IDIOMA } from "@/lib/sesion";

export default async function Portada() {
  const galletas = await cookies();
  const t = textosDe(galletas.get(IDIOMA)?.value);

  return (
    <main
      id="contenido"
      className="mx-auto flex min-h-dvh max-w-3xl flex-col items-center justify-center gap-8 px-4 py-16 text-center"
    >
      <div>
        <p className="text-sm font-semibold tracking-wide text-marca-500">
          {t.marca}
        </p>
        <h1 className="mt-2 text-balance text-4xl font-bold sm:text-5xl">
          {t.lema}
        </h1>
      </div>

      <div className="flex flex-col items-center gap-4 sm:flex-row">
        <BotonDemo />
        <Link
          href="/ingresar"
          className="rounded-lg border border-borde px-6 py-3 font-medium hover:bg-superficie"
        >
          {t.entrar}
        </Link>
      </div>
    </main>
  );
}
