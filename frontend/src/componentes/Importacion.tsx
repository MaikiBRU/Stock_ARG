"use client";

import { FileUp } from "lucide-react";
import { useState } from "react";

import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton } from "@/componentes/ui/Boton";
import { Casilla } from "@/componentes/ui/Campo";
import { Dialogo, PieDeDialogo } from "@/componentes/ui/Dialogo";
import { Alerta, Insignia } from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { formatear } from "@/i18n/textos";
import { mensajeDe, pedir } from "@/lib/api";

type Resultado = {
  aplicada: boolean;
  a_crear: number;
  a_actualizar: number;
  con_error: number;
  filas: {
    numero: number;
    accion: "crear" | "actualizar" | "error";
    nombre: string | null;
    codigo_barra: string | null;
    errores: string[];
  }[];
};

/**
 * Importacion en dos pasos (RF-C09): primero se previsualiza, y solo
 * se escribe cuando la persona confirma lo que vio.
 */
export function DialogoDeImportacion({
  abierto,
  alCerrar,
  base,
  que,
  conCategorias = false,
  alTerminar,
}: {
  abierto: boolean;
  alCerrar: () => void;
  /** Ruta de la API: "/productos", "/clientes" o "/proveedores". */
  base: string;
  que: string;
  conCategorias?: boolean;
  alTerminar: () => void;
}) {
  const { t } = useTextos();
  const { avisar } = useAvisos();
  const [archivo, setArchivo] = useState<File | null>(null);
  const [crearCategorias, setCrearCategorias] = useState(true);
  const [vista, setVista] = useState<Resultado | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function cerrar() {
    setArchivo(null);
    setVista(null);
    setError(null);
    alCerrar();
  }

  function formulario() {
    const datos = new FormData();
    if (archivo) datos.append("archivo", archivo);
    if (conCategorias) {
      datos.append("crear_categorias", String(crearCategorias));
    }
    return datos;
  }

  async function previsualizar() {
    setOcupado(true);
    setError(null);
    try {
      setVista(
        await pedir<Resultado>(`${base}/importar/previsualizar`, {
          method: "POST",
          cuerpo: formulario(),
        }),
      );
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
    } finally {
      setOcupado(false);
    }
  }

  async function aplicar() {
    setOcupado(true);
    setError(null);
    try {
      const hecho = await pedir<Resultado>(`${base}/importar`, {
        method: "POST",
        cuerpo: formulario(),
      });
      avisar(
        formatear(t.importacionAplicada, {
          c: hecho.a_crear,
          a: hecho.a_actualizar,
        }),
      );
      alTerminar();
      cerrar();
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
    } finally {
      setOcupado(false);
    }
  }

  const aplicables = vista ? vista.a_crear + vista.a_actualizar : 0;
  const tonos = { crear: "ok", actualizar: "marca", error: "alerta" } as const;
  const acciones = {
    crear: t.accionCrear,
    actualizar: t.accionActualizar,
    error: t.accionError,
  };

  return (
    <Dialogo
      abierto={abierto}
      alCerrar={cerrar}
      titulo={formatear(t.importarTitulo, { que: que.toLowerCase() })}
      descripcion={t.importarTexto}
      ancho={vista ? "lg" : "md"}
    >
      <div className="flex flex-col gap-4">
        <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-borde-fuerte px-4 py-6 text-center text-sm transition-colors focus-within:border-marca hover:bg-sutil/60">
          <FileUp size={20} className="text-suave" aria-hidden />
          <span className="font-medium break-all">
            {archivo ? archivo.name : t.archivo}
          </span>
          <span className="text-xs text-suave">CSV · 2 MB</span>
          <input
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            onChange={(e) => {
              setArchivo(e.target.files?.[0] ?? null);
              setVista(null);
            }}
          />
        </label>

        {conCategorias && (
          <Casilla
            etiqueta={t.crearCategorias}
            checked={crearCategorias}
            onChange={(e) => {
              setCrearCategorias(e.target.checked);
              setVista(null);
            }}
          />
        )}

        {error && <Alerta>{error}</Alerta>}

        {vista && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-3 gap-2 text-center">
              {[
                { texto: t.aCrear, valor: vista.a_crear, tono: "text-ok" },
                {
                  texto: t.aActualizar,
                  valor: vista.a_actualizar,
                  tono: "text-marca-texto",
                },
                {
                  texto: t.conError,
                  valor: vista.con_error,
                  tono: "text-alerta",
                },
              ].map((cifra) => (
                <div
                  key={cifra.texto}
                  className="rounded-lg border border-borde px-2 py-3"
                >
                  <p className={`cifra text-xl font-semibold ${cifra.tono}`}>
                    {cifra.valor}
                  </p>
                  <p className="text-xs text-suave">{cifra.texto}</p>
                </div>
              ))}
            </div>
            {vista.con_error > 0 && (
              <p className="text-xs text-suave">{t.corregirErrores}</p>
            )}
            <div className="max-h-64 overflow-y-auto rounded-lg border border-borde">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-superficie">
                  <tr className="border-b border-borde text-left text-xs text-suave">
                    <th className="px-3 py-2 font-medium">{t.fila}</th>
                    <th className="px-3 py-2 font-medium">{t.nombre}</th>
                    <th className="px-3 py-2 font-medium">{t.accion}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borde">
                  {vista.filas.map((fila) => (
                    <tr key={fila.numero} className="align-top">
                      <td className="cifra px-3 py-2 text-suave">
                        {fila.numero}
                      </td>
                      <td className="px-3 py-2">
                        {fila.nombre ?? "—"}
                        {fila.errores.length > 0 && (
                          <ul className="mt-0.5 text-xs text-alerta">
                            {fila.errores.map((texto) => (
                              <li key={texto}>{texto}</li>
                            ))}
                          </ul>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <Insignia tono={tonos[fila.accion]}>
                          {acciones[fila.accion]}
                        </Insignia>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <PieDeDialogo>
        <Boton onClick={cerrar}>{t.cancelar}</Boton>
        {vista ? (
          <Boton
            variante="primario"
            onClick={aplicar}
            cargando={ocupado}
            disabled={aplicables === 0}
          >
            {formatear(t.aplicar, { n: aplicables })}
          </Boton>
        ) : (
          <Boton
            variante="primario"
            onClick={previsualizar}
            cargando={ocupado}
            disabled={!archivo}
          >
            {t.previsualizar}
          </Boton>
        )}
      </PieDeDialogo>
    </Dialogo>
  );
}
