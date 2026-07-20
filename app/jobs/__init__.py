"""Canonical asynchronous job execution foundation for KAORI.

Keep this initializer side-effect free. Web routes, Celery tasks, analytics planners,
and provider services import individual job modules during application bootstrap.
"""
