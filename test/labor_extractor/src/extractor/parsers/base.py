from abc import ABC, abstractmethod
from pathlib import Path

class BaseParser(ABC):
    @abstractmethod
    def parse(self, filepath: Path) -> list[dict]:
        """Liest die Datei ein und gibt standardisierte Daten zurück."""
        pass
