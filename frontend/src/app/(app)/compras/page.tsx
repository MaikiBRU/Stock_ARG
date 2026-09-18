"use client";

import { Ban, Plus, ShoppingBag, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  ElegirProducto,
  type ProductoElegido,
} from "@/componentes/ElegirProducto";
import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton, BotonIcono } from "@/componentes/ui/Boton";
import {
  AreaDeTexto,
  Campo,
  Casilla,
  claseDeEntrada,
  Selector,
  SelectorSuelto,
} from "@/componentes/ui/Campo";
import { Dialogo, PieDeDialogo } from "@/componentes/ui/Dialogo";
import {
  Alerta,
  EncabezadoDePagina,
  EstadoVacio,
  Esqueleto,
  Insignia,
} from "@/componentes/ui/Superficie";
import { Celda, Fila, Paginacion, Tabla } from "@/componentes/ui/Tabla";
import { useTextos } from "@/i18n/proveedor";
import { formatear } from "@/i18n/textos";
import { consulta, mensajeDe, pedir, type Pagina } from "@/lib/api";
import { fecha, fechaHora, hoyEnElComercio, pesos } from "@/lib/formato";
import { useConsulta } from "@/lib/ganchos";

type Resumen = {
  id: number;
  fecha: string;
  total: string;
  comprobante: string | null;
  estado: "registrada" | "anulada";
  id_proveedor: number;
  proveedor: string | null;
};

type Compra = Resumen & {
  notas: string | null;
  anulada_en: string | null;
  motivo_anulacion: string | null;
  items: {
    id: number;
    nombre_producto: string;
    cantidad: number;
    costo_unitario: string;
    subtotal: string;
  }[];
};

type Proveedor = { id: number; razon_social: string };

type Linea = { producto: ProductoElegido; cantidad: string; costo: string };

const LIMITE = 25;

function Estado({ estado }: { estado: Resumen["estado"] }) {
  const { t } = useTextos();
  return estado === "anulada" ? (
    <Insignia tono="alerta">{t.estadoAnulada}</Insignia>
  ) : (
    <Insignia tono="ok">{t.estadoRegistrada}</Insignia>
  );
}

