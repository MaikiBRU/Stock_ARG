"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  BotonGoogle,
  HAY_GOOGLE,
  MarcoDeAcceso,
  Separador,
} from "@/componentes/Acceso";
import { Boton } from "@/componentes/ui/Boton";
import { Campo } from "@/componentes/ui/Campo";
import { Alerta } from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { mensajeDe, pedir } from "@/lib/api";

export default function Registro() {
  const { t } = useTextos();
  const router = useRouter();
  const [creando, setCreando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function registrar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const formulario = new FormData(evento.currentTarget);
    const email = String(formulario.get("email"));
    setCreando(true);
    setError(null);

    try {
      await pedir("/auth/registro", {
        method: "POST",
        cuerpo: {
          nombre: formulario.get("nombre"),
          email,
          contrasena: formulario.get("contrasena"),
        },
      });
      // El correo viaja en la ruta solo para completar el campo; el
      // codigo, que es lo que vale, llega por mail.
      router.push(`/verificar?email=${encodeURIComponent(email)}`);
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
      setCreando(false);
    }
  }

  return (
    <MarcoDeAcceso
      titulo={t.registroTitulo}
      texto={t.registroTexto}
      pie={
        <Link href="/ingresar" className="hover:text-texto">
          {t.yaTengoCuenta}
        </Link>
      }
    >
      <form onSubmit={registrar} className="flex flex-col gap-4">
        <Campo
          etiqueta={t.nombre}
          name="nombre"
          required
          minLength={2}
          maxLength={120}
          autoComplete="name"
          autoFocus
        />
        <Campo
          etiqueta={t.correo}
          name="email"
          type="email"
          required
          autoComplete="email"
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
        {error && <Alerta>{error}</Alerta>}
        <Boton type="submit" variante="primario" tamano="lg" cargando={creando}>
          {creando ? t.creando : t.crearCuenta}
        </Boton>
      </form>
      {HAY_GOOGLE && (
        <>
          <Separador />
          <BotonGoogle />
        </>
      )}
    </MarcoDeAcceso>
  );
}
