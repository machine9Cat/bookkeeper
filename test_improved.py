#!/usr/bin/env python3
"""测试改进功能"""
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

# 注册
print("=== 注册用户 ===")
register("admin", "123456")
register("user1", "123456")
register("user2", "123456")

# 登录
admin = login("admin", "123456")
admin_token = admin["token"]

# 审核 user1 和 user2
api("post", "/api/users/2/approve", admin_token)
api("post", "/api/users/3/approve", admin_token)

user1 = login("user1", "123456")
user1_token = user1["token"]

user2 = login("user2", "123456")
user2_token = user2["token"]

print("✅ 所有用户注册并审核完成\n")

# === 测试1：待审核记录任何用户都可编辑/删除 ===
print("=== 测试1：待审核记录权限 ===")

# user1 添加记录
api("post", "/api/expenses", user1_token, {
    "category_id": 1, "item_name": "user1的物品", "quantity": 1, "unit": "个", "unit_price": 100,
    "handler": "张三", "payment_method": "现金", "purchase_channel": "淘宝", "accounting_date": "2026-06"
})

# user2 编辑 user1 的未审核记录（应成功）
print("user2 编辑 user1 的未审核记录:")
status, data = api("put", "/api/expenses/1", user2_token, {
    "category_id": 1, "item_name": "user1的物品（user2修改）", "quantity": 2, "unit": "个", "unit_price": 50,
    "handler": "张三", "payment_method": "现金", "purchase_channel": "淘宝"
})
print(f"  状态: {status}, 结果: {data['message'] if status == 200 else data['detail']}")

# 管理员审核该记录
api("post", "/api/expenses/1/review", admin_token)

# user2 尝试编辑已审核记录（应失败）
print("user2 尝试编辑已审核记录:")
status, data = api("put", "/api/expenses/1", user2_token, {
    "category_id": 1, "item_name": "再次修改", "quantity": 1, "unit": "个", "unit_price": 10,
    "handler": "张三", "payment_method": "现金", "purchase_channel": "淘宝"
})
print(f"  状态: {status}, 结果: {data['detail']}")

# 管理员编辑已审核记录（应成功）
print("管理员编辑已审核记录:")
status, data = api("put", "/api/expenses/1", admin_token, {
    "category_id": 1, "item_name": "管理员修改", "quantity": 5, "unit": "个", "unit_price": 20,
    "handler": "张三", "payment_method": "现金", "purchase_channel": "淘宝"
})
print(f"  状态: {status}, 结果: {data['message']}")

# === 测试2：删除用户时检查记录 ===
print("\n=== 测试2：删除用户时检查记录 ===")

# 尝试删除 user1（有记录，应失败）
print("尝试删除 user1（有记录）:")
status, data = api("delete", "/api/users/2", admin_token)
print(f"  状态: {status}, 结果: {data['detail']}")

# user2 没有记录，可以删除
print("尝试删除 user2（无记录）:")
status, data = api("delete", "/api/users/3", admin_token)
print(f"  状态: {status}, 结果: {data['message']}")

# 确认 user2 已删除
print("确认用户列表:")
status, data = api("get", "/api/users", admin_token)
for u in data:
    print(f"  {u['username']} ({u['role']}) - {u['status']}")

print("\n✅ 所有测试完成！")
