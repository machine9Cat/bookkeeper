#!/usr/bin/env python3
"""测试下拉数据和行内编辑"""
import requests
import json

BASE = "http://localhost:8000"

def api(method, path, token=None, json_data=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = getattr(requests, method)(f"{BASE}{path}", json=json_data, headers=headers)
    return r.status_code, r.json()

# 注册
r = requests.post(f"{BASE}/api/register", json={"username": "admin", "password": "123456"})
admin_token = r.json().get("token") or requests.post(f"{BASE}/api/login", json={"username": "admin", "password": "123456"}).json()["token"]

print("✅ 登录成功\n")

# 测试字典API返回格式
print("=== 付款方式 API ===")
status, data = api("get", "/api/payment-methods", admin_token)
print(f"状态: {status}, 数量: {len(data)}")
for item in data[:3]:
    print(f"  {json.dumps(item, ensure_ascii=False)}")

print("\n=== 经手人 API ===")
status, data = api("get", "/api/handlers", admin_token)
print(f"状态: {status}, 数量: {len(data)}")
for item in data[:3]:
    print(f"  {json.dumps(item, ensure_ascii=False)}")

print("\n=== 购买渠道 API ===")
status, data = api("get", "/api/channels", admin_token)
print(f"状态: {status}, 数量: {len(data)}")
for item in data[:3]:
    print(f"  {json.dumps(item, ensure_ascii=False)}")

print("\n=== 大类 API ===")
status, data = api("get", "/api/categories", admin_token)
print(f"状态: {status}, 数量: {len(data)}")
for item in data[:3]:
    print(f"  {json.dumps(item, ensure_ascii=False)}")

# 添加一条记录并测试行内保存
print("\n=== 测试行内保存 ===")
status, data = api("post", "/api/expenses", admin_token, {
    "category_id": 1, "item_name": "测试物品", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "张三", "payment_method": "现金", "purchase_channel": "淘宝", "accounting_date": "2026-06"
})
print(f"添加记录: {data}")

# 修改付款方式
status, data = api("put", "/api/expenses/1", admin_token, {
    "category_id": 1, "item_name": "测试物品", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "张三", "payment_method": "微信", "purchase_channel": "淘宝", "accounting_date": "2026-06"
})
print(f"修改付款方式: {data}")

# 验证修改
status, data = api("get", "/api/expenses?page_size=1", admin_token)
if data['items']:
    item = data['items'][0]
    print(f"验证: 付款方式={item['payment_method']}, 录入人={item.get('creator_name')}")

print("\n✅ 测试完成！")
