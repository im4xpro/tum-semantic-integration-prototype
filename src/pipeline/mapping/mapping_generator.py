import datetime
import json
import re

from ..connectors.models import ExtractedSchema
from ..ontology.manager import OntologyManager
from .llm_clients.factory import LLMClientFactory
from .models import MappingConfig, MappingDocument, SubjectMapping
from .prompt_strategies.chain_of_thought import ChainOfThoughtPromptStrategy
from .prompt_strategies.few_shot import FewShotPromptStrategy
from .prompt_strategies.zero_shot import ZeroShotPromptStrategy


class MappingGeneratorError(Exception):
    pass


class MappingGenerator:
    def __init__(self, config: MappingConfig):
        self.config = config
        self._client = LLMClientFactory.create(config.provider, config.llm_model)
        self._strategy = self._build_strategy()

    def _build_strategy(self):
        strategies = {
            "zero_shot": ZeroShotPromptStrategy,
            "few_shot": FewShotPromptStrategy,
            "chain_of_thought": ChainOfThoughtPromptStrategy,
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
        column_descriptions: dict[str, str] | None = None,
    ) -> MappingDocument:
        ontology = ontology_manager.get_formatted_ontology(self.config.ontology_format)

        descriptions = column_descriptions if self.config.include_descriptions else None
        system_prompt, user_prompt = self._strategy.build_prompt(
            schema, ontology, descriptions, ontology_manager
        )

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
            include_descriptions=self.config.include_descriptions,
            subject_mappings=subject_mappings,
            unmapped_fields=raw.get("unmapped_fields", []),
            generation_timestamp=datetime.datetime.now(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _parse_json(self, response_text: str) -> dict:
        text = response_text.strip()

        # Reasoning strategies (e.g. chain_of_thought) emit prose before a fenced
        # ```json block; plain strategies emit pure JSON, optionally fenced.
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        elif not text.startswith("{"):
            text = self._extract_first_json_object(text)

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise MappingGeneratorError(
                f"Failed to parse LLM response as JSON: {e}\nResponse: {text[:500]}"
            )

    @staticmethod
    def _extract_first_json_object(text: str) -> str:
        start = text.find("{")
        if start == -1:
            return text

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            char = text[i]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        return text[start:]
