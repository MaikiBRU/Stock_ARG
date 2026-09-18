"use client";

import { createContext, useContext, type ReactNode } from "react";

import { textosDe, type Idioma, type Textos } from "@/i18n/textos";

const Contexto = createContext<{ idioma: Idioma; t: Textos }>({
  idioma: "es",
  t: textosDe("es"),
});

/** Pone los textos del idioma elegido al alcance de las pantallas. */
export function ProveedorDeIdioma({
  idioma,
  children,
}: {
  idioma: Idioma;
  children: ReactNode;
}) {
  return (
    <Contexto.Provider value={{ idioma, t: textosDe(idioma) }}>
      {children}
    </Contexto.Provider>
  );
}

/** Textos del idioma en curso. */
export function useTextos() {
  return useContext(Contexto);
}
