"""The controlled public boundary of the fundamental pipeline.

Only modules explicitly exported from here are a stable contract that
``engine.valuation`` (or any other external consumer) may
depend on. Nothing under ``engine.public`` imports
``engine.valuation`` -- the dependency direction is
valuation -> public, never the reverse.
"""
