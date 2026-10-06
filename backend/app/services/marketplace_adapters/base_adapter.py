from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple

class BaseMarketplaceAdapter(ABC):

    @abstractmethod
    def detect_report(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """
        Detects report structure, sheet names, raw rows, and detected headers.
        """
        pass

    @abstractmethod
    def parse_workbook(self, file_path: str, file_type: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Parses raw spreadsheet into normalized sales/return records and cashback/settlement records.
        """
        pass
