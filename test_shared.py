#!/usr/bin/env python3
"""测试共享账本功能"""
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

# 注册用户
print("=== 注册管理员 ===")
print(json.dumps(register("admin", "123456"), ensure_ascii=False, indent=2))

print("\n=== 注册 user1 ===")
print(json.dumps(register("user1", "123456"), ensure_ascii=False, indent=2))

# 登录
admin = login("admin", "123456")
admin_token = admin["token"]
print(f"\n管理员登录成功: {admin['username']} ({admin['role']})")

# 管理员审核 user1
print("\n=== 审核 user1 ===")
print(json.dumps(api("post", "/api/users/2/approve", admin_token)[1], ensure_ascii=False))

user1 = login("user1", "123456")
user1_token = user1["token"]
print(f"\nuser1 登录成功: {user1['username']} ({user1['role']})")

# 管理员添加支出
print("\n=== 管理员添加支出记录 ===")
status, data = api("post", "/api/expenses", admin_token, {
    "category_id": 1,
    "item_name": "管理员的物品",
    "quantity": 5,
    "unit": "个",
    "unit_price": 20,
    "handler": "张三",
    "payment_method": "现金",
    "purchase_channel": "淘宝",
    "accounting_date": "2026-06"
})
print(f"状态: {status}, 结果: {json.dumps(data, ensure_ascii=False)}")

# user1 添加支出
print("\n=== user1 添加支出记录 ===")
status, data = api("post", "/api/expenses", user1_token, {
    "category_id": 2,
    "item_name": "user1的物品",
    "quantity": 3,
    "unit": "个",
    "unit_price": 15,
    "handler": "李四",
    "payment_method": "微信",
    "purchase_channel": "京东",
    "accounting_date": "2026-06"
})
print(f"状态: {status}, 结果: {json.dumps(data, ensure_ascii=False)}")

# 管理员查看全部记录
print("\n=== 管理员查看全部记录 ===")
status, data = api("get", "/api/expenses?page_size=10", admin_token)
print(f"总数: {data['total']}")
for item in data['items']:
    print(f"  ID={item['id']} | {item['item_name']} | 录入人: {item.get('creator_name', '?')} | user_id={item.get('user_id', '?')}")

# user1 查看全部记录（应该和管理员看到的一样）
print("\n=== user1 查看全部记录 ===")
status, data = api("get", "/api/expenses?page_size=10", user1_token)
print(f"总数: {data['total']}")
for item in data['items']:
    print(f"  ID={item['id']} | {item['item_name']} | 录入人: {item.get('creator_name', '?')} | user_id={item.get('user_id', '?')}")

# user1 尝试编辑管理员的记录（应被拒绝）
print("\n=== user1 尝试编辑管理员记录 (ID=1) ===")
status, data = api("put", "/api/expenses/1", user1_token, {
    "category_id": 1, "item_name": "修改测试", "quantity": 1, "unit": "个", "unit_price": 10,
    "handler": "张三", "payment_method": "现金", "purchase_channel": "淘宝"
})
print(f"状态: {status}, 结果: {json.dumps(data, ensure_ascii=False)}")

# user1 编辑自己的记录（应成功）
print("\n=== user1 编辑自己的记录 (ID=2) ===")
status, data = api("put", "/api/expenses/2", user1_token, {
    "category_id": 2, "item_name": "user1的物品（已修改）", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "李四", "payment_method": "微信", "purchase_channel": "京东"
})
print(f"状态: {status}, 结果: {json.dumps(data, ensure_ascii=False)}")

# 管理员审核记录
print("\n=== 管理员审核 ID=2 ===")
status, data = api("post", "/api/expenses/2/review", admin_token)
print(f"状态: {status}, 结果: {json.dumps(data, ensure_ascii=False)}")

# user1 尝试编辑已审核记录（应被拒绝）
print("\n=== user1 尝试编辑已审核记录 (ID=2) ===")
status, data = api("put", "/api/expenses/2", user1_token, {
    "category_id": 2, "item_name": "再次修改", "quantity": 1, "unit": "个", "unit_price": 10,
    "handler": "李四", "payment_method": "微信", "purchase_channel": "京东"
})
print(f"状态: {status}, 结果: {json.dumps(data, ensure_ascii=False)}")

# 管理员编辑已审核记录（应成功）
print("\n=== 管理员编辑已审核记录 (ID=2) ===")
status, data = api("put", "/api/expenses/2", admin_token, {
    "category_id": 2, "item_name": "管理员修改", "quantity": 10, "unit": "个", "unit_price": 30,
    "handler": "李四", "payment_method": "微信", "purchase_channel": "京东"
})
print(f"状态: {status}, 结果: {json.dumps(data, ensure_ascii=False)}")

# 统计测试
print("\n=== 统计（全账本）===")
status, data = api("get", "/api/stats/summary?month=2026-06", admin_token)
print(f"月度总支出: ¥{data['total_expense']}")
print(f"按大类: {json.dumps(data['by_category'], ensure_ascii=False)}")

print("\n✅ 所有测试完成！")