function NuevaCompra({
  proveedores,
  alGuardar,
  alCancelar,
}: {
  proveedores: Proveedor[];
  alGuardar: () => void;
  alCancelar: () => void;
}) {
  const { t, idioma } = useTextos();
  const [lineas, setLineas] = useState<Linea[]>([]);
  const [actualizarCosto, setActualizarCosto] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function agregar(producto: ProductoElegido | null) {
    if (!producto) return;
    setLineas((actuales) =>
      actuales.some((l) => l.producto.id === producto.id)
        ? actuales
        : [
            ...actuales,
            {
              producto,
              cantidad: "1",
              // Quien ve los costos arranca con el ultimo cargado.
              costo:
                producto.precio_costo && Number(producto.precio_costo) > 0
                  ? producto.precio_costo
                  : "",
            },
          ],
    );
  }

  function cambiar(id: number, cambios: Partial<Linea>) {
    setLineas((actuales) =>
      actuales.map((l) => (l.producto.id === id ? { ...l, ...cambios } : l)),
    );
  }

  const total = lineas.reduce(
    (suma, l) => suma + (Number(l.cantidad) || 0) * (Number(l.costo) || 0),
    0,
  );

  async function guardar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (lineas.length === 0) {
      setError(t.sinLineas);
      return;
    }
    const f = new FormData(evento.currentTarget);
    setGuardando(true);
    setError(null);
    try {
      await pedir("/compras", {
        method: "POST",
        cuerpo: {
          id_proveedor: Number(f.get("id_proveedor")),
          fecha: f.get("fecha") || undefined,
          comprobante: String(f.get("comprobante") ?? "").trim() || null,
          notas: String(f.get("notas") ?? "").trim() || null,
          actualizar_costo: actualizarCosto,
          items: lineas.map((l) => ({
            id_producto: l.producto.id,
            cantidad: Number(l.cantidad),
            costo_unitario: Number(l.costo).toFixed(2),
          })),
        },
      });
      alGuardar();
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
      setGuardando(false);
    }
  }

  return (
    <form onSubmit={guardar} className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <Selector
          etiqueta={t.proveedor}
          name="id_proveedor"
          required
          defaultValue=""
          className="sm:col-span-3"
        >
          <option value="" disabled>
            {t.elegirProveedor}
          </option>
          {proveedores.map((p) => (
            <option key={p.id} value={p.id}>
              {p.razon_social}
            </option>
          ))}
        </Selector>
        <Campo
          etiqueta={t.fecha}
          name="fecha"
          type="date"
          required
          max={hoyEnElComercio()}
          defaultValue={hoyEnElComercio()}
        />
        <Campo
          etiqueta={t.numeroComprobante}
          name="comprobante"
          opcional
          maxLength={60}
          className="sm:col-span-2"
        />
      </div>

      <div className="flex flex-col gap-3">
        <ElegirProducto
          etiqueta={t.agregarLinea}
          valor={null}
          alElegir={agregar}
        />
        {lineas.length > 0 && (
          <ul className="divide-y divide-borde rounded-lg border border-borde">
            {lineas.map((linea) => (
              <li
                key={linea.producto.id}
                className="flex flex-wrap items-center gap-2 px-3 py-2.5"
              >
                <span className="min-w-0 flex-1 basis-40 truncate text-sm font-medium">
                  {linea.producto.nombre}
                </span>
                <label className="flex items-center gap-1.5 text-xs text-suave">
                  {t.cantidad}
                  <input
                    type="number"
                    min="1"
                    step="1"
                    required
                    value={linea.cantidad}
                    onChange={(e) =>
                      cambiar(linea.producto.id, { cantidad: e.target.value })
                    }
                    className={`${claseDeEntrada} w-20`}
                  />
                </label>
                <label className="flex items-center gap-1.5 text-xs text-suave">
                  {t.costoUnitario}
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    required
                    inputMode="decimal"
                    value={linea.costo}
                    onChange={(e) =>
                      cambiar(linea.producto.id, { costo: e.target.value })
                    }
                    className={`${claseDeEntrada} w-28`}
                  />
                </label>
                <span className="cifra w-24 text-right text-sm font-medium">
                  {pesos(
                    (Number(linea.cantidad) || 0) * (Number(linea.costo) || 0),
                    idioma,
                  )}
                </span>
                <BotonIcono
                  etiqueta={`${t.quitar}: ${linea.producto.nombre}`}
                  icono={Trash2}
                  onClick={() =>
                    setLineas((actuales) =>
                      actuales.filter((l) => l.producto.id !== linea.producto.id),
                    )
                  }
                />
              </li>
            ))}
          </ul>
        )}
        <p className="flex items-baseline justify-between border-t border-borde pt-3">
          <span className="text-sm font-medium">{t.total}</span>
          <span className="cifra text-xl font-semibold">
            {pesos(total, idioma)}
          </span>
        </p>
      </div>

      <Casilla
        etiqueta={t.actualizarCosto}
        checked={actualizarCosto}
        onChange={(e) => setActualizarCosto(e.target.checked)}
      />
      <AreaDeTexto etiqueta={t.notas} name="notas" opcional maxLength={500} />

      {error && <Alerta>{error}</Alerta>}
      <PieDeDialogo>
        <Boton onClick={alCancelar}>{t.cancelar}</Boton>
        <Boton type="submit" variante="primario" cargando={guardando}>
          {t.nuevaCompra}
        </Boton>
      </PieDeDialogo>
    </form>
  );
}

