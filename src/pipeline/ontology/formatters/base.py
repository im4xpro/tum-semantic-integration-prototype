from abc import ABC, abstractmethod
from ..models import OntologyModel, FormattedOntology

class BaseFormatter(ABC):

    @abstractmethod
    def format(self, ontology: OntologyModel) -> FormattedOntology:
        pass