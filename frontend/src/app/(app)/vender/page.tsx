"use client";

import {
  CircleCheck,
  FileText,
  Minus,
  Plus,
  ScanBarcode,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton, BotonIcono } from "@/componentes/ui/Boton";
import { Campo, claseDeEntrada } from "@/componentes/ui/Campo";
import { Buscador } from "@/componentes/ui/Controles";
import { Alerta, EstadoVacio } from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { formatear } from "@/i18n/textos";
import {
  consulta,
  descargar,
  mensajeDe,
  pedir,
  type Pagina,
} from "@/lib/api";
import { numero, pesos } from "@/lib/formato";
import { useConsulta, useDemora } from "@/lib/ganchos";

type Producto = {
  id: number;
  nombre: string;
  codigo_barra: string | null;
  precio_venta: string;
  stock_actual: number;
};

type MedioDePago = { id: number; nombre: string; es_efectivo: boolean };

type Cliente = { id: number; nombre: string; apellido: string | null };

type Linea = { producto: Producto; cantidad: number };

type VentaHecha = { id: number; total: string; vuelto: string | null };

// Un codigo de barras es una tira larga de digitos: el lector la tipea
// entera y manda Enter.
const PARECE_CODIGO = /^\d{8,14}$/;

function nombreDe(cliente: Cliente) {
  return cliente.apellido
    ? `${cliente.nombre} ${cliente.apellido}`
    : cliente.nombre;
}

