"""The controlled public boundary of the fundamental pipeline.

Only modules explicitly exported from here are a stable contract that
``fundamental_pipeline.valuation`` (or any other external consumer) may
depend on. Nothing under ``fundamental_pipeline.public`` imports
``fundamental_pipeline.valuation`` -- the dependency direction is
valuation -> public, never the reverse.
"""
