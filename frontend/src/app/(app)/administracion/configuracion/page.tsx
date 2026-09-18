"use client";

import { useState } from "react";

import { useUsuario } from "@/componentes/Sesion";
import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton } from "@/componentes/ui/Boton";
import { Campo } from "@/componentes/ui/Campo";
import { Alerta, Esqueleto, Tarjeta } from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { mensajeDe, pedir } from "@/lib/api";
import { useConsulta } from "@/lib/ganchos";
import { administra } from "@/lib/rutas";

type Configuracion = { valores: Record<string, string> };

export default function AjustesDelComercio() {
  const { t } = useTextos();
  const usuario = useUsuario();
  const { avisar } = useAvisos();
  const puedeEditar = administra(usuario.rol);
  const { datos, error, recargar } =
    useConsulta<Configuracion>("/configuracion");
  const [guardando, setGuardando] = useState(false);
  const [falla, setFalla] = useState<string | null>(null);

  const campos = [
    { clave: "nombre_comercio", etiqueta: t.nombreComercio, tipo: "text" },
    { clave: "dias_aviso_vencimiento", etiqueta: t.diasAvisoVencimiento, min: 1, max: 365 },
    { clave: "stock_umbral_bajo", etiqueta: t.umbralBajo, min: 0, max: 99 },
    { clave: "stock_umbral_medio", etiqueta: t.umbralMedio, min: 1, max: 100 },
    { clave: "descuento_max_vendedor", etiqueta: t.descuentoMaxVendedor, min: 0, max: 100 },
  ];

  async function guardar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const f = new FormData(evento.currentTarget);
    // Solo viaja lo que cambio: el resto queda como estaba.
    const cambios = Object.fromEntries(
      campos
        .map((c) => [c.clave, String(f.get(c.clave) ?? "").trim()])
        .filter(([clave, valor]) => valor !== datos?.valores[clave]),
    );
    if (Object.keys(cambios).length === 0) return;
    setGuardando(true);
    setFalla(null);
    try {
      await pedir("/configuracion", { method: "PUT", cuerpo: { cambios } });
      avisar(t.cambiosGuardados);
      recargar();
    } catch (e) {
      setFalla(mensajeDe(e, t.errorGenerico));
    } finally {
      setGuardando(false);
    }
  }

  if (error) {
    return <Alerta>{error.estado === 403 ? t.sinPermiso : error.message}</Alerta>;
  }

  return (
    <Tarjeta
      titulo={t.configuracion}
      descripcion={puedeEditar ? undefined : t.soloLectura}
      className="max-w-2xl"
    >
      {!datos ? (
        <Esqueleto className="h-64" />
      ) : (
        <form onSubmit={guardar} className="grid gap-4 sm:grid-cols-2">
          {campos.map((campo) => (
            <Campo
              key={campo.clave}
              etiqueta={campo.etiqueta}
              name={campo.clave}
              type={campo.tipo ?? "number"}
              min={campo.min}
              max={campo.max}
              step={campo.tipo ? undefined : 1}
              required
              maxLength={campo.tipo ? 80 : undefined}
              disabled={!puedeEditar}
              defaultValue={datos.valores[campo.clave] ?? ""}
              className={campo.tipo ? "sm:col-span-2" : ""}
            />
          ))}
          {falla && (
            <div className="sm:col-span-2">
              <Alerta>{falla}</Alerta>
            </div>
          )}
          {puedeEditar && (
            <div className="flex justify-end sm:col-span-2">
              <Boton type="submit" variante="primario" cargando={guardando}>
                {t.guardar}
              </Boton>
            </div>
          )}
        </form>
      )}
    </Tarjeta>
  );
}
