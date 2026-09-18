"use client";

import {
  Package,
  Pencil,
  Plus,
  PowerOff,
  RotateCcw,
  Upload,
} from "lucide-react";
import { useState } from "react";

import { DialogoDeImportacion } from "@/componentes/Importacion";
import { useUsuario } from "@/componentes/Sesion";
import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton, BotonIcono } from "@/componentes/ui/Boton";
import {
  AreaDeTexto,
  Campo,
  Casilla,
  Selector,
  SelectorSuelto,
} from "@/componentes/ui/Campo";
import { Buscador, Exportar } from "@/componentes/ui/Controles";
import { Dialogo, PieDeDialogo } from "@/componentes/ui/Dialogo";
import {
  Alerta,
  EncabezadoDePagina,
  EstadoVacio,
  Insignia,
} from "@/componentes/ui/Superficie";
import { Celda, Fila, Paginacion, Tabla } from "@/componentes/ui/Tabla";
import { useTextos } from "@/i18n/proveedor";
import { consulta, mensajeDe, pedir, type Pagina } from "@/lib/api";
import { fecha, numero, pesos } from "@/lib/formato";
import { useConsulta, useDemora } from "@/lib/ganchos";
import { administra, gestiona } from "@/lib/rutas";

export type Producto = {
  id: number;
  nombre: string;
  codigo_barra: string | null;
  descripcion: string | null;
  precio_venta: string;
  precio_costo: string | null;
  margen: string | null;
  stock_actual: number;
  stock_minimo: number;
  stock_inicial: number;
  porcentaje_stock: number;
  estado_stock: "ok" | "medio" | "bajo";
  bajo_minimo: boolean;
  fecha_vencimiento: string | null;
  id_categoria: number | null;
  id_proveedor: number | null;
  activo: boolean;
  categoria: { id: number; nombre: string } | null;
};

type Categoria = { id: number; nombre: string };
type Proveedor = { id: number; razon_social: string };

const LIMITE = 25;

/** Nivel de stock con color y una barra corta. */
function NivelDeStock({ producto }: { producto: Producto }) {
  const { t, idioma } = useTextos();
  const tono =
    producto.stock_actual <= 0 || producto.estado_stock === "bajo"
      ? "alerta"
      : producto.estado_stock === "medio"
        ? "aviso"
        : "ok";
  const colores = { ok: "bg-ok", aviso: "bg-aviso", alerta: "bg-alerta" };
  const nombres = {
    ok: t.estadoOk,
    medio: t.estadoMedio,
    bajo: t.estadoBajo,
  };
  return (
    <div className="flex items-center justify-end gap-3">
      <div
        className="hidden h-1.5 w-14 overflow-hidden rounded-full bg-sutil sm:block"
        title={`${producto.porcentaje_stock}%`}
        aria-hidden
      >
        <div
          className={`h-full rounded-full ${colores[tono]}`}
          style={{ width: `${Math.min(100, producto.porcentaje_stock)}%` }}
        />
      </div>
      <span className="cifra w-10 text-right font-medium">
        {numero(producto.stock_actual, idioma)}
      </span>
      <span className="hidden w-16 md:inline-block">
        <Insignia tono={tono}>
          {producto.stock_actual <= 0
            ? t.sinStock
            : nombres[producto.estado_stock]}
        </Insignia>
      </span>
    </div>
  );
}

