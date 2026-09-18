import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Sin esto, el modo desarrollo escribe AGENTS.md y CLAUDE.md en cada
  // arranque; no son parte del proyecto.
  agentRules: false,
};

export default nextConfig;
