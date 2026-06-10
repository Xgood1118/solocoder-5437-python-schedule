import urllib.request
import urllib.parse
import json
import sys

def api_post(url, data=None):
    if data is not None:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
    else:
        req = urllib.request.Request(url, method='POST')
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode('utf-8')

def api_get(url):
    try:
        resp = urllib.request.urlopen(url)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode('utf-8')

base = 'http://localhost:9090'

print('=== Test 1: Root / Health ===')
r, err = api_get(f'{base}/')
print(f"  Name: {r['name']}, Port: {r['port']}")
r, err = api_get(f'{base}/health')
print(f"  Health: {r['status']}")

print()
print('=== Test 2: Check existing data ===')
orders, err = api_get(f'{base}/orders')
print(f"  Orders: {len(orders)}")
lines, err = api_get(f'{base}/lines')
print(f"  Lines: {len(lines)}")

if len(orders) < 2 or len(lines) < 2:
    print('  Creating test data...')
    api_post(f'{base}/orders', {
        'order_no': 'T001', 'product_code': 'P001', 'quantity': 100,
        'due_date': '2026-07-15', 'priority': 'P0',
        'customer_importance': 'VIP', 'customer_name': 'VIP客户A'
    })
    api_post(f'{base}/orders', {
        'order_no': 'T002', 'product_code': 'P002', 'quantity': 200,
        'due_date': '2026-07-20', 'priority': 'P1',
        'customer_importance': '大客户', 'customer_name': '大客户B'
    })
    api_post(f'{base}/orders', {
        'order_no': 'T003', 'product_code': 'P001', 'quantity': 150,
        'due_date': '2026-07-18', 'priority': 'P2',
        'customer_importance': '普通客户', 'customer_name': '普通客户C'
    })
    api_post(f'{base}/lines', {
        'line_id': 'T001', 'line_name': '测试产线1',
        'supported_products': ['P001', 'P002'],
        'daily_capacity': 50, 'mold_status': '已装好',
        'current_mold': 'M001', 'worker_shift': '白班'
    })
    api_post(f'{base}/lines', {
        'line_id': 'T002', 'line_name': '测试产线2',
        'supported_products': ['P001', 'P003'],
        'daily_capacity': 80, 'mold_status': '待切换',
        'worker_shift': '白班'
    })
    print('  Test data created.')

print()
print('=== Test 3: Run Schedule (CP-SAT) ===')
obj = '最大化按时交付订单数'
result, err = api_post(f'{base}/schedule/run?objective={urllib.parse.quote(obj)}&use_cp_sat=true')
if err:
    print(f"  Error: {err}")
else:
    print(f"  Solver: {result['solver_used']}")
    print(f"  Solve time: {result['solve_time_seconds']}s")
    print(f"  Work orders: {len(result['work_orders'])}")
    for wo in result['work_orders']:
        print(f"    {wo['order_no']} -> {wo['line_id']}: {wo['start_time'][:16]} ~ {wo['end_time'][:16]}")
    print(f"  Bottlenecks: {len(result['bottleneck_analysis'])}")
    print(f"  Has conflicts: {result['has_conflicts']}")

print()
print('=== Test 4: Get Current Schedule ===')
sched, err = api_get(f'{base}/schedule')
print(f"  Work orders: {len(sched['work_orders'])}")

print()
print('=== Test 5: Gantt Charts ===')
g, err = api_get(f'{base}/gantt/by-line')
print(f"  By line: {len(g['rows'])} rows")
for row in g['rows']:
    print(f"    {row['row_name']}: {len(row['bars'])} bars")

g2, err = api_get(f'{base}/gantt/by-order')
print(f"  By order: {len(g2['rows'])} rows")

g3, err = api_get(f'{base}/gantt/by-customer')
print(f"  By customer: {len(g3['rows'])} rows")

print()
print('=== Test 6: Manual Adjustment ===')
orders_list, _ = api_get(f'{base}/orders')
if orders_list:
    first = orders_list[0]['order_no']
    adj, err = api_post(f'{base}/replan/manual', {
        'order_no': first,
        'new_start_time': '2026-07-01T08:00:00'
    })
    if err:
        print(f"  Error: {err}")
    else:
        print(f"  Success: {adj['success']}")
        print(f"  Message: {adj['message']}")

print()
print('=== Test 7: Freeze / Unfreeze ===')
if orders_list:
    first = orders_list[0]['order_no']
    fr, err = api_post(f'{base}/replan/freeze/{first}')
    print(f"  Freeze: {fr['message']}")
    uf, err = api_post(f'{base}/replan/unfreeze/{first}')
    print(f"  Unfreeze: {uf['message']}")

print()
print('=== Test 8: Auto Optimize ===')
obj2 = '最小化总延期天数'
opt, err = api_post(f'{base}/replan/auto-optimize?objective={urllib.parse.quote(obj2)}')
if err:
    print(f"  Error: {err}")
else:
    print(f"  Solver: {opt['solver_used']}")
    print(f"  Diffs: {len(opt['diffs'])}")
    for d in opt['diffs']:
        print(f"    {d['order_no']}: {d['change_type']}")

print()
print('=== Test 9: Stats ===')
stats, err = api_get(f'{base}/stats/achievement')
print(f"  Overall rate: {stats['overall_rate']}")
print(f"  By line: {len(stats['by_line'])} items")
print(f"  By product: {len(stats['by_product'])} items")

print()
print('=== Test 10: Holidays & Molds ===')
h, err = api_get(f'{base}/lines/holidays/all')
print(f"  Holidays: {len(h['holidays'])} days")
m, err = api_get(f'{base}/lines/molds/all')
print(f"  Molds: {len(m)} items")

print()
print('ALL TESTS COMPLETED!')
