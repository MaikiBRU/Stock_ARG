"use client";

import { Ban, FileText, Receipt } from "lucide-react";
import { useState } from "react";

import { useUsuario } from "@/componentes/Sesion";
import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton } from "@/componentes/ui/Boton";
import { claseDeEntrada, SelectorSuelto } from "@/componentes/ui/Campo";
import { Buscador, Exportar } from "@/componentes/ui/Controles";
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
import {
  consulta,
  descargar,
  mensajeDe,
  pedir,
  type Pagina,
} from "@/lib/api";
import { fechaHora, numero, pesos } from "@/lib/formato";
import { useConsulta, useDemora } from "@/lib/ganchos";
import { gestiona } from "@/lib/rutas";

type Resumen = {
  id: number;
  fecha_hora: string;
  total: string;
  estado: "registrada" | "anulada";
  cantidad_articulos: number;
  medio_pago: string | null;
  vendedor: string | null;
  cliente: string | null;
};

type Venta = Resumen & {
  descuento: string;
  recibido: string | null;
  vuelto: string | null;
  anulada_en: string | null;
  motivo_anulacion: string | null;
  items: {
    id: number;
    nombre_producto: string;
    cantidad: number;
    precio_unitario: string;
    descuento: string;
    subtotal: string;
  }[];
};

type Medio = { id: number; nombre: string };

const LIMITE = 25;

function EstadoDeVenta({ estado }: { estado: Resumen["estado"] }) {
  const { t } = useTextos();
  return estado === "anulada" ? (
    <Insignia tono="alerta">{t.estadoAnulada}</Insignia>
  ) : (
    <Insignia tono="ok">{t.estadoRegistrada}</Insignia>
  );
}

