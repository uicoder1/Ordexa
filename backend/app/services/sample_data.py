import os
from sqlalchemy.orm import Session
from app.models.models import Product, OrderItemLedger, CashBackLedger, UploadedFile, SKUMetric
from app.services.flipkart_parser import flipkart_parser, clean_sku
from app.services.calculation_engine import calculation_engine

SAMPLE_WORKBOOK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "tests", "fixtures", "sample_flipkart.xlsx"
)

class SampleDataGenerator:

    @staticmethod
    def seed_sample_data(db: Session, organization_id: str):
        """
        Seeds sanitized Flipkart demo dataset (2,373 rows) into OrderItemLedger & CashBackLedger for tenant.
        """
        # Clear existing tenant ledger rows & metrics
        db.query(SKUMetric).filter(SKUMetric.organization_id == organization_id).delete()
        db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == organization_id).delete()
        db.query(CashBackLedger).filter(CashBackLedger.organization_id == organization_id).delete()
        db.query(Product).filter(Product.organization_id == organization_id).delete()
        db.commit()

        if not os.path.exists(SAMPLE_WORKBOOK_PATH):
            return

        upload = UploadedFile(
            organization_id=organization_id,
            filename="Sample_Flipkart_Report.xlsx",
            marketplace="Flipkart",
            storage_path=SAMPLE_WORKBOOK_PATH,
            file_type="xlsx",
            file_size=os.path.getsize(SAMPLE_WORKBOOK_PATH),
            upload_status="completed",
            rows_processed=2373
        )
        db.add(upload)
        db.commit()

        sales_records, cashback_records = flipkart_parser.parse_flipkart_workbook(SAMPLE_WORKBOOK_PATH, "xlsx")

        existing_products = {}
        for r in sales_records:
            sku_c = r['sku']
            if not sku_c:
                continue

            if sku_c not in existing_products:
                p = Product(
                    organization_id=organization_id,
                    sku=sku_c,
                    product_name=r.get('product_name') or f"SKU {sku_c}",
                    purchase_cost=0.0,
                    selling_price=r.get('invoice_amount', 0.0),
                    marketplace="Flipkart"
                )
                db.add(p)
                existing_products[sku_c] = p

            item = OrderItemLedger(
                organization_id=organization_id,
                upload_id=upload.id,
                seller_gstin=r.get('seller_gstin'),
                order_id=r['order_id'],
                order_item_id=r['order_item_id'],
                product_name=r.get('product_name'),
                fsn=r.get('fsn'),
                sku=sku_c,
                hsn_code=r.get('hsn_code'),
                event_type=r.get('event_type'),
                event_subtype=r.get('event_subtype', 'SALE'),
                order_type=r.get('order_type'),
                fulfilment_type=r.get('fulfilment_type'),
                order_date=r.get('order_date'),
                quantity=r.get('quantity', 1),
                shipping_charge=r.get('shipping_charge', 0.0),
                invoice_amount=r.get('invoice_amount', 0.0),
                taxable_value=r.get('taxable_value', 0.0),
                tcs=r.get('tcs', 0.0),
                tds=r.get('tds', 0.0),
                customer_delivery_state=r.get('customer_delivery_state'),
                marketplace='Flipkart'
            )
            db.add(item)

        for cb in cashback_records:
            cb_item = CashBackLedger(
                organization_id=organization_id,
                upload_id=upload.id,
                seller_gstin=cb.get('seller_gstin'),
                order_id=cb['order_id'],
                order_item_id=cb['order_item_id'],
                document_type=cb.get('document_type'),
                document_subtype=cb.get('document_subtype'),
                credit_debit_note_id=cb.get('credit_debit_note_id'),
                invoice_amount=cb.get('invoice_amount', 0.0),
                invoice_date=cb.get('invoice_date'),
                taxable_value=cb.get('taxable_value', 0.0),
                tcs=cb.get('tcs', 0.0),
                tds=cb.get('tds', 0.0),
                customer_delivery_state=cb.get('customer_delivery_state')
            )
            db.add(cb_item)

        db.commit()

        # Compute metrics
        calculation_engine.calculate_sku_metrics(db, organization_id)

sample_data_generator = SampleDataGenerator()
