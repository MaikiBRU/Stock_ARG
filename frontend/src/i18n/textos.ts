/**
 * Textos en espanol e ingles (RNF-14).
 *
 * Un diccionario plano, sin libreria: son pocas pantallas y asi el
 * idioma se resuelve en el servidor, sin parpadeo al cargar.
 */

export type Idioma = "es" | "en";

export const IDIOMAS: Idioma[] = ["es", "en"];

export const textos = {
  es: {
    marca: "StockARG",
    lema: "Stock, ventas y clientes de un comercio, en un solo lugar.",
    entrar: "Ingresar",
    probarDemo: "Probar la demo",
    abriendoDemo: "Preparando el comercio de prueba...",
    correo: "Correo",
    contrasena: "Contrasena",
    ingresando: "Ingresando...",
    olvide: "Olvide mi contrasena",
    crearCuenta: "Crear una cuenta",
    volverAlInicio: "Volver al inicio",
    panel: "Panel",
    productos: "Productos",
    ventas: "Ventas",
    stock: "Stock",
    clientes: "Clientes",
    proveedores: "Proveedores",
    reportes: "Reportes",
    administracion: "Administracion",
    salir: "Salir",
    ventasDelDia: "Ventas de hoy",
    tickets: "Tickets",
    ticketPromedio: "Ticket promedio",
    bajoMinimo: "Bajo minimo",
    porVencer: "Por vencer",
    vencidos: "Vencidos",
    sinDatos: "Todavia no hay datos para mostrar.",
    cargando: "Cargando...",
    modoDemo: "Estas en la demo",
    terminaEn: "Termina en",
    reiniciarDemo: "Reiniciar",
    salirDemo: "Terminar",
    errorGenerico: "Algo salio mal. Intentalo de nuevo.",
  },
  en: {
    marca: "StockARG",
    lema: "Stock, sales and customers for a small shop, in one place.",
    entrar: "Sign in",
    probarDemo: "Try the demo",
    abriendoDemo: "Setting up the sample shop...",
    correo: "Email",
    contrasena: "Password",
    ingresando: "Signing in...",
    olvide: "I forgot my password",
    crearCuenta: "Create an account",
    volverAlInicio: "Back to home",
    panel: "Dashboard",
    productos: "Products",
    ventas: "Sales",
    stock: "Stock",
    clientes: "Customers",
    proveedores: "Suppliers",
    reportes: "Reports",
    administracion: "Administration",
    salir: "Sign out",
    ventasDelDia: "Today's sales",
    tickets: "Tickets",
    ticketPromedio: "Average ticket",
    bajoMinimo: "Below minimum",
    porVencer: "Expiring soon",
    vencidos: "Expired",
    sinDatos: "Nothing to show yet.",
    cargando: "Loading...",
    modoDemo: "You are in the demo",
    terminaEn: "Ends in",
    reiniciarDemo: "Reset",
    salirDemo: "End",
    errorGenerico: "Something went wrong. Please try again.",
  },
} as const;

// Las claves las fija el espanol; los valores son texto comun, no la
// frase exacta de cada idioma.
export type Textos = Record<keyof (typeof textos)["es"], string>;

/** Diccionario del idioma pedido, con espanol como respaldo. */
export function textosDe(idioma: string | undefined): Textos {
  return idioma === "en" ? textos.en : textos.es;
}
