from abc import ABC, abstractmethod

from ...connectors.models import ExtractedSchema
from ...ontology.manager import OntologyManager
from ...ontology.models import FormattedOntology


class BasePromptStrategy(ABC):

    @abstractmethod
    def build_prompt(
        self,
        schema: ExtractedSchema,
        ontology: FormattedOntology,
        column_descriptions: dict[str, str] | None = None,
        ontology_manager: OntologyManager | None = None,
    ) -> tuple[str, str]:
        # returns (system_prompt, user_prompt)
        pass