import { defineCloudflareConfig } from "@opennextjs/cloudflare";

// Sin cache incremental: todas las paginas son dinamicas (dependen de
// la cookie de idioma y de la sesion), asi que no hay nada que guardar
// entre pedidos y no hace falta un bucket de R2.
export default defineCloudflareConfig({});
