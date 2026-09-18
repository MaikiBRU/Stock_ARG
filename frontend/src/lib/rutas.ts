/** Pantalla de entrada segun el rol: el vendedor no ve el panel. */

export type Rol = "propietario" | "encargado" | "vendedor";

export function inicioPara(rol: Rol) {
  return rol === "vendedor" ? "/vender" : "/panel";
}

/** True si el rol gestiona el comercio (propietario o encargado). */
export function gestiona(rol: Rol) {
  return rol === "propietario" || rol === "encargado";
}
