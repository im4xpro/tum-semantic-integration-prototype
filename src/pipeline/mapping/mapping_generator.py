import json
import datetime

from .models import MappingDocument, SubjectMapping, MappingConfig
from .llm_clients.factory import LLMClientFactory

from .prompt_strategies.zero_shot import ZeroShotStrategy
from ..connectors.models import ExtractedSchema
from ..ontology.manager import OntologyManager


class MappingGeneratorError(Exception):
    pass


class MappingGenerator:

    def __init__(self, config: MappingConfig):
        self.config = config
        self._client = LLMClientFactory.create(config.provider, config.llm_model)
        self._strategy = self._build_strategy()

    def _build_strategy(self):
        strategies = {
            "zero_shot": ZeroShotStrategy,
        }
        strategy_class = strategies.get(self.config.strategy)
        if not strategy_class:
            raise NotImplementedError(
                f"Strategy '{self.config.strategy}' not implemented yet"
            )
        return strategy_class()

    def generate(
        self,
        schema: ExtractedSchema,
        ontology_manager: OntologyManager,
    ) -> MappingDocument:
        ontology = ontology_manager.get_formatted_ontology(self.config.ontology_format)

        system_prompt, user_prompt = self._strategy.build_prompt(schema, ontology)

        print(f"Prompt size: {len(system_prompt) + len(user_prompt)} chars")
        print(f"System prompt:\n{system_prompt}\n")
        print(f"User prompt:\n{user_prompt}\n")

        response_text, prompt_tokens, completion_tokens = self._client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=self.config.temperature,
        )

        raw = self._parse_json(response_text)

        subject_mappings = [
            SubjectMapping(**sm) for sm in raw.get("subject_mappings", [])
        ]

        return MappingDocument(
            source_name=schema.source_name,
            llm_model=self.config.llm_model,
            strategy=self.config.strategy,
            ontology_format=self.config.ontology_format,
            rag_enabled=self.config.rag_enabled,
            subject_mappings=subject_mappings,
            unmapped_fields=raw.get("unmapped_fields", []),
            generation_timestamp=datetime.datetime.now(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _parse_json(self, response_text: str) -> dict:
        text = response_text.strip()

        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise MappingGeneratorError(
                f"Failed to parse LLM response as JSON: {e}\n"
                f"Response: {text[:500]}"
            )