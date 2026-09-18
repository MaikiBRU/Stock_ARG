"use client";

import { Power, PowerOff, Sparkles, Wallet } from "lucide-react";
import { useState } from "react";

import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton, BotonIcono } from "@/componentes/ui/Boton";
import { Casilla, claseDeEntrada } from "@/componentes/ui/Campo";
import { Alerta, EstadoVacio, Insignia } from "@/componentes/ui/Superficie";
import { Celda, Fila, Tabla } from "@/componentes/ui/Tabla";
import { useTextos } from "@/i18n/proveedor";
import { mensajeDe, pedir } from "@/lib/api";
import { useConsulta } from "@/lib/ganchos";

type Medio = { id: number; nombre: string; es_efectivo: boolean; activo: boolean };

export default function Medios() {
  const { t } = useTextos();
  const { avisar } = useAvisos();
  const { datos, error, cargando, recargar } = useConsulta<Medio[]>(
    "/medios-pago?solo_activos=false",
  );
  const [nombre, setNombre] = useState("");
  const [efectivo, setEfectivo] = useState(false);
  const [guardando, setGuardando] = useState(false);

  async function accion(promesa: Promise<unknown>) {
    try {
      await promesa;
      avisar(t.cambiosGuardados);
      return true;
    } catch (falla) {
      avisar(mensajeDe(falla, t.errorGenerico), "alerta");
      return false;
    } finally {
      recargar();
    }
  }

  async function crear(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setGuardando(true);
    const ok = await accion(
      pedir("/medios-pago", {
        method: "POST",
        cuerpo: { nombre: nombre.trim(), es_efectivo: efectivo },
      }),
    );
    if (ok) {
      setNombre("");
      setEfectivo(false);
    }
    setGuardando(false);
  }

  const items = datos ?? [];

  return (
    <div className="rounded-xl border border-borde bg-superficie shadow-xs">
      <form
        onSubmit={crear}
        className="flex flex-wrap items-center gap-3 border-b border-borde p-3"
      >
        <input
          aria-label={t.nuevoMedio}
          placeholder={t.nuevoMedio}
          required
          maxLength={50}
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          className={`${claseDeEntrada} w-full sm:w-64`}
        />
        <Casilla
          etiqueta={t.esEfectivo}
          checked={efectivo}
          onChange={(e) => setEfectivo(e.target.checked)}
        />
        <Boton type="submit" variante="primario" cargando={guardando}>
          {t.guardar}
        </Boton>
      </form>

      {error ? (
        <div className="p-4">
          <Alerta>{error.estado === 403 ? t.sinPermiso : error.message}</Alerta>
        </div>
      ) : (
        <Tabla
          columnas={[
            { texto: t.nombre },
            { texto: t.tipo },
            { texto: t.estado },
            { texto: t.acciones, alinear: "derecha", sr: true },
          ]}
          cargando={cargando}
          vacia={items.length === 0}
          estadoVacio={
            <EstadoVacio
              icono={Wallet}
              titulo={t.sinDatos}
              accion={
                <Boton
                  icono={Sparkles}
                  onClick={() =>
                    accion(pedir("/medios-pago/sembrar", { method: "POST" }))
                  }
                >
                  {t.sembrarMedios}
                </Boton>
              }
            />
          }
        >
          {items.map((medio) => (
            <Fila key={medio.id} apagada={!medio.activo}>
              <Celda className="font-medium">{medio.nombre}</Celda>
              <Celda className="text-suave">
                {medio.es_efectivo ? t.efectivo : "—"}
              </Celda>
              <Celda>
                <Insignia tono={medio.activo ? "ok" : "neutro"}>
                  {medio.activo ? t.activo : t.inactivo}
                </Insignia>
              </Celda>
              <Celda alinear="derecha">
                {medio.activo ? (
                  <BotonIcono
                    etiqueta={`${t.deshabilitar}: ${medio.nombre}`}
                    icono={PowerOff}
                    onClick={() =>
                      accion(pedir(`/medios-pago/${medio.id}`, { method: "DELETE" }))
                    }
                  />
                ) : (
                  <BotonIcono
                    etiqueta={`${t.habilitar}: ${medio.nombre}`}
                    icono={Power}
                    onClick={() =>
                      accion(
                        pedir(`/medios-pago/${medio.id}/habilitar`, {
                          method: "POST",
                        }),
                      )
                    }
                  />
                )}
              </Celda>
            </Fila>
          ))}
        </Tabla>
      )}
    </div>
  );
}
