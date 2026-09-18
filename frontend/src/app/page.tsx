import {
  Boxes,
  ChartColumn,
  ScanBarcode,
  ShieldCheck,
  Truck,
  UsersRound,
} from "lucide-react";
import { cookies } from "next/headers";
import Link from "next/link";

import { BotonDemo } from "@/componentes/BotonDemo";
import { CambioDeIdioma, Logo } from "@/componentes/Idioma";
import { clasesDeBoton } from "@/componentes/ui/Boton";
import { textosDe } from "@/i18n/textos";
import { IDIOMA } from "@/lib/sesion";

export default async function Portada() {
  const galletas = await cookies();
  const t = textosDe(galletas.get(IDIOMA)?.value);

  const rasgos = [
    { icono: ScanBarcode, titulo: t.rasgoVentaTitulo, texto: t.rasgoVentaTexto },
    { icono: Boxes, titulo: t.rasgoStockTitulo, texto: t.rasgoStockTexto },
    { icono: Truck, titulo: t.rasgoGestionTitulo, texto: t.rasgoGestionTexto },
    { icono: ChartColumn, titulo: t.rasgoReportesTitulo, texto: t.rasgoReportesTexto },
    { icono: UsersRound, titulo: t.rasgoRolesTitulo, texto: t.rasgoRolesTexto },
    { icono: ShieldCheck, titulo: t.rasgoSeguridadTitulo, texto: t.rasgoSeguridadTexto },
  ];

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Logo />
        <div className="flex items-center gap-1">
          <CambioDeIdioma />
          <Link href="/ingresar" className={clasesDeBoton("fantasma", "md")}>
            {t.entrar}
          </Link>
        </div>
      </header>

      <main id="contenido" className="flex-1">
        <section className="relative overflow-hidden">
          {/* Reticula tenue de fondo: da profundidad sin competir con el texto. */}
          <div
            aria-hidden
            className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,var(--color-borde)_1px,transparent_1px),linear-gradient(to_bottom,var(--color-borde)_1px,transparent_1px)] [mask-image:radial-gradient(ellipse_60%_55%_at_50%_0%,black,transparent)] bg-[size:48px_48px] opacity-60"
          />
          <div className="mx-auto flex max-w-3xl flex-col items-center px-4 pt-16 pb-20 text-center sm:px-6 sm:pt-24">
            <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-borde bg-superficie px-3 py-1 text-xs text-suave shadow-xs">
              <span className="size-1.5 rounded-full bg-ok" aria-hidden />
              {t.hechoPor}
            </span>
            <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
              {t.lema}
            </h1>
            <p className="mt-5 max-w-xl text-base text-pretty text-suave sm:text-lg">
              {t.sublema}
            </p>
            <div className="mt-9 flex w-full max-w-sm flex-col gap-3 sm:w-auto sm:max-w-none sm:flex-row sm:items-start">
              <BotonDemo className="sm:w-52" />
              <Link
                href="/ingresar"
                className={clasesDeBoton("secundario", "lg", "sm:w-40")}
              >
                {t.entrar}
              </Link>
            </div>
            <p className="mt-4 text-xs text-suave">{t.demoAclaracion}</p>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
          <ul className="grid gap-px overflow-hidden rounded-2xl border border-borde bg-borde sm:grid-cols-2 lg:grid-cols-3">
            {rasgos.map(({ icono: Icono, titulo, texto }) => (
              <li key={titulo} className="bg-superficie p-6">
                <span className="inline-flex size-9 items-center justify-center rounded-lg bg-marca-suave text-marca-texto">
                  <Icono size={18} aria-hidden />
                </span>
                <h2 className="mt-4 text-sm font-semibold">{titulo}</h2>
                <p className="mt-1 text-sm text-suave">{texto}</p>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="border-t border-borde">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-6 text-xs text-suave sm:px-6">
          <span>© {new Date().getFullYear()} StockARG</span>
          <span>{t.hechoPor}</span>
        </div>
      </footer>
    </div>
  );
}
