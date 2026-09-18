"use client";

import { CircleAlert, CircleCheck, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { useTextos } from "@/i18n/proveedor";

import { Boton } from "./Boton";
import { AreaDeTexto } from "./Campo";
import { Dialogo, PieDeDialogo } from "./Dialogo";

type Aviso = { id: number; texto: string; tono: "ok" | "alerta" };

type Confirmacion = {
  titulo: string;
  texto?: string;
  accion: string;
  peligro?: boolean;
  conMotivo?: boolean;
};

type Contexto = {
  avisar: (texto: string, tono?: Aviso["tono"]) => void;
  /** Resuelve con el motivo escrito ("" si no se pidio), o null. */
  confirmar: (pedido: Confirmacion) => Promise<string | null>;
};

const Avisos = createContext<Contexto | null>(null);

/**
 * Avisos que aparecen y se van solos, y una confirmacion reutilizable
 * para las acciones que no se pueden deshacer.
 */
export function ProveedorDeAvisos({ children }: { children: ReactNode }) {
  const { t } = useTextos();
  const [avisos, setAvisos] = useState<Aviso[]>([]);
  const [pedido, setPedido] = useState<Confirmacion | null>(null);
  const [motivo, setMotivo] = useState("");
  const resolver = useRef<((valor: string | null) => void) | null>(null);
  const siguiente = useRef(0);

  const quitar = useCallback((id: number) => {
    setAvisos((actuales) => actuales.filter((a) => a.id !== id));
  }, []);

  const avisar = useCallback(
    (texto: string, tono: Aviso["tono"] = "ok") => {
      const id = ++siguiente.current;
      setAvisos((actuales) => [...actuales.slice(-2), { id, texto, tono }]);
      setTimeout(() => quitar(id), tono === "alerta" ? 7000 : 4000);
    },
    [quitar],
  );

  const confirmar = useCallback((nuevo: Confirmacion) => {
    resolver.current?.(null);
    setMotivo("");
    setPedido(nuevo);
    return new Promise<string | null>((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  function responder(valor: string | null) {
    resolver.current?.(valor);
    resolver.current = null;
    setPedido(null);
  }

  return (
    <Avisos.Provider value={{ avisar, confirmar }}>
      {children}

      <Dialogo
        abierto={pedido !== null}
        alCerrar={() => responder(null)}
        titulo={pedido?.titulo}
        descripcion={pedido?.texto}
        ancho="sm"
      >
        <form
          onSubmit={(evento) => {
            evento.preventDefault();
            responder(motivo.trim());
          }}
        >
          {pedido?.conMotivo && (
            <AreaDeTexto
              etiqueta={t.motivo}
              opcional
              maxLength={255}
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
            />
          )}
          <PieDeDialogo>
            <Boton onClick={() => responder(null)}>{t.cancelar}</Boton>
            <Boton
              type="submit"
              variante={pedido?.peligro ? "peligro" : "primario"}
              autoFocus={!pedido?.conMotivo}
            >
              {pedido?.accion}
            </Boton>
          </PieDeDialogo>
        </form>
      </Dialogo>

      <div
        aria-live="polite"
        className="pointer-events-none fixed right-4 bottom-4 left-4 z-50 flex flex-col items-center gap-2 sm:left-auto sm:items-end"
      >
        {avisos.map((aviso) => (
          <div
            key={aviso.id}
            role={aviso.tono === "alerta" ? "alert" : "status"}
            className="aparecer pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-xl border border-borde bg-superficie px-4 py-3 text-sm shadow-flotante"
          >
            {aviso.tono === "ok" ? (
              <CircleCheck
                size={17}
                className="mt-px shrink-0 text-ok"
                aria-hidden
              />
            ) : (
              <CircleAlert
                size={17}
                className="mt-px shrink-0 text-alerta"
                aria-hidden
              />
            )}
            <p className="flex-1">{aviso.texto}</p>
            <button
              type="button"
              onClick={() => quitar(aviso.id)}
              aria-label={t.cerrar}
              className="-mr-1 text-suave hover:text-texto"
            >
              <X size={15} aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </Avisos.Provider>
  );
}

export function useAvisos() {
  const contexto = useContext(Avisos);
  if (!contexto) throw new Error("useAvisos va dentro de ProveedorDeAvisos.");
  return contexto;
}
