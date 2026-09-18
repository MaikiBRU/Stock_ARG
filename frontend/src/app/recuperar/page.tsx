"use client";

import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { MarcoDeAcceso } from "@/componentes/Acceso";
import { Boton } from "@/componentes/ui/Boton";
import { Campo } from "@/componentes/ui/Campo";
import { Alerta } from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { mensajeDe, pedir } from "@/lib/api";

type Mensaje = { mensaje: string };

export default function Recuperar() {
  const { t } = useTextos();
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hecho, setHecho] = useState<string | null>(null);

  async function enviar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const email = new FormData(evento.currentTarget).get("email");
    setEnviando(true);
    setError(null);
    try {
      // La respuesta es la misma exista o no la cuenta: asi no sirve
      // para averiguar que correos estan registrados.
      const respuesta = await pedir<Mensaje>("/auth/recuperar", {
        method: "POST",
        cuerpo: { email },
      });
      setHecho(respuesta.mensaje);
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <MarcoDeAcceso
      titulo={t.recuperarTitulo}
      texto={t.recuperarTexto}
      pie={
        <Link href="/ingresar" className="hover:text-texto">
          {t.yaTengoCuenta}
        </Link>
      }
    >
      {hecho ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-xl border border-borde bg-superficie p-4 text-sm"
        >
          <MailCheck size={18} className="mt-0.5 shrink-0 text-ok" aria-hidden />
          <p>{hecho}</p>
        </div>
      ) : (
        <form onSubmit={enviar} className="flex flex-col gap-4">
          <Campo
            etiqueta={t.correo}
            name="email"
            type="email"
            required
            autoComplete="email"
            autoFocus
          />
          {error && <Alerta>{error}</Alerta>}
          <Boton
            type="submit"
            variante="primario"
            tamano="lg"
            cargando={enviando}
          >
            {enviando ? t.enviando : t.enviarEnlace}
          </Boton>
        </form>
      )}
    </MarcoDeAcceso>
  );
}
