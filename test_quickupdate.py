#!/usr/bin/env python3
"""测试快速修改功能"""
import requests
import json

BASE = "http://localhost:8000"

def login(username, password):
    r = requests.post(f"{BASE}/api/login", json={"username": username, "password": password})
    return r.json()

def register(username, password):
    r = requests.post(f"{BASE}/api/register", json={"username": username, "password": password})
    return r.json()

def api(method, path, token=None, json_data=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = getattr(requests, method)(f"{BASE}{path}", json=json_data, headers=headers)
    return r.status_code, r.json()

# 注册并登录
register("admin", "123456")
register("user1", "123456")
admin = login("admin", "123456")
admin_token = admin["token"]
api("post", "/api/users/2/approve", admin_token)
user1 = login("user1", "123456")
user1_token = user1["token"]

print("✅ 用户准备完成\n")

# 添加记录
api("post", "/api/expenses", user1_token, {
    "category_id": 1, "item_name": "测试物品", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "张三", "payment_method": "现金", "purchase_channel": "淘宝", "accounting_date": "2026-06"
})

# 查看记录
print("=== 初始记录 ===")
status, data = api("get", "/api/expenses?page_size=10", admin_token)
for item in data['items']:
    print(f"ID: {item['id']}, 大类: {item.get('category_name')}, 经手人: {item['handler']}, 付款: {item['payment_method']}, 渠道: {item['purchase_channel']}")

# 测试快速修改 - user1 修改经手人
print("\n=== user1 快速修改经手人 ===")
status, data = api("put", "/api/expenses/1", user1_token, {
    "category_id": 1, "item_name": "测试物品", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "李四", "payment_method": "现金", "purchase_channel": "淘宝", "accounting_date": "2026-06"
})
print(f"状态: {status}, 结果: {data.get('message') or data.get('detail')}")

# 测试快速修改 - user1 修改付款方式
print("\n=== user1 快速修改付款方式 ===")
status, data = api("put", "/api/expenses/1", user1_token, {
    "category_id": 1, "item_name": "测试物品", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "李四", "payment_method": "微信", "purchase_channel": "淘宝", "accounting_date": "2026-06"
})
print(f"状态: {status}, 结果: {data.get('message') or data.get('detail')}")

# 测试快速修改 - user1 修改购买渠道
print("\n=== user1 快速修改购买渠道 ===")
status, data = api("put", "/api/expenses/1", user1_token, {
    "category_id": 1, "item_name": "测试物品", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "李四", "payment_method": "微信", "purchase_channel": "京东", "accounting_date": "2026-06"
})
print(f"状态: {status}, 结果: {data.get('message') or data.get('detail')}")

# 测试快速修改 - user1 修改大类
print("\n=== user1 快速修改大类 ===")
status, data = api("put", "/api/expenses/1", user1_token, {
    "category_id": 2, "item_name": "测试物品", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "李四", "payment_method": "微信", "purchase_channel": "京东", "accounting_date": "2026-06"
})
print(f"状态: {status}, 结果: {data.get('message') or data.get('detail')}")

# 审核后测试
api("post", "/api/expenses/1/review", admin_token)

print("\n=== 审核后 user1 尝试修改 ===")
status, data = api("put", "/api/expenses/1", user1_token, {
    "category_id": 1, "item_name": "测试物品", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "张三", "payment_method": "现金", "purchase_channel": "淘宝", "accounting_date": "2026-06"
})
print(f"状态: {status}, 结果: {data.get('detail')}")

print("\n=== 审核后管理员修改 ===")
status, data = api("put", "/api/expenses/1", admin_token, {
    "category_id": 3, "item_name": "测试物品", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "王五", "payment_method": "支付宝", "purchase_channel": "拼多多", "accounting_date": "2026-06"
})
print(f"状态: {status}, 结果: {data.get('message')}")

# 确认最终结果
print("\n=== 最终记录状态 ===")
status, data = api("get", "/api/expenses?page_size=10", admin_token)
for item in data['items']:
    print(f"ID: {item['id']}, 大类: {item.get('category_name')}, 经手人: {item['handler']}, 付款: {item['payment_method']}, 渠道: {item['purchase_channel']}, 审核: {item['reviewed']}")

print("\n✅ 快速修改测试完成！")
