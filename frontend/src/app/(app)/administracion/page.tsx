"use client";

import { Plus, Power, PowerOff, UsersRound } from "lucide-react";
import { useState } from "react";

import { useUsuario } from "@/componentes/Sesion";
import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton, BotonIcono } from "@/componentes/ui/Boton";
import { Campo, Selector, SelectorSuelto } from "@/componentes/ui/Campo";
import { Dialogo, PieDeDialogo } from "@/componentes/ui/Dialogo";
import {
  Alerta,
  EstadoVacio,
  Insignia,
} from "@/componentes/ui/Superficie";
import { Celda, Fila, Paginacion, Tabla } from "@/componentes/ui/Tabla";
import { useTextos } from "@/i18n/proveedor";
import { consulta, mensajeDe, pedir, type Pagina } from "@/lib/api";
import { useConsulta } from "@/lib/ganchos";
import type { Rol } from "@/lib/rutas";

type Cuenta = {
  id: number;
  email: string;
  nombre: string;
  rol: Rol;
  activo: boolean;
  verificado: boolean;
  bloqueado: boolean;
};

const LIMITE = 25;

function useNombresDeRol() {
  const { t } = useTextos();
  return {
    propietario: t.rolPropietario,
    encargado: t.rolEncargado,
    vendedor: t.rolVendedor,
  } satisfies Record<Rol, string>;
}

