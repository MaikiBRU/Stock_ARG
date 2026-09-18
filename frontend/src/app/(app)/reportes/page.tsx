"use client";

import {
  Receipt,
  ShoppingBag,
  TrendingUp,
  TriangleAlert,
  Wallet,
} from "lucide-react";
import { useState } from "react";

import { useUsuario } from "@/componentes/Sesion";
import { Boton } from "@/componentes/ui/Boton";
import { claseDeEntrada } from "@/componentes/ui/Campo";
import { Exportar, Segmentos } from "@/componentes/ui/Controles";
import { BarrasHorizontales, GraficoDeBarras } from "@/componentes/ui/Grafico";
import {
  Alerta,
  EncabezadoDePagina,
  Esqueleto,
  Indicador,
  Tarjeta,
} from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { consulta } from "@/lib/api";
import { diaCorto, fecha, numero, pesos, pesosCortos } from "@/lib/formato";
import { useConsulta } from "@/lib/ganchos";
import { administra } from "@/lib/rutas";

type Periodo = "hoy" | "semana" | "mes" | "fechas";

type Ventas = {
  desde: string;
  hasta: string;
  cantidad_ventas: number;
  total_facturado: string;
  ticket_promedio: string;
};
type Punto = { fecha: string; cantidad_ventas: number; total: string };
type Ranking = {
  ranking: {
    id_producto: number;
    nombre: string;
    unidades: number;
    facturado: string;
  }[];
};
type PorMedio = {
  detalle: {
    id_medio_pago: number;
    nombre: string;
    cantidad_ventas: number;
    total: string;
  }[];
};
type PorCategoria = {
  detalle: {
    id_categoria: number | null;
    nombre: string;
    unidades: number;
    total: string;
  }[];
};
type Compras = { cantidad_compras: number; total_gastado: string };
type Rentabilidad = {
  detalle: {
    id_producto: number;
    nombre: string;
    unidades: number;
    ingreso: string;
    costo: string;
    ganancia: string;
    margen_porcentaje: string | null;
  }[];
  total_ingreso: string;
  total_costo: string;
  ganancia: string;
  advertencia: string;
};

function Vacio() {
  const { t } = useTextos();
  return <p className="py-6 text-center text-sm text-suave">{t.sinDatos}</p>;
}

