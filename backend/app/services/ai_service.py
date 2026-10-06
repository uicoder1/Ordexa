import json
from typing import Dict, Any
from app.config import settings
from google import genai

class AIService:

    @staticmethod
    def generate_sku_explanation(metric_data: Dict[str, Any], return_reasons: list) -> Dict[str, Any]:
        """
        Generates structured plain English business explanations for a SKU using Gemini API,
        or deterministic fallback if key is not configured.
        """
        sku = metric_data.get("sku")
        product_name = metric_data.get("product_name", sku)
        revenue = metric_data.get("revenue", 0.0)
        profit = metric_data.get("actual_profit", 0.0)
        margin = metric_data.get("profit_margin", 0.0)
        return_rate = metric_data.get("return_rate", 0.0)
        rto_rate = metric_data.get("rto_rate", 0.0)
        return_cost = metric_data.get("return_cost", 0.0)
        risk = metric_data.get("risk_level", "HEALTHY")
        action = metric_data.get("recommended_action", "Healthy")

        # Fallback explanation generator
        fallback_explanation = AIService._generate_fallback(
            product_name=product_name,
            revenue=revenue,
            profit=profit,
            margin=margin,
            return_rate=return_rate,
            rto_rate=rto_rate,
            return_cost=return_cost,
            risk=risk,
            action=action,
            return_reasons=return_reasons
        )

        if not settings.GEMINI_API_KEY:
            return fallback_explanation

        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            prompt = f"""
You are ProfitPilot AI, a calm, straightforward e-commerce business advisor.
Analyze the following SKU metrics and produce a clear explanation for a small business owner.
DO NOT use complex jargon (e.g. avoid 'negative contribution economics', 'reverse logistics expenditure').
Use plain language like: 'This product is losing money because reverse shipping fees are eating your profit.'

DATA:
- Product: {product_name} (SKU: {sku})
- Revenue: ₹{revenue:,.2f}
- Actual Profit: ₹{profit:,.2f}
- Profit Margin: {margin:.1f}%
- Return Rate: {return_rate:.1f}%
- RTO Rate: {rto_rate:.1f}%
- Total Return Cost: ₹{return_cost:,.2f}
- Risk Level: {risk}
- Recommendation: {action}
- Top Return Reasons: {json.dumps(return_reasons)}

Return ONLY a raw valid JSON object with these exact keys:
{{
  "why_attention_needed": "2 sentences explaining the main issue",
  "what_is_happening": "Explanation of financial leakage",
  "possible_causes": ["Cause 1", "Cause 2", "Cause 3"],
  "suggested_actions": ["Action 1", "Action 2", "Action 3"]
}}
"""
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            
            parsed = json.loads(text)
            return parsed
        except Exception as e:
            # On any API or parsing exception, return structured fallback
            return fallback_explanation

    @staticmethod
    def _generate_fallback(
        product_name: str, revenue: float, profit: float, margin: float,
        return_rate: float, rto_rate: float, return_cost: float,
        risk: str, action: str, return_reasons: list
    ) -> Dict[str, Any]:
        top_reason = return_reasons[0]["reason"] if return_reasons else "Quality / Sizing"

        if profit < 0:
            why = f"{product_name} is currently losing ₹{abs(profit):,.2f} despite bringing in ₹{revenue:,.2f} in gross sales."
            happening = f"For every ₹100 of sales, you are spending more than ₹100 on product costs, shipping, and return charges."
            causes = [
                f"High return rate of {return_rate:.1f}% generating reverse shipping charges.",
                f"Primary return reason reported: '{top_reason}'.",
                "Product purchase cost is too close to the net settlement payout."
            ]
            actions = [
                f"Pause marketing or ad spend on SKU until packaging and description are improved.",
                f"Review supplier unit cost or negotiate a ₹{abs(profit)/max(1, revenue)*100:.0f} price increase.",
                "Inspect returned inventory to confirm if items are damaged or falsely returned."
            ]
        elif margin < 10.0:
            why = f"{product_name} has a razor-thin profit margin of only {margin:.1f}%."
            happening = f"Although the product generates ₹{profit:,.2f} profit, customer returns costing ₹{return_cost:,.2f} are eating up your margin."
            causes = [
                f"Return rate of {return_rate:.1f}% is above the healthy 10% threshold.",
                f"RTO rate of {rto_rate:.1f}% costs non-refundable courier fees."
            ]
            actions = [
                "Improve product size guide and photo accuracy on marketplace listings.",
                "Implement strict quality control before dispatch to reduce returns.",
                "Consider bundling to increase average order value and margin cushion."
            ]
        else:
            why = f"{product_name} is performing healthily with a {margin:.1f}% profit margin and ₹{profit:,.2f} net profit."
            happening = "Sales volume and product margins are well aligned with manageable return costs."
            causes = [
                f"Acceptable return rate of {return_rate:.1f}%.",
                "Healthy unit margin covering marketplace fees."
            ]
            actions = [
                "Maintain current pricing and inventory levels.",
                "Consider scaling ad budget for this high-performing SKU."
            ]

        return {
            "why_attention_needed": why,
            "what_is_happening": happening,
            "possible_causes": causes,
            "suggested_actions": actions
        }

ai_service = AIService()
