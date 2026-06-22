from abc import ABC, abstractmethod

from ..models import FormattedOntology, OntologyModel


class BaseFormatter(ABC):

    @abstractmethod
    def format(self, ontology: OntologyModel) -> FormattedOntology:
        pass