/** Pantalla de entrada y permisos segun el rol. */

export type Rol = "propietario" | "encargado" | "vendedor";

export function inicioPara(rol: Rol) {
  return rol === "vendedor" ? "/vender" : "/panel";
}

/** True si el rol gestiona el comercio (propietario o encargado). */
export function gestiona(rol: Rol) {
  return rol === "propietario" || rol === "encargado";
}

/** True si el rol administra usuarios, cobros y ajustes. */
export function administra(rol: Rol) {
  return rol === "propietario";
}
