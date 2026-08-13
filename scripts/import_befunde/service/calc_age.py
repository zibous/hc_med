from datetime import datetime, date

class PatientAgeCalculator:
    """Kapselt das Geburtsdatum eines Patienten für wiederholte Altersberechnungen."""
    
    def __init__(self, birth_date: date):
        if not isinstance(birth_date, date):
            raise TypeError("birth_date muss ein datetime.date-Objekt sein.")
        self.birth_date = birth_date

    def age_at(self, measurement_date: str) -> int | None:
        """Berechnet das Alter des Patienten an einem spezifischen Messdatum."""
        try:
            meas_date = datetime.strptime(measurement_date, "%Y-%m-%d").date()
            age = meas_date.year - self.birth_date.year
            
            if (meas_date.month, meas_date.day) < (self.birth_date.month, self.birth_date.day):
                age -= 1
            return age
        except (ValueError, TypeError):
            return None
