"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useTextos } from "@/i18n/proveedor";
import { descargar, ErrorDeApi, pedir } from "@/lib/api";
import { numero, pesos } from "@/lib/formato";

type Producto = {
  id: number;
  nombre: string;
  codigo_barra: string | null;
  precio_venta: string;
  stock_actual: number;
};

type MedioDePago = {
  id: number;
  nombre: string;
  es_efectivo: boolean;
};

type Linea = { producto: Producto; cantidad: number };

type VentaHecha = { id: number; total: string; vuelto: string | null };

// Un codigo de barras es una tira larga de digitos: el lector la tipea
// entera y manda Enter.
const PARECE_CODIGO = /^\d{8,14}$/;

export default function Vender() {
  const { t, idioma } = useTextos();
  const buscador = useRef<HTMLInputElement>(null);

  const [busqueda, setBusqueda] = useState("");
  const [resultados, setResultados] = useState<Producto[]>([]);
  const [lineas, setLineas] = useState<Linea[]>([]);
  const [medios, setMedios] = useState<MedioDePago[]>([]);
  const [idMedio, setIdMedio] = useState<number | null>(null);
  const [recibido, setRecibido] = useState("");
  const [cobrando, setCobrando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hecha, setHecha] = useState<VentaHecha | null>(null);

  useEffect(() => {
    pedir<MedioDePago[]>("/medios-pago")
      .then((lista) => {
        setMedios(lista);
        setIdMedio((lista.find((m) => m.es_efectivo) ?? lista[0])?.id ?? null);
      })
      .catch(() => setError(t.errorGenerico));
  }, [t.errorGenerico]);

  // Busqueda en vivo (RF-E03): espera a que se deje de tipear para no
  // disparar una peticion por letra.
  useEffect(() => {
    const texto = busqueda.trim();
    if (texto.length < 2 || PARECE_CODIGO.test(texto)) return;
    let vigente = true;
    const espera = setTimeout(() => {
      pedir<{ items: Producto[] }>(
        `/productos?busqueda=${encodeURIComponent(texto)}&limite=8`,
      )
        .then((pagina) => {
          if (vigente) setResultados(pagina.items);
        })
        .catch(() => {
          if (vigente) setResultados([]);
        });
    }, 250);
    return () => {
      vigente = false;
      clearTimeout(espera);
    };
  }, [busqueda]);

  const total = useMemo(
    () =>
      lineas.reduce(
        (suma, linea) =>
          suma + Number(linea.producto.precio_venta) * linea.cantidad,
        0,
      ),
    [lineas],
  );

  const medio = medios.find((m) => m.id === idMedio) ?? null;
  const vuelto = recibido ? Number(recibido) - total : null;

  function cambiarBusqueda(valor: string) {
    setBusqueda(valor);
    const texto = valor.trim();
    // Con menos de dos letras, o con un codigo de barras, no hay nada
    // que sugerir: la lista se vacia en el acto.
    if (texto.length < 2 || PARECE_CODIGO.test(texto)) setResultados([]);
  }

  function agregar(producto: Producto) {
    setError(null);
    setHecha(null);
    setLineas((actuales) => {
      const existente = actuales.find((l) => l.producto.id === producto.id);
      const enTicket = existente?.cantidad ?? 0;
      if (enTicket >= producto.stock_actual) {
        setError(`${producto.nombre}: ${t.sinStock}`);
        return actuales;
      }
      if (existente) {
        return actuales.map((l) =>
          l.producto.id === producto.id
            ? { ...l, cantidad: l.cantidad + 1 }
            : l,
        );
      }
      return [...actuales, { producto, cantidad: 1 }];
    });
    setBusqueda("");
    setResultados([]);
    buscador.current?.focus();
  }

  function cambiarCantidad(id: number, delta: number) {
    setLineas((actuales) =>
      actuales
        .map((l) =>
          l.producto.id === id
            ? {
                ...l,
                cantidad: Math.min(
                  l.producto.stock_actual,
                  Math.max(0, l.cantidad + delta),
                ),
              }
            : l,
        )
        .filter((l) => l.cantidad > 0),
    );
  }

  async function buscarPorCodigo(codigo: string) {
    try {
      agregar(
        await pedir<Producto>(`/productos/codigo/${encodeURIComponent(codigo)}`),
      );
    } catch (falla) {
      setError(falla instanceof ErrorDeApi ? falla.message : t.errorGenerico);
      setBusqueda("");
    }
  }

  function alPresionarEnBusqueda(evento: React.KeyboardEvent) {
    if (evento.key !== "Enter") return;
    evento.preventDefault();
    const texto = busqueda.trim();
    if (PARECE_CODIGO.test(texto)) {
      buscarPorCodigo(texto);
    } else if (resultados[0]) {
      agregar(resultados[0]);
    }
  }

  const vaciar = useCallback(() => {
    setLineas([]);
    setRecibido("");
    setError(null);
    setBusqueda("");
    buscador.current?.focus();
  }, []);

  const cobrar = useCallback(async () => {
    if (lineas.length === 0 || !medio || cobrando) return;
    if (medio.es_efectivo && recibido && Number(recibido) < total) {
      setError(t.recibidoInsuficiente);
      return;
    }

    setCobrando(true);
    setError(null);
    try {
      // El total no viaja: lo calcula el servidor con los precios de
      // lista, y un total enviado se rechaza.
      const venta = await pedir<VentaHecha>("/ventas", {
        method: "POST",
        cuerpo: {
          items: lineas.map((l) => ({
            id_producto: l.producto.id,
            cantidad: l.cantidad,
          })),
          id_medio_pago: medio.id,
          recibido:
            medio.es_efectivo && recibido
              ? Number(recibido).toFixed(2)
              : undefined,
        },
      });
      setHecha(venta);
      setLineas([]);
      setRecibido("");
    } catch (falla) {
      setError(falla instanceof ErrorDeApi ? falla.message : t.errorGenerico);
    } finally {
      setCobrando(false);
      buscador.current?.focus();
    }
  }, [cobrando, lineas, medio, recibido, total, t]);

  // Atajos de teclado (RF-E16): se cobra sin tocar el mouse.
  useEffect(() => {
    function alPresionar(evento: KeyboardEvent) {
      if (evento.key === "F2") {
        evento.preventDefault();
        buscador.current?.focus();
      } else if (evento.key === "F9") {
        evento.preventDefault();
        cobrar();
      } else if (evento.key === "Escape") {
        vaciar();
      }
    }
    window.addEventListener("keydown", alPresionar);
    return () => window.removeEventListener("keydown", alPresionar);
  }, [cobrar, vaciar]);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <section className="flex flex-col gap-4">
        <h1 className="text-2xl font-bold">{t.vender}</h1>

        <div className="relative">
          <label htmlFor="buscador" className="sr-only">
            {t.buscarProducto}
          </label>
          <input
            id="buscador"
            ref={buscador}
            value={busqueda}
            onChange={(e) => cambiarBusqueda(e.target.value)}
            onKeyDown={alPresionarEnBusqueda}
            placeholder={t.buscarProducto}
            autoComplete="off"
            role="combobox"
            aria-expanded={resultados.length > 0}
            aria-controls="resultados"
            className="w-full rounded-lg border border-borde bg-superficie px-4 py-3 text-base"
          />
          {resultados.length > 0 && (
            <ul
              id="resultados"
              role="listbox"
              className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-borde bg-superficie shadow-lg"
            >
              {resultados.map((producto) => (
                <li key={producto.id} role="option" aria-selected={false}>
                  <button
                    type="button"
                    onClick={() => agregar(producto)}
                    disabled={producto.stock_actual <= 0}
                    className="flex w-full justify-between gap-4 px-4 py-2 text-left hover:bg-fondo disabled:opacity-50"
                  >
                    <span className="truncate">{producto.nombre}</span>
                    <span className="shrink-0 text-sm text-suave">
                      {pesos(producto.precio_venta, idioma)} ·{" "}
                      {producto.stock_actual > 0
                        ? `${numero(producto.stock_actual, idioma)} ${t.disponibles}`
                        : t.sinStock}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <p className="text-xs text-suave">{t.atajos}</p>

        {error && (
          <p role="alert" className="rounded-lg bg-superficie p-3 text-alerta">
            {error}
          </p>
        )}

        {hecha && (
          <div
            role="status"
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ok bg-superficie p-4"
          >
            <p>
              <strong>
                {t.ventaRegistrada} #{hecha.id}
              </strong>{" "}
              — {t.total} {pesos(hecha.total, idioma)}
              {hecha.vuelto && Number(hecha.vuelto) > 0
                ? ` · ${t.vuelto} ${pesos(hecha.vuelto, idioma)}`
                : ""}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() =>
                  descargar(
                    `/ventas/${hecha.id}/comprobante`,
                    `comprobante-${hecha.id}.pdf`,
                  ).catch((falla) =>
                    setError(
                      falla instanceof ErrorDeApi
                        ? falla.message
                        : t.errorGenerico,
                    ),
                  )
                }
                className="rounded-lg border border-borde px-3 py-1.5 text-sm"
              >
                {t.comprobante}
              </button>
              <button
                type="button"
                onClick={() => setHecha(null)}
                className="rounded-lg bg-marca-500 px-3 py-1.5 text-sm text-white"
              >
                {t.nuevaVenta}
              </button>
            </div>
          </div>
        )}
      </section>

      <aside
        aria-label={t.ticket}
        className="flex flex-col gap-4 rounded-xl border border-borde bg-superficie p-4"
      >
        <h2 className="font-semibold">{t.ticket}</h2>

        {lineas.length === 0 ? (
          <p className="text-sm text-suave">{t.ticketVacio}</p>
        ) : (
          <ul className="divide-y divide-borde">
            {lineas.map((linea) => (
              <li key={linea.producto.id} className="flex flex-col gap-1 py-2">
                <div className="flex justify-between gap-2">
                  <span className="truncate">{linea.producto.nombre}</span>
                  <span className="shrink-0 font-medium">
                    {pesos(
                      Number(linea.producto.precio_venta) * linea.cantidad,
                      idioma,
                    )}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <button
                    type="button"
                    aria-label={`${t.restar}: ${linea.producto.nombre}`}
                    onClick={() => cambiarCantidad(linea.producto.id, -1)}
                    className="h-7 w-7 rounded border border-borde"
                  >
                    −
                  </button>
                  <span className="w-8 text-center">{linea.cantidad}</span>
                  <button
                    type="button"
                    aria-label={`${t.sumar}: ${linea.producto.nombre}`}
                    onClick={() => cambiarCantidad(linea.producto.id, 1)}
                    disabled={linea.cantidad >= linea.producto.stock_actual}
                    className="h-7 w-7 rounded border border-borde disabled:opacity-40"
                  >
                    +
                  </button>
                  <span className="text-suave">
                    × {pesos(linea.producto.precio_venta, idioma)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}

        <p
          aria-live="polite"
          className="flex justify-between border-t border-borde pt-3 text-xl font-bold"
        >
          <span>{t.total}</span>
          <span>{pesos(total, idioma)}</span>
        </p>

        <label className="flex flex-col gap-1 text-sm">
          {t.medioDePago}
          <select
            value={idMedio ?? ""}
            onChange={(e) => setIdMedio(Number(e.target.value))}
            className="rounded-lg border border-borde bg-superficie px-3 py-2"
          >
            {medios.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nombre}
              </option>
            ))}
          </select>
        </label>

        {medio?.es_efectivo && (
          <label className="flex flex-col gap-1 text-sm">
            {t.recibido}
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              value={recibido}
              onChange={(e) => setRecibido(e.target.value)}
              className="rounded-lg border border-borde bg-superficie px-3 py-2"
            />
            {vuelto !== null && vuelto >= 0 && (
              <span className="text-suave">
                {t.vuelto}: {pesos(vuelto, idioma)}
              </span>
            )}
          </label>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={vaciar}
            disabled={lineas.length === 0}
            className="rounded-lg border border-borde px-3 py-2 text-sm disabled:opacity-50"
          >
            {t.vaciar}
          </button>
          <button
            type="button"
            onClick={cobrar}
            disabled={lineas.length === 0 || cobrando || !medio}
            className="flex-1 rounded-lg bg-marca-500 px-4 py-2 font-medium text-white hover:bg-marca-700 disabled:opacity-50"
          >
            {cobrando ? t.cobrando : `${t.cobrar} (F9)`}
          </button>
        </div>
      </aside>
    </div>
  );
}
