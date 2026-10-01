# Slicing Pie · horas de GitHub

CLI de Python que lee las issues de un **GitHub Project**, toma los tickets **Done** con asignado y estimado, y muestra en terminal el **Slicing Pie** de las horas de trabajo.

Por ahora solo cuenta horas. El modelo (Mike Moyer) para tiempo no pagado es:

```text
rebanadas = horas × tarifa de mercado × 2
% pie     = rebanadas de la persona / rebanadas totales
```

Las horas salen del campo de estimado del Project. Si un ticket tiene varios asignados, las horas se parten a partes iguales.

## Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recomendado) o pip

## Arranque rápido (demo, sin GitHub)

```bash
uv sync
uv run slicingpie
```

Eso usa `slicingpie.toml` en modo `demo` y pinta un pie de ejemplo. También vale:

```bash
uv run slicingpie --verbose
uv run slicingpie --json
```

## Datos reales de un GitHub Project

1. Copia `slicingpie.toml.example` a `slicingpie.local.toml` (este archivo no se versiona).
2. Pon `mode = "github"`, el dueño del Project y su número.
3. Crea un token:
   - Clásico: scopes `repo` y `project` (o `read:project`).
   - Fine-grained: **Issues: Read** y **Projects: Read**.
4. Exporta el token (mejor que dejarlo en el archivo):

```bash
export GITHUB_TOKEN=ghp_...
uv run slicingpie -c slicingpie.local.toml --verbose
```

El número del Project está en la URL:

```text
https://github.com/orgs/MI-ORG/projects/12     → owner = MI-ORG, project_number = 12
https://github.com/users/MI-USER/projects/3    → owner_type = user, project_number = 3
```

Los nombres de campo (`Status`, `Estimate`, valores Done) tienen que coincidir con los del Project. No distinguen mayúsculas.

## Archivo de configuración

Toda la config vive en un TOML local. El CLI busca, en este orden:

1. `--config ruta`
2. `slicingpie.local.toml` en el directorio actual
3. `slicingpie.toml`

| Sección | Qué controla |
| --- | --- |
| `mode` | `demo` o `github` |
| `[github]` | token, owner, tipo de dueño, número de Project |
| `[fields]` | nombre del campo de estado, valores Done, campo de estimado |
| `[slicing_pie]` | multiplicador (2), tarifa por defecto, horas por unidad de estimado |
| `[rates]` | tarifa horaria de mercado por login de GitHub |
| `[display]` | símbolo de moneda |

Si el estimado está en story points, pon `hours_per_estimate_unit` (por ejemplo `4`). Un valor tipo `8h` se trata siempre como horas.

Tickets Done **sin estimado**, **sin asignado** o con **0 horas** no entran al pie; el informe los lista como omitidos.

## Desarrollo

```bash
uv sync
uv run pytest
uv run slicingpie --verbose
```