function FormularioDeProducto({
  producto,
  categorias,
  proveedores,
  verCostos,
  alGuardar,
  alCancelar,
}: {
  producto: Producto | null;
  categorias: Categoria[];
  proveedores: Proveedor[];
  verCostos: boolean;
  alGuardar: () => void;
  alCancelar: () => void;
}) {
  const { t } = useTextos();
  const { avisar } = useAvisos();
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function guardar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const f = new FormData(evento.currentTarget);
    const texto = (clave: string) => String(f.get(clave) ?? "").trim();
    const entero = (clave: string) =>
      texto(clave) === "" ? undefined : Number(texto(clave));

    const cuerpo: Record<string, unknown> = {
      nombre: texto("nombre"),
      codigo_barra: texto("codigo_barra") || null,
      descripcion: texto("descripcion") || null,
      precio_venta: texto("precio_venta"),
      stock_minimo: entero("stock_minimo") ?? 0,
      stock_inicial: entero("stock_inicial") ?? null,
      fecha_vencimiento: texto("fecha_vencimiento") || null,
      id_categoria: entero("id_categoria") ?? null,
      id_proveedor: entero("id_proveedor") ?? null,
    };
    // El costo solo viaja si quien edita lo puede ver: si no, se
    // conserva el que esta guardado.
    if (verCostos) cuerpo.precio_costo = texto("precio_costo") || "0";
    if (!producto) cuerpo.stock_actual = entero("stock_actual") ?? 0;

    setGuardando(true);
    setError(null);
    try {
      await pedir(producto ? `/productos/${producto.id}` : "/productos", {
        method: producto ? "PUT" : "POST",
        cuerpo,
      });
      avisar(t.productoGuardado);
      alGuardar();
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
      setGuardando(false);
    }
  }

  return (
    <form onSubmit={guardar} className="grid gap-4 sm:grid-cols-2">
      <Campo
        etiqueta={t.nombre}
        name="nombre"
        required
        maxLength={140}
        defaultValue={producto?.nombre}
        className="sm:col-span-2"
        autoFocus
      />
      <Campo
        etiqueta={t.codigoBarra}
        name="codigo_barra"
        opcional
        maxLength={50}
        inputMode="numeric"
        defaultValue={producto?.codigo_barra ?? ""}
      />
      <Selector
        etiqueta={t.categoria}
        name="id_categoria"
        defaultValue={producto?.id_categoria ?? ""}
      >
        <option value="">{t.sinCategoria}</option>
        {categorias.map((c) => (
          <option key={c.id} value={c.id}>
            {c.nombre}
          </option>
        ))}
      </Selector>
      <Campo
        etiqueta={t.precioVenta}
        name="precio_venta"
        type="number"
        required
        min="0"
        step="0.01"
        inputMode="decimal"
        defaultValue={producto?.precio_venta}
      />
      {verCostos ? (
        <Campo
          etiqueta={t.precioCosto}
          name="precio_costo"
          type="number"
          min="0"
          step="0.01"
          inputMode="decimal"
          defaultValue={producto?.precio_costo ?? ""}
        />
      ) : (
        <div className="hidden sm:block" />
      )}
      {producto ? (
        <p className="self-end rounded-lg bg-sutil px-3 py-2 text-xs text-suave sm:col-span-2">
          {t.stockActual}: <strong>{producto.stock_actual}</strong> ·{" "}
          {t.stockNoEditable}
        </p>
      ) : (
        <Campo
          etiqueta={t.stockActual}
          name="stock_actual"
          type="number"
          min="0"
          step="1"
          defaultValue={0}
        />
      )}
      <Campo
        etiqueta={t.stockMinimo}
        name="stock_minimo"
        type="number"
        min="0"
        step="1"
        defaultValue={producto?.stock_minimo ?? 0}
      />
      <Campo
        etiqueta={t.stockInicial}
        name="stock_inicial"
        type="number"
        min="0"
        step="1"
        opcional
        ayuda={t.stockInicialAyuda}
        defaultValue={producto?.stock_inicial ?? ""}
      />
      <Campo
        etiqueta={t.vencimiento}
        name="fecha_vencimiento"
        type="date"
        opcional
        defaultValue={producto?.fecha_vencimiento ?? ""}
      />
      <Selector
        etiqueta={t.proveedor}
        name="id_proveedor"
        defaultValue={producto?.id_proveedor ?? ""}
        className="sm:col-span-2"
      >
        <option value="">{t.sinProveedor}</option>
        {proveedores.map((p) => (
          <option key={p.id} value={p.id}>
            {p.razon_social}
          </option>
        ))}
      </Selector>
      <AreaDeTexto
        etiqueta={t.descripcion}
        name="descripcion"
        opcional
        maxLength={500}
        defaultValue={producto?.descripcion ?? ""}
        className="sm:col-span-2"
      />
      {error && (
        <div className="sm:col-span-2">
          <Alerta>{error}</Alerta>
        </div>
      )}
      <div className="sm:col-span-2">
        <PieDeDialogo>
          <Boton onClick={alCancelar}>{t.cancelar}</Boton>
          <Boton type="submit" variante="primario" cargando={guardando}>
            {t.guardar}
          </Boton>
        </PieDeDialogo>
      </div>
    </form>
  );
}

