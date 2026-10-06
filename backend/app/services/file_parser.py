import pandas as pd
import io
from typing import List, Dict, Tuple, Any

# Standard target fields expected by ProfitPilot backend
STANDARD_FIELDS = {
    "sku": "SKU / Item Code",
    "order_id": "Order ID",
    "transaction_id": "Transaction ID",
    "product_name": "Product Name",
    "quantity": "Quantity",
    "selling_price": "Selling Price / Order Value",
    "settlement_amount": "Net Settlement Amount",
    "marketplace_fee": "Marketplace / Referral Fee",
    "commission": "Commission Fee",
    "shipping_charge": "Forward Shipping Charge",
    "return_charge": "Return / Reverse Logistics Fee",
    "order_status": "Order Status (Delivered, Returned, RTO)",
    "return_reason": "Return Reason",
    "order_date": "Order / Transaction Date"
}

# Heuristic patterns for Amazon, Flipkart, Meesho, Shopify, Custom reports
HEADER_ALIASES = {
    "sku": ["sku", "seller sku", "product sku", "sku code", "item sku", "variant sku", "merchant sku", "msku"],
    "order_id": ["order id", "amazon order id", "sub order id", "order no", "order_number", "order number"],
    "transaction_id": ["transaction id", "settlement id", "payout id", "payment id", "reference id", "txn id"],
    "product_name": ["product name", "item description", "title", "product title", "item name", "description"],
    "quantity": ["quantity", "qty", "units", "items count", "item quantity", "number of items"],
    "selling_price": ["selling price", "item price", "item subtotal", "order amount", "principal", "price", "sale price"],
    "settlement_amount": ["settlement amount", "net amount", "payout amount", "bank transfer amount", "total net amount", "net payout"],
    "marketplace_fee": ["marketplace fee", "referral fee", "closing fee", "platform fee", "fixed fee", "technology fee"],
    "commission": ["commission", "commission fee", "category fee", "marketplace commission"],
    "shipping_charge": ["shipping fee", "forward shipping", "shipping charge", "delivery charge", "weight handling fee"],
    "return_charge": ["return shipping fee", "reverse logistics charge", "rto fee", "return shipping", "reverse shipping"],
    "order_status": ["order status", "status", "item status", "shipment status", "delivery status"],
    "return_reason": ["return reason", "customer return reason", "cancellation reason", "reason"],
    "order_date": ["order date", "date", "transaction date", "posted date", "purchase date", "created at"]
}

class FileParserService:

    @staticmethod
    def read_file_preview(file_path: str, file_type: str) -> Tuple[List[str], List[Dict[str, Any]], int]:
        """
        Reads first 10 rows preview and returns (detected_headers, sample_rows, total_row_count)
        """
        try:
            if file_type.lower() in ["xlsx", "xls"]:
                with open(file_path, "rb") as f:
                    df = pd.read_excel(f, nrows=100)
            else:
                # Try UTF-8, then latin1 encoding
                try:
                    df = pd.read_csv(file_path, nrows=100)
                except Exception:
                    df = pd.read_csv(file_path, nrows=100, encoding="latin1")

            headers = [str(c).strip() for c in df.columns]
            # Replace NaNs with empty string
            preview_rows = df.head(5).fillna("").to_dict(orient="records")
            total_rows = len(df)
            return headers, preview_rows, total_rows
        except Exception as e:
            raise ValueError(f"Failed to parse file: {str(e)}")

    @staticmethod
    def auto_detect_mapping(headers: List[str]) -> Dict[str, str]:
        """
        Matches raw file headers to standard internal field keys.
        """
        mapping = {}
        headers_lower = {h.lower().strip(): h for h in headers}

        for target_field, aliases in HEADER_ALIASES.items():
            matched_header = ""
            for alias in aliases:
                if alias in headers_lower:
                    matched_header = headers_lower[alias]
                    break
                # Partial match
                for raw_header, orig in headers_lower.items():
                    if alias in raw_header:
                        matched_header = orig
                        break
                if matched_header:
                    break
            
            if matched_header:
                mapping[target_field] = matched_header

        return mapping

    @staticmethod
    def load_normalized_rows(file_path: str, file_type: str, mapping: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Loads the entire spreadsheet and maps columns into normalized internal dictionaries.
        """
        if file_type.lower() in ["xlsx", "xls"]:
            with open(file_path, "rb") as f:
                df = pd.read_excel(f)
        else:
            try:
                df = pd.read_csv(file_path)
            except Exception:
                df = pd.read_csv(file_path, encoding="latin1")

        df = df.fillna("")
        normalized_records = []

        # Invert mapping: standard_field -> raw_column_name
        for idx, row in df.iterrows():
            record = {}
            for field, raw_col in mapping.items():
                if raw_col and raw_col in row:
                    val = row[raw_col]
                    record[field] = val
                else:
                    record[field] = None

            # Skip rows without SKU or Order ID
            if not record.get("sku"):
                continue

            normalized_records.append(record)

        return normalized_records

file_parser = FileParserService()
