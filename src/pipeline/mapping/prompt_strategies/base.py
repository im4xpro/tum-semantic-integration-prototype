from abc import ABC, abstractmethod
from ...connectors.models import ExtractedSchema
from ...ontology.models import FormattedOntology

class BasePromptStrategy(ABC):
    
    @abstractmethod
    def build_prompt(
        self,
        schema: ExtractedSchema,
        ontology: FormattedOntology,
    ) -> tuple[str, str]:
        # returns (system_prompt, user_prompt)
        pass