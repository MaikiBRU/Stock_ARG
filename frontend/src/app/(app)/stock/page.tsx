"use client";

import {
  ArrowLeftRight,
  Boxes,
  CircleAlert,
  CircleCheck,
  CircleDashed,
  PackageMinus,
  PackageX,
  X,
} from "lucide-react";
import { useState } from "react";

import {
  ElegirProducto,
  type ProductoElegido,
} from "@/componentes/ElegirProducto";
import { useUsuario } from "@/componentes/Sesion";
import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton } from "@/componentes/ui/Boton";
import {
  AreaDeTexto,
  Campo,
  claseDeEntrada,
  Selector,
  SelectorSuelto,
} from "@/componentes/ui/Campo";
import { Exportar } from "@/componentes/ui/Controles";
import { Dialogo, PieDeDialogo } from "@/componentes/ui/Dialogo";
import {
  Alerta,
  EncabezadoDePagina,
  EstadoVacio,
  Indicador,
  Insignia,
  type Tono,
} from "@/componentes/ui/Superficie";
import { Celda, Fila, Paginacion, Tabla } from "@/componentes/ui/Tabla";
import { useTextos } from "@/i18n/proveedor";
import { consulta, mensajeDe, pedir, type Pagina } from "@/lib/api";
import { fechaHora, numero } from "@/lib/formato";
import { useConsulta } from "@/lib/ganchos";
import { gestiona } from "@/lib/rutas";

type Tipo = "entrada" | "salida" | "ajuste" | "venta" | "baja" | "devolucion";

type Movimiento = {
  id: number;
  id_producto: number;
  tipo: Tipo;
  cantidad: number;
  stock_resultante: number;
  nota: string | null;
  fecha_hora: string;
  producto: string | null;
  usuario: string | null;
};

type Resumen = {
  total: number;
  bajo: number;
  medio: number;
  ok: number;
  sin_stock: number;
};

const LIMITE = 25;

const TONO_DE_TIPO: Record<Tipo, Tono> = {
  entrada: "ok",
  devolucion: "ok",
  salida: "aviso",
  venta: "marca",
  baja: "alerta",
  ajuste: "neutro",
};

function useNombresDeTipo() {
  const { t } = useTextos();
  return {
    entrada: t.tipoEntrada,
    salida: t.tipoSalida,
    ajuste: t.tipoAjuste,
    venta: t.tipoVenta,
    baja: t.tipoBaja,
    devolucion: t.tipoDevolucion,
  } satisfies Record<Tipo, string>;
}

/** Cantidad con signo: lo que entra suma, lo que sale resta. */
function signo(tipo: Tipo) {
  if (tipo === "entrada" || tipo === "devolucion") return "+";
  if (tipo === "ajuste") return "=";
  return "−";
}

