#!/usr/bin/env python3
"""测试所有改进"""
import requests
import json

BASE = "http://localhost:8000"

def api(method, path, token=None, json_data=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = getattr(requests, method)(f"{BASE}{path}", json=json_data, headers=headers)
    return r.status_code, r.json()

# 注册并登录
r = requests.post(f"{BASE}/api/register", json={"username": "admin", "password": "123456"})
admin_token = r.json()["token"]

r = requests.post(f"{BASE}/api/register", json={"username": "user1", "password": "123456"})
api("post", "/api/users/2/approve", admin_token)
user1_token = requests.post(f"{BASE}/api/login", json={"username": "user1", "password": "123456"}).json()["token"]

print("✅ 用户准备完成")

# 添加测试数据
for i in range(5):
    api("post", "/api/expenses", user1_token, {
        "category_id": (i % 3) + 1,
        "item_name": f"物品{i+1}",
        "quantity": (i + 1) * 2,
        "unit": "个",
        "unit_price": (i + 1) * 10,
        "handler": ["张三", "李四", "王五"][i % 3],
        "payment_method": ["现金", "微信", "支付宝"][i % 3],
        "purchase_channel": ["淘宝", "京东", "拼多多"][i % 3],
        "accounting_date": "2026-06"
    })
print(f"✅ 添加了 5 条测试数据")

# 测试1：管理员刷新后role保持
print("\n=== 测试1：验证 /api/me 返回 role ===")
status, data = api("get", "/api/me", admin_token)
print(f"状态: {status}, role: {data.get('role')}")

status, data = api("get", "/api/me", user1_token)
print(f"user1 role: {data.get('role')}")

# 测试2：只有未审核可修改（包括管理员）
print("\n=== 测试2：权限测试 ===")
# 审核 ID=1
api("post", "/api/expenses/1/review", admin_token)

# 管理员尝试修改已审核记录
status, data = api("put", "/api/expenses/1", admin_token, {
    "category_id": 1, "item_name": "修改测试", "quantity": 1, "unit": "个", "unit_price": 10,
    "handler": "张三", "payment_method": "现金", "purchase_channel": "淘宝"
})
print(f"管理员修改已审核记录: 状态={status}, 结果={data.get('detail')}")

# 管理员修改未审核记录
status, data = api("put", "/api/expenses/2", admin_token, {
    "category_id": 2, "item_name": "管理员修改", "quantity": 10, "unit": "个", "unit_price": 50,
    "handler": "李四", "payment_method": "微信", "purchase_channel": "京东"
})
print(f"管理员修改未审核记录: 状态={status}, 结果={data.get('message')}")

# 测试3：录入人自动更新
print("\n=== 测试3：录入人更新 ===")
status, data = api("get", "/api/expenses?page_size=10", admin_token)
for item in data['items']:
    if item['id'] == 2:
        print(f"ID=2 录入人: {item['creator_name']} (应为admin)")

# 测试4：排序功能
print("\n=== 测试4：排序功能 ===")
# 按总价降序
status, data = api("get", "/api/expenses?sort_field=total_price&sort_dir=desc&page_size=5", admin_token)
print("按总价降序:")
for item in data['items']:
    print(f"  ID={item['id']}: ¥{item['total_price']}")

# 按总价升序
status, data = api("get", "/api/expenses?sort_field=total_price&sort_dir=asc&page_size=5", admin_token)
print("按总价升序:")
for item in data['items']:
    print(f"  ID={item['id']}: ¥{item['total_price']}")

# 按经手人排序
status, data = api("get", "/api/expenses?sort_field=handler&sort_dir=asc&page_size=5", admin_token)
print("按经手人升序:")
for item in data['items']:
    print(f"  ID={item['id']}: {item['handler']}")

print("\n✅ 所有测试完成！")
