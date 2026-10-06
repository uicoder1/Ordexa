from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import OrderItemLedger, CashBackLedger, Product, SKUMetric, CalculationConfig, Order, Return, Settlement
from app.services.flipkart_parser import normalize_sku, normalize_product_name
from fastapi import HTTPException
from datetime import datetime


class CalculationEngine:

    @staticmethod
    def get_or_create_config(db: Session, organization_id: str) -> CalculationConfig:
        config = db.query(CalculationConfig).filter(CalculationConfig.organization_id == organization_id).first()
        if not config:
            config = CalculationConfig(
                organization_id=organization_id,
                settlement_is_net=True,
                deduct_marketplace_fees=False,
                include_shipping=True,
                include_return_cost=True,
                critical_risk_margin_threshold=5.0,
                warning_risk_return_rate_threshold=15.0,
                warning_risk_rto_rate_threshold=10.0
            )
            db.add(config)
            db.commit()
            db.refresh(config)
        return config

    @staticmethod
    def calculate_sku_metrics(db: Session, organization_id: str):
        """
        Calculates normalized SKU metrics strictly based on OrderItemLedger and Product cost catalog.
        Does not fake Net Settlement, Actual Profit, or RTO rates when underlying source data is missing.
        """
        config = CalculationEngine.get_or_create_config(db, organization_id)

        # 1. Fetch catalog products for tenant
        products = db.query(Product).filter(Product.organization_id == organization_id).all()
        prod_cost_map: Dict[str, Tuple[float, str, str, str]] = {}
        for p in products:
            sku_clean = normalize_sku(p.sku)
            if sku_clean:
                p_name = normalize_product_name(p.product_name) or f"SKU {sku_clean}"
                prod_cost_map[sku_clean.upper()] = (p.purchase_cost or 0.0, p_name, p.category or "General", sku_clean)

        # 2. Fetch all ledger entries for tenant
        ledger_items = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == organization_id).all()

        # Check if settlement report exists
        has_settlements = db.query(Settlement).filter(Settlement.organization_id == organization_id).count() > 0

        # Collect unique SKUs (uppercase -> canonical string)
        all_skus: Dict[str, str] = {}
        for item in ledger_items:
            if item.sku:
                norm = normalize_sku(item.sku)
                if norm:
                    all_skus[norm.upper()] = norm
        for p_sku_upper, (_, _, _, p_sku_norm) in prod_cost_map.items():
            all_skus[p_sku_upper] = p_sku_norm

        # Clear existing metrics to maintain clean state
        db.query(SKUMetric).filter(SKUMetric.organization_id == organization_id).delete()
        db.commit()

        new_metrics = []

        for sku_upper in sorted(all_skus.keys()):
            sku_canonical = all_skus[sku_upper]
            sku_items = [i for i in ledger_items if i.sku and normalize_sku(i.sku).upper() == sku_upper]

            fallback_name = sku_items[0].product_name if sku_items and sku_items[0].product_name else f"SKU {sku_canonical}"
            purchase_cost, raw_product_name, category, _ = prod_cost_map.get(
                sku_upper,
                (0.0, fallback_name, "General", sku_canonical)
            )
            product_name = normalize_product_name(raw_product_name) or f"SKU {sku_canonical}"

            # Categorize events by subtype
            sale_events = [i for i in sku_items if i.event_subtype == "SALE"]
            return_events = [i for i in sku_items if i.event_subtype == "RETURN"]
            cancellation_events = [i for i in sku_items if i.event_subtype == "CANCELLATION"]
            return_cancel_events = [i for i in sku_items if i.event_subtype == "RETURN_CANCELLATION"]

            # Units & Values based on UNIQUE Order Item ID (per requirements 4 & 5)
            sale_item_ids = set(i.order_item_id for i in sale_events)
            return_item_ids = set(i.order_item_id for i in return_events)
            cancellation_item_ids = set(i.order_item_id for i in cancellation_events)

            units_sold = len(sale_item_ids)
            returned_units = len(return_item_ids)
            cancellation_units = len(cancellation_item_ids)

            revenue = sum(i.invoice_amount or 0.0 for i in sale_events)
            return_value = sum(i.invoice_amount or 0.0 for i in return_events)
            returns_count = len(return_events)
            total_orders = len(set(i.order_id for i in sale_events)) or len(set(i.order_id for i in sku_items))

            # Sale-linked return calculation:
            sale_linked_returns_count = len(sale_item_ids.intersection(return_item_ids))

            if units_sold > 0:
                sale_linked_return_rate = round((sale_linked_returns_count / units_sold) * 100.0, 2)
            else:
                sale_linked_return_rate = 0.0

            # Overall return rate
            if units_sold > 0:
                return_rate = round(min(100.0, (returned_units / units_sold) * 100.0), 2)
            else:
                return_rate = 100.0 if returned_units > 0 else 0.0

            # COGS & Financial calculations
            cogs_available = (purchase_cost > 0.0)
            settlement_available = has_settlements
            rto_available = False # RTO not explicitly present in Flipkart Sales Report

            if cogs_available:
                total_product_cost = round(purchase_cost * units_sold, 2)
            else:
                total_product_cost = None

            # Actual Profit and Net Settlement:
            if cogs_available and settlement_available:
                # If settlement report exists, calculate actual profit
                settlement_rec = db.query(func.sum(Settlement.settlement_amount)).filter(
                    Settlement.organization_id == organization_id,
                    func.upper(Settlement.sku) == sku_upper
                ).scalar() or 0.0
                net_settlement = round(settlement_rec, 2)
                actual_profit = round(net_settlement - total_product_cost, 2)
                profit_margin = round((actual_profit / revenue * 100.0), 2) if revenue > 0 else 0.0
            else:
                net_settlement = None
                actual_profit = None
                profit_margin = None

            profit_leakage = None # Leakage calculation requires settlement source

            # Data Confidence Level
            if units_sold >= 50:
                data_confidence = "HIGH"
            elif units_sold >= 30:
                data_confidence = "GOOD"
            elif units_sold >= 10:
                data_confidence = "MODERATE"
            else:
                data_confidence = "INSUFFICIENT"

            # Health Status & Reason Determination with minimum sample size logic
            item_label = "sale item" if units_sold == 1 else "sale items"
            if units_sold < 10:
                risk_level = "INSUFFICIENT_DATA"
                recommended_action = "Insufficient Data"
                if sale_linked_returns_count > 0:
                    reason = f"{sale_linked_return_rate}% return activity, but only {units_sold} {item_label} observed."
                else:
                    reason = f"Only {units_sold} {item_label} observed."
            elif units_sold < 30:
                # 10–29 sale items: percentage displayed, status capped at WATCH
                if cogs_available and actual_profit is not None and actual_profit < 0:
                    risk_level = "LOSS_MAKING"
                    recommended_action = "Loss Making"
                    reason = f"Negative margin (₹{actual_profit}) after COGS"
                elif sale_linked_return_rate >= 15.0:
                    risk_level = "WATCH"
                    recommended_action = "Watch"
                    reason = f"{sale_linked_return_rate}% sale-linked return activity ({sale_linked_returns_count} returns)"
                else:
                    risk_level = "HEALTHY"
                    recommended_action = "Healthy"
                    reason = "Healthy performance & return activity"
            else:
                # 30+ sale items: Eligible for normal return-risk ranking
                if cogs_available and actual_profit is not None and actual_profit < 0:
                    risk_level = "LOSS_MAKING"
                    recommended_action = "Loss Making"
                    reason = f"Negative margin (₹{actual_profit}) after COGS"
                elif sale_linked_return_rate >= 25.0:
                    risk_level = "HIGH_RETURN"
                    recommended_action = "High Return"
                    reason = f"{sale_linked_return_rate}% sale-linked return activity ({sale_linked_returns_count} returns)"
                elif sale_linked_return_rate >= 15.0:
                    risk_level = "WATCH"
                    recommended_action = "Watch"
                    reason = f"{sale_linked_return_rate}% sale-linked return activity ({sale_linked_returns_count} returns)"
                else:
                    risk_level = "HEALTHY"
                    recommended_action = "Healthy"
                    reason = "Healthy performance & return activity"

            metric = SKUMetric(
                organization_id=organization_id,
                sku=sku_canonical,
                period_name="All Time",
                total_orders=total_orders,
                units_sold=units_sold,
                returned_units=returned_units,
                cancellation_units=cancellation_units,
                revenue=round(revenue, 2),
                returns_count=returns_count,
                return_rate=return_rate,
                sale_linked_return_rate=sale_linked_return_rate,
                rto_count=0,
                rto_rate=None, # Explicitly None / Data unavailable
                total_product_cost=total_product_cost,
                marketplace_fees=None, # Settlement unavailable
                shipping_cost=round(sum(i.shipping_charge or 0.0 for i in sale_events), 2),
                return_cost=0.0,
                return_value=round(return_value, 2),
                refund_amount=round(return_value, 2),
                net_settlement=net_settlement,
                actual_profit=actual_profit,
                profit_margin=profit_margin,
                profit_leakage=profit_leakage,
                cogs_available=cogs_available,
                settlement_available=settlement_available,
                rto_available=rto_available,
                data_confidence=data_confidence,
                risk_level=risk_level,
                recommended_action=recommended_action,
                reason=reason,
                calculated_at=datetime.utcnow()
            )
            new_metrics.append(metric)

        db.add_all(new_metrics)
        db.commit()

    @staticmethod
    def get_overview_summary(db: Session, organization_id: str) -> Dict[str, Any]:
        """
        Generates Overview KPIs from OrderItemLedger.
        """
        items = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == organization_id).all()
        cb_items = db.query(CashBackLedger).filter(CashBackLedger.organization_id == organization_id).all()
        products = db.query(Product).filter(Product.organization_id == organization_id).all()

        sale_events = [i for i in items if i.event_subtype == "SALE"]
        return_events = [i for i in items if i.event_subtype == "RETURN"]
        cancellation_events = [i for i in items if i.event_subtype == "CANCELLATION"]
        return_cancel_events = [i for i in items if i.event_subtype == "RETURN_CANCELLATION"]

        total_sales_value = sum(i.invoice_amount or 0.0 for i in sale_events)
        total_returned_value = sum(i.invoice_amount or 0.0 for i in return_events)
        total_units_sold = sum(i.quantity or 1 for i in sale_events)

        unique_orders = len(set(i.order_id for i in items))
        unique_order_items = len(set(i.order_item_id for i in items))
        unique_skus = len(set(i.sku for i in items if i.sku)) or len(products)

        # Date range
        dates = [i.order_date for i in items if i.order_date is not None]
        if dates:
            min_date = min(dates).strftime("%d %b %Y")
            max_date = max(dates).strftime("%d %b %Y")
            data_period = f"{min_date} to {max_date}"
        else:
            data_period = "No Date Range"

        # Sale-linked returns
        sale_order_items = set(i.order_item_id for i in sale_events)
        return_order_items = set(i.order_item_id for i in return_events)
        sale_linked_returns = len(sale_order_items.intersection(return_order_items))
        unlinked_returns = len(return_order_items - sale_order_items)
        unique_sale_order_items_count = len(sale_order_items)

        sale_linked_return_rate = round((sale_linked_returns / unique_sale_order_items_count * 100.0), 1) if unique_sale_order_items_count > 0 else 0.0

        has_cogs = any(p.purchase_cost and p.purchase_cost > 0 for p in products)
        has_settlements = db.query(Settlement).filter(Settlement.organization_id == organization_id).count() > 0

        return {
            "sales_value": round(total_sales_value, 2),
            "units_sold": total_units_sold,
            "sale_events_count": len(sale_events),
            "unique_sale_order_items_count": unique_sale_order_items_count,
            "return_events_count": len(return_events),
            "returned_order_items_count": len(return_order_items),
            "cancellation_events_count": len(cancellation_events),
            "return_cancellation_events_count": len(return_cancel_events),
            "returned_value": round(total_returned_value, 2),
            "unique_orders_count": unique_orders,
            "unique_order_items_count": unique_order_items,
            "unique_skus_count": unique_skus,
            "data_period": data_period,
            "sale_linked_returns_count": sale_linked_returns,
            "sale_linked_return_rate": sale_linked_return_rate,
            "unlinked_returns_count": unlinked_returns,
            "rto_available": False,
            "rto_message": "RTO data unavailable from this report.",
            "cogs_available": has_cogs,
            "actual_profit_message": "Actual Profit unavailable. Add product costs." if not has_cogs else None,
            "settlement_available": has_settlements,
            "settlement_message": "Settlement reconciliation unavailable. Upload marketplace settlement report." if not has_settlements else None
        }

    @staticmethod
    def get_sku_detail(db: Session, organization_id: str, sku: str) -> Dict[str, Any]:
        """
        Generates comprehensive Product Detail & Return Intelligence for a single SKU
        strictly from normalized OrderItemLedger and Product records.
        """
        sku_canonical = normalize_sku(sku)
        if not sku_canonical:
            raise HTTPException(status_code=404, detail="Product not found in the current imported dataset.")

        sku_upper = sku_canonical.upper()

        all_ledger_items = db.query(OrderItemLedger).filter(
            OrderItemLedger.organization_id == organization_id
        ).all()

        items = [i for i in all_ledger_items if i.sku and normalize_sku(i.sku).upper() == sku_upper]

        product = db.query(Product).filter(
            Product.organization_id == organization_id,
            func.upper(Product.sku) == sku_upper
        ).first()

        if not items and not product:
            raise HTTPException(status_code=404, detail="Product not found in the current imported dataset.")

        sale_events = [i for i in items if i.event_subtype == "SALE"]
        return_events = [i for i in items if i.event_subtype == "RETURN"]
        cancellation_events = [i for i in items if i.event_subtype == "CANCELLATION"]
        return_cancel_events = [i for i in items if i.event_subtype == "RETURN_CANCELLATION"]

        sale_order_item_ids = set(i.order_item_id for i in sale_events)
        return_order_item_ids = set(i.order_item_id for i in return_events)
        cancellation_item_ids = set(i.order_item_id for i in cancellation_events)
        sale_linked_return_item_ids = sale_order_item_ids.intersection(return_order_item_ids)

        sale_items_count = len(sale_order_item_ids)
        returned_items_count = len(return_order_item_ids)
        sale_linked_returns_count = len(sale_linked_return_item_ids)

        sale_linked_return_rate = round((sale_linked_returns_count / sale_items_count * 100.0), 2) if sale_items_count > 0 else 0.0

        returned_value = round(sum(i.invoice_amount or 0.0 for i in return_events), 2)
        sales_revenue = round(sum(i.invoice_amount or 0.0 for i in sale_events), 2)
        avg_return_value = round(returned_value / returned_items_count, 2) if returned_items_count > 0 else 0.0

        cancellation_events_count = len(cancellation_events)
        cancellation_rate = round((cancellation_events_count / sale_items_count * 100.0), 2) if sale_items_count > 0 else 0.0
        return_cancellation_events_count = len(return_cancel_events)

        if sale_items_count >= 50:
            data_confidence = "HIGH"
        elif sale_items_count >= 30:
            data_confidence = "GOOD"
        elif sale_items_count >= 10:
            data_confidence = "MODERATE"
        else:
            data_confidence = "INSUFFICIENT"

        item_label = "sale item" if sale_items_count == 1 else "sale items"
        if sale_items_count < 10:
            status = "Insufficient Data"
            reason = f"Only {sale_items_count} {item_label} observed."
        elif sale_linked_return_rate >= 25.0:
            status = "High Return"
            reason = f"{sale_linked_return_rate}% sale-linked return activity ({sale_linked_returns_count} returns)"
        elif sale_linked_return_rate >= 15.0:
            status = "Watch"
            reason = f"{sale_linked_return_rate}% sale-linked return activity ({sale_linked_returns_count} returns)"
        else:
            status = "Healthy"
            reason = "Healthy performance & return activity"

        has_cogs = bool(product and product.purchase_cost and product.purchase_cost > 0)
        has_settlements = db.query(Settlement).filter(
            Settlement.organization_id == organization_id,
            func.upper(Settlement.sku) == sku_upper
        ).count() > 0

        # Return Trend Data (Chronological Date vs Sale Items & Return Items)
        timeline_map: Dict[str, Dict[str, Any]] = {}
        for i in items:
            if not i.order_date:
                continue
            dt_str = i.order_date.strftime("%Y-%m-%d")
            if dt_str not in timeline_map:
                timeline_map[dt_str] = {"date": dt_str, "sale_order_items": set(), "return_order_items": set()}
            if i.event_subtype == "SALE":
                timeline_map[dt_str]["sale_order_items"].add(i.order_item_id)
            elif i.event_subtype == "RETURN":
                timeline_map[dt_str]["return_order_items"].add(i.order_item_id)

        trend_chart = []
        for dt_str, data in sorted(timeline_map.items()):
            trend_chart.append({
                "date": dt_str,
                "sale_items": len(data["sale_order_items"]),
                "return_items": len(data["return_order_items"])
            })

        # Order Type Analysis (Only display categories that actually exist for selected SKU)
        ot_sales: Dict[str, set] = {}
        ot_returns: Dict[str, set] = {}
        for i in sale_events:
            ot = i.order_type.strip() if i.order_type else "Unknown"
            if ot not in ot_sales:
                ot_sales[ot] = set()
            ot_sales[ot].add(i.order_item_id)
        for i in return_events:
            ot = i.order_type.strip() if i.order_type else "Unknown"
            if ot not in ot_returns:
                ot_returns[ot] = set()
            ot_returns[ot].add(i.order_item_id)

        all_order_types = sorted(set(list(ot_sales.keys()) + list(ot_returns.keys())))
        order_type_analysis = []
        for ot in all_order_types:
            s_cnt = len(ot_sales.get(ot, set()))
            r_cnt = len(ot_returns.get(ot, set()))
            rate = round((r_cnt / s_cnt * 100.0), 1) if s_cnt > 0 else 0.0
            order_type_analysis.append({
                "order_type": ot,
                "sale_items": s_cnt,
                "returned_items": r_cnt,
                "return_rate": rate
            })

        # Delivery State Analysis
        state_sales: Dict[str, set] = {}
        state_returns: Dict[str, set] = {}
        for i in sale_events:
            st = (i.customer_delivery_state or i.customer_billing_state or i.shipped_from_state or "").strip()
            if not st:
                st = "Unknown"
            if st not in state_sales:
                state_sales[st] = set()
            state_sales[st].add(i.order_item_id)
        for i in return_events:
            st = (i.customer_delivery_state or i.customer_billing_state or i.shipped_from_state or "").strip()
            if not st:
                st = "Unknown"
            if st not in state_returns:
                state_returns[st] = set()
            state_returns[st].add(i.order_item_id)

        all_states = set(list(state_sales.keys()) + list(state_returns.keys()))
        state_analysis = []
        for st in all_states:
            s_cnt = len(state_sales.get(st, set()))
            r_cnt = len(state_returns.get(st, set()))
            rate = round((r_cnt / s_cnt * 100.0), 1) if s_cnt > 0 else 0.0
            state_analysis.append({
                "state": st,
                "sale_items": s_cnt,
                "returned_items": r_cnt,
                "return_rate": rate
            })

        state_analysis.sort(key=lambda x: (x["returned_items"], x["return_rate"]), reverse=True)

        # Product Insight Panel
        if sale_items_count < 10:
            insight_headline = f"Only {sale_items_count} {item_label} were observed."
            insight_detail = "Return percentage may not be representative due to small sample size."
        else:
            insight_headline = f"{sale_linked_return_rate}% of sale order items for this product also have a return event in the reporting period."
            insight_detail = f"{returned_items_count} returned items were recorded across {sale_items_count} sale items."

        data_quality = {
            "sale_events_available": len(sale_events) > 0,
            "return_events_available": len(return_events) > 0,
            "order_type_available": len(ot_sales) > 0 or len(ot_returns) > 0,
            "delivery_state_available": len(state_sales) > 0 or len(state_returns) > 0,
            "cogs_available": has_cogs,
            "settlement_available": has_settlements,
            "rto_available": False
        }

        raw_p_name = product.product_name if product else (items[0].product_name if items and items[0].product_name else f"SKU {sku_canonical}")
        prod_name_clean = normalize_product_name(raw_p_name) or f"SKU {sku_canonical}"

        return {
            "sku": sku_canonical,
            "product_name": prod_name_clean,
            "marketplace": "Flipkart",
            "status": status,
            "reason": reason,
            "data_confidence": data_confidence,
            "purchase_cost": product.purchase_cost if product else 0.0,
            "top_summary": {
                "sale_items": sale_items_count,
                "returned_items": returned_items_count,
                "sale_linked_return_rate": sale_linked_return_rate,
                "return_events": len(return_events),
                "cancellation_events": cancellation_events_count,
                "return_cancellation_events": return_cancellation_events_count,
                "returned_value": returned_value,
                "sales_revenue": sales_revenue,
                "avg_return_value": avg_return_value,
                "actual_profit": None
            },
            "cancellations": {
                "cancellation_events": cancellation_events_count,
                "cancellation_rate": cancellation_rate,
                "return_cancellation_events": return_cancellation_events_count
            },
            "trend_chart": trend_chart,
            "order_type_analysis": order_type_analysis,
            "state_analysis": state_analysis,
            "insight": {
                "status": status,
                "headline": insight_headline,
                "detail": insight_detail
            },
            "data_quality": data_quality
        }

calculation_engine = CalculationEngine()
