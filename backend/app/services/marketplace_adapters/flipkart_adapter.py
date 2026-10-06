from typing import List, Dict, Any, Tuple
from app.services.marketplace_adapters.base_adapter import BaseMarketplaceAdapter
from app.services.flipkart_parser import flipkart_parser

class FlipkartAdapter(BaseMarketplaceAdapter):

    def detect_report(self, file_path: str, file_type: str) -> Dict[str, Any]:
        return flipkart_parser.detect_sheets_and_report_types(file_path, file_type)

    def parse_workbook(self, file_path: str, file_type: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return flipkart_parser.parse_flipkart_workbook(file_path, file_type)
