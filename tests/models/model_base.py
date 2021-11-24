from abc import ABC
from typing import Dict


class Model(ABC):
    """Abstract base class for all models. Enables easier type hinting
    in packages that interact with generated code."""

    swagger_types: Dict[str, str]
    attribute_map: Dict[str, str]