/** Eleccion opcional del cliente de la venta (RF-E07). */
function ElegirCliente({
  cliente,
  alElegir,
}: {
  cliente: Cliente | null;
  alElegir: (cliente: Cliente | null) => void;
}) {
  const { t } = useTextos();
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const buscado = useDemora(texto.trim(), 250);
  const { datos, alDia } = useConsulta<Pagina<Cliente>>(
    abierto && buscado.length >= 2
      ? `/clientes${consulta({ busqueda: buscado, limite: 6 })}`
      : null,
  );
  const opciones =
    alDia && buscado === texto.trim() ? (datos?.items ?? []) : [];

  if (cliente) {
    return (
      <div className="flex h-9 items-center justify-between gap-2 rounded-lg border border-borde bg-sutil/60 pr-1 pl-3 text-sm">
        <span className="flex min-w-0 items-center gap-2">
          <UserRound size={15} className="shrink-0 text-suave" aria-hidden />
          <span className="truncate">{nombreDe(cliente)}</span>
        </span>
        <BotonIcono
          etiqueta={t.quitarCliente}
          icono={X}
          onClick={() => alElegir(null)}
        />
      </div>
    );
  }

  if (!abierto) {
    return (
      <button
        type="button"
        onClick={() => setAbierto(true)}
        className={`${claseDeEntrada} flex items-center gap-2 text-left text-suave`}
      >
        <UserRound size={15} aria-hidden />
        {t.consumidorFinal}
      </button>
    );
  }

  return (
    <div className="relative">
      <Buscador
        autoFocus
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            setAbierto(false);
          }
        }}
        onBlur={() => setTimeout(() => setAbierto(false), 150)}
        placeholder={t.buscarCliente}
        aria-label={t.buscarCliente}
      />
      {opciones.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-borde bg-superficie py-1 shadow-flotante">
          {opciones.map((opcion) => (
            <li key={opcion.id}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  alElegir(opcion);
                  setAbierto(false);
                  setTexto("");
                }}
                className="w-full px-3 py-2 text-left text-sm hover:bg-sutil"
              >
                {nombreDe(opcion)}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Vender() {
  const { t, idioma } = useTextos();
  const { avisar } = useAvisos();
  const buscador = useRef<HTMLInputElement>(null);

  const [busqueda, setBusqueda] = useState("");
  const [resaltado, setResaltado] = useState(0);
  const [lineas, setLineas] = useState<Linea[]>([]);
  const [idMedio, setIdMedio] = useState<number | null>(null);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [descuento, setDescuento] = useState("");
  const [recibido, setRecibido] = useState("");
  const [cobrando, setCobrando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hecha, setHecha] = useState<VentaHecha | null>(null);

  const { datos: medios } = useConsulta<MedioDePago[]>(
    "/medios-pago?solo_activos=true",
  );
  const listaDeMedios = useMemo(() => medios ?? [], [medios]);
  // Si no se eligio nada, queda el efectivo (o el primero que haya).
  const medio =
    listaDeMedios.find((m) => m.id === idMedio) ??
    listaDeMedios.find((m) => m.es_efectivo) ??
    listaDeMedios[0] ??
    null;

  // Busqueda en vivo (RF-E03): espera a que se deje de tipear para no
  // disparar una peticion por letra.
  const texto = useDemora(busqueda.trim(), 200);
  const buscando = texto.length >= 2 && !PARECE_CODIGO.test(texto);
  const { datos: encontrados, alDia } = useConsulta<Pagina<Producto>>(
    buscando ? `/productos${consulta({ busqueda: texto, limite: 8 })}` : null,
  );
  // Solo cuentan los resultados del texto que esta escrito ahora: con
  // los de la busqueda anterior, un Enter rapido agregaria otro producto.
  const vigentes = buscando && alDia && texto === busqueda.trim();
  const resultados = vigentes ? (encontrados?.items ?? []) : [];

  const subtotal = useMemo(
    () =>
      lineas.reduce(
        (suma, linea) =>
          suma + Number(linea.producto.precio_venta) * linea.cantidad,
        0,
      ),
    [lineas],
  );
  const montoDescuento = Math.min(subtotal, Math.max(0, Number(descuento) || 0));
  const total = subtotal - montoDescuento;
  const vuelto = recibido ? Number(recibido) - total : null;

  function cambiarBusqueda(valor: string) {
    setBusqueda(valor);
    setResaltado(0);
  }

  const agregar = useCallback(
    (producto: Producto) => {
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
      buscador.current?.focus();
    },
    [t.sinStock],
  );

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
        await pedir<Producto>(
          `/productos/codigo/${encodeURIComponent(codigo)}`,
        ),
      );
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
      setBusqueda("");
    }
  }

  function alPresionarEnBusqueda(evento: React.KeyboardEvent) {
    if (evento.key === "ArrowDown" && resultados.length > 0) {
      evento.preventDefault();
      setResaltado((r) => (r + 1) % resultados.length);
    } else if (evento.key === "ArrowUp" && resultados.length > 0) {
      evento.preventDefault();
      setResaltado((r) => (r - 1 + resultados.length) % resultados.length);
    } else if (evento.key === "Enter") {
      evento.preventDefault();
      const escrito = busqueda.trim();
      if (PARECE_CODIGO.test(escrito)) {
        buscarPorCodigo(escrito);
      } else if (resultados[resaltado]) {
        agregar(resultados[resaltado]);
      }
    }
  }

  const vaciar = useCallback(() => {
    setLineas([]);
    setRecibido("");
    setDescuento("");
    setCliente(null);
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
          id_cliente: cliente?.id,
          descuento: montoDescuento > 0 ? montoDescuento.toFixed(2) : undefined,
          recibido:
            medio.es_efectivo && recibido
              ? Number(recibido).toFixed(2)
              : undefined,
        },
      });
      setHecha(venta);
      avisar(formatear(t.ventaRegistrada, { id: venta.id }));
      setLineas([]);
      setRecibido("");
      setDescuento("");
      setCliente(null);
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
    } finally {
      setCobrando(false);
      buscador.current?.focus();
    }
  }, [
    avisar,
    cliente,
    cobrando,
    lineas,
    medio,
    montoDescuento,
    recibido,
    total,
    t,
  ]);

  // Atajos de teclado (RF-E16): se cobra sin tocar el mouse.
  useEffect(() => {
    function alPresionar(evento: KeyboardEvent) {
      if (evento.key === "F2") {
        evento.preventDefault();
        buscador.current?.focus();
      } else if (evento.key === "F9") {
        evento.preventDefault();
        cobrar();
      } else if (evento.key === "Escape" && !document.querySelector("dialog[open]")) {
        vaciar();
      }
    }
    window.addEventListener("keydown", alPresionar);
    return () => window.removeEventListener("keydown", alPresionar);
  }, [cobrar, vaciar]);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
      <section className="flex min-w-0 flex-col gap-4">
        <div className="flex items-end justify-between gap-3">
          <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">
            {t.vender}
          </h1>
          <p className="hidden text-xs text-suave sm:block">{t.atajos}</p>
        </div>

        <div className="relative">
          <label htmlFor="buscador" className="sr-only">
            {t.buscarProducto}
          </label>
          <div className="relative">
            <ScanBarcode
              size={18}
              aria-hidden
              className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-suave"
            />
            <input
              id="buscador"
              ref={buscador}
              value={busqueda}
              onChange={(e) => cambiarBusqueda(e.target.value)}
              onKeyDown={alPresionarEnBusqueda}
              placeholder={t.buscarProducto}
              autoComplete="off"
              autoFocus
              role="combobox"
              aria-expanded={resultados.length > 0}
              aria-controls="resultados"
              aria-activedescendant={
                resultados[resaltado]
                  ? `resultado-${resultados[resaltado].id}`
                  : undefined
              }
              className={`${claseDeEntrada} h-12 rounded-xl pl-11 text-base`}
            />
          </div>
          {resultados.length > 0 && (
            <ul
              id="resultados"
              role="listbox"
              className="aparecer absolute z-20 mt-1.5 w-full overflow-hidden rounded-xl border border-borde bg-superficie py-1 shadow-flotante"
            >
              {resultados.map((producto, i) => (
                <li
                  key={producto.id}
                  id={`resultado-${producto.id}`}
                  role="option"
                  aria-selected={i === resaltado}
                  aria-disabled={producto.stock_actual <= 0}
                >
                  <button
                    type="button"
                    tabIndex={-1}
                    onMouseEnter={() => setResaltado(i)}
                    onClick={() => agregar(producto)}
                    disabled={producto.stock_actual <= 0}
                    className={`flex w-full items-center justify-between gap-4 px-4 py-2.5 text-left disabled:opacity-50 ${
                      i === resaltado ? "bg-sutil" : ""
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">
                        {producto.nombre}
                      </span>
                      {producto.codigo_barra && (
                        <span className="block font-mono text-xs text-suave">
                          {producto.codigo_barra}
                        </span>
                      )}
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="cifra block text-sm font-medium">
                        {pesos(producto.precio_venta, idioma)}
                      </span>
                      <span className="block text-xs text-suave">
                        {producto.stock_actual > 0
                          ? formatear(t.disponibles, {
                              n: numero(producto.stock_actual, idioma),
                            })
                          : t.sinStock}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {vigentes && encontrados && encontrados.items.length === 0 && (
              <p className="mt-2 text-sm text-suave">{t.sinResultados}</p>
            )}
        </div>

        {error && <Alerta>{error}</Alerta>}

        {hecha && (
          <div
            role="status"
            className="aparecer flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ok/30 bg-ok-suave p-4"
          >
            <p className="flex items-center gap-2 text-sm">
              <CircleCheck size={18} className="text-ok" aria-hidden />
              <span>
                <strong className="font-semibold">
                  {formatear(t.ventaRegistrada, { id: hecha.id })}
                </strong>{" "}
                · {pesos(hecha.total, idioma)}
                {hecha.vuelto && Number(hecha.vuelto) > 0
                  ? ` · ${t.vuelto} ${pesos(hecha.vuelto, idioma)}`
                  : ""}
              </span>
            </p>
            <div className="flex gap-2">
              <Boton
                tamano="sm"
                icono={FileText}
                onClick={() =>
                  descargar(
                    `/ventas/${hecha.id}/comprobante`,
                    `comprobante-${hecha.id}.pdf`,
                  ).catch((falla) =>
                    setError(mensajeDe(falla, t.errorGenerico)),
                  )
                }
              >
                {t.comprobante}
              </Boton>
              <Boton
                tamano="sm"
                variante="primario"
                onClick={() => setHecha(null)}
              >
                {t.nuevaVenta}
              </Boton>
            </div>
          </div>
        )}

        <div className="rounded-xl border border-borde bg-superficie shadow-xs">
          {lineas.length === 0 ? (
            <EstadoVacio icono={ScanBarcode} titulo={t.ticketVacio} />
          ) : (
            <ul className="divide-y divide-borde">
              {lineas.map((linea) => (
                <li
                  key={linea.producto.id}
                  className="flex items-center gap-3 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {linea.producto.nombre}
                    </p>
                    <p className="cifra text-xs text-suave">
                      {pesos(linea.producto.precio_venta, idioma)}
                    </p>
                  </div>
                  <div className="flex items-center rounded-lg border border-borde">
                    <BotonIcono
                      etiqueta={`${t.restar}: ${linea.producto.nombre}`}
                      icono={Minus}
                      onClick={() => cambiarCantidad(linea.producto.id, -1)}
                    />
                    <span className="cifra w-8 text-center text-sm font-medium">
                      {linea.cantidad}
                    </span>
                    <BotonIcono
                      etiqueta={`${t.sumar}: ${linea.producto.nombre}`}
                      icono={Plus}
                      onClick={() => cambiarCantidad(linea.producto.id, 1)}
                      disabled={linea.cantidad >= linea.producto.stock_actual}
                    />
                  </div>
                  <p className="cifra w-24 text-right text-sm font-semibold">
                    {pesos(
                      Number(linea.producto.precio_venta) * linea.cantidad,
                      idioma,
                    )}
                  </p>
                  <BotonIcono
                    etiqueta={`${t.quitar}: ${linea.producto.nombre}`}
                    icono={Trash2}
                    onClick={() =>
                      cambiarCantidad(linea.producto.id, -linea.cantidad)
                    }
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <aside
        aria-label={t.ticket}
        className="flex h-fit flex-col gap-5 rounded-xl border border-borde bg-superficie p-5 shadow-xs lg:sticky lg:top-6"
      >
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-medium">{t.cliente}</span>
          <ElegirCliente cliente={cliente} alElegir={setCliente} />
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-medium">{t.medioDePago}</span>
          {listaDeMedios.length === 0 && medios ? (
            <p className="text-sm text-alerta">{t.sinMediosDePago}</p>
          ) : (
            <div
              role="radiogroup"
              aria-label={t.medioDePago}
              className="grid grid-cols-2 gap-1.5"
            >
              {listaDeMedios.map((m) => {
                const elegido = medio?.id === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    role="radio"
                    aria-checked={elegido}
                    onClick={() => setIdMedio(m.id)}
                    className={`h-9 truncate rounded-lg border px-2 text-[13px] font-medium transition-colors ${
                      elegido
                        ? "border-marca bg-marca-suave text-marca-texto"
                        : "border-borde text-suave hover:bg-sutil hover:text-texto"
                    }`}
                  >
                    {m.nombre}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <Campo
          etiqueta={t.descuentoGeneral}
          opcional
          type="number"
          inputMode="decimal"
          min="0"
          step="0.01"
          value={descuento}
          onChange={(e) => setDescuento(e.target.value)}
        />

        {medio?.es_efectivo && (
          <Campo
            etiqueta={t.recibido}
            type="number"
            inputMode="decimal"
            min="0"
            step="0.01"
            value={recibido}
            onChange={(e) => setRecibido(e.target.value)}
            ayuda={
              vuelto !== null && vuelto >= 0
                ? `${t.vuelto}: ${pesos(vuelto, idioma)}`
                : undefined
            }
            error={
              vuelto !== null && vuelto < 0 ? t.recibidoInsuficiente : null
            }
          />
        )}

        <dl className="flex flex-col gap-1.5 border-t border-borde pt-4 text-sm">
          <div className="flex justify-between text-suave">
            <dt>{t.subtotal}</dt>
            <dd className="cifra">{pesos(subtotal, idioma)}</dd>
          </div>
          {montoDescuento > 0 && (
            <div className="flex justify-between text-suave">
              <dt>{t.descuento}</dt>
              <dd className="cifra">−{pesos(montoDescuento, idioma)}</dd>
            </div>
          )}
          <div
            aria-live="polite"
            className="mt-1 flex items-baseline justify-between"
          >
            <dt className="font-medium">{t.total}</dt>
            <dd className="cifra text-3xl font-semibold tracking-tight">
              {pesos(total, idioma)}
            </dd>
          </div>
        </dl>

        <div className="flex gap-2">
          <Boton onClick={vaciar} disabled={lineas.length === 0}>
            {t.vaciar}
          </Boton>
          <Boton
            variante="primario"
            tamano="lg"
            className="flex-1"
            onClick={cobrar}
            disabled={lineas.length === 0 || !medio}
            cargando={cobrando}
          >
            {cobrando ? t.cobrando : t.cobrar}
            {!cobrando && (
              <kbd className="rounded bg-white/15 px-1.5 py-0.5 font-mono text-[11px]">
                F9
              </kbd>
            )}
          </Boton>
        </div>
      </aside>
    </div>
  );
}