function FormularioDeMovimiento({
  baja,
  alGuardar,
  alCancelar,
}: {
  baja: boolean;
  alGuardar: () => void;
  alCancelar: () => void;
}) {
  const { t } = useTextos();
  const nombres = useNombresDeTipo();
  const [producto, setProducto] = useState<ProductoElegido | null>(null);
  const [tipo, setTipo] = useState<Tipo>("entrada");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function guardar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!producto) {
      setError(t.elegirProducto);
      return;
    }
    const f = new FormData(evento.currentTarget);
    const cantidad = Number(f.get("cantidad"));
    const nota = String(f.get("nota") ?? "").trim() || null;

    setGuardando(true);
    setError(null);
    try {
      if (baja) {
        await pedir("/stock/bajas", {
          method: "POST",
          cuerpo: {
            id_producto: producto.id,
            cantidad,
            motivo: f.get("motivo"),
            detalle: nota,
          },
        });
      } else {
        await pedir("/stock/movimientos", {
          method: "POST",
          cuerpo: { id_producto: producto.id, tipo, cantidad, nota },
        });
      }
      alGuardar();
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
      setGuardando(false);
    }
  }

  return (
    <form onSubmit={guardar} className="flex flex-col gap-4">
      <ElegirProducto
        etiqueta={t.producto}
        valor={producto}
        alElegir={setProducto}
        autoFocus
      />
      <div className="grid gap-4 sm:grid-cols-2">
        {baja ? (
          <Selector etiqueta={t.motivo} name="motivo" defaultValue="vencido">
            <option value="vencido">{t.motivoVencido}</option>
            <option value="danado">{t.motivoDanado}</option>
            <option value="otro">{t.motivoOtro}</option>
          </Selector>
        ) : (
          <Selector
            etiqueta={t.tipo}
            value={tipo}
            onChange={(e) => setTipo(e.target.value as Tipo)}
          >
            {(["entrada", "salida", "ajuste", "devolucion"] as const).map(
              (valor) => (
                <option key={valor} value={valor}>
                  {nombres[valor]}
                </option>
              ),
            )}
          </Selector>
        )}
        <Campo
          etiqueta={t.cantidad}
          name="cantidad"
          type="number"
          required
          min="1"
          step="1"
          max={
            baja || tipo === "salida"
              ? (producto?.stock_actual ?? undefined)
              : undefined
          }
        />
      </div>
      {!baja && tipo === "ajuste" && (
        <p className="rounded-lg bg-sutil px-3 py-2 text-xs text-suave">
          {t.ajusteAyuda}
        </p>
      )}
      <AreaDeTexto
        etiqueta={baja ? t.detalle : t.nota}
        name="nota"
        opcional
        maxLength={255}
      />
      {error && <Alerta>{error}</Alerta>}
      <PieDeDialogo>
        <Boton onClick={alCancelar}>{t.cancelar}</Boton>
        <Boton
          type="submit"
          variante={baja ? "peligro" : "primario"}
          cargando={guardando}
        >
          {baja ? t.registrarBaja : t.registrarMovimiento}
        </Boton>
      </PieDeDialogo>
    </form>
  );
}