export default function Reportes() {
  const { t, idioma } = useTextos();
  const usuario = useUsuario();
  const [periodo, setPeriodo] = useState<Periodo>("mes");
  const [borrador, setBorrador] = useState({ desde: "", hasta: "" });
  const [fechas, setFechas] = useState({ desde: "", hasta: "" });
  const [orden, setOrden] = useState<"unidades" | "facturacion">("unidades");

  // Con fechas elegidas a mano, el rango manda; si no, el periodo.
  const rango =
    periodo === "fechas"
      ? consulta({ desde: fechas.desde, hasta: fechas.hasta })
      : consulta({ periodo });
  const listo = periodo !== "fechas" || Boolean(fechas.desde && fechas.hasta);
  const ruta = (base: string, extra = "") =>
    listo ? `${base}${rango}${extra}` : null;
  const union = rango ? "&" : "?";

  const ventas = useConsulta<Ventas>(ruta("/reportes/ventas"));
  const serie = useConsulta<Punto[]>(ruta("/reportes/ventas/serie"));
  const ranking = useConsulta<Ranking>(
    ruta("/reportes/mas-vendidos", `${union}ordenar_por=${orden}&limite=10`),
  );
  const medios = useConsulta<PorMedio>(ruta("/reportes/medios-pago"));
  const categorias = useConsulta<PorCategoria>(ruta("/reportes/categorias"));
  const compras = useConsulta<Compras>(ruta("/reportes/compras"));
  const rentabilidad = useConsulta<Rentabilidad>(
    administra(usuario.rol) ? ruta("/reportes/rentabilidad") : null,
  );

  const error =
    ventas.error ?? serie.error ?? ranking.error ?? medios.error ?? null;

  const exportar = (reporte: string) =>
    `/reportes/exportar?reporte=${reporte}${rango ? `&${rango.slice(1)}` : ""}`;

  return (
    <div className="flex flex-col gap-6">
      <EncabezadoDePagina
        titulo={t.reportes}
        descripcion={
          ventas.datos
            ? `${t.reportesTexto} ${fecha(ventas.datos.desde, idioma)} – ${fecha(ventas.datos.hasta, idioma)}`
            : t.reportesTexto
        }
        acciones={
          <Segmentos
            etiqueta={t.periodo}
            valor={periodo}
            alCambiar={setPeriodo}
            opciones={[
              { valor: "hoy", texto: t.hoy },
              { valor: "semana", texto: t.semana },
              { valor: "mes", texto: t.mes },
              { valor: "fechas", texto: t.personalizado },
            ]}
          />
        }
      />

      {periodo === "fechas" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setFechas(borrador);
          }}
          className="flex flex-wrap items-end gap-3 rounded-xl border border-borde bg-superficie p-3 shadow-xs"
        >
          <label className="flex flex-col gap-1 text-xs text-suave">
            {t.desde}
            <input
              type="date"
              required
              value={borrador.desde}
              max={borrador.hasta || undefined}
              onChange={(e) =>
                setBorrador((b) => ({ ...b, desde: e.target.value }))
              }
              className={`${claseDeEntrada} w-40`}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-suave">
            {t.hasta}
            <input
              type="date"
              required
              value={borrador.hasta}
              min={borrador.desde || undefined}
              onChange={(e) =>
                setBorrador((b) => ({ ...b, hasta: e.target.value }))
              }
              className={`${claseDeEntrada} w-40`}
            />
          </label>
          <Boton type="submit" variante="primario">
            {t.aplicarFechas}
          </Boton>
        </form>
      )}

      {error && (
        <Alerta>{error.estado === 403 ? t.sinPermiso : error.message}</Alerta>
      )}

      {listo && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Indicador
              etiqueta={t.facturado}
              valor={
                ventas.datos
                  ? pesos(ventas.datos.total_facturado, idioma)
                  : "—"
              }
              icono={Wallet}
            />
            <Indicador
              etiqueta={t.cantidadVentas}
              valor={
                ventas.datos
                  ? numero(ventas.datos.cantidad_ventas, idioma)
                  : "—"
              }
              icono={Receipt}
            />
            <Indicador
              etiqueta={t.ticketPromedio}
              valor={
                ventas.datos
                  ? pesos(ventas.datos.ticket_promedio, idioma)
                  : "—"
              }
              icono={TrendingUp}
            />
            <Indicador
              etiqueta={t.gastoEnCompras}
              valor={
                compras.datos ? pesos(compras.datos.total_gastado, idioma) : "—"
              }
              detalle={
                compras.datos
                  ? `${numero(compras.datos.cantidad_compras, idioma)} ${t.compras.toLowerCase()}`
                  : undefined
              }
              icono={ShoppingBag}
              tono="aviso"
            />
          </div>

          <Tarjeta titulo={t.evolucion}>
            {!serie.datos ? (
              <Esqueleto className="h-48" />
            ) : serie.datos.length === 0 ? (
              <Vacio />
            ) : (
              <GraficoDeBarras
                puntos={serie.datos.map((punto) => ({
                  etiqueta: diaCorto(punto.fecha, idioma),
                  valor: Number(punto.total),
                  detalle: `${pesos(punto.total, idioma)} · ${numero(punto.cantidad_ventas, idioma)} ${t.tickets.toLowerCase()}`,
                }))}
                etiquetaDeEje={(valor) => pesosCortos(valor, idioma)}
              />
            )}
          </Tarjeta>

          <div className="grid gap-4 lg:grid-cols-3">
            <Tarjeta
              titulo={t.ranking}
              className="lg:col-span-2"
              accion={
                <div className="flex flex-wrap justify-end gap-2">
                  <Segmentos
                    etiqueta={t.ordenarPor}
                    valor={orden}
                    alCambiar={setOrden}
                    opciones={[
                      { valor: "unidades", texto: t.porUnidades },
                      { valor: "facturacion", texto: t.porFacturacion },
                    ]}
                  />
                  <Exportar
                    ruta={exportar("mas-vendidos")}
                    nombre="mas-vendidos"
                  />
                </div>
              }
            >
              {!ranking.datos ? (
                <Esqueleto className="h-48" />
              ) : ranking.datos.ranking.length === 0 ? (
                <Vacio />
              ) : (
                <BarrasHorizontales
                  filas={ranking.datos.ranking.map((fila) => ({
                    clave: fila.id_producto,
                    etiqueta: fila.nombre,
                    valor:
                      orden === "unidades"
                        ? fila.unidades
                        : Number(fila.facturado),
                    texto: `${numero(fila.unidades, idioma)} ${t.unidades} · ${pesos(fila.facturado, idioma)}`,
                  }))}
                />
              )}
            </Tarjeta>

            <div className="flex flex-col gap-4">
              <Tarjeta
                titulo={t.porMedio}
                accion={
                  <Exportar ruta={exportar("medios-pago")} nombre="medios-pago" />
                }
              >
                {!medios.datos ? (
                  <Esqueleto className="h-24" />
                ) : medios.datos.detalle.length === 0 ? (
                  <Vacio />
                ) : (
                  <BarrasHorizontales
                    filas={medios.datos.detalle.map((fila) => ({
                      clave: fila.id_medio_pago,
                      etiqueta: fila.nombre,
                      valor: Number(fila.total),
                      texto: pesos(fila.total, idioma),
                    }))}
                  />
                )}
              </Tarjeta>
              <Tarjeta
                titulo={t.porCategoria}
                accion={
                  <Exportar ruta={exportar("categorias")} nombre="categorias" />
                }
              >
                {!categorias.datos ? (
                  <Esqueleto className="h-24" />
                ) : categorias.datos.detalle.length === 0 ? (
                  <Vacio />
                ) : (
                  <BarrasHorizontales
                    filas={categorias.datos.detalle.map((fila) => ({
                      clave: fila.id_categoria ?? fila.nombre,
                      etiqueta: fila.nombre,
                      valor: Number(fila.total),
                      texto: pesos(fila.total, idioma),
                    }))}
                  />
                )}
              </Tarjeta>
            </div>
          </div>

          {administra(usuario.rol) && (
            <Tarjeta titulo={t.rentabilidad} sinRelleno>
              {!rentabilidad.datos ? (
                <div className="p-5">
                  <Esqueleto className="h-32" />
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-2 px-5 pb-4">
                    {[
                      { e: t.ingreso, v: rentabilidad.datos.total_ingreso },
                      { e: t.costo, v: rentabilidad.datos.total_costo },
                      { e: t.ganancia, v: rentabilidad.datos.ganancia },
                    ].map((dato) => (
                      <div
                        key={dato.e}
                        className="rounded-lg border border-borde px-3 py-2.5"
                      >
                        <p className="text-xs text-suave">{dato.e}</p>
                        <p className="cifra mt-0.5 font-semibold">
                          {pesos(dato.v, idioma)}
                        </p>
                      </div>
                    ))}
                  </div>
                  {rentabilidad.datos.advertencia && (
                    <p className="mx-5 mb-4 flex items-start gap-2 rounded-lg bg-aviso-suave px-3 py-2 text-xs text-aviso">
                      <TriangleAlert
                        size={14}
                        className="mt-px shrink-0"
                        aria-hidden
                      />
                      {rentabilidad.datos.advertencia}
                    </p>
                  )}
                  {rentabilidad.datos.detalle.length === 0 ? (
                    <Vacio />
                  ) : (
                    <div className="overflow-x-auto border-t border-borde">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-borde text-xs text-suave">
                            <th className="px-5 py-2.5 text-left font-medium">
                              {t.producto}
                            </th>
                            <th className="px-4 py-2.5 text-right font-medium">
                              {t.unidades}
                            </th>
                            <th className="hidden px-4 py-2.5 text-right font-medium sm:table-cell">
                              {t.ingreso}
                            </th>
                            <th className="hidden px-4 py-2.5 text-right font-medium sm:table-cell">
                              {t.costo}
                            </th>
                            <th className="px-4 py-2.5 text-right font-medium">
                              {t.ganancia}
                            </th>
                            <th className="px-5 py-2.5 text-right font-medium">
                              {t.margenPct}
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-borde">
                          {rentabilidad.datos.detalle.map((fila) => (
                            <tr key={fila.id_producto}>
                              <td className="px-5 py-2.5">{fila.nombre}</td>
                              <td className="cifra px-4 py-2.5 text-right">
                                {numero(fila.unidades, idioma)}
                              </td>
                              <td className="cifra hidden px-4 py-2.5 text-right text-suave sm:table-cell">
                                {pesos(fila.ingreso, idioma)}
                              </td>
                              <td className="cifra hidden px-4 py-2.5 text-right text-suave sm:table-cell">
                                {pesos(fila.costo, idioma)}
                              </td>
                              <td className="cifra px-4 py-2.5 text-right font-medium">
                                {pesos(fila.ganancia, idioma)}
                              </td>
                              <td className="cifra px-5 py-2.5 text-right text-suave">
                                {fila.margen_porcentaje !== null
                                  ? `${numero(fila.margen_porcentaje, idioma)}%`
                                  : "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </Tarjeta>
          )}
        </>
      )}
    </div>
  );
}
