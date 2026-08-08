from datetime import datetime
from extract_labvalues import PATIENT_GEBURTSDATUM


def calculate_age_at_date(measurement_date: str) -> int | None:
    """Berechnet das Alter zum Messzeitpunkt."""
    try:
        d = datetime.strptime(measurement_date, "%Y-%m-%d").date()
        age = d.year - PATIENT_GEBURTSDATUM.year
        if (d.month, d.day) < (PATIENT_GEBURTSDATUM.month, PATIENT_GEBURTSDATUM.day):
            age -= 1
        return age
    except (ValueError, TypeError):
        return None
