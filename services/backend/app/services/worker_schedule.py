from app.schemas.schedule import ScheduleSnapshot

# Replaced atomically by the single worker; never persisted or refreshed by a timer.
snapshot: ScheduleSnapshot | None = None
