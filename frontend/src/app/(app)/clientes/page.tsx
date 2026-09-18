"use client";

import { Users } from "lucide-react";

import { Directorio } from "@/componentes/Directorio";
import { useUsuario } from "@/componentes/Sesion";
import { useTextos } from "@/i18n/proveedor";
import { gestiona } from "@/lib/rutas";

export default function Clientes() {
  const { t } = useTextos();
  const usuario = useUsuario();

  return (
    <Directorio
      config={{
        titulo: t.clientes,
        descripcion: t.clientesTexto,
        icono: Users,
        base: "/clientes",
        nombreDe: (c) => String(c.nombre_completo ?? c.nombre),
        secundarioDe: (c) =>
          c.documento ? String(c.documento) : c.cuit ? String(c.cuit) : null,
        campos: [
          { clave: "nombre", etiqueta: t.nombre, max: 80, requerido: true },
          { clave: "apellido", etiqueta: t.apellido, max: 80 },
          { clave: "documento", etiqueta: t.documento, max: 20 },
          { clave: "cuit", etiqueta: t.cuit, max: 15 },
          { clave: "telefono", etiqueta: t.telefono, max: 40, tipo: "tel" },
          { clave: "email", etiqueta: t.correo, max: 254, tipo: "email" },
          { clave: "direccion", etiqueta: t.direccion, max: 180 },
          { clave: "localidad", etiqueta: t.localidad, max: 90 },
          { clave: "notas", etiqueta: t.notas, max: 500, area: true },
        ],
        textos: {
          nuevo: t.nuevoCliente,
          editar: t.editarCliente,
          guardado: t.clienteGuardado,
          eliminar: t.eliminarCliente,
          eliminarTexto: t.eliminarClienteTexto,
          buscar: t.buscarClienteLista,
        },
        puedeEditar: gestiona(usuario.rol),
      }}
    />
  );
}
