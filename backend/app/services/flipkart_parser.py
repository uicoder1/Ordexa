import pandas as pd
import math
from typing import List, Dict, Any, Tuple
from datetime import datetime

def safe_float(val, default=0.0) -> float:
    if val is None or pd.isna(val) or val == "":
        return default
    if isinstance(val, (int, float)):
        return default if math.isnan(val) or math.isinf(val) else float(val)
    s = str(val).replace('₹', '').replace(',', '').strip()
    try:
        f = float(s)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default

def safe_int(val, default=1) -> int:
    if val is None or pd.isna(val) or val == "":
        return default
    try:
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else int(f)
    except (ValueError, TypeError):
        return default

def safe_str(val, default="") -> str:
    if val is None or pd.isna(val):
        return default
    s = str(val).strip()
    return default if s.lower() == "nan" else s

def normalize_sku(raw_sku: Any) -> str:
    if raw_sku is None or pd.isna(raw_sku):
        return ""
    s = str(raw_sku).strip()
    if not s or s.lower() == "nan":
        return ""

    while True:
        s_prev = s
        s = s.strip('"\': \t\r\n')
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1]
        if s.lower().startswith("sku:"):
            s = s[4:]
        if s == s_prev:
            break

    return s.strip('"\': \t\r\n')

def clean_sku(raw_sku: Any) -> str:
    return normalize_sku(raw_sku)

def normalize_product_name(raw_name: Any) -> str:
    if raw_name is None or pd.isna(raw_name):
        return ""
    s = str(raw_name).strip()
    if not s or s.lower() == "nan":
        return ""

    while True:
        s_prev = s
        s = s.strip('"\': \t\r\n')
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1]
        if s == s_prev:
            break

    s = s.replace('""', '"').replace("''", "'")

    words = s.split()
    if not words:
        return ""

    if len(words) > 1 and words[0].lower() == words[1].lower():
        words.pop(0)

    return " ".join(words)



def parse_date(date_val: Any) -> Any:
    if not date_val or pd.isna(date_val):
        return None
    if isinstance(date_val, (datetime, pd.Timestamp)):
        return date_val.to_pydatetime() if hasattr(date_val, 'to_pydatetime') else date_val
    s = str(date_val).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return pd.to_datetime(s).to_pydatetime()
    except Exception:
        return None

