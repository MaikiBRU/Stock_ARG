"use client";

import { Pestanas } from "@/componentes/ui/Controles";
import { EncabezadoDePagina } from "@/componentes/ui/Superficie";
import { useTextos } from "@/i18n/proveedor";

/** Administracion: una ruta por pestana, asi cada una tiene su enlace. */
export default function LayoutDeAdministracion({
  children,
}: {
  children: React.ReactNode;
}) {
  const { t } = useTextos();
  return (
    <div className="flex flex-col gap-6">
      <EncabezadoDePagina
        titulo={t.administracion}
        descripcion={t.administracionTexto}
      />
      <Pestanas
        pestanas={[
          { href: "/administracion", texto: t.usuarios },
          { href: "/administracion/medios", texto: t.mediosDePago },
          { href: "/administracion/configuracion", texto: t.configuracion },
          { href: "/administracion/auditoria", texto: t.auditoria },
        ]}
      />
      {children}
    </div>
  );
}
