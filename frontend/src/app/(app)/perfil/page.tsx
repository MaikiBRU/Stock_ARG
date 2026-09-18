"use client";

import { useState } from "react";

import { useUsuario } from "@/componentes/Sesion";
import { useAvisos } from "@/componentes/ui/Avisos";
import { Boton } from "@/componentes/ui/Boton";
import { Campo } from "@/componentes/ui/Campo";
import {
  Alerta,
  EncabezadoDePagina,
  Tarjeta,
} from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { mensajeDe, pedir } from "@/lib/api";

export default function Perfil() {
  const { t } = useTextos();
  const usuario = useUsuario();
  const { avisar } = useAvisos();
  const [guardandoDatos, setGuardandoDatos] = useState(false);
  const [guardandoClave, setGuardandoClave] = useState(false);
  const [errorDatos, setErrorDatos] = useState<string | null>(null);
  const [errorClave, setErrorClave] = useState<string | null>(null);

  const roles = {
    propietario: t.rolPropietario,
    encargado: t.rolEncargado,
    vendedor: t.rolVendedor,
  };

  async function guardarDatos(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const nombre = String(new FormData(evento.currentTarget).get("nombre")).trim();
    setGuardandoDatos(true);
    setErrorDatos(null);
    try {
      await pedir("/auth/perfil", { method: "PUT", cuerpo: { nombre } });
      avisar(t.cambiosGuardados);
      // El nombre se muestra en la barra lateral: se recarga la sesion.
      window.location.reload();
    } catch (falla) {
      setErrorDatos(mensajeDe(falla, t.errorGenerico));
      setGuardandoDatos(false);
    }
  }

  async function cambiarClave(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const formulario = evento.currentTarget;
    const f = new FormData(formulario);
    if (f.get("nueva") !== f.get("repetida")) {
      setErrorClave(t.contrasenasDistintas);
      return;
    }
    setGuardandoClave(true);
    setErrorClave(null);
    try {
      await pedir("/auth/contrasena", {
        method: "PUT",
        cuerpo: {
          contrasena_actual: f.get("actual"),
          contrasena_nueva: f.get("nueva"),
        },
      });
      formulario.reset();
      avisar(t.contrasenaCambiada);
    } catch (falla) {
      setErrorClave(mensajeDe(falla, t.errorGenerico));
    } finally {
      setGuardandoClave(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <EncabezadoDePagina titulo={t.perfil} descripcion={t.perfilTexto} />
      <div className="grid max-w-4xl gap-4 lg:grid-cols-2">
        <Tarjeta titulo={t.datosPersonales}>
          <form onSubmit={guardarDatos} className="flex flex-col gap-4">
            <Campo
              etiqueta={t.nombre}
              name="nombre"
              required
              minLength={2}
              maxLength={120}
              defaultValue={usuario.nombre}
            />
            <Campo etiqueta={t.correo} value={usuario.email} disabled readOnly />
            <Campo
              etiqueta={t.rol}
              value={roles[usuario.rol]}
              disabled
              readOnly
            />
            {errorDatos && <Alerta>{errorDatos}</Alerta>}
            <Boton
              type="submit"
              variante="primario"
              cargando={guardandoDatos}
              className="self-end"
            >
              {t.guardar}
            </Boton>
          </form>
        </Tarjeta>

        <Tarjeta titulo={t.cambiarContrasena}>
          <form onSubmit={cambiarClave} className="flex flex-col gap-4">
            <Campo
              etiqueta={t.contrasenaActual}
              name="actual"
              type="password"
              required
              autoComplete="current-password"
            />
            <Campo
              etiqueta={t.nuevaContrasena}
              name="nueva"
              type="password"
              required
              minLength={8}
              maxLength={72}
              autoComplete="new-password"
              ayuda={t.requisitoContrasena}
            />
            <Campo
              etiqueta={t.repetirContrasena}
              name="repetida"
              type="password"
              required
              autoComplete="new-password"
            />
            {errorClave && <Alerta>{errorClave}</Alerta>}
            <Boton
              type="submit"
              variante="primario"
              cargando={guardandoClave}
              className="self-end"
            >
              {t.cambiarContrasena}
            </Boton>
          </form>
        </Tarjeta>
      </div>
    </div>
  );
}
