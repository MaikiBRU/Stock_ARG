"use client";

import { Pencil, Plus, Trash2, Upload, type LucideIcon } from "lucide-react";
import { useState } from "react";

import { DialogoDeImportacion } from "@/componentes/Importacion";
import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton, BotonIcono } from "@/componentes/ui/Boton";
import { AreaDeTexto, Campo, Casilla } from "@/componentes/ui/Campo";
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
import { consulta, mensajeDe, pedir, type Pagina } from "@/lib/api";
import { fecha, numero, pesos } from "@/lib/formato";
import { useConsulta, useDemora } from "@/lib/ganchos";

/** Fila de cliente o de proveedor: todo texto salvo id y activo. */
export type Ficha = {
  id: number;
  activo: boolean;
  telefono: string | null;
  email: string | null;
  localidad: string | null;
  [clave: string]: string | number | boolean | null;
};

export type CampoDeFicha = {
  clave: string;
  etiqueta: string;
  max: number;
  requerido?: boolean;
  tipo?: "text" | "email" | "tel";
  largo?: boolean;
  area?: boolean;
};

type Resumen = {
  cantidad_compras: number;
  total_comprado: string;
  ultima_compra: string | null;
};

type ProductoDelProveedor = {
  id: number;
  nombre: string;
  stock_actual: number;
};

type Configuracion = {
  titulo: string;
  descripcion: string;
  icono: LucideIcon;
  /** "/clientes" o "/proveedores". */
  base: string;
  nombreDe: (ficha: Ficha) => string;
  secundarioDe: (ficha: Ficha) => string | null;
  campos: CampoDeFicha[];
  textos: {
    nuevo: string;
    editar: string;
    guardado: string;
    eliminar: string;
    eliminarTexto: string;
    buscar: string;
  };
  puedeEditar: boolean;
  conProductos?: boolean;
};

const LIMITE = 25;

