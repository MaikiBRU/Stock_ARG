"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { CambioDeIdioma, Logo } from "@/componentes/Idioma";
import { useTextos } from "@/i18n/proveedor";
import { mensajeDe, pedir } from "@/lib/api";
import { inicioPara, type Rol } from "@/lib/rutas";
import { marcarSesion } from "@/lib/sesion";

/** Lo que devuelve la API al abrir una sesion. */
export type Token = {
  expira_en_minutos: number;
  usuario: { rol: Rol };
};

/** Deja la marca de sesion y lleva a la pantalla que le toca al rol. */
export function useEntrar() {
  const router = useRouter();
  return useCallback(
    (sesion: Token) => {
      marcarSesion(sesion.expira_en_minutos);
      router.push(inicioPara(sesion.usuario.rol));
    },
    [router],
  );
}

/** Marco comun de las pantallas de acceso: centrado y sin distracciones. */
export function MarcoDeAcceso({
  titulo,
  texto,
  children,
  pie,
}: {
  titulo: string;
  texto?: ReactNode;
  children: ReactNode;
  pie?: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/" className="rounded-md">
          <Logo />
        </Link>
        <CambioDeIdioma />
      </header>
      <main
        id="contenido"
        className="flex flex-1 items-start justify-center px-4 pt-8 pb-16 sm:items-center sm:pt-0"
      >
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
          {texto && <p className="mt-1.5 text-sm text-suave">{texto}</p>}
          <div className="mt-7">{children}</div>
          {pie && (
            <div className="mt-8 flex flex-col items-center gap-2 text-sm text-suave">
              {pie}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

/** Separador "o" entre dos formas de entrar. */
export function Separador() {
  const { t } = useTextos();
  return (
    <div className="my-5 flex items-center gap-3 text-xs text-suave">
      <span className="h-px flex-1 bg-borde" />
      {t.o}
      <span className="h-px flex-1 bg-borde" />
    </div>
  );
}

const ID_DE_GOOGLE = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

/** True si el sitio ofrece entrar con Google. */
export const HAY_GOOGLE = Boolean(ID_DE_GOOGLE);

type Google = {
  accounts: {
    id: {
      initialize: (opciones: {
        client_id: string;
        callback: (respuesta: { credential: string }) => void;
      }) => void;
      renderButton: (
        elemento: HTMLElement,
        opciones: Record<string, string | number>,
      ) => void;
    };
  };
};

/**
 * Boton oficial de Google (RF-A06). Solo aparece si el sitio tiene un
 * client id configurado; sin el, la API igual responderia 503.
 */
export function BotonGoogle() {
  const { t, idioma } = useTextos();
  const entrar = useEntrar();
  const contenedor = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ID_DE_GOOGLE) return;
    const idCliente = ID_DE_GOOGLE;

    function dibujar() {
      const google = (window as unknown as { google?: Google }).google;
      if (!google || !contenedor.current) return;
      google.accounts.id.initialize({
        client_id: idCliente,
        callback: async ({ credential }) => {
          setError(null);
          try {
            entrar(
              await pedir<Token>("/auth/google", {
                method: "POST",
                cuerpo: { credential },
              }),
            );
          } catch (falla) {
            setError(mensajeDe(falla, t.errorGenerico));
          }
        },
      });
      google.accounts.id.renderButton(contenedor.current, {
        theme: "outline",
        size: "large",
        width: contenedor.current.offsetWidth || 320,
        text: "continue_with",
        locale: idioma,
      });
    }

    const existente = document.getElementById("google-gsi");
    if (existente) {
      dibujar();
      return;
    }
    const script = document.createElement("script");
    script.id = "google-gsi";
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = dibujar;
    document.head.appendChild(script);
  }, [entrar, idioma, t.errorGenerico]);

  if (!ID_DE_GOOGLE) return null;

  return (
    <div className="flex flex-col gap-2">
      <div ref={contenedor} className="flex min-h-10 justify-center" />
      {error && (
        <p role="alert" className="text-center text-sm text-alerta">
          {error}
        </p>
      )}
    </div>
  );
}
