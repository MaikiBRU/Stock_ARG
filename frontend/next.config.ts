import type { NextConfig } from "next";

// Encabezados de seguridad para todas las paginas. La politica de
// contenido completa (CSP) queda para cuando Next la soporte sin
// "unsafe-inline"; por ahora se cierra lo que no depende de eso.
const encabezados = [
  // Nadie puede meter la app en un iframe (clickjacking).
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
  // Solo HTTPS por dos anios. Sin "preload": no se inscribe el dominio.
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains",
  },
];

// Un build de produccion que apunte a la API local quedaria publicado
// sin poder hablar con nada. Pasa si un .env.local (que Next prioriza
// sobre .env.production) trae la URL de desarrollo: se corta el build.
const api = process.env.NEXT_PUBLIC_API_URL ?? "";
if (
  process.env.NODE_ENV === "production" &&
  /localhost|127\.0\.0\.1/.test(api)
) {
  throw new Error(
    `NEXT_PUBLIC_API_URL apunta a ${api} en un build de produccion. ` +
      "La configuracion local va en .env.development.local.",
  );
}

const nextConfig: NextConfig = {
  // Sin esto, el modo desarrollo escribe AGENTS.md y CLAUDE.md en cada
  // arranque; no son parte del proyecto.
  agentRules: false,
  // No anunciar con que esta hecho el sitio.
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: encabezados }];
  },
};

export default nextConfig;