class FlipkartParserService:

    @staticmethod
    def detect_sheets_and_report_types(file_path: str, file_type: str) -> Dict[str, Any]:
        """
        Inspects file sheets and columns to detect available Flipkart reports.
        """
        info = {
            "sheets": [],
            "has_sales_report": False,
            "has_cashback_report": False,
            "has_settlement_report": False,
            "detected_reports": [],
            "total_rows": 0,
            "orders_count": 0,
            "skus_count": 0,
            "sales_count": 0,
            "returns_count": 0,
            "cancellations_count": 0,
            "return_cancellations_count": 0,
            "customer_states_detected": False,
        }

        if file_type.lower() in ["xlsx", "xls"]:
            excel_file = pd.ExcelFile(file_path)
            info["sheets"] = excel_file.sheet_names

            # Ignore instructions or help sheets
            valid_sheets = [s for s in excel_file.sheet_names if s.lower() not in ["help", "instructions", "readme"]]

            for sname in valid_sheets:
                df = pd.read_excel(excel_file, sheet_name=sname)
                cols_lower = [str(c).lower().strip() for c in df.columns]

                if "document type" in cols_lower or "credit note id" in cols_lower or "credit note id/ debit note id" in cols_lower or "cash back" in sname.lower() or "cashback" in sname.lower():
                    info["has_cashback_report"] = True
                    if "Cash Back Report" not in info["detected_reports"]:
                        info["detected_reports"].append("Cash Back Report")
                    info["total_rows"] += len(df)

                elif "event sub type" in cols_lower or "event type" in cols_lower or "sales" in sname.lower() or "order item id" in cols_lower:
                    info["has_sales_report"] = True
                    if "Sales Report" not in info["detected_reports"]:
                        info["detected_reports"].append("Sales Report")
                    
                    # Quick stats
                    if "order item id" in cols_lower:
                        idx_col = [c for c in df.columns if str(c).lower().strip() == "order item id"][0]
                        info["orders_count"] = df[idx_col].nunique()
                    
                    if "sku" in cols_lower:
                        sku_col = [c for c in df.columns if str(c).lower().strip() == "sku"][0]
                        clean_skus = df[sku_col].dropna().astype(str).apply(clean_sku)
                        info["skus_count"] = clean_skus[clean_skus != ""].nunique()

                    if "event sub type" in cols_lower:
                        evt_col = [c for c in df.columns if str(c).lower().strip() == "event sub type"][0]
                        subtypes = df[evt_col].astype(str).str.lower()
                        info["sales_count"] = int((subtypes == "sale").sum())
                        info["returns_count"] = int((subtypes == "return").sum())
                        info["cancellations_count"] = int((subtypes == "cancellation").sum())
                        info["return_cancellations_count"] = int((subtypes == "return cancellation").sum())

                    if any("delivery state" in c for c in cols_lower):
                        info["customer_states_detected"] = True

                    info["total_rows"] += len(df)

                elif "settlement" in cols_lower or "payout" in cols_lower or "bank transfer" in cols_lower:
                    info["has_settlement_report"] = True
                    if "Settlement Report" not in info["detected_reports"]:
                        info["detected_reports"].append("Settlement Report")
                    info["total_rows"] += len(df)

        else:
            # Single CSV file
            try:
                df = pd.read_csv(file_path)
            except Exception:
                df = pd.read_csv(file_path, encoding="latin1")

            cols_lower = [str(c).lower().strip() for c in df.columns]

            if "event sub type" in cols_lower or "order item id" in cols_lower:
                info["has_sales_report"] = True
                info["detected_reports"].append("Sales Report")
                info["total_rows"] = len(df)
                if "order item id" in cols_lower:
                    idx_col = [c for c in df.columns if str(c).lower().strip() == "order item id"][0]
                    info["orders_count"] = df[idx_col].nunique()
                if "sku" in cols_lower:
                    sku_col = [c for c in df.columns if str(c).lower().strip() == "sku"][0]
                    clean_skus = df[sku_col].dropna().astype(str).apply(clean_sku)
                    info["skus_count"] = clean_skus[clean_skus != ""].nunique()

                if "event sub type" in cols_lower:
                    evt_col = [c for c in df.columns if str(c).lower().strip() == "event sub type"][0]
                    subtypes = df[evt_col].astype(str).str.lower()
                    info["sales_count"] = int((subtypes == "sale").sum())
                    info["returns_count"] = int((subtypes == "return").sum())
                    info["cancellations_count"] = int((subtypes == "cancellation").sum())
                    info["return_cancellations_count"] = int((subtypes == "return cancellation").sum())

                if any("delivery state" in c for c in cols_lower):
                    info["customer_states_detected"] = True

        return info

    @staticmethod
    def parse_flipkart_workbook(file_path: str, file_type: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Parses Flipkart workbook (or CSV) into normalized Sales records and Cashback records.
        """
        sales_records = []
        cashback_records = []

        if file_type.lower() in ["xlsx", "xls"]:
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names

            # Process Sales Report sheet
            sales_sheets = [s for s in sheet_names if "sales" in s.lower()]
            if sales_sheets:
                df_sales = pd.read_excel(excel_file, sheet_name=sales_sheets[0])
                sales_records = FlipkartParserService._process_sales_dataframe(df_sales)
            else:
                # Try first valid non-help sheet
                non_help = [s for s in sheet_names if s.lower() not in ["help", "instructions", "readme"]]
                if non_help:
                    df_sales = pd.read_excel(excel_file, sheet_name=non_help[0])
                    sales_records = FlipkartParserService._process_sales_dataframe(df_sales)

            # Process Cash Back Report sheet
            cb_sheets = [s for s in sheet_names if "cash back" in s.lower() or "cashback" in s.lower()]
            if cb_sheets:
                df_cb = pd.read_excel(excel_file, sheet_name=cb_sheets[0])
                cashback_records = FlipkartParserService._process_cashback_dataframe(df_cb)

        else:
            try:
                df = pd.read_csv(file_path)
            except Exception:
                df = pd.read_csv(file_path, encoding="latin1")

            sales_records = FlipkartParserService._process_sales_dataframe(df)

        return sales_records, cashback_records

    @staticmethod
    def _process_sales_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
        records = []
        if df.empty:
            return records

        # Standardize column lookup dictionary
        col_map = {str(c).strip(): c for c in df.columns}

        def get_val(row, col_name, default=""):
            # Check exact match or partial match
            if col_name in col_map:
                return row[col_map[col_name]]

            c_low = col_name.lower().strip()
            aliases = [c_low]

            if c_low in ["order id", "order_id"]:
                aliases.extend(["order id", "order_id", "order no", "order number", "order_number", "sub order id", "sub_order_id", "order #"])
            elif c_low in ["order item id", "order_item_id"]:
                aliases.extend(["order item id", "order_item_id", "item id", "item_id", "order item no", "sub order item id"])
            elif c_low in ["sku"]:
                aliases.extend(["sku", "seller sku", "product sku", "sku code", "item sku", "variant sku", "merchant sku", "msku", "fsn"])
            elif c_low in ["product title/description", "product title", "product description"]:
                aliases.extend(["product title/description", "product title", "product description", "product name", "item description", "title", "description", "item name"])
            elif c_low in ["event sub type", "event_subtype"]:
                aliases.extend(["event sub type", "event_subtype", "event subtype", "order status", "status", "event type"])

            for alias in aliases:
                for k, orig in col_map.items():
                    if alias in k.lower().strip():
                        return row[orig]
            return default

        for idx, row in df.iterrows():
            raw_sku = get_val(row, "SKU")
            sku = clean_sku(raw_sku)

            if not sku:
                continue

            order_id = safe_str(get_val(row, "Order ID")) or f"ORD-{idx+1}"
            order_item_id = safe_str(get_val(row, "Order Item ID")) or order_id

            raw_subtype = safe_str(get_val(row, "Event Sub Type"))
            subtype_upper = raw_subtype.upper().replace(" ", "_")
            if "RETURN_CANCELLATION" in subtype_upper or "RETURNCANCELLATION" in subtype_upper:
                event_subtype = "RETURN_CANCELLATION"
            elif "CANCELLATION" in subtype_upper or "CANCEL" in subtype_upper:
                event_subtype = "CANCELLATION"
            elif "RETURN" in subtype_upper:
                event_subtype = "RETURN"
            else:
                event_subtype = "SALE"

            price_before_discount = safe_float(get_val(row, "Price before discount"))
            discount = safe_float(get_val(row, "Total Discount"))
            price_after_discount = safe_float(get_val(row, "Price after discount"))
            if price_after_discount == 0.0 and price_before_discount > 0:
                price_after_discount = price_before_discount - discount

            shipping_charge = safe_float(get_val(row, "Shipping Charges"))
            invoice_amount = safe_float(get_val(row, "Final Invoice Amount"))
            if invoice_amount == 0.0 and price_after_discount > 0:
                invoice_amount = price_after_discount + shipping_charge

            taxable_value = safe_float(get_val(row, "Taxable Value"))
            seller_share = safe_float(get_val(row, "Seller Share"))
            bank_offer_share = safe_float(get_val(row, "Bank Offer Share"))

            # TCS fields
            tcs_total = safe_float(get_val(row, "Total TCS Deducted"))
            if tcs_total == 0.0:
                tcs_total = (safe_float(get_val(row, "TCS IGST Amount")) +
                             safe_float(get_val(row, "TCS CGST Amount")) +
                             safe_float(get_val(row, "TCS SGST Amount")))

            tds = safe_float(get_val(row, "TDS Amount"))

            rec = {
                "seller_gstin": safe_str(get_val(row, "Seller GSTIN")),
                "order_id": order_id,
                "order_item_id": order_item_id,
                "product_name": normalize_product_name(get_val(row, "Product Title/Description")) or f"SKU {sku}",
                "fsn": safe_str(get_val(row, "FSN")),
                "sku": sku,
                "hsn_code": safe_str(get_val(row, "HSN Code")),
                "event_type": safe_str(get_val(row, "Event Type")) or "Order",
                "event_subtype": event_subtype,
                "order_type": safe_str(get_val(row, "Order Type")) or "Prepaid",
                "fulfilment_type": safe_str(get_val(row, "Fulfilment Type")),
                "order_date": parse_date(get_val(row, "Order Date")),
                "order_approval_date": parse_date(get_val(row, "Order Approval Date")),
                "quantity": max(1, safe_int(get_val(row, "Item Quantity"), 1)),
                "shipped_from_state": safe_str(get_val(row, "Order Shipped From (State)")),
                "warehouse_id": safe_str(get_val(row, "Warehouse ID")),
                "price_before_discount": price_before_discount,
                "discount": discount,
                "seller_share": seller_share,
                "bank_offer_share": bank_offer_share,
                "price_after_discount": price_after_discount,
                "shipping_charge": shipping_charge,
                "invoice_amount": invoice_amount,
                "taxable_value": taxable_value,
                "igst_rate": safe_float(get_val(row, "IGST Rate")),
                "igst_amount": safe_float(get_val(row, "IGST Amount")),
                "cgst_rate": safe_float(get_val(row, "CGST Rate")),
                "cgst_amount": safe_float(get_val(row, "CGST Amount")),
                "sgst_rate": safe_float(get_val(row, "SGST Rate")),
                "sgst_amount": safe_float(get_val(row, "SGST Amount")),
                "tcs": tcs_total,
                "tds": tds,
                "buyer_invoice_id": safe_str(get_val(row, "Buyer Invoice ID")),
                "buyer_invoice_date": parse_date(get_val(row, "Buyer Invoice Date")),
                "buyer_invoice_amount": safe_float(get_val(row, "Buyer Invoice Amount")),
                "customer_billing_pincode": safe_str(get_val(row, "Billing Pincode")),
                "customer_billing_state": safe_str(get_val(row, "Billing State")),
                "customer_delivery_pincode": safe_str(get_val(row, "Delivery Pincode")),
                "customer_delivery_state": safe_str(get_val(row, "Delivery State")),
                "usual_price": safe_float(get_val(row, "Usual Price")),
                "is_shopsy": "yes" in safe_str(get_val(row, "Is Shopsy Order")).lower() or "true" in safe_str(get_val(row, "Is Shopsy Order")).lower(),
                "marketplace": "Flipkart"
            }
            records.append(rec)

        return records

    @staticmethod
    def _process_cashback_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
        records = []
        if df.empty:
            return records

        col_map = {str(c).strip(): c for c in df.columns}

        def get_val(row, col_name, default=""):
            if col_name in col_map:
                return row[col_map[col_name]]
            c_low = col_name.lower()
            for k, orig in col_map.items():
                if c_low in k.lower():
                    return row[orig]
            return default

        for idx, row in df.iterrows():
            order_id = safe_str(get_val(row, "Order ID"))
            order_item_id = safe_str(get_val(row, "Order Item ID"))
            if not order_id or not order_item_id:
                continue

            tcs_total = safe_float(get_val(row, "Total TCS Deducted"))
            if tcs_total == 0.0:
                tcs_total = (safe_float(get_val(row, "TCS IGST Amount")) +
                             safe_float(get_val(row, "TCS CGST Amount")) +
                             safe_float(get_val(row, "TCS SGST Amount")))

            rec = {
                "seller_gstin": safe_str(get_val(row, "Seller GSTIN")),
                "order_id": order_id,
                "order_item_id": order_item_id,
                "document_type": safe_str(get_val(row, "Document Type")),
                "document_subtype": safe_str(get_val(row, "Document Sub Type")),
                "credit_debit_note_id": safe_str(get_val(row, "Credit Note ID/ Debit Note ID")),
                "invoice_amount": safe_float(get_val(row, "Invoice Amount")),
                "invoice_date": parse_date(get_val(row, "Invoice Date")),
                "taxable_value": safe_float(get_val(row, "Taxable Value")),
                "igst_amount": safe_float(get_val(row, "IGST Amount")),
                "cgst_amount": safe_float(get_val(row, "CGST Amount")),
                "sgst_amount": safe_float(get_val(row, "SGST Amount")),
                "tcs": tcs_total,
                "tds": safe_float(get_val(row, "TDS Amount")),
                "customer_delivery_state": safe_str(get_val(row, "Delivery State")),
                "is_shopsy": "yes" in safe_str(get_val(row, "Is Shopsy Order")).lower()
            }
            records.append(rec)

        return records

flipkart_parser = FlipkartParserService()
