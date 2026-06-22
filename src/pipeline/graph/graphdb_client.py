import requests
from pydantic_settings import BaseSettings
from rdflib import Graph


class GraphDBConfig(BaseSettings):
    url: str
    repository: str
    username: str | None = None
    password: str | None = None

    model_config = {"env_file": ".env", "env_prefix": "GRAPHDB_", "extra": "ignore"}


class GraphDBError(Exception):
    pass


class GraphDBClient:

    def __init__(self, config: GraphDBConfig):
        self.config = config
        # requests.auth expects a (user, password) tuple of strings or None.
        # Ensure we never pass a None password in the tuple to satisfy type checkers.
        self._auth = (config.username, config.password or "") if config.username else None

    # ── Connection ────────────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """Verify the repository exists and is writable. Returns repo info."""
        try:
            resp = self._get("/rest/repositories")
            repos = resp.json()
            info = next((r for r in repos if r["id"] == self.config.repository), None)
            if info is None:
                raise GraphDBError(
                    f"Repository '{self.config.repository}' not found. "
                    f"Available: {[r['id'] for r in repos]}"
                )
            if not info.get("writable"):
                raise GraphDBError(f"Repository '{self.config.repository}' is read-only")
            return info
        except requests.RequestException as e:
            raise GraphDBError(f"Cannot reach GraphDB at {self.config.url}: {e}")

    # ── Write ─────────────────────────────────────────────────────────────────

    def upload_graph(self, graph: Graph, named_graph_uri: str) -> int:
        """
        Serialize graph to Turtle and POST it into the given named graph.
        Returns the number of triples in the uploaded graph.
        """
        turtle = graph.serialize(format="turtle")
        params = {"context": f"<{named_graph_uri}>"}
        self._post_statements(turtle.encode(), "text/turtle", params)
        return len(graph)

    def clear_named_graph(self, named_graph_uri: str) -> None:
        """Delete all triples in a named graph (safe to call on an empty graph)."""
        params = {"context": f"<{named_graph_uri}>"}
        url = f"{self.config.url}/repositories/{self.config.repository}/statements"
        resp = requests.delete(url, params=params, auth=self._auth)
        if not resp.ok:
            raise GraphDBError(f"Clear failed [{resp.status_code}]: {resp.text[:200]}")

    def replace_named_graph(self, graph: Graph, named_graph_uri: str) -> int:
        """
        Atomically replace a named graph: clear first, then upload.
        Safe to call repeatedly — re-running the pipeline won't accumulate duplicates.
        """
        self.clear_named_graph(named_graph_uri)
        return self.upload_graph(graph, named_graph_uri)

    # ── Query ─────────────────────────────────────────────────────────────────

    def count_triples(self, named_graph_uri: str | None = None) -> int:
        """Return the triple count in a named graph (or the whole repo if None)."""
        if named_graph_uri:
            q = f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{named_graph_uri}> {{ ?s ?p ?o }} }}"
        else:
            q = "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"
        rows = self._sparql_select(q)
        return int(rows[0]["n"]["value"]) if rows else 0

    def list_named_graphs(self) -> list[str]:
        """Return all named graph URIs in the repository."""
        url = f"{self.config.url}/repositories/{self.config.repository}/contexts"
        resp = requests.get(url, headers={"Accept": "application/sparql-results+json"}, auth=self._auth)
        if not resp.ok:
            raise GraphDBError(f"Contexts query failed [{resp.status_code}]: {resp.text[:200]}")
        bindings = resp.json()["results"]["bindings"]
        return sorted(b["contextID"]["value"] for b in bindings)

    def construct_named_graph(self, named_graph_uri: str) -> Graph:
        """Fetch a named graph back out of the repository as an rdflib Graph."""
        query = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{named_graph_uri}> {{ ?s ?p ?o }} }}"
        url = f"{self.config.url}/repositories/{self.config.repository}"
        resp = requests.post(
            url,
            data=query.encode(),
            headers={"Content-Type": "application/sparql-query", "Accept": "text/turtle"},
            auth=self._auth,
        )
        if not resp.ok:
            raise GraphDBError(f"CONSTRUCT failed [{resp.status_code}]: {resp.text[:200]}")
        g = Graph()
        g.parse(data=resp.text, format="turtle")
        return g

    def sparql_select(self, query: str) -> list[dict]:
        """Run an arbitrary SPARQL SELECT, returning raw SPARQL-JSON bindings."""
        return self._sparql_select(query)

    def sparql_ask(self, query: str) -> bool:
        """Run a SPARQL ASK query (the query must scope its own GRAPH clause)."""
        url = f"{self.config.url}/repositories/{self.config.repository}"
        resp = requests.post(
            url,
            data=query.encode(),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            auth=self._auth,
        )
        if not resp.ok:
            raise GraphDBError(f"SPARQL ASK failed [{resp.status_code}]: {resp.text[:200]}")
        return resp.json()["boolean"]

    # ── Internals ─────────────────────────────────────────────────────────────

    def _get(self, path: str) -> requests.Response:
        resp = requests.get(f"{self.config.url}{path}", auth=self._auth)
        if not resp.ok:
            raise GraphDBError(f"GET {path} failed [{resp.status_code}]: {resp.text[:200]}")
        return resp

    def _post_statements(self, data: bytes, content_type: str, params: dict) -> None:
        url = f"{self.config.url}/repositories/{self.config.repository}/statements"
        resp = requests.post(
            url,
            params=params,
            data=data,
            headers={"Content-Type": content_type},
            auth=self._auth,
        )
        if not resp.ok:
            raise GraphDBError(f"Upload failed [{resp.status_code}]: {resp.text[:200]}")

    def _sparql_select(self, query: str) -> list[dict]:
        url = f"{self.config.url}/repositories/{self.config.repository}"
        resp = requests.post(
            url,
            data=query.encode(),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            auth=self._auth,
        )
        if not resp.ok:
            raise GraphDBError(f"SPARQL query failed [{resp.status_code}]: {resp.text[:200]}")
        return resp.json()["results"]["bindings"]
