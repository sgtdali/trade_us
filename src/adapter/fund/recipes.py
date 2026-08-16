"""Running a recipe.

A recipe is a fixed sequence of skills, not a plan the system composes. Two
steps, in one order, decided in advance: read the filing, then update the
tracker. A router that chose its own steps would be a system whose behaviour
could not be predicted from its code.

The skill executor is injected. The real one shells out to codex; the tests
pass a stub. That seam is not for testing convenience -- it is where the
contract check lives, and the contract check is what stands between a
malformed model output and the owner's judgement.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from . import schemas
from .errors import FundError

#: Which skills a recipe runs, in order. Closed and fixed.
RECIPE_STEPS: dict[str, tuple[str, ...]] = {
    "deep_dive_then_tracker": ("earnings-deep-dive", "thesis-tracker"),
    "tracker": ("thesis-tracker",),
    "blind_review": ("earnings-deep-dive", "thesis-tracker"),
    "onboarding_underwrite": ("long-short-pitch",),
    "idea_generation": ("idea-generation",),
}

CODEX_TIMEOUT_SECONDS = 1800

PIN_RELATIVE_PATH = "config/fund/plugin-pin.json"


class RecipeError(FundError):
    """A recipe could not be run."""


class ContractFailure(RecipeError):
    """A skill produced something that does not satisfy its output contract."""


def load_pin(root: Path | None = None) -> str | None:
    """The plugin version this system was calibrated against, if one is pinned.

    A skill upgrade changes what the analysis says without changing a line of
    this repository. Pinning does not prevent that -- it makes it a decision
    rather than a surprise.
    """
    path = (root or schemas.repo_root()) / PIN_RELATIVE_PATH
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("plugin_version")


def check_pin(plugin_root: Path, root: Path | None = None) -> None:
    pinned = load_pin(root)
    if pinned is None:
        return
    installed = plugin_root.name
    if installed != pinned:
        raise RecipeError(
            f"the public-equity-investing plugin is {installed}, but this system is "
            f"pinned to {pinned}. A skill upgrade changes what the analysis says.\n"
            f"  Run the contract fixtures against {installed} first, then update "
            f"{PIN_RELATIVE_PATH}."
        )


class Executor(Protocol):
    """Runs one skill against one pack and returns its sidecar."""

    def __call__(self, skill: str, pack: Mapping[str, Any], workdir: Path) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class StepResult:
    skill: str
    sidecar: dict[str, Any]
    artifact_path: Path


@dataclass(frozen=True)
class RecipeResult:
    steps: tuple[StepResult, ...]

    @property
    def final(self) -> StepResult:
        return self.steps[-1]

    @property
    def proposed_assessment(self) -> dict[str, Any] | None:
        for step in reversed(self.steps):
            proposal = step.sidecar.get("proposed_assessment")
            if proposal:
                return dict(proposal)
        return None


def run(
    *,
    recipe: str,
    pack: Mapping[str, Any],
    executor: Executor,
    workdir: Path,
    root: Path | None = None,
) -> RecipeResult:
    steps = RECIPE_STEPS.get(recipe)
    if steps is None:
        raise RecipeError(f"unknown recipe: {recipe!r}")

    workdir.mkdir(parents=True, exist_ok=True)
    results: list[StepResult] = []
    running_pack = dict(pack)

    for index, skill in enumerate(steps, start=1):
        step_dir = workdir / f"{index:02d}-{skill}"
        step_dir.mkdir(parents=True, exist_ok=True)
        (step_dir / "pack.json").write_text(
            json.dumps(running_pack, indent=2, ensure_ascii=False), encoding="utf-8")

        sidecar = dict(executor(skill, running_pack, step_dir))
        errors = schemas.schema_errors(sidecar, schemas.SKILL_OUTPUT, root)
        if errors:
            raise ContractFailure(
                f"{skill} output does not satisfy its contract: " + "; ".join(errors[:4])
            )

        artifact = step_dir / "sidecar.json"
        artifact.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(StepResult(skill=skill, sidecar=sidecar, artifact_path=artifact))

        # Each step sees what the one before it established -- and nothing more.
        # The tracker gets the deep dive's findings, not a second copy of the
        # pack with extra context quietly attached.
        running_pack = dict(running_pack)
        running_pack["upstream"] = {
            "skill": skill,
            "findings": sidecar["findings"],
            "open_questions": sidecar.get("open_questions", []),
        }

    return RecipeResult(steps=tuple(results))


# --------------------------------------------------------------------------
# The real executor
# --------------------------------------------------------------------------

SKILL_MODEL: dict[str, tuple[str, str]] = {
    "earnings-deep-dive": ("gpt-5.6-sol", "high"),
    "thesis-tracker": ("gpt-5.6-sol", "high"),
    "long-short-pitch": ("gpt-5.6-sol", "high"),
    "idea-generation": ("gpt-5.6-sol", "medium"),
}
DEFAULT_MODEL = ("gpt-5.6-sol", "medium")


def _instructions(skill: str, pack: Mapping[str, Any]) -> str:
    return "\n".join([
        f"# {skill}",
        "",
        "Read `pack.json` in this directory. It is the complete input; nothing about",
        "position size, cash, P&L or capital at risk is in it, and none of those are",
        "inputs to the judgement you are making. Do not speculate about them.",
        "",
        "Follow the instructions inside the pack, then write two files here:",
        "",
        "- `result.md` -- your analysis, in prose, in whatever structure suits it.",
        "- `sidecar.json` -- the machine-readable summary, matching the schema at",
        "  `schemas/fund/skill-output.schema.json`.",
        "",
        "Every finding in the sidecar needs a source. A finding with no source is an",
        "opinion, and opinions do not update a thesis. If the pack lists questions",
        "under `questions_you_must_answer`, answer each one by `check_id` -- and if you",
        "could not answer one, say so rather than omitting it.",
        "",
        "If the downside cannot be stated, say so and why. An unstated downside is not",
        "a smaller one.",
    ])


def codex_executor(
    *,
    plugin_root: Path,
    repo_root: Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    timeout: int = CODEX_TIMEOUT_SECONDS,
) -> Executor:
    """The production executor: shells out to codex with the PEI plugin loaded."""

    check_pin(plugin_root)

    def execute(skill: str, pack: Mapping[str, Any], workdir: Path) -> Mapping[str, Any]:
        skill_path = plugin_root / "skills" / skill / "SKILL.md"
        if not skill_path.is_file():
            raise RecipeError(f"SKILL.md not found: {skill_path}")

        (workdir / "instructions.md").write_text(_instructions(skill, pack), encoding="utf-8")
        model, effort = SKILL_MODEL.get(skill, DEFAULT_MODEL)
        prompt = (
            f"Your PEI plugin skill files live at {plugin_root}. Load and follow "
            f"{skill_path} (and the shared contracts it references) for analytical "
            "method. Then read instructions.md and pack.json in your working "
            "directory and produce exactly the two files instructions.md asks for."
        )

        # shell=True is required on Windows: codex is installed as an npm .cmd
        # wrapper and CreateProcess will not resolve it through PATHEXT.
        command = [
            "codex", "--search", "-m", model, "-c", f"model_reasoning_effort={effort}",
            "exec", "-C", str(workdir), "--add-dir", str(plugin_root),
            "-o", str(workdir / "codex-log.md"), "-",
        ]
        try:
            completed = runner(command, cwd=repo_root, input=prompt, text=True,
                               capture_output=True, encoding="utf-8", timeout=timeout,
                               shell=True)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RecipeError(f"codex could not be run: {exc}") from exc
        if completed.returncode != 0:
            raise RecipeError(
                f"codex failed (exit {completed.returncode}): "
                f"{(completed.stderr or completed.stdout or '').strip()[:800]}"
            )

        sidecar_path = workdir / "sidecar.json"
        if not sidecar_path.is_file():
            raise ContractFailure(f"{skill} produced no sidecar.json")
        try:
            return json.loads(sidecar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ContractFailure(f"{skill} sidecar.json is not valid JSON: {exc}") from exc

    return execute


def stub_executor(sidecars: Mapping[str, Mapping[str, Any]]) -> Executor:
    """An executor that returns prepared sidecars. For tests and dry runs."""

    def execute(skill: str, pack: Mapping[str, Any], workdir: Path) -> Mapping[str, Any]:
        if skill not in sidecars:
            raise RecipeError(f"no prepared sidecar for {skill!r}")
        sidecar = dict(sidecars[skill])
        sidecar.setdefault("produced_at",
                           datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        sidecar.setdefault("security_id", pack["security_id"])
        sidecar.setdefault("job_id", pack["job_id"])
        (workdir / "result.md").write_text(f"# {skill}\n\nstub run\n", encoding="utf-8")
        return sidecar

    return execute
