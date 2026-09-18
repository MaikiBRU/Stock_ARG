"use client";

import { ScrollText } from "lucide-react";
import { useState } from "react";

import { claseDeEntrada } from "@/componentes/ui/Campo";
import { Buscador } from "@/componentes/ui/Controles";
import { Alerta, EstadoVacio, Insignia } from "@/componentes/ui/Superficie";
import { Celda, Fila, Paginacion, Tabla } from "@/componentes/ui/Tabla";
import { useTextos } from "@/i18n/proveedor";
import { consulta, type Pagina } from "@/lib/api";
import { fechaHora } from "@/lib/formato";
import { useConsulta, useDemora } from "@/lib/ganchos";

type Registro = {
  id: number;
  email_usuario: string | null;
  accion: string;
  entidad: string;
  id_entidad: string | null;
  detalle: Record<string, unknown> | null;
  fecha_hora: string;
};

const LIMITE = 50;

/** Detalle compacto: clave=valor, sin llaves ni comillas. */
function resumir(detalle: Registro["detalle"]) {
  if (!detalle) return "—";
  return Object.entries(detalle)
    .map(([clave, valor]) =>
      `${clave}=${typeof valor === "object" ? JSON.stringify(valor) : String(valor)}`,
    )
    .join(" · ");
}

export default function Auditoria() {
  const { t, idioma } = useTextos();
  const [accion, setAccion] = useState("");
  const [entidad, setEntidad] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [pagina, setPagina] = useState(1);
  const filtroAccion = useDemora(accion.trim());
  const filtroEntidad = useDemora(entidad.trim());

  const { datos, error, cargando } = useConsulta<Pagina<Registro>>(
    `/auditoria${consulta({
      accion: filtroAccion,
      entidad: filtroEntidad,
      desde,
      hasta,
      pagina,
      limite: LIMITE,
    })}`,
  );
  const items = datos?.items ?? [];

  function filtrar(fijar: (valor: string) => void) {
    return (valor: string) => {
      fijar(valor);
      setPagina(1);
    };
  }

  return (
    <div className="rounded-xl border border-borde bg-superficie shadow-xs">
      <div className="flex flex-wrap items-center gap-2 border-b border-borde p-3">
        <Buscador
          className="w-full sm:w-44"
          placeholder={t.accion}
          aria-label={t.accion}
          value={accion}
          onChange={(e) => filtrar(setAccion)(e.target.value)}
        />
        <Buscador
          className="w-full sm:w-44"
          placeholder={t.entidad}
          aria-label={t.entidad}
          value={entidad}
          onChange={(e) => filtrar(setEntidad)(e.target.value)}
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
      </div>

      {error ? (
        <div className="p-4">
          <Alerta>{error.estado === 403 ? t.sinPermiso : error.message}</Alerta>
        </div>
      ) : (
        <Tabla
          columnas={[
            { texto: t.fecha },
            { texto: t.usuario, oculta: "md" },
            { texto: t.accion },
            { texto: t.entidad, oculta: "sm" },
            { texto: t.detalle, oculta: "lg" },
          ]}
          cargando={cargando}
          vacia={items.length === 0}
          estadoVacio={<EstadoVacio icono={ScrollText} titulo={t.sinResultados} />}
        >
          {items.map((registro) => (
            <Fila key={registro.id}>
              <Celda className="cifra whitespace-nowrap text-suave">
                {fechaHora(registro.fecha_hora, idioma)}
              </Celda>
              <Celda oculta="md" className="text-suave">
                {registro.email_usuario ?? "—"}
              </Celda>
              <Celda>
                <Insignia tono="marca">{registro.accion}</Insignia>
              </Celda>
              <Celda oculta="sm" className="text-suave">
                {registro.entidad}
                {registro.id_entidad && ` #${registro.id_entidad}`}
              </Celda>
              <Celda oculta="lg" className="max-w-md">
                <span
                  className="block truncate font-mono text-xs text-suave"
                  title={resumir(registro.detalle)}
                >
                  {resumir(registro.detalle)}
                </span>
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
  );
}
