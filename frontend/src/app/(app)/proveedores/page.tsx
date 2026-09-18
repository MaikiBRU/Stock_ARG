"use client";

import { Truck } from "lucide-react";

import { Directorio } from "@/componentes/Directorio";
import { useTextos } from "@/i18n/proveedor";

export default function Proveedores() {
  const { t } = useTextos();

  return (
    <Directorio
      config={{
        titulo: t.proveedores,
        descripcion: t.proveedoresTexto,
        icono: Truck,
        base: "/proveedores",
        nombreDe: (p) => String(p.razon_social),
        secundarioDe: (p) =>
          [p.cuit, p.contacto].filter(Boolean).join(" · ") || null,
        campos: [
          {
            clave: "razon_social",
            etiqueta: t.razonSocial,
            max: 160,
            requerido: true,
            largo: true,
          },
          { clave: "cuit", etiqueta: t.cuit, max: 15 },
          { clave: "contacto", etiqueta: t.contacto, max: 120 },
          { clave: "telefono", etiqueta: t.telefono, max: 40, tipo: "tel" },
          { clave: "email", etiqueta: t.correo, max: 254, tipo: "email" },
          { clave: "direccion", etiqueta: t.direccion, max: 180 },
          { clave: "localidad", etiqueta: t.localidad, max: 90 },
          { clave: "notas", etiqueta: t.notas, max: 500, area: true },
        ],
        textos: {
          nuevo: t.nuevoProveedor,
          editar: t.editarProveedor,
          guardado: t.proveedorGuardado,
          eliminar: t.eliminarProveedor,
          eliminarTexto: t.eliminarProveedorTexto,
          buscar: t.buscarProveedor,
        },
        puedeEditar: true,
        conProductos: true,
      }}
    />
  );
}
