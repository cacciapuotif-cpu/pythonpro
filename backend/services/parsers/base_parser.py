from abc import ABC, abstractmethod


class BaseDocumentParser(ABC):
    @abstractmethod
    def parse(self, filepath: str) -> dict:
        """
        Ritorna un dizionario normalizzato con dati piano, aziende,
        azioni formative, piano finanziario e warnings.
        """
        pass