function NuevoUsuario({
  alGuardar,
  alCancelar,
}: {
  alGuardar: () => void;
  alCancelar: () => void;
}) {
  const { t } = useTextos();
  const roles = useNombresDeRol();
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function guardar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const f = new FormData(evento.currentTarget);
    setGuardando(true);
    setError(null);
    try {
      await pedir("/usuarios", {
        method: "POST",
        cuerpo: {
          nombre: String(f.get("nombre")).trim(),
          email: String(f.get("email")).trim(),
          contrasena: f.get("contrasena"),
          rol: f.get("rol"),
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
        minLength={2}
        maxLength={120}
        autoFocus
      />
      <Campo
        etiqueta={t.correo}
        name="email"
        type="email"
        required
        autoComplete="off"
      />
      <Campo
        etiqueta={t.contrasena}
        name="contrasena"
        type="password"
        required
        minLength={8}
        maxLength={72}
        autoComplete="new-password"
        ayuda={t.requisitoContrasena}
      />
      <Selector etiqueta={t.rol} name="rol" defaultValue="vendedor">
        {(Object.keys(roles) as Rol[]).map((rol) => (
          <option key={rol} value={rol}>
            {roles[rol]}
          </option>
        ))}
      </Selector>
      {error && <Alerta>{error}</Alerta>}
      <PieDeDialogo>
        <Boton onClick={alCancelar}>{t.cancelar}</Boton>
        <Boton type="submit" variante="primario" cargando={guardando}>
          {t.nuevoUsuario}
        </Boton>
      </PieDeDialogo>
    </form>
  );
}

export default function Usuarios() {
  const { t } = useTextos();
  const yo = useUsuario();
  const roles = useNombresDeRol();
  const { avisar, confirmar } = useAvisos();
  const [pagina, setPagina] = useState(1);
  const [nuevo, setNuevo] = useState(false);

  const { datos, error, cargando, recargar } = useConsulta<Pagina<Cuenta>>(
    `/usuarios${consulta({ pagina, limite: LIMITE })}`,
  );

  async function accion(promesa: Promise<unknown>, aviso: string) {
    try {
      await promesa;
      avisar(aviso);
    } catch (falla) {
      avisar(mensajeDe(falla, t.errorGenerico), "alerta");
    } finally {
      recargar();
    }
  }

  async function deshabilitar(cuenta: Cuenta) {
    const ok = await confirmar({
      titulo: t.deshabilitarUsuario,
      texto: `${cuenta.nombre}. ${t.deshabilitarUsuarioTexto}`,
      accion: t.deshabilitar,
      peligro: true,
    });
    if (ok === null) return;
    accion(
      pedir(`/usuarios/${cuenta.id}`, { method: "DELETE" }),
      t.cambiosGuardados,
    );
  }

  const items = datos?.items ?? [];

  return (
    <div className="rounded-xl border border-borde bg-superficie shadow-xs">
      <div className="flex items-center justify-between gap-3 border-b border-borde p-3 pl-5">
        <h2 className="text-sm font-semibold">{t.usuarios}</h2>
        <Boton variante="primario" icono={Plus} onClick={() => setNuevo(true)}>
          {t.nuevoUsuario}
        </Boton>
      </div>

      {error ? (
        <div className="p-4">
          <Alerta>{error.estado === 403 ? t.sinPermiso : error.message}</Alerta>
        </div>
      ) : (
        <Tabla
          columnas={[
            { texto: t.nombre },
            { texto: t.rol },
            { texto: t.estado, oculta: "sm" },
            { texto: t.acciones, alinear: "derecha", sr: true },
          ]}
          cargando={cargando}
          vacia={items.length === 0}
          estadoVacio={<EstadoVacio icono={UsersRound} titulo={t.sinDatos} />}
        >
          {items.map((cuenta) => {
            const soyYo = cuenta.id === yo.id;
            return (
              <Fila key={cuenta.id} apagada={!cuenta.activo}>
                <Celda>
                  <p className="font-medium">
                    {cuenta.nombre}
                    {soyYo && (
                      <span className="ml-1.5 text-xs font-normal text-suave">
                        ({t.vos})
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-suave">{cuenta.email}</p>
                </Celda>
                <Celda>
                  {/* Nadie se cambia el rol a si mismo: evita quedarse
                      sin propietario por un clic. */}
                  <SelectorSuelto
                    aria-label={`${t.rol}: ${cuenta.nombre}`}
                    value={cuenta.rol}
                    disabled={soyYo || !cuenta.activo}
                    onChange={(e) =>
                      accion(
                        pedir(`/usuarios/${cuenta.id}/rol`, {
                          method: "PUT",
                          cuerpo: { rol: e.target.value },
                        }),
                        t.rolCambiado,
                      )
                    }
                    className="w-40"
                  >
                    {(Object.keys(roles) as Rol[]).map((rol) => (
                      <option key={rol} value={rol}>
                        {roles[rol]}
                      </option>
                    ))}
                  </SelectorSuelto>
                </Celda>
                <Celda oculta="sm">
                  <div className="flex flex-wrap gap-1">
                    <Insignia tono={cuenta.activo ? "ok" : "neutro"}>
                      {cuenta.activo ? t.activo : t.inactivo}
                    </Insignia>
                    {!cuenta.verificado && (
                      <Insignia tono="aviso">{t.sinVerificar}</Insignia>
                    )}
                    {cuenta.bloqueado && (
                      <Insignia tono="alerta">{t.bloqueado}</Insignia>
                    )}
                  </div>
                </Celda>
                <Celda alinear="derecha">
                  {!soyYo &&
                    (cuenta.activo ? (
                      <BotonIcono
                        etiqueta={`${t.deshabilitar}: ${cuenta.nombre}`}
                        icono={PowerOff}
                        onClick={() => deshabilitar(cuenta)}
                      />
                    ) : (
                      <BotonIcono
                        etiqueta={`${t.habilitar}: ${cuenta.nombre}`}
                        icono={Power}
                        onClick={() =>
                          accion(
                            pedir(`/usuarios/${cuenta.id}/habilitar`, {
                              method: "POST",
                            }),
                            t.cambiosGuardados,
                          )
                        }
                      />
                    ))}
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

      <Dialogo
        abierto={nuevo}
        alCerrar={() => setNuevo(false)}
        titulo={t.nuevoUsuario}
      >
        {nuevo && (
          <NuevoUsuario
            alCancelar={() => setNuevo(false)}
            alGuardar={() => {
              setNuevo(false);
              avisar(t.usuarioCreado);
              recargar();
            }}
          />
        )}
      </Dialogo>
    </div>
  );
}