function DetalleDeVenta({
  id,
  puedeAnular,
  alAnular,
}: {
  id: number;
  puedeAnular: boolean;
  alAnular: () => void;
}) {
  const { t, idioma } = useTextos();
  const { avisar, confirmar } = useAvisos();
  const {
    datos: venta,
    error,
    recargar,
  } = useConsulta<Venta>(`/ventas/${id}`);

  if (error) return <Alerta>{error.message}</Alerta>;
  if (!venta) {
    return (
      <div className="flex flex-col gap-3">
        <Esqueleto className="h-5 w-1/2" />
        <Esqueleto className="h-32" />
      </div>
    );
  }

  async function anular() {
    const motivo = await confirmar({
      titulo: t.anularVenta,
      texto: t.anularTexto,
      accion: t.anular,
      peligro: true,
      conMotivo: true,
    });
    if (motivo === null) return;
    try {
      await pedir(`/ventas/${id}/anular`, {
        method: "POST",
        cuerpo: { motivo: motivo || null },
      });
      avisar(t.ventaAnulada);
      recargar();
      alAnular();
    } catch (falla) {
      avisar(mensajeDe(falla, t.errorGenerico), "alerta");
    }
  }

  const cabecera = [
    { etiqueta: t.fecha, valor: fechaHora(venta.fecha_hora, idioma) },
    { etiqueta: t.medioDePago, valor: venta.medio_pago ?? "—" },
    { etiqueta: t.cliente, valor: venta.cliente ?? t.consumidorFinal },
    { etiqueta: t.vendedor, valor: venta.vendedor ?? "—" },
  ];

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <EstadoDeVenta estado={venta.estado} />
        {venta.anulada_en && (
          <span className="text-xs text-suave">
            {formatear(t.anuladaEl, {
              fecha: fechaHora(venta.anulada_en, idioma),
            })}
          </span>
        )}
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        {cabecera.map((dato) => (
          <div key={dato.etiqueta} className="min-w-0">
            <dt className="text-xs text-suave">{dato.etiqueta}</dt>
            <dd className="mt-0.5 truncate font-medium">{dato.valor}</dd>
          </div>
        ))}
      </dl>
      {venta.motivo_anulacion && (
        <p className="rounded-lg bg-alerta-suave px-3 py-2 text-sm text-alerta">
          {t.motivo}: {venta.motivo_anulacion}
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
            {venta.items.map((item) => (
              <tr key={item.id}>
                <td className="px-3 py-2">
                  {item.nombre_producto}
                  <span className="cifra block text-xs text-suave">
                    {pesos(item.precio_unitario, idioma)}
                    {Number(item.descuento) > 0 &&
                      ` · −${pesos(item.descuento, idioma)}`}
                  </span>
                </td>
                <td className="cifra px-3 py-2 text-right">
                  {item.cantidad}
                </td>
                <td className="cifra px-3 py-2 text-right font-medium">
                  {pesos(item.subtotal, idioma)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <dl className="flex flex-col gap-1 text-sm">
        {Number(venta.descuento) > 0 && (
          <div className="flex justify-between text-suave">
            <dt>{t.descuento}</dt>
            <dd className="cifra">−{pesos(venta.descuento, idioma)}</dd>
          </div>
        )}
        <div className="flex justify-between text-base font-semibold">
          <dt>{t.total}</dt>
          <dd className="cifra">{pesos(venta.total, idioma)}</dd>
        </div>
        {venta.recibido !== null && (
          <>
            <div className="flex justify-between text-suave">
              <dt>{t.recibido}</dt>
              <dd className="cifra">{pesos(venta.recibido, idioma)}</dd>
            </div>
            <div className="flex justify-between text-suave">
              <dt>{t.vuelto}</dt>
              <dd className="cifra">{pesos(venta.vuelto ?? 0, idioma)}</dd>
            </div>
          </>
        )}
      </dl>

      <PieDeDialogo>
        {puedeAnular && venta.estado === "registrada" && (
          <Boton
            variante="fantasma"
            icono={Ban}
            onClick={anular}
            className="mr-auto text-alerta hover:text-alerta"
          >
            {t.anular}
          </Boton>
        )}
        <Boton
          icono={FileText}
          onClick={() =>
            descargar(
              `/ventas/${venta.id}/comprobante`,
              `comprobante-${venta.id}.pdf`,
            ).catch((falla) =>
              avisar(mensajeDe(falla, t.errorGenerico), "alerta"),
            )
          }
        >
          {t.comprobante}
        </Boton>
      </PieDeDialogo>
    </div>
  );
}

export default function Ventas() {
  const { t, idioma } = useTextos();
  const usuario = useUsuario();
  const esGestion = gestiona(usuario.rol);

  const [texto, setTexto] = useState("");
  const busqueda = useDemora(texto.trim());
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [estado, setEstado] = useState("");
  const [idMedio, setIdMedio] = useState("");
  const [pagina, setPagina] = useState(1);
  const [abierta, setAbierta] = useState<number | null>(null);

  const filtros = { desde, hasta, estado };
  const { datos, error, cargando, recargar } = useConsulta<Pagina<Resumen>>(
    `/ventas${consulta({
      ...filtros,
      busqueda,
      id_medio_pago: idMedio,
      pagina,
      limite: LIMITE,
    })}`,
  );
  const { datos: medios } = useConsulta<Medio[]>("/medios-pago");

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
        titulo={t.ventas}
        descripcion={esGestion ? t.ventasTexto : t.misVentasTexto}
        acciones={
          esGestion && (
            <Exportar
              ruta={`/ventas/exportar${consulta(filtros)}`}
              nombre="ventas"
            />
          )
        }
      />

      <div className="rounded-xl border border-borde bg-superficie shadow-xs">
        <div className="flex flex-wrap items-center gap-2 border-b border-borde p-3">
          <Buscador
            className="w-full sm:w-56"
            placeholder={t.buscarVenta}
            aria-label={t.buscar}
            value={texto}
            onChange={(e) => {
              setTexto(e.target.value);
              setPagina(1);
            }}
          />
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
          <SelectorSuelto
            aria-label={t.estado}
            value={estado}
            onChange={(e) => filtrar(setEstado)(e.target.value)}
            className="w-full sm:w-40"
          >
            <option value="">
              {t.estado}: {t.todos.toLowerCase()}
            </option>
            <option value="registrada">{t.estadoRegistrada}</option>
            <option value="anulada">{t.estadoAnulada}</option>
          </SelectorSuelto>
          <SelectorSuelto
            aria-label={t.medioDePago}
            value={idMedio}
            onChange={(e) => filtrar(setIdMedio)(e.target.value)}
            className="w-full sm:w-48"
          >
            <option value="">
              {t.medioDePago}: {t.todos.toLowerCase()}
            </option>
            {(medios ?? []).map((m) => (
              <option key={m.id} value={m.id}>
                {m.nombre}
              </option>
            ))}
          </SelectorSuelto>
        </div>

        {error ? (
          <div className="p-4">
            <Alerta>{error.message}</Alerta>
          </div>
        ) : (
          <Tabla
            columnas={[
              { texto: t.ticket },
              { texto: t.fecha },
              { texto: t.cliente, oculta: "md" },
              ...(esGestion
                ? [{ texto: t.vendedor, oculta: "lg" as const }]
                : []),
              { texto: t.medioDePago, oculta: "sm" },
              { texto: t.articulos, alinear: "derecha", oculta: "lg" },
              { texto: t.total, alinear: "derecha" },
              { texto: t.estado, alinear: "derecha" },
            ]}
            cargando={cargando}
            vacia={items.length === 0}
            estadoVacio={
              <EstadoVacio icono={Receipt} titulo={t.sinResultados} />
            }
          >
            {items.map((venta) => (
              <Fila
                key={venta.id}
                alElegir={() => setAbierta(venta.id)}
                apagada={venta.estado === "anulada"}
              >
                <Celda className="cifra font-medium">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setAbierta(venta.id);
                    }}
                    className="rounded hover:underline"
                  >
                    #{venta.id}
                  </button>
                </Celda>
                <Celda className="cifra whitespace-nowrap text-suave">
                  {fechaHora(venta.fecha_hora, idioma)}
                </Celda>
                <Celda oculta="md">{venta.cliente ?? "—"}</Celda>
                {esGestion && (
                  <Celda oculta="lg" className="text-suave">
                    {venta.vendedor ?? "—"}
                  </Celda>
                )}
                <Celda oculta="sm" className="text-suave">
                  {venta.medio_pago ?? "—"}
                </Celda>
                <Celda alinear="derecha" oculta="lg" className="cifra">
                  {numero(venta.cantidad_articulos, idioma)}
                </Celda>
                <Celda
                  alinear="derecha"
                  className={`cifra font-medium whitespace-nowrap ${venta.estado === "anulada" ? "line-through" : ""}`}
                >
                  {pesos(venta.total, idioma)}
                </Celda>
                <Celda alinear="derecha">
                  <EstadoDeVenta estado={venta.estado} />
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
        titulo={abierta ? formatear(t.ticketNumero, { id: abierta }) : ""}
      >
        {abierta !== null && (
          <DetalleDeVenta
            id={abierta}
            puedeAnular={esGestion}
            alAnular={recargar}
          />
        )}
      </Dialogo>
    </div>
  );
}