function DetalleDeCompra({ id, alAnular }: { id: number; alAnular: () => void }) {
  const { t, idioma } = useTextos();
  const { avisar, confirmar } = useAvisos();
  const {
    datos: compra,
    error,
    recargar,
  } = useConsulta<Compra>(`/compras/${id}`);

  if (error) return <Alerta>{error.message}</Alerta>;
  if (!compra) return <Esqueleto className="h-40" />;

  async function anular() {
    const motivo = await confirmar({
      titulo: t.anularCompra,
      texto: t.anularCompraTexto,
      accion: t.anular,
      peligro: true,
      conMotivo: true,
    });
    if (motivo === null) return;
    try {
      await pedir(`/compras/${id}/anular`, {
        method: "POST",
        cuerpo: { motivo: motivo || null },
      });
      avisar(t.compraAnulada);
      recargar();
      alAnular();
    } catch (falla) {
      avisar(mensajeDe(falla, t.errorGenerico), "alerta");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <Estado estado={compra.estado} />
        {compra.anulada_en && (
          <span className="text-xs text-suave">
            {formatear(t.anuladaEl, {
              fecha: fechaHora(compra.anulada_en, idioma),
            })}
          </span>
        )}
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        {[
          { etiqueta: t.proveedor, valor: compra.proveedor ?? "—" },
          { etiqueta: t.fecha, valor: fecha(compra.fecha, idioma) },
          { etiqueta: t.numeroComprobante, valor: compra.comprobante ?? "—" },
          { etiqueta: t.notas, valor: compra.notas ?? "—" },
        ].map((dato) => (
          <div key={dato.etiqueta} className="min-w-0">
            <dt className="text-xs text-suave">{dato.etiqueta}</dt>
            <dd className="mt-0.5 break-words font-medium">{dato.valor}</dd>
          </div>
        ))}
      </dl>
      {compra.motivo_anulacion && (
        <p className="rounded-lg bg-alerta-suave px-3 py-2 text-sm text-alerta">
          {t.motivo}: {compra.motivo_anulacion}
        </p>
      )}
      <div className="overflow-hidden rounded-lg border border-borde">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-borde bg-sutil/50 text-xs text-suave">
              <th className="px-3 py-2 text-left font-medium">{t.producto}</th>
              <th className="px-3 py-2 text-right font-medium">
                {t.cantidad}
              </th>
              <th className="px-3 py-2 text-right font-medium">
                {t.subtotal}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-borde">
            {compra.items.map((item) => (
              <tr key={item.id}>
                <td className="px-3 py-2">
                  {item.nombre_producto}
                  <span className="cifra block text-xs text-suave">
                    {pesos(item.costo_unitario, idioma)}
                  </span>
                </td>
                <td className="cifra px-3 py-2 text-right">{item.cantidad}</td>
                <td className="cifra px-3 py-2 text-right font-medium">
                  {pesos(item.subtotal, idioma)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="flex justify-between text-base font-semibold">
        <span>{t.total}</span>
        <span className="cifra">{pesos(compra.total, idioma)}</span>
      </p>
      {compra.estado === "registrada" && (
        <PieDeDialogo>
          <Boton
            variante="fantasma"
            icono={Ban}
            onClick={anular}
            className="text-alerta hover:text-alerta"
          >
            {t.anular}
          </Boton>
        </PieDeDialogo>
      )}
    </div>
  );
}

export default function Compras() {
  const { t, idioma } = useTextos();
  const { avisar } = useAvisos();
  const [idProveedor, setIdProveedor] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [pagina, setPagina] = useState(1);
  const [abierta, setAbierta] = useState<number | null>(null);
  const [nueva, setNueva] = useState(false);

  const { datos, error, cargando, recargar } = useConsulta<Pagina<Resumen>>(
    `/compras${consulta({
      id_proveedor: idProveedor,
      desde,
      hasta,
      pagina,
      limite: LIMITE,
    })}`,
  );
  const { datos: proveedores } = useConsulta<Pagina<Proveedor>>(
    "/proveedores?limite=100",
  );

  function filtrar(fijar: (valor: string) => void) {
    return (valor: string) => {
      fijar(valor);
      setPagina(1);
    };
  }

  const items = datos?.items ?? [];

  return (
    <div className="flex flex-col gap-6">
      <EncabezadoDePagina
        titulo={t.compras}
        descripcion={t.comprasTexto}
        acciones={
          <Boton variante="primario" icono={Plus} onClick={() => setNueva(true)}>
            {t.nuevaCompra}
          </Boton>
        }
      />

      <div className="rounded-xl border border-borde bg-superficie shadow-xs">
        <div className="flex flex-wrap items-center gap-2 border-b border-borde p-3">
          <SelectorSuelto
            aria-label={t.proveedor}
            value={idProveedor}
            onChange={(e) => filtrar(setIdProveedor)(e.target.value)}
            className="w-full sm:w-64"
          >
            <option value="">
              {t.proveedor}: {t.todos.toLowerCase()}
            </option>
            {(proveedores?.items ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.razon_social}
              </option>
            ))}
          </SelectorSuelto>
          <label className="flex items-center gap-2 text-xs text-suave">
            {t.desde}
            <input
              type="date"
              value={desde}
              max={hasta || undefined}
              onChange={(e) => filtrar(setDesde)(e.target.value)}
              className={`${claseDeEntrada} w-38`}
            />
          </label>
          <label className="flex items-center gap-2 text-xs text-suave">
            {t.hasta}
            <input
              type="date"
              value={hasta}
              min={desde || undefined}
              onChange={(e) => filtrar(setHasta)(e.target.value)}
              className={`${claseDeEntrada} w-38`}
            />
          </label>
        </div>

        {error ? (
          <div className="p-4">
            <Alerta>{error.estado === 403 ? t.sinPermiso : error.message}</Alerta>
          </div>
        ) : (
          <Tabla
            columnas={[
              { texto: "#" },
              { texto: t.fecha },
              { texto: t.proveedor },
              { texto: t.numeroComprobante, oculta: "md" },
              { texto: t.total, alinear: "derecha" },
              { texto: t.estado, alinear: "derecha", oculta: "sm" },
            ]}
            cargando={cargando}
            vacia={items.length === 0}
            estadoVacio={
              <EstadoVacio
                icono={ShoppingBag}
                titulo={t.sinResultados}
                accion={
                  <Boton
                    variante="primario"
                    icono={Plus}
                    onClick={() => setNueva(true)}
                  >
                    {t.nuevaCompra}
                  </Boton>
                }
              />
            }
          >
            {items.map((compra) => (
              <Fila
                key={compra.id}
                alElegir={() => setAbierta(compra.id)}
                apagada={compra.estado === "anulada"}
              >
                <Celda className="cifra font-medium">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setAbierta(compra.id);
                    }}
                    className="rounded hover:underline"
                  >
                    #{compra.id}
                  </button>
                </Celda>
                <Celda className="cifra text-suave">
                  {fecha(compra.fecha, idioma)}
                </Celda>
                <Celda>{compra.proveedor ?? "—"}</Celda>
                <Celda oculta="md" className="text-suave">
                  {compra.comprobante ?? "—"}
                </Celda>
                <Celda
                  alinear="derecha"
                  className={`cifra font-medium whitespace-nowrap ${compra.estado === "anulada" ? "line-through" : ""}`}
                >
                  {pesos(compra.total, idioma)}
                </Celda>
                <Celda alinear="derecha" oculta="sm">
                  <Estado estado={compra.estado} />
                </Celda>
              </Fila>
            ))}
          </Tabla>
        )}

        {datos && datos.total > 0 && (
          <Paginacion
            pagina={pagina}
            total={datos.total}
            limite={LIMITE}
            alCambiar={setPagina}
          />
        )}
      </div>

      <Dialogo
        abierto={abierta !== null}
        alCerrar={() => setAbierta(null)}
        titulo={abierta ? formatear(t.compraNumero, { id: abierta }) : ""}
      >
        {abierta !== null && (
          <DetalleDeCompra id={abierta} alAnular={recargar} />
        )}
      </Dialogo>

      <Dialogo
        abierto={nueva}
        alCerrar={() => setNueva(false)}
        titulo={t.nuevaCompra}
        ancho="xl"
      >
        {nueva && (
          <NuevaCompra
            proveedores={proveedores?.items ?? []}
            alCancelar={() => setNueva(false)}
            alGuardar={() => {
              setNueva(false);
              avisar(t.compraRegistrada);
              recargar();
            }}
          />
        )}
      </Dialogo>
    </div>
  );
}
