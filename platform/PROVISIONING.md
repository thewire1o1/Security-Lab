# DPSR framework provisioning

DPSR project initialization is responsible for creating a usable framework project, adding `dpsr.toml`, and registering the project in persistent platform state.

## Next.js

The `nextjs` profile provisions with the official `create-next-app` CLI using explicit noninteractive options for TypeScript, ESLint, Tailwind CSS, App Router, `src/`, Turbopack, npm, and disabled nested Git initialization. Node.js 20.9 or newer is required.

Verification runs the profile's bounded `lint` and `build` jobs. Development and production server commands are intentionally long-running and are not eligible for synchronous MCP job execution.

## FastAPI

The `fastapi` profile creates an isolated `.venv`, installs project-local dependencies, writes a health endpoint and a pytest health check, and registers bounded `lint` and `test` jobs. Its development server is intentionally long-running and is not eligible for synchronous MCP job execution.

## Failure behavior

New projects created under the managed DPSR project root are removed when provisioning fails, allowing a clean retry. Custom external paths are never recursively deleted by the provisioner.
