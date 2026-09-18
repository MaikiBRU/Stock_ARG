"use client";

import { useEffect, useState } from "react";

import { useTextos } from "@/i18n/proveedor";
import { ErrorDeApi, pedir } from "@/lib/api";
import { numero, pesos } from "@/lib/formato";

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
    sin_datos: boolean;
  };
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
};

function Indicador({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <div className="rounded-xl border border-borde bg-superficie p-4">
      <p className="text-sm text-suave">{titulo}</p>
      <p className="mt-1 text-2xl font-semibold">{valor}</p>
    </div>
  );
}

function ListaDeAlerta({
  titulo,
  productos,
}: {
  titulo: string;
  productos: Producto[];
}) {
  const { t } = useTextos();

  return (
    <section className="rounded-xl border border-borde bg-superficie p-4">
      <h2 className="font-semibold">
        {titulo} <span className="text-suave">({numero(productos.length)})</span>
      </h2>
      {productos.length === 0 ? (
        <p className="mt-2 text-sm text-suave">{t.sinDatos}</p>
      ) : (
        <ul className="mt-2 divide-y divide-borde text-sm">
          {productos.slice(0, 5).map((producto) => (
            <li key={producto.id} className="flex justify-between py-2">
              <span className="truncate pr-2">{producto.nombre}</span>
              <span className="shrink-0 text-suave">
                {numero(producto.stock_actual)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function Panel() {
  const { t, idioma } = useTextos();
  const [panel, setPanel] = useState<Panel | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    pedir<Panel>("/panel")
      .then((datos) => {
        if (vigente) setPanel(datos);
      })
      .catch((falla) => {
        if (!vigente) return;
        setError(falla instanceof ErrorDeApi ? falla.message : null);
      });
    return () => {
      vigente = false;
    };
  }, []);

  if (error) {
    return (
      <p role="alert" className="text-alerta">
        {error}
      </p>
    );
  }
  if (!panel) return <p>{t.cargando}</p>;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">{t.panel}</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Indicador
          titulo={t.ventasDelDia}
          valor={pesos(panel.ventas_del_dia.total_facturado, idioma)}
        />
        <Indicador
          titulo={t.tickets}
          valor={numero(panel.ventas_del_dia.cantidad_ventas, idioma)}
        />
        <Indicador
          titulo={t.ticketPromedio}
          valor={pesos(panel.ventas_del_dia.ticket_promedio, idioma)}
        />
        <Indicador
          titulo={t.stock}
          valor={numero(panel.resumen_stock.total, idioma)}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ListaDeAlerta titulo={t.bajoMinimo} productos={panel.bajo_minimo} />
        <ListaDeAlerta
          titulo={t.porVencer}
          productos={panel.proximos_a_vencer}
        />
        <ListaDeAlerta titulo={t.vencidos} productos={panel.vencidos} />
      </div>
    </div>
  );
}
