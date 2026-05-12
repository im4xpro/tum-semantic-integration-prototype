from abc import ABC, abstractmethod
from .model import ExtractedSchema

class ConnectorError(Exception):
    pass

class BaseConnector(ABC):
    
    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass
    
    @abstractmethod
    def extract_schema(self) -> ExtractedSchema:
        pass
    
    @abstractmethod
    def fetch_records(self, limit: int) -> list[dict]:
        pass
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc, tb):
        self.disconnect()
        return False