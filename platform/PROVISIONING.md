# APOTHEON ONE Framework Provisioning

> **Unified. Elevated.**  
> Development & Security Platform by Digital Paragon

APOTHEON ONE project initialization creates a usable framework project, adds the project manifest, and registers the result in persistent platform state.

## Next.js

The `nextjs` profile provisions with the official `create-next-app` CLI using explicit noninteractive options for TypeScript, ESLint, Tailwind CSS, App Router, `src/`, Turbopack, npm, and disabled nested Git initialization. Node.js 20.9 or newer is required.

Verification runs the profile's bounded `lint` and `build` jobs. Development and production server commands are intentionally long-running and are not eligible for synchronous MCP job execution.

## FastAPI

The `fastapi` profile creates an isolated `.venv`, installs project-local dependencies, writes a `/health` endpoint and pytest health check, and registers bounded `lint` and `test` jobs. Its development server is intentionally long-running and is not eligible for synchronous MCP job execution.

## Full-stack web

The `fullstack-web` profile composes the same Next.js and FastAPI provisioners under `apps/web` and `apps/api`. It also creates:

- a PostgreSQL service and persistent volume in `compose.yaml`;
- Dockerfiles for the web and API applications;
- a generated local database password stored only in the project's ignored `.env`;
- an `.env.example` without credentials;
- a Next.js `/api/backend-health` route that reaches the FastAPI health endpoint through `API_INTERNAL_URL`;
- a shared-package area and infrastructure directory; and
- bounded project-level `lint`, `test`, and `build` jobs.

The ordinary `build` job validates the Next.js production build and Compose configuration without building container images. `container-build` is available as a separate bounded job. `dev` remains long-running and is not eligible for synchronous MCP execution.

## Failure behavior

New projects created under the managed project root are removed when provisioning fails, allowing a clean retry. Custom external paths are never recursively deleted by the provisioner.

## Project removal

The compatibility CLI's project-remove operation removes only a registry entry and leaves files untouched.

Recursive project deletion removes the project directory only after resolving and proving that the registered project is a child of the managed project root. Registered projects outside that root cannot be deleted through this operation.
