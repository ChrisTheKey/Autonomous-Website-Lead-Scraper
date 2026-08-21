"""This repository's ZERO child-agent surface.

Separate from ``app/`` on purpose: ``app`` is the FastAPI product, this is the
thin, dependency-light layer HWD-ZERO invokes. Keeping them apart means ZERO can
run the agent on a laptop that has not started Postgres, Redis or Celery, and an
action that genuinely needs one of those says so instead of failing obscurely.
"""

__all__ = ["actions", "protocol"]
