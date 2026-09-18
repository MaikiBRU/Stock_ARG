"use client";

import { Pencil, Plus, Tags, Trash2 } from "lucide-react";
import { useState } from "react";

import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton, BotonIcono } from "@/componentes/ui/Boton";
import { AreaDeTexto, Campo } from "@/componentes/ui/Campo";
import { Dialogo, PieDeDialogo } from "@/componentes/ui/Dialogo";
import {
  Alerta,
  EncabezadoDePagina,
  EstadoVacio,
} from "@/componentes/ui/Superficie";
import { Celda, Fila, Tabla } from "@/componentes/ui/Tabla";
import { useTextos } from "@/i18n/proveedor";
import { mensajeDe, pedir } from "@/lib/api";
import { useConsulta } from "@/lib/ganchos";

type Categoria = { id: number; nombre: string; descripcion: string | null };

function Formulario({
  categoria,
  alGuardar,
  alCancelar,
}: {
  categoria: Categoria | null;
  alGuardar: () => void;
  alCancelar: () => void;
}) {
  const { t } = useTextos();
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function guardar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const f = new FormData(evento.currentTarget);
    setGuardando(true);
    setError(null);
    try {
      await pedir(categoria ? `/categorias/${categoria.id}` : "/categorias", {
        method: categoria ? "PUT" : "POST",
        cuerpo: {
          nombre: String(f.get("nombre")).trim(),
          descripcion: String(f.get("descripcion")).trim() || null,
        },
      });
      alGuardar();
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
      setGuardando(false);
    }
  }

  return (
    <form onSubmit={guardar} className="flex flex-col gap-4">
      <Campo
        etiqueta={t.nombre}
        name="nombre"
        required
        maxLength={80}
        defaultValue={categoria?.nombre}
        autoFocus
      />
      <AreaDeTexto
        etiqueta={t.descripcion}
        name="descripcion"
        opcional
        maxLength={255}
        defaultValue={categoria?.descripcion ?? ""}
      />
      {error && <Alerta>{error}</Alerta>}
      <PieDeDialogo>
        <Boton onClick={alCancelar}>{t.cancelar}</Boton>
        <Boton type="submit" variante="primario" cargando={guardando}>
          {t.guardar}
        </Boton>
      </PieDeDialogo>
    </form>
  );
}

export default function Categorias() {
  const { t } = useTextos();
  const { avisar, confirmar } = useAvisos();
  const { datos, error, cargando, recargar } =
    useConsulta<Categoria[]>("/categorias");
  const [editando, setEditando] = useState<Categoria | "nueva" | null>(null);

  async function eliminar(categoria: Categoria) {
    const ok = await confirmar({
      titulo: t.eliminarCategoria,
      texto: `${categoria.nombre}. ${t.eliminarCategoriaTexto}`,
      accion: t.eliminar,
      peligro: true,
    });
    if (ok === null) return;
    try {
      const respuesta = await pedir<{ mensaje: string }>(
        `/categorias/${categoria.id}`,
        { method: "DELETE" },
      );
      avisar(respuesta.mensaje);
      recargar();
    } catch (falla) {
      avisar(mensajeDe(falla, t.errorGenerico), "alerta");
    }
  }

  const items = datos ?? [];

  return (
    <div className="flex flex-col gap-6">
      <EncabezadoDePagina
        titulo={t.categorias}
        descripcion={t.categoriasTexto}
        acciones={
          <Boton
            variante="primario"
            icono={Plus}
            onClick={() => setEditando("nueva")}
          >
            {t.nuevaCategoria}
          </Boton>
        }
      />

      <div className="rounded-xl border border-borde bg-superficie shadow-xs">
        {error ? (
          <div className="p-4">
            <Alerta>{error.estado === 403 ? t.sinPermiso : error.message}</Alerta>
          </div>
        ) : (
          <Tabla
            columnas={[
              { texto: t.nombre },
              { texto: t.descripcion, oculta: "sm" },
              { texto: t.acciones, alinear: "derecha", sr: true },
            ]}
            cargando={cargando}
            vacia={items.length === 0}
            estadoVacio={<EstadoVacio icono={Tags} titulo={t.sinDatos} />}
          >
            {items.map((categoria) => (
              <Fila key={categoria.id}>
                <Celda className="font-medium">{categoria.nombre}</Celda>
                <Celda oculta="sm" className="text-suave">
                  {categoria.descripcion ?? "—"}
                </Celda>
                <Celda alinear="derecha">
                  <div className="flex justify-end gap-0.5">
                    <BotonIcono
                      etiqueta={`${t.editar}: ${categoria.nombre}`}
                      icono={Pencil}
                      onClick={() => setEditando(categoria)}
                    />
                    <BotonIcono
                      etiqueta={`${t.eliminar}: ${categoria.nombre}`}
                      icono={Trash2}
                      onClick={() => eliminar(categoria)}
                    />
                  </div>
                </Celda>
              </Fila>
            ))}
          </Tabla>
        )}
      </div>

      <Dialogo
        abierto={editando !== null}
        alCerrar={() => setEditando(null)}
        titulo={editando === "nueva" ? t.nuevaCategoria : t.editarCategoria}
      >
        {editando !== null && (
          <Formulario
            categoria={editando === "nueva" ? null : editando}
            alCancelar={() => setEditando(null)}
            alGuardar={() => {
              setEditando(null);
              avisar(t.cambiosGuardados);
              recargar();
            }}
          />
        )}
      </Dialogo>
    </div>
  );
}
