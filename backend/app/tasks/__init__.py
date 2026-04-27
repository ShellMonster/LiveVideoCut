# Stage modules (stages/*.py) import from app.tasks.pipeline inside function bodies
# to avoid circular imports: pipeline imports stages, stages import pipeline utilities.
# Do NOT move these imports to module level.
