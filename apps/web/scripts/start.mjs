import { cpSync } from "node:fs"
import { resolve } from "node:path"
import { pathToFileURL } from "node:url"
import { parseArgs } from "node:util"

const { values } = parseArgs({
  options: { hostname: { type: "string" }, port: { type: "string" } },
})
const root = resolve(import.meta.dirname, "..")
const standalone = resolve(root, ".next/standalone/apps/web")
cpSync(resolve(root, ".next/static"), resolve(standalone, ".next/static"), { recursive: true })
cpSync(resolve(root, "public"), resolve(standalone, "public"), { recursive: true })
process.env.HOSTNAME = values.hostname ?? "127.0.0.1"
process.env.PORT = values.port ?? process.env.PORT ?? "3000"
await import(pathToFileURL(resolve(standalone, "server.js")).href)
