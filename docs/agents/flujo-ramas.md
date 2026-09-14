# Flujo de ramas

Cuatro capas, de arriba hacia abajo. Cada commit entra por la capa mas baja y sube por merge.

| Rama | Rol | Quien escribe |
|---|---|---|
| `main` | Produccion (Render + Vercel). **No se toca.** | Solo merge desde `dev`, decidido por el equipo. |
| `dev` | Integracion del equipo. | Solo via PR desde una rama personal. |
| `<usuario>` (`rarechimera87`, `andres_nino`, ...) | Rama personal: lo que cada uno tiene listo para compartir. | Solo merge desde `feature/*` propias, con `--no-ff`. |
| `feature/<nombre>` | Un cambio acotado. Nace de la personal y muere en la personal. | Commits directos. |

## Reglas

- Nunca commitear directo en `main`, `dev` ni en la rama personal.
- Todo cambio empieza con `git checkout <usuario> && git checkout -b feature/<nombre>`.
- Al terminar: `git checkout <usuario> && git merge --no-ff feature/<nombre> && git push && git branch -d feature/<nombre>`.
- Antes de abrir el PR `<usuario> -> dev`, traer lo de los demas con `git merge dev` en la personal.
- Trabajo viejo que no sigue se archiva con un tag `archivo/<nombre>` y se borra la rama; no se dejan ramas muertas.
