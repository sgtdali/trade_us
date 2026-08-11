class PipelineError(Exception):
    """Base domain error for the fundamental pipeline."""


class ConfigError(PipelineError):
    """Company, routing, or registry configuration is missing or invalid."""


class UnimplementedModuleError(PipelineError):
    """A registered but not-yet-implemented company-type or sector module was invoked."""


class UnsafePathError(PipelineError):
    """A path or ticker failed the repository-containment or naming safety check."""


class PeriodError(PipelineError):
    """A period label, comparison, discrete-derivation, or TTM assembly is invalid."""


class FormulaError(PipelineError):
    """A formula could not be resolved or evaluated against its declared inputs."""


class DriftDetected(PipelineError):
    """Generated output differs from committed production output under --check."""


class TransactionalWriteError(PipelineError):
    """A multi-file bundle write failed during the replacement phase and was
    rolled back to its pre-call state."""


class RollbackError(TransactionalWriteError):
    """A multi-file bundle write failed during the replacement phase AND the
    rollback itself could not fully restore one or more targets. The
    exception message names every path that could not be restored and, for
    previously-existing targets, the backup path its original bytes are
    still recoverable from -- nothing is silently lost."""