function Formulario({
  config,
  ficha,
  alGuardar,
  alCancelar,
}: {
  config: Configuracion;
  ficha: Ficha | null;
  alGuardar: () => void;
  alCancelar: () => void;
}) {
  const { t } = useTextos();
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function guardar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const f = new FormData(evento.currentTarget);
    // Los campos vacios viajan como null: la API no guarda textos vacios.
    const cuerpo = Object.fromEntries(
      config.campos.map((campo) => [
        campo.clave,
        String(f.get(campo.clave) ?? "").trim() || null,
      ]),
    );
    setGuardando(true);
    setError(null);
    try {
      await pedir(ficha ? `${config.base}/${ficha.id}` : config.base, {
        method: ficha ? "PUT" : "POST",
        cuerpo,
      });
      alGuardar();
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
      setGuardando(false);
    }
  }

  return (
    <form onSubmit={guardar} className="grid gap-4 sm:grid-cols-2">
      {config.campos.map((campo, i) =>
        campo.area ? (
          <AreaDeTexto
            key={campo.clave}
            etiqueta={campo.etiqueta}
            name={campo.clave}
            maxLength={campo.max}
            opcional={!campo.requerido}
            defaultValue={String(ficha?.[campo.clave] ?? "")}
            className="sm:col-span-2"
          />
        ) : (
          <Campo
            key={campo.clave}
            etiqueta={campo.etiqueta}
            name={campo.clave}
            type={campo.tipo ?? "text"}
            required={campo.requerido}
            opcional={!campo.requerido}
            maxLength={campo.max}
            defaultValue={String(ficha?.[campo.clave] ?? "")}
            autoFocus={i === 0}
            className={campo.largo ? "sm:col-span-2" : ""}
          />
        ),
      )}
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

function Detalle({
  config,
  ficha,
  alEditar,
}: {
  config: Configuracion;
  ficha: Ficha;
  alEditar: () => void;
}) {
  const { t, idioma } = useTextos();
  const { datos: resumen } = useConsulta<Resumen>(
    config.puedeEditar ? `${config.base}/${ficha.id}/compras` : null,
  );
  const { datos: productos } = useConsulta<ProductoDelProveedor[]>(
    config.conProductos ? `${config.base}/${ficha.id}/productos` : null,
  );

  return (
    <div className="flex flex-col gap-5">
      {config.puedeEditar && (
        <div className="grid grid-cols-3 gap-2">
          {[
            {
              etiqueta: t.cantidadCompras,
              valor: resumen ? numero(resumen.cantidad_compras, idioma) : null,
            },
            {
              etiqueta: t.totalComprado,
              valor: resumen ? pesos(resumen.total_comprado, idioma) : null,
            },
            {
              etiqueta: t.ultimaCompra,
              valor: resumen
                ? resumen.ultima_compra
                  ? fecha(resumen.ultima_compra, idioma)
                  : t.nunca
                : null,
            },
          ].map((dato) => (
            <div
              key={dato.etiqueta}
              className="min-w-0 rounded-lg border border-borde px-3 py-2.5"
            >
              <p className="truncate text-xs text-suave">{dato.etiqueta}</p>
              {dato.valor === null ? (
                <Esqueleto className="mt-1.5 h-5 w-16" />
              ) : (
                <p className="cifra mt-0.5 truncate text-sm font-semibold">
                  {dato.valor}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      <dl className="grid gap-x-4 gap-y-3 text-sm sm:grid-cols-2">
        {config.campos.map((campo) => (
          <div
            key={campo.clave}
            className={campo.area || campo.largo ? "sm:col-span-2" : ""}
          >
            <dt className="text-xs text-suave">{campo.etiqueta}</dt>
            <dd className="mt-0.5 break-words whitespace-pre-line">
              {ficha[campo.clave] ? String(ficha[campo.clave]) : "—"}
            </dd>
          </div>
        ))}
      </dl>

      {config.conProductos && (
        <div>
          <h3 className="mb-2 text-xs font-medium text-suave">
            {t.productosDelProveedor}
          </h3>
          {productos === null ? (
            <Esqueleto className="h-16" />
          ) : productos.length === 0 ? (
            <p className="text-sm text-suave">{t.sinDatos}</p>
          ) : (
            <ul className="divide-y divide-borde rounded-lg border border-borde text-sm">
              {productos.map((producto) => (
                <li
                  key={producto.id}
                  className="flex justify-between gap-3 px-3 py-2"
                >
                  <span className="truncate">{producto.nombre}</span>
                  <span className="cifra shrink-0 text-suave">
                    {numero(producto.stock_actual, idioma)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {config.puedeEditar && ficha.activo && (
        <PieDeDialogo>
          <Boton icono={Pencil} onClick={alEditar}>
            {t.editar}
          </Boton>
        </PieDeDialogo>
      )}
    </div>
  );
}

/** Listado, alta, edicion y baja de clientes o de proveedores. */
export function Directorio({ config }: { config: Configuracion }) {
  const { t } = useTextos();
  const { avisar, confirmar } = useAvisos();
  const [texto, setTexto] = useState("");
  const busqueda = useDemora(texto.trim());
  const [inactivos, setInactivos] = useState(false);
  const [pagina, setPagina] = useState(1);
  const [viendo, setViendo] = useState<Ficha | null>(null);
  const [editando, setEditando] = useState<Ficha | "nueva" | null>(null);
  const [importando, setImportando] = useState(false);

  const filtros = { busqueda, incluir_inactivos: inactivos };
  const { datos, error, cargando, recargar } = useConsulta<Pagina<Ficha>>(
    `${config.base}${consulta({ ...filtros, pagina, limite: LIMITE })}`,
  );

  async function eliminar(ficha: Ficha) {
    const ok = await confirmar({
      titulo: config.textos.eliminar,
      texto: `${config.nombreDe(ficha)}. ${config.textos.eliminarTexto}`,
      accion: t.eliminar,
      peligro: true,
    });
    if (ok === null) return;
    try {
      const respuesta = await pedir<{ mensaje: string }>(
        `${config.base}/${ficha.id}`,
        { method: "DELETE" },
      );
      avisar(respuesta.mensaje);
      recargar();
    } catch (falla) {
      avisar(mensajeDe(falla, t.errorGenerico), "alerta");
    }
  }

  const items = datos?.items ?? [];

  return (
    <div className="flex flex-col gap-6">
      <EncabezadoDePagina
        titulo={config.titulo}
        descripcion={config.descripcion}
        acciones={
          config.puedeEditar && (
            <>
              <Exportar
                ruta={`${config.base}/exportar${consulta(filtros)}`}
                nombre={config.base.slice(1)}
              />
              <Boton icono={Upload} onClick={() => setImportando(true)}>
                {t.importar}
              </Boton>
              <Boton
                variante="primario"
                icono={Plus}
                onClick={() => setEditando("nueva")}
              >
                {config.textos.nuevo}
              </Boton>
            </>
          )
        }
      />

      <div className="rounded-xl border border-borde bg-superficie shadow-xs">
        <div className="flex flex-wrap items-center gap-3 border-b border-borde p-3">
          <Buscador
            className="w-full sm:w-72"
            placeholder={config.textos.buscar}
            aria-label={t.buscar}
            value={texto}
            onChange={(e) => {
              setTexto(e.target.value);
              setPagina(1);
            }}
          />
          {config.puedeEditar && (
            <Casilla
              etiqueta={t.mostrarInactivos}
              checked={inactivos}
              onChange={(e) => {
                setInactivos(e.target.checked);
                setPagina(1);
              }}
            />
          )}
        </div>

        {error ? (
          <div className="p-4">
            <Alerta>{error.estado === 403 ? t.sinPermiso : error.message}</Alerta>
          </div>
        ) : (
          <Tabla
            columnas={[
              { texto: t.nombre },
              { texto: t.telefono, oculta: "md" },
              { texto: t.correo, oculta: "lg" },
              { texto: t.localidad, oculta: "sm" },
              ...(config.puedeEditar
                ? [{ texto: t.acciones, alinear: "derecha" as const, sr: true }]
                : []),
            ]}
            cargando={cargando}
            vacia={items.length === 0}
            estadoVacio={
              <EstadoVacio icono={config.icono} titulo={t.sinResultados} />
            }
          >
            {items.map((ficha) => {
              const secundario = config.secundarioDe(ficha);
              return (
                <Fila
                  key={ficha.id}
                  alElegir={() => setViendo(ficha)}
                  apagada={!ficha.activo}
                >
                  <Celda>
                    <p className="font-medium">
                      {config.nombreDe(ficha)}
                      {!ficha.activo && (
                        <span className="ml-2 align-middle">
                          <Insignia>{t.inactivo}</Insignia>
                        </span>
                      )}
                    </p>
                    {secundario && (
                      <p className="cifra text-xs text-suave">{secundario}</p>
                    )}
                  </Celda>
                  <Celda oculta="md" className="cifra text-suave">
                    {ficha.telefono ?? "—"}
                  </Celda>
                  <Celda oculta="lg" className="text-suave">
                    {ficha.email ?? "—"}
                  </Celda>
                  <Celda oculta="sm" className="text-suave">
                    {ficha.localidad ?? "—"}
                  </Celda>
                  {config.puedeEditar && (
                    <Celda alinear="derecha">
                      {ficha.activo && (
                        <div
                          className="flex justify-end gap-0.5"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <BotonIcono
                            etiqueta={`${t.editar}: ${config.nombreDe(ficha)}`}
                            icono={Pencil}
                            onClick={() => setEditando(ficha)}
                          />
                          <BotonIcono
                            etiqueta={`${t.eliminar}: ${config.nombreDe(ficha)}`}
                            icono={Trash2}
                            onClick={() => eliminar(ficha)}
                          />
                        </div>
                      )}
                    </Celda>
                  )}
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
        abierto={viendo !== null}
        alCerrar={() => setViendo(null)}
        titulo={viendo ? config.nombreDe(viendo) : ""}
        ancho="lg"
      >
        {viendo && (
          <Detalle
            config={config}
            ficha={viendo}
            alEditar={() => {
              setEditando(viendo);
              setViendo(null);
            }}
          />
        )}
      </Dialogo>

      <Dialogo
        abierto={editando !== null}
        alCerrar={() => setEditando(null)}
        titulo={
          editando === "nueva" ? config.textos.nuevo : config.textos.editar
        }
        ancho="lg"
      >
        {editando !== null && (
          <Formulario
            config={config}
            ficha={editando === "nueva" ? null : editando}
            alCancelar={() => setEditando(null)}
            alGuardar={() => {
              setEditando(null);
              avisar(config.textos.guardado);
              recargar();
            }}
          />
        )}
      </Dialogo>

      {config.puedeEditar && (
        <DialogoDeImportacion
          abierto={importando}
          alCerrar={() => setImportando(false)}
          base={config.base}
          que={config.titulo}
          alTerminar={recargar}
        />
      )}
    </div>
  );
}
