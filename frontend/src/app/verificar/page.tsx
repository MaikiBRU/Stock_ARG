"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { MarcoDeAcceso, useEntrar, type Token } from "@/componentes/Acceso";
import { Boton } from "@/componentes/ui/Boton";
import { Campo } from "@/componentes/ui/Campo";
import { Alerta } from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";
import { formatear } from "@/i18n/textos";
import { mensajeDe, pedir } from "@/lib/api";

function Formulario() {
  const { t } = useTextos();
  const entrar = useEntrar();
  const inicial = useSearchParams().get("email") ?? "";
  const [email, setEmail] = useState(inicial);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  async function verificar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const codigo = String(new FormData(evento.currentTarget).get("codigo"));
    setOcupado(true);
    setError(null);
    try {
      entrar(
        await pedir<Token>("/auth/verificar", {
          method: "POST",
          cuerpo: { email, codigo },
        }),
      );
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
      setOcupado(false);
    }
  }

  async function reenviar() {
    setError(null);
    try {
      await pedir("/auth/reenviar", { method: "POST", cuerpo: { email } });
      setAviso(t.codigoReenviado);
    } catch (falla) {
      setError(mensajeDe(falla, t.errorGenerico));
    }
  }

  return (
    <MarcoDeAcceso
      titulo={t.verificarTitulo}
      texto={inicial ? formatear(t.verificarTexto, { email: inicial }) : null}
      pie={
        <Link href="/ingresar" className="hover:text-texto">
          {t.yaTengoCuenta}
        </Link>
      }
    >
      <form onSubmit={verificar} className="flex flex-col gap-4">
        <Campo
          etiqueta={t.correo}
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        <Campo
          etiqueta={t.codigo}
          name="codigo"
          required
          inputMode="numeric"
          pattern="\d{6}"
          maxLength={6}
          autoComplete="one-time-code"
          autoFocus={Boolean(inicial)}
          className="[&_input]:text-center [&_input]:font-mono [&_input]:text-lg [&_input]:tracking-[0.4em]"
        />
        {error && <Alerta>{error}</Alerta>}
        {aviso && (
          <p role="status" className="text-sm text-ok">
            {aviso}
          </p>
        )}
        <Boton type="submit" variante="primario" tamano="lg" cargando={ocupado}>
          {ocupado ? t.verificando : t.verificar}
        </Boton>
        <Boton
          variante="fantasma"
          onClick={reenviar}
          disabled={!email || ocupado}
        >
          {t.reenviarCodigo}
        </Boton>
      </form>
    </MarcoDeAcceso>
  );
}

export default function Verificar() {
  return (
    <Suspense>
      <Formulario />
    </Suspense>
  );
}