export default function Productos() {
  const { t, idioma } = useTextos();
  const usuario = useUsuario();
  const { avisar, confirmar } = useAvisos();
  const puedeEditar = gestiona(usuario.rol);
  const verCostos = administra(usuario.rol);

  const [texto, setTexto] = useState("");
  const busqueda = useDemora(texto.trim());
  const [idCategoria, setIdCategoria] = useState("");
  const [soloBajo, setSoloBajo] = useState(false);
  const [inactivos, setInactivos] = useState(false);
  const [orden, setOrden] = useState("nombre");
  const [pagina, setPagina] = useState(1);
  const [editando, setEditando] = useState<Producto | "nuevo" | null>(null);
  const [importando, setImportando] = useState(false);

  const filtros = {
    busqueda,
    id_categoria: idCategoria,
    solo_bajo_minimo: soloBajo,
    incluir_inactivos: inactivos,
  };
  const { datos, error, cargando, recargar } = useConsulta<Pagina<Producto>>(
    `/productos${consulta({ ...filtros, orden, pagina, limite: LIMITE })}`,
  );
  const { datos: categorias } = useConsulta<Categoria[]>("/categorias");
  const { datos: proveedores } = useConsulta<Pagina<Proveedor>>(
    puedeEditar ? "/proveedores?limite=100" : null,
  );

  // Cambiar un filtro vuelve a la primera pagina.
  function filtrar<T>(fijar: (valor: T) => void) {
    return (valor: T) => {
      fijar(valor);
      setPagina(1);
    };
  }

  async function desactivar(producto: Producto) {
    const ok = await confirmar({
      titulo: t.desactivarProducto,
      texto: `${producto.nombre}. ${t.desactivarProductoTexto}`,
      accion: t.desactivar,
      peligro: true,
    });
    if (ok === null) return;
    try {
      const respuesta = await pedir<{ mensaje: string }>(
        `/productos/${producto.id}`,
        { method: "DELETE" },
      );
      avisar(respuesta.mensaje);
      recargar();
    } catch (falla) {
      avisar(mensajeDe(falla, t.errorGenerico), "alerta");
    }
  }

  async function reactivar(producto: Producto) {
    try {
      await pedir(`/productos/${producto.id}/reactivar`, { method: "POST" });
      avisar(t.productoReactivado);
      recargar();
    } catch (falla) {
      avisar(mensajeDe(falla, t.errorGenerico), "alerta");
    }
  }

  const items = datos?.items ?? [];
  const hayFiltros = Boolean(busqueda || idCategoria || soloBajo || inactivos);

  return (
    <div className="flex flex-col gap-6">
      <EncabezadoDePagina
        titulo={t.productos}
        descripcion={t.productosTexto}
        acciones={
          puedeEditar && (
            <>
              <Exportar
                ruta={`/productos/exportar${consulta(filtros)}`}
                nombre="productos"
              />
              <Boton icono={Upload} onClick={() => setImportando(true)}>
                {t.importar}
              </Boton>
              <Boton
                variante="primario"
                icono={Plus}
                onClick={() => setEditando("nuevo")}
              >
                {t.nuevoProducto}
              </Boton>
            </>
          )
        }
      />

      <div className="rounded-xl border border-borde bg-superficie shadow-xs">
        <div className="flex flex-wrap items-center gap-2 border-b border-borde p-3">
          <Buscador
            className="w-full sm:w-64"
            placeholder={t.buscarProductoLista}
            aria-label={t.buscar}
            value={texto}
            onChange={(e) => {
              setTexto(e.target.value);
              setPagina(1);
            }}
          />
          <SelectorSuelto
            aria-label={t.categoria}
            value={idCategoria}
            onChange={(e) => filtrar(setIdCategoria)(e.target.value)}
            className="w-full sm:w-44"
          >
            <option value="">
              {t.categoria}: {t.todos.toLowerCase()}
            </option>
            {(categorias ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </SelectorSuelto>
          <SelectorSuelto
            aria-label={t.ordenarPor}
            value={orden}
            onChange={(e) => filtrar(setOrden)(e.target.value)}
            className="w-full sm:w-52"
          >
            <option value="nombre">
              {t.ordenarPor}: {t.porNombre.toLowerCase()}
            </option>
            <option value="precio">
              {t.ordenarPor}: {t.porPrecio.toLowerCase()}
            </option>
            <option value="stock">
              {t.ordenarPor}: {t.porStock.toLowerCase()}
            </option>
          </SelectorSuelto>
          <div className="flex flex-wrap items-center gap-4 px-1">
            <Casilla
              etiqueta={t.soloBajoMinimo}
              checked={soloBajo}
              onChange={(e) => filtrar(setSoloBajo)(e.target.checked)}
            />
            {puedeEditar && (
              <Casilla
                etiqueta={t.mostrarInactivos}
                checked={inactivos}
                onChange={(e) => filtrar(setInactivos)(e.target.checked)}
              />
            )}
          </div>
        </div>

        {error ? (
          <div className="p-4">
            <Alerta>{error.message}</Alerta>
          </div>
        ) : (
          <Tabla
            columnas={[
              { texto: t.producto },
              { texto: t.categoria, oculta: "md" },
              { texto: t.precio, alinear: "derecha" },
              ...(verCostos
                ? [
                    {
                      texto: t.margen,
                      alinear: "derecha" as const,
                      oculta: "lg" as const,
                    },
                  ]
                : []),
              { texto: t.stock, alinear: "derecha" },
              { texto: t.vencimiento, oculta: "lg" },
              ...(puedeEditar
                ? [{ texto: t.acciones, alinear: "derecha" as const, sr: true }]
                : []),
            ]}
            cargando={cargando}
            vacia={items.length === 0}
            estadoVacio={
              <EstadoVacio
                icono={Package}
                titulo={t.sinResultados}
                accion={
                  hayFiltros ? undefined : (
                    puedeEditar && (
                      <Boton
                        variante="primario"
                        icono={Plus}
                        onClick={() => setEditando("nuevo")}
                      >
                        {t.nuevoProducto}
                      </Boton>
                    )
                  )
                }
              />
            }
          >
            {items.map((producto) => (
              <Fila key={producto.id} apagada={!producto.activo}>
                <Celda>
                  <p className="font-medium">
                    {producto.nombre}
                    {!producto.activo && (
                      <span className="ml-2 align-middle">
                        <Insignia>{t.inactivo}</Insignia>
                      </span>
                    )}
                  </p>
                  {producto.codigo_barra && (
                    <p className="font-mono text-xs text-suave">
                      {producto.codigo_barra}
                    </p>
                  )}
                </Celda>
                <Celda oculta="md" className="text-suave">
                  {producto.categoria?.nombre ?? "—"}
                </Celda>
                <Celda alinear="derecha" className="cifra font-medium">
                  {pesos(producto.precio_venta, idioma)}
                </Celda>
                {verCostos && (
                  <Celda alinear="derecha" oculta="lg" className="cifra text-suave">
                    {producto.margen !== null
                      ? `${numero(producto.margen, idioma)}%`
                      : "—"}
                  </Celda>
                )}
                <Celda alinear="derecha">
                  <NivelDeStock producto={producto} />
                </Celda>
                <Celda oculta="lg" className="cifra text-suave">
                  {producto.fecha_vencimiento
                    ? fecha(producto.fecha_vencimiento, idioma)
                    : "—"}
                </Celda>
                {puedeEditar && (
                  <Celda alinear="derecha">
                    <div className="flex justify-end gap-0.5">
                      {producto.activo ? (
                        <>
                          <BotonIcono
                            etiqueta={`${t.editar}: ${producto.nombre}`}
                            icono={Pencil}
                            onClick={() => setEditando(producto)}
                          />
                          <BotonIcono
                            etiqueta={`${t.desactivar}: ${producto.nombre}`}
                            icono={PowerOff}
                            onClick={() => desactivar(producto)}
                          />
                        </>
                      ) : (
                        <BotonIcono
                          etiqueta={`${t.reactivar}: ${producto.nombre}`}
                          icono={RotateCcw}
                          onClick={() => reactivar(producto)}
                        />
                      )}
                    </div>
                  </Celda>
                )}
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
        abierto={editando !== null}
        alCerrar={() => setEditando(null)}
        titulo={editando === "nuevo" ? t.nuevoProducto : t.editarProducto}
        ancho="lg"
      >
        {editando !== null && (
          <FormularioDeProducto
            producto={editando === "nuevo" ? null : editando}
            categorias={categorias ?? []}
            proveedores={proveedores?.items ?? []}
            verCostos={verCostos}
            alCancelar={() => setEditando(null)}
            alGuardar={() => {
              setEditando(null);
              recargar();
            }}
          />
        )}
      </Dialogo>

      <DialogoDeImportacion
        abierto={importando}
        alCerrar={() => setImportando(false)}
        base="/productos"
        que={t.productos}
        conCategorias
        alTerminar={recargar}
      />
    </div>
  );
}
