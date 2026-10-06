import httpx

client = httpx.Client(base_url='http://127.0.0.1:8000/api/v1')

signup_res = client.post('/auth/signup', json={
    'email': 'seller_audit_100@profitpilot.com',
    'password': 'Password123!',
    'name': 'Reconciliation Audit Store'
})

print("SIGNUP STATUS:", signup_res.status_code)
if signup_res.status_code != 200:
    print("SIGNUP ERROR:", signup_res.text)
    exit(1)

data = signup_res.json()
token = data['access_token']
org_id = data['active_organization_id']
headers = {'Authorization': f'Bearer {token}', 'X-Organization-ID': org_id}

summary = client.get('/dashboard/summary', headers=headers).json()
print("DASHBOARD SUMMARY:", summary)

skus = client.get('/dashboard/skus', headers=headers).json()
print("TOTAL SKUs:", len(skus))

for item in skus[:3]:
    print(f"SKU: {item['sku']} | Orders: {item['total_orders']} | Units: {item['units_sold']} | Revenue: ₹{item['revenue']} | ReturnRate: {item['return_rate']}% | RTORate: {item['rto_rate']}% | Profit: ₹{item['actual_profit']} | Margin: {item['profit_margin']}% | Risk: {item['risk_level']}")

reconciliation = client.get('/skus/AP-TSHIRT-BLK-M/reconciliation', headers=headers).json()
print("RECONCILIATION FOR AP-TSHIRT-BLK-M:")
print(reconciliation)
