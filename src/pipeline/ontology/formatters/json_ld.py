from pathlib import Path

from rdflib import Graph

from ..models import FormattedOntology, OntologyModel
from .base import BaseFormatter


class JsonLdFormatter(BaseFormatter):
    """The ontology file converted to JSON-LD, with no bespoke shaping.

    Like the turtle formatter this renders the source file rather than the parsed
    OntologyModel, so it carries every axiom the file does. That makes turtle and
    json_ld a controlled pair — same content, same order, different syntax — which
    is what isolates the effect of serialisation from the effect of verbosity that
    the compact/class_list formats vary.
    """

    def __init__(self, ontology_path: Path):
        self.ontology_path = ontology_path

    def format(self, ontology: OntologyModel) -> FormattedOntology:
        graph = Graph()
        graph.parse(self.ontology_path, format="turtle")
        # auto_compact builds @context from the graph's own prefix bindings, so terms
        # stay as bsm:/owl:/rdfs: names. Without it rdflib emits expanded JSON-LD,
        # which repeats every full URI and roughly triples the prompt.
        content = graph.serialize(format="json-ld", auto_compact=True, indent=2)
        return FormattedOntology(
            format="json_ld",
            content=content,
            token_count=len(content) // 4,
        )
