"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorDeApi, pedir } from "@/lib/api";

type Resultado<T> = {
  clave: string | null;
  datos: T | null;
  error: ErrorDeApi | null;
};

/**
 * Trae una ruta de la API y la vuelve a traer cuando cambia.
 *
 * Con `ruta` en null no pide nada. El estado de carga no se guarda
 * aparte: se deduce de que la respuesta en mano sea de otra ruta, asi
 * que nunca queda desfasado de lo que se esta mostrando.
 */
export function useConsulta<T>(ruta: string | null) {
  const [version, setVersion] = useState(0);
  const [resultado, setResultado] = useState<Resultado<T>>({
    clave: null,
    datos: null,
    error: null,
  });
  const clave = ruta === null ? null : `${ruta}#${version}`;

  useEffect(() => {
    if (ruta === null || clave === null) return;
    let vigente = true;
    pedir<T>(ruta)
      .then((datos) => {
        if (vigente) setResultado({ clave, datos, error: null });
      })
      .catch((falla: unknown) => {
        if (!vigente) return;
        setResultado((anterior) => ({
          clave,
          // Si falla una recarga, lo que ya se veia se conserva.
          datos: anterior.datos,
          error:
            falla instanceof ErrorDeApi
              ? falla
              : new ErrorDeApi(0, null, String(falla)),
        }));
      });
    return () => {
      vigente = false;
    };
  }, [ruta, clave]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);

  return {
    datos: resultado.datos,
    error: resultado.clave === clave ? resultado.error : null,
    cargando: ruta !== null && resultado.clave !== clave,
    // True si los datos en mano son de esta ruta y no de la anterior:
    // una busqueda no puede actuar sobre resultados de otro texto.
    alDia: ruta !== null && resultado.clave === clave,
    recargar,
  };
}

/** El valor, pero recien cuando deja de cambiar por `ms` milisegundos. */
export function useDemora<T>(valor: T, ms = 300) {
  const [demorado, setDemorado] = useState(valor);
  useEffect(() => {
    const espera = setTimeout(() => setDemorado(valor), ms);
    return () => clearTimeout(espera);
  }, [valor, ms]);
  return demorado;
}
