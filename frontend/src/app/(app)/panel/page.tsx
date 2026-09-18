"use client";

import {
  CalendarClock,
  CircleAlert,
  Package,
  PackageX,
  Plus,
  Receipt,
  TrendingUp,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { useUsuario } from "@/componentes/Sesion";
import { clasesDeBoton } from "@/componentes/ui/Boton";
import { BarrasHorizontales, GraficoDeBarras } from "@/componentes/ui/Grafico";
import {
  Alerta,
  EncabezadoDePagina,
  Esqueleto,
  Indicador,
  Tarjeta,
} from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { formatear } from "@/i18n/textos";
import { diaCorto, fecha, numero, pesos, pesosCortos } from "@/lib/formato";
import { useConsulta } from "@/lib/ganchos";

type Producto = {
  id: number;
  nombre: string;
  stock_actual: number;
  stock_minimo: number;
  fecha_vencimiento: string | null;
};

type Panel = {
  fecha: string;
  ventas_del_dia: {
    cantidad_ventas: number;
    total_facturado: string;
    ticket_promedio: string;
  };
  medios_de_pago: {
    id_medio_pago: number;
    nombre: string;
    cantidad_ventas: number;
    total: string;
  }[];
  resumen_stock: {
    total: number;
    bajo: number;
    medio: number;
    ok: number;
    sin_stock: number;
  };
  bajo_minimo: Producto[];
  proximos_a_vencer: Producto[];
  vencidos: Producto[];
  mas_vendidos_del_mes: {
    id_producto: number;
    nombre: string;
    unidades: number;
    facturado: string;
  }[];
  serie_ventas: { fecha: string; cantidad_ventas: number; total: string }[];
  rentabilidad_del_mes: string | null;
};

function Vacio({ texto }: { texto: string }) {
  return <p className="py-6 text-center text-sm text-suave">{texto}</p>;
}

function ListaDeAlerta({
  titulo,
  icono: Icono,
  tono,
  productos,
  detalle,
}: {
  titulo: string;
  icono: LucideIcon;
  tono: string;
  productos: Producto[];
  detalle: (producto: Producto) => string;
}) {
  const { t } = useTextos();
  return (
    <Tarjeta
      titulo={
        <span className="flex items-center gap-2">
          <Icono size={15} className={tono} aria-hidden />
          {titulo}
          <span className="cifra font-normal text-suave">
            {productos.length}
          </span>
        </span>
      }
      sinRelleno
    >
      {productos.length === 0 ? (
        <Vacio texto={t.sinDatos} />
      ) : (
        <ul className="divide-y divide-borde pb-1">
          {productos.slice(0, 6).map((producto) => (
            <li
              key={producto.id}
              className="flex items-center justify-between gap-3 px-5 py-2.5 text-sm"
            >
              <span className="truncate">{producto.nombre}</span>
              <span className="cifra shrink-0 text-xs text-suave">
                {detalle(producto)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Tarjeta>
  );
}

export default function Panel() {
  const { t, idioma } = useTextos();
  const usuario = useUsuario();
  const { datos: panel, error } = useConsulta<Panel>("/panel");

  if (error) {
    return (
      <Alerta>{error.estado === 403 ? t.sinPermiso : error.message}</Alerta>
    );
  }

  const nombre = usuario.nombre.split(" ")[0];
  const encabezado = (
    <EncabezadoDePagina
      titulo={formatear(t.hola, { nombre })}
      descripcion={
        panel ? `${t.resumenDeHoy} ${fecha(panel.fecha, idioma)}` : t.cargando
      }
      acciones={
        <Link href="/vender" className={clasesDeBoton("primario")}>
          <Plus size={16} aria-hidden />
          {t.nuevaVenta}
        </Link>
      }
    />
  );

  if (!panel) {
    return (
      <div className="flex flex-col gap-6">
        {encabezado}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Esqueleto key={i} className="h-28 rounded-xl" />
          ))}
        </div>
        <Esqueleto className="h-72 rounded-xl" />
      </div>
    );
  }

  const stock = panel.resumen_stock;
  const tramos = [
    { clave: "ok", valor: stock.ok, texto: t.stockBien, color: "bg-ok" },
    {
      clave: "medio",
      valor: stock.medio,
      texto: t.stockMedio,
      color: "bg-aviso",
    },
    {
      clave: "bajo",
      valor: stock.bajo,
      texto: t.stockBajo,
      color: "bg-alerta",
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {encabezado}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Indicador
          etiqueta={t.ventasDelDia}
          valor={pesos(panel.ventas_del_dia.total_facturado, idioma)}
          icono={Wallet}
        />
        <Indicador
          etiqueta={t.tickets}
          valor={numero(panel.ventas_del_dia.cantidad_ventas, idioma)}
          icono={Receipt}
        />
        <Indicador
          etiqueta={t.ticketPromedio}
          valor={pesos(panel.ventas_del_dia.ticket_promedio, idioma)}
          icono={TrendingUp}
        />
        {panel.rentabilidad_del_mes !== null ? (
          <Indicador
            etiqueta={t.gananciaDelMes}
            valor={pesos(panel.rentabilidad_del_mes, idioma)}
            icono={TrendingUp}
            tono="ok"
          />
        ) : (
          <Indicador
            etiqueta={t.productosActivos}
            valor={numero(stock.total, idioma)}
            icono={Package}
          />
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Tarjeta titulo={t.ventasUltimosDias} className="lg:col-span-2">
          {panel.serie_ventas.length === 0 ? (
            <Vacio texto={t.sinDatos} />
          ) : (
            <GraficoDeBarras
              puntos={panel.serie_ventas.map((punto) => ({
                etiqueta: diaCorto(punto.fecha, idioma),
                valor: Number(punto.total),
                detalle: `${pesos(punto.total, idioma)} · ${numero(punto.cantidad_ventas, idioma)} ${t.tickets.toLowerCase()}`,
              }))}
              etiquetaDeEje={(valor) => pesosCortos(valor, idioma)}
            />
          )}
        </Tarjeta>

        <Tarjeta titulo={t.mediosDeHoy}>
          {panel.medios_de_pago.length === 0 ? (
            <Vacio texto={t.sinDatos} />
          ) : (
            <BarrasHorizontales
              filas={panel.medios_de_pago.map((medio) => ({
                clave: medio.id_medio_pago,
                etiqueta: medio.nombre,
                valor: Number(medio.total),
                texto: pesos(medio.total, idioma),
              }))}
            />
          )}
        </Tarjeta>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Tarjeta titulo={t.masVendidosMes} className="lg:col-span-2">
          {panel.mas_vendidos_del_mes.length === 0 ? (
            <Vacio texto={t.sinDatos} />
          ) : (
            <BarrasHorizontales
              filas={panel.mas_vendidos_del_mes.slice(0, 6).map((fila) => ({
                clave: fila.id_producto,
                etiqueta: fila.nombre,
                valor: fila.unidades,
                texto: `${numero(fila.unidades, idioma)} ${t.unidades} · ${pesos(fila.facturado, idioma)}`,
              }))}
            />
          )}
        </Tarjeta>

        <Tarjeta
          titulo={t.stock}
          accion={
            <Link
              href="/stock"
              className="text-xs font-medium text-marca-texto hover:underline"
            >
              {t.verTodo}
            </Link>
          }
        >
          <p className="cifra text-2xl font-semibold tracking-tight">
            {numero(stock.total, idioma)}{" "}
            <span className="text-sm font-normal text-suave">
              {t.productosActivos.toLowerCase()}
            </span>
          </p>
          <div
            className="mt-4 flex h-2 overflow-hidden rounded-full bg-sutil"
            aria-hidden
          >
            {tramos.map((tramo) => (
              <div
                key={tramo.clave}
                className={tramo.color}
                style={{
                  width: `${stock.total ? (tramo.valor / stock.total) * 100 : 0}%`,
                }}
              />
            ))}
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            {tramos.map((tramo) => (
              <div key={tramo.clave} className="flex items-center gap-2">
                <span
                  className={`size-2 rounded-full ${tramo.color}`}
                  aria-hidden
                />
                <dt className="text-suave">{tramo.texto}</dt>
                <dd className="cifra ml-auto font-medium">
                  {numero(tramo.valor, idioma)}
                </dd>
              </div>
            ))}
            <div className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-texto" aria-hidden />
              <dt className="text-suave">{t.sinStockN}</dt>
              <dd className="cifra ml-auto font-medium">
                {numero(stock.sin_stock, idioma)}
              </dd>
            </div>
          </dl>
        </Tarjeta>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ListaDeAlerta
          titulo={t.bajoMinimo}
          icono={CircleAlert}
          tono="text-alerta"
          productos={panel.bajo_minimo}
          detalle={(p) =>
            `${numero(p.stock_actual, idioma)} / ${numero(p.stock_minimo, idioma)}`
          }
        />
        <ListaDeAlerta
          titulo={t.porVencer}
          icono={CalendarClock}
          tono="text-aviso"
          productos={panel.proximos_a_vencer}
          detalle={(p) =>
            p.fecha_vencimiento ? fecha(p.fecha_vencimiento, idioma) : ""
          }
        />
        <ListaDeAlerta
          titulo={t.vencidos}
          icono={PackageX}
          tono="text-alerta"
          productos={panel.vencidos}
          detalle={(p) =>
            p.fecha_vencimiento ? fecha(p.fecha_vencimiento, idioma) : ""
          }
        />
      </div>
    </div>
  );
}