export default function Stock() {
  const { t, idioma } = useTextos();
  const usuario = useUsuario();
  const { avisar } = useAvisos();
  const nombres = useNombresDeTipo();
  const puedeEditar = gestiona(usuario.rol);

  const [tipo, setTipo] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [filtroProducto, setFiltroProducto] = useState<{
    id: number;
    nombre: string;
  } | null>(null);
  const [pagina, setPagina] = useState(1);
  const [dialogo, setDialogo] = useState<"movimiento" | "baja" | null>(null);

  const filtros = {
    tipo,
    desde,
    hasta,
    id_producto: filtroProducto?.id,
  };
  const { datos: resumen, recargar: recargarResumen } =
    useConsulta<Resumen>("/stock/resumen");
  const { datos, error, cargando, recargar } = useConsulta<
    Pagina<Movimiento>
  >(`/stock/movimientos${consulta({ ...filtros, pagina, limite: LIMITE })}`);

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
        titulo={t.stock}
        descripcion={t.stockTexto}
        acciones={
          puedeEditar && (
            <>
              <Exportar
                ruta={`/stock/movimientos/exportar${consulta(filtros)}`}
                nombre="movimientos"
              />
              <Boton icono={PackageMinus} onClick={() => setDialogo("baja")}>
                {t.registrarBaja}
              </Boton>
              <Boton
                variante="primario"
                icono={ArrowLeftRight}
                onClick={() => setDialogo("movimiento")}
              >
                {t.registrarMovimiento}
              </Boton>
            </>
          )
        }
      />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <Indicador
          etiqueta={t.totalProductos}
          valor={resumen ? numero(resumen.total, idioma) : "—"}
          icono={Boxes}
        />
        <Indicador
          etiqueta={t.stockBien}
          valor={resumen ? numero(resumen.ok, idioma) : "—"}
          icono={CircleCheck}
          tono="ok"
        />
        <Indicador
          etiqueta={t.stockMedio}
          valor={resumen ? numero(resumen.medio, idioma) : "—"}
          icono={CircleDashed}
          tono="aviso"
        />
        <Indicador
          etiqueta={t.stockBajo}
          valor={resumen ? numero(resumen.bajo, idioma) : "—"}
          icono={CircleAlert}
          tono="alerta"
        />
        <Indicador
          etiqueta={t.sinStockN}
          valor={resumen ? numero(resumen.sin_stock, idioma) : "—"}
          icono={PackageX}
          tono="alerta"
        />
      </div>

      <div className="rounded-xl border border-borde bg-superficie shadow-xs">
        <div className="flex flex-wrap items-center gap-2 border-b border-borde p-3">
          <h2 className="mr-auto px-1 text-sm font-semibold">
            {t.movimientos}
          </h2>
          {filtroProducto && (
            <span className="inline-flex h-9 items-center gap-1 rounded-lg bg-marca-suave pr-1 pl-3 text-sm text-marca-texto">
              {filtroProducto.nombre}
              <button
                type="button"
                aria-label={t.limpiarFiltros}
                onClick={() => {
                  setFiltroProducto(null);
                  setPagina(1);
                }}
                className="inline-flex size-7 items-center justify-center rounded-md hover:bg-marca/10"
              >
                <X size={14} aria-hidden />
              </button>
            </span>
          )}
          <SelectorSuelto
            aria-label={t.tipo}
            value={tipo}
            onChange={(e) => filtrar(setTipo)(e.target.value)}
            className="w-full sm:w-40"
          >
            <option value="">
              {t.tipo}: {t.todos.toLowerCase()}
            </option>
            {(Object.keys(nombres) as Tipo[]).map((valor) => (
              <option key={valor} value={valor}>
                {nombres[valor]}
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
            <Alerta>{error.message}</Alerta>
          </div>
        ) : (
          <Tabla
            columnas={[
              { texto: t.fecha },
              { texto: t.producto },
              { texto: t.tipo },
              { texto: t.cantidad, alinear: "derecha" },
              { texto: t.stockResultante, alinear: "derecha", oculta: "sm" },
              { texto: t.usuario, oculta: "lg" },
              { texto: t.nota, oculta: "md" },
            ]}
            cargando={cargando}
            vacia={items.length === 0}
            estadoVacio={
              <EstadoVacio icono={ArrowLeftRight} titulo={t.sinResultados} />
            }
          >
            {items.map((movimiento) => {
              const nombre =
                movimiento.producto ?? `#${movimiento.id_producto}`;
              return (
                <Fila key={movimiento.id}>
                  <Celda className="cifra whitespace-nowrap text-suave">
                    {fechaHora(movimiento.fecha_hora, idioma)}
                  </Celda>
                  <Celda>
                    <button
                      type="button"
                      onClick={() => {
                        setFiltroProducto({
                          id: movimiento.id_producto,
                          nombre,
                        });
                        setPagina(1);
                      }}
                      className="rounded text-left font-medium hover:underline"
                    >
                      {nombre}
                    </button>
                  </Celda>
                  <Celda>
                    <Insignia tono={TONO_DE_TIPO[movimiento.tipo]}>
                      {nombres[movimiento.tipo]}
                    </Insignia>
                  </Celda>
                  <Celda alinear="derecha" className="cifra font-medium">
                    {signo(movimiento.tipo)}
                    {numero(movimiento.cantidad, idioma)}
                  </Celda>
                  <Celda alinear="derecha" oculta="sm" className="cifra">
                    {numero(movimiento.stock_resultante, idioma)}
                  </Celda>
                  <Celda oculta="lg" className="text-suave">
                    {movimiento.usuario ?? "—"}
                  </Celda>
                  <Celda oculta="md" className="max-w-56 truncate text-suave">
                    {movimiento.nota ?? "—"}
                  </Celda>
                </Fila>
              );
            })}
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
        abierto={dialogo !== null}
        alCerrar={() => setDialogo(null)}
        titulo={dialogo === "baja" ? t.registrarBaja : t.registrarMovimiento}
      >
        {dialogo !== null && (
          <FormularioDeMovimiento
            baja={dialogo === "baja"}
            alCancelar={() => setDialogo(null)}
            alGuardar={() => {
              avisar(
                dialogo === "baja" ? t.bajaRegistrada : t.movimientoRegistrado,
              );
              setDialogo(null);
              recargar();
              recargarResumen();
            }}
          />
        )}
      </Dialogo>
    </div>
  );
}
